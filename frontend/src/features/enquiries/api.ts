import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { statusKeys } from '@/features/statuses/api';
import { api } from '@/lib/api/client';
import type { Paginated } from '@/types/api';
import type {
  ActivityEvent,
  Attachment,
  CallLog,
  CallOutcome,
  CustomValue,
  Enquiry,
  EnquiryDetail,
  FilterGroup,
  FollowUp,
  FormResponse,
  Note,
  Source,
  Status,
} from '@/types/crm';

import { countRules } from './filters';

export interface EnquiryListParams {
  page: number;
  page_size: number;
  view: string;
  saved_view?: number | null;
  q?: string;
  sort?: string;
  status?: number[];
  owner?: string[]; // user ids or "me"
  source?: Source[];
  created_from?: string;
  created_to?: string;
  filter?: FilterGroup | null;
}

/** Query string the API understands (arrays as comma lists, the filter tree as JSON). */
export function toQueryParams(params: EnquiryListParams): Record<string, string | number> {
  const out: Record<string, string | number> = {
    page: params.page,
    page_size: params.page_size,
    view: params.view,
  };
  if (params.saved_view) out.saved_view = params.saved_view;
  if (params.q?.trim()) out.q = params.q.trim();
  if (params.sort) out.sort = params.sort;
  if (params.status?.length) out.status = params.status.join(',');
  if (params.owner?.length) out.owner = params.owner.join(',');
  if (params.source?.length) out.source = params.source.join(',');
  if (params.created_from) out.created_from = params.created_from;
  if (params.created_to) out.created_to = params.created_to;
  if (params.filter && countRules(params.filter) > 0) out.filter = JSON.stringify(params.filter);
  return out;
}

export const enquiryKeys = {
  all: ['enquiries'] as const,
  lists: ['enquiries', 'list'] as const,
  list: (params: EnquiryListParams) => ['enquiries', 'list', params] as const,
  detail: (id: number) => ['enquiries', 'detail', id] as const,
  child: (id: number, kind: string) => ['enquiries', 'detail', id, kind] as const,
};

export interface EnquiryCreateInput {
  name: string;
  phone?: string;
  email?: string;
  status_id?: number | null;
  primary_owner_id?: number | null;
  secondary_owner_ids?: number[];
  campaign_name?: string;
  custom_fields?: Record<string, CustomValue>;
  note?: string;
}

export type EnquiryUpdateInput = Partial<{
  name: string;
  email: string;
  status_id: number;
  primary_owner_id: number | null;
  secondary_owner_ids: number[];
  campaign_name: string;
  adset_name: string;
  ad_name: string;
  custom_fields: Record<string, CustomValue>;
}>;

// --- list and detail ----------------------------------------------------------------
export function useEnquiries(params: EnquiryListParams) {
  return useQuery({
    queryKey: enquiryKeys.list(params),
    queryFn: () =>
      api
        .get<Paginated<Enquiry>>('/enquiries', { params: toQueryParams(params) })
        .then((r) => r.data),
    placeholderData: keepPreviousData,
  });
}

export function useEnquiry(id: number) {
  return useQuery({
    queryKey: enquiryKeys.detail(id),
    queryFn: () => api.get<EnquiryDetail>(`/enquiries/${id}`).then((r) => r.data),
  });
}

function useInvalidateEnquiries() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: enquiryKeys.lists });
    void queryClient.invalidateQueries({ queryKey: ['views', 'counts'] });
    void queryClient.invalidateQueries({ queryKey: ['contacts'] });
  };
}

export function useCreateEnquiry() {
  const invalidate = useInvalidateEnquiries();
  return useMutation({
    mutationFn: (values: EnquiryCreateInput) =>
      api.post<EnquiryDetail>('/enquiries', values).then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useUpdateEnquiry(id: number) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateEnquiries();
  return useMutation({
    mutationFn: (values: EnquiryUpdateInput) =>
      api.patch<EnquiryDetail>(`/enquiries/${id}`, values).then((r) => r.data),
    // Optimistic status change: the badge updates at once and rolls back on error.
    onMutate: async (values) => {
      if (values.status_id === undefined) return {};
      await queryClient.cancelQueries({ queryKey: enquiryKeys.detail(id) });
      const previous = queryClient.getQueryData<EnquiryDetail>(enquiryKeys.detail(id));
      const status = queryClient
        .getQueryData<Status[]>(statusKeys.all)
        ?.find((s) => s.id === values.status_id);
      if (previous && status) {
        queryClient.setQueryData(enquiryKeys.detail(id), { ...previous, status });
      }
      return { previous };
    },
    onError: (_error, _values, context) => {
      if (context?.previous) queryClient.setQueryData(enquiryKeys.detail(id), context.previous);
    },
    onSuccess: (data) => {
      queryClient.setQueryData(enquiryKeys.detail(id), data);
      void queryClient.invalidateQueries({ queryKey: enquiryKeys.child(id, 'timeline') });
      invalidate();
    },
  });
}

export function useDeleteEnquiry() {
  const invalidate = useInvalidateEnquiries();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/enquiries/${id}`),
    onSuccess: invalidate,
  });
}

export type BulkAction = 'set_status' | 'assign' | 'add_secondary_owner' | 'delete';

export function useBulkAction() {
  const invalidate = useInvalidateEnquiries();
  return useMutation({
    mutationFn: (body: { ids: number[]; action: BulkAction; value?: number | null }) =>
      api.post<{ updated: number; skipped: number }>('/enquiries/bulk', body).then((r) => r.data),
    onSuccess: invalidate,
  });
}

// --- timeline and original form response ------------------------------------------------
export function useTimeline(id: number, pageSize: number) {
  return useQuery({
    queryKey: [...enquiryKeys.child(id, 'timeline'), pageSize],
    queryFn: () =>
      api
        .get<Paginated<ActivityEvent>>(`/enquiries/${id}/timeline`, {
          params: { page_size: pageSize },
        })
        .then((r) => r.data),
    placeholderData: keepPreviousData,
  });
}

export function useFormResponse(id: number) {
  return useQuery({
    queryKey: enquiryKeys.child(id, 'form-response'),
    queryFn: () =>
      api
        .get<FormResponse>(`/enquiries/${id}/form-response`)
        .then((r) => r.data)
        .catch((error) => {
          if (error?.response?.status === 404) return null; // manual enquiries have none
          throw error;
        }),
    staleTime: Infinity,
  });
}

// --- work items ------------------------------------------------------------------------
function useChildList<T>(id: number, kind: string) {
  return useQuery({
    queryKey: enquiryKeys.child(id, kind),
    queryFn: () =>
      api
        .get<Paginated<T>>(`/enquiries/${id}/${kind}`, { params: { page_size: 200 } })
        .then((r) => r.data.results),
  });
}

function useChildMutation<TBody, TResult>(
  id: number,
  kind: string,
  request: (body: TBody) => Promise<TResult>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: enquiryKeys.child(id, kind) });
      void queryClient.invalidateQueries({ queryKey: enquiryKeys.child(id, 'timeline') });
      void queryClient.invalidateQueries({ queryKey: enquiryKeys.lists });
    },
  });
}

export const useNotes = (id: number) => useChildList<Note>(id, 'notes');
export interface NoteInput {
  body: string;
  /** Voice note recorded in the browser. */
  audio?: Blob | null;
  audioDurationSeconds?: number;
}

export const useAddNote = (id: number) =>
  useChildMutation(id, 'notes', ({ body, audio, audioDurationSeconds }: NoteInput) => {
    const form = new FormData();
    form.append('body', body);
    if (audio) {
      const ext = audio.type.includes('mp4') ? 'm4a' : audio.type.includes('ogg') ? 'ogg' : 'webm';
      form.append('audio', audio, `voice-note.${ext}`);
      form.append('audio_duration_seconds', String(Math.round(audioDurationSeconds ?? 0)));
    }
    return api
      .post<Note>(`/enquiries/${id}/notes`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  });

/** Voice notes are private: fetched with the auth header, played from a blob URL. */
export async function fetchNoteAudio(enquiryId: number, noteId: number): Promise<string> {
  const response = await api.get<Blob>(`/enquiries/${enquiryId}/notes/${noteId}/audio`, {
    responseType: 'blob',
  });
  return URL.createObjectURL(response.data);
}

export const useCalls = (id: number) => useChildList<CallLog>(id, 'calls');
export const useLogCall = (id: number) =>
  useChildMutation(
    id,
    'calls',
    (body: { outcome: CallOutcome; duration_seconds: number; notes: string }) =>
      api.post<CallLog>(`/enquiries/${id}/calls`, body).then((r) => r.data),
  );

export const useFollowUps = (id: number) => useChildList<FollowUp>(id, 'followups');
export const useAddFollowUp = (id: number) =>
  useChildMutation(
    id,
    'followups',
    (body: { title: string; due_at: string; assignee_id?: number | null; auto_call?: boolean }) =>
      api.post<FollowUp>(`/enquiries/${id}/followups`, body).then((r) => r.data),
  );
export const useToggleFollowUp = (id: number) =>
  useChildMutation(id, 'followups', ({ followupId, done }: { followupId: number; done: boolean }) =>
    api.patch<FollowUp>(`/enquiries/${id}/followups/${followupId}`, { done }).then((r) => r.data),
  );

/** Turn the Exotel auto-call of one scheduled call on or off (this enquiry only). */
export const useFollowUpAutoCall = (id: number) =>
  useChildMutation(
    id,
    'followups',
    ({ followupId, autoCall }: { followupId: number; autoCall: boolean }) =>
      api
        .patch<FollowUp>(`/enquiries/${id}/followups/${followupId}`, { auto_call: autoCall })
        .then((r) => r.data),
  );

/** New time for a scheduled call; it is auto-called again then. */
export const useRescheduleFollowUp = (id: number) =>
  useChildMutation(
    id,
    'followups',
    ({ followupId, dueAt }: { followupId: number; dueAt: string }) =>
      api
        .patch<FollowUp>(`/enquiries/${id}/followups/${followupId}`, { due_at: dueAt })
        .then((r) => r.data),
  );

export interface CallWindow {
  enabled: boolean;
  /** 0 = Monday. */
  days: number[];
  start: string;
  end: string;
}

/** Is Exotel auto-calling of scheduled calls on for this workspace? */
export function useCalling() {
  return useQuery({
    queryKey: ['integrations', 'calling'],
    queryFn: () =>
      api
        .get<{
          exotel_connected: boolean;
          auto_call_followups: boolean;
          call_window: CallWindow;
        }>('/integrations/calling')
        .then((r) => r.data),
    staleTime: 60_000,
  });
}

export const useAttachments = (id: number) => useChildList<Attachment>(id, 'attachments');
export const useUploadAttachment = (id: number) =>
  useChildMutation(id, 'attachments', (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api
      .post<Attachment>(`/enquiries/${id}/attachments`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  });

/** Files are private: fetch with the auth header, then hand the blob to the browser. */
export async function downloadAttachment(enquiryId: number, attachment: Attachment) {
  const response = await api.get<Blob>(
    `/enquiries/${enquiryId}/attachments/${attachment.id}/download`,
    { responseType: 'blob' },
  );
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = attachment.file_name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
