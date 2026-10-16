import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';

import { useAuth } from '@/features/auth/useAuth';
import { api } from '@/lib/api/client';
import { UserFacingError } from '@/lib/api/errors';
import type { PageParams, Paginated } from '@/types/api';

export type TokenState = 'ok' | 'expiring' | 'expired' | 'none';

export interface MetaStatus {
  status: 'not_connected' | 'pending_page' | 'connected' | 'disconnected';
  page_id?: string | null;
  page_name?: string;
  token_state: TokenState;
  token_expires_at?: string | null;
  leads_access_ok?: boolean;
  leads_access_error?: string;
  leads_access_checked_at?: string | null;
  detect_ad_details?: boolean;
  connected_at?: string | null;
  auto_connect_forms?: boolean;
  last_backfill_at?: string | null;
  app_configured?: boolean;
  webhook_url?: string;
  redirect_uri?: string;
}

export interface MetaPage {
  id: string;
  name: string;
  available: boolean;
}

export interface MetaForm {
  id: number;
  form_id: string;
  name: string;
  status_on_meta: string;
  created_time: string | null;
  is_connected: boolean;
  connected_at: string | null;
  leads_received: number;
  last_lead_at: string | null;
  question_count: number;
}

export type TargetType = 'name' | 'phone' | 'email' | 'custom' | 'ignore' | '';

export interface MappingQuestion {
  question: string;
  label: string;
  samples: string[];
  target_type: TargetType;
  custom_field: string | null;
  is_mapped: boolean;
}

export interface FormMapping {
  form_id: string;
  name: string;
  questions: MappingQuestion[];
}

export interface SyncLog {
  id: number;
  leadgen_id: string;
  form_id: string;
  status:
    'synced' | 'duplicate' | 'restored' | 'form_not_connected' | 'campaign_not_selected' | 'failed';
  source: 'webhook' | 'backfill' | 'retry' | 'test' | 'manual';
  enquiry_id: number | null;
  message: string;
  created_at: string;
}

export interface FailedSync {
  id: number;
  leadgen_id: string;
  form_id: string;
  error: string;
  attempts: number;
  resolved_at: string | null;
  last_attempt_at: string;
  created_at: string;
}

const keys = {
  all: ['meta'] as const,
  status: ['meta', 'status'] as const,
  pages: ['meta', 'pages'] as const,
  forms: (p: FormListParams) => ['meta', 'forms', p] as const,
  mapping: (id: number) => ['meta', 'mapping', id] as const,
  syncLogs: (p: PageParams) => ['meta', 'sync-logs', p] as const,
  failed: (p: PageParams) => ['meta', 'failed', p] as const,
};

function useInvalidateMeta() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.all }),
      queryClient.invalidateQueries({ queryKey: ['integrations'] }), // Apps overview
    ]);
}

/** Owner/Admin only; others never call the endpoint. */
export function useMetaStatus() {
  const { can } = useAuth();
  return useQuery({
    queryKey: keys.status,
    queryFn: () => api.get<MetaStatus>('/meta/status').then((r) => r.data),
    enabled: can('manage_meta'),
    staleTime: 60_000,
  });
}

/** The login popup and the main window talk over this channel (same origin). */
export const OAUTH_CHANNEL = 'lms-meta-oauth';
export interface OAuthMessage {
  type: 'result' | 'ack';
  /** '' = Meta lead ads; otherwise the app (whatsapp, google_sheets) that logged in. */
  app?: string;
  result?: 'ok' | 'error';
  message?: string;
}

/** "Connect Meta": the Facebook login popup for lead ads. */
export function useConnectMeta({ onConnected }: { onConnected: () => void }) {
  return useOAuthPopup({ app: '', startPath: '/meta/connect', onConnected });
}

/**
 * Login in a popup (Facebook, Google). The popup ends on /meta/oauth-done, which reports back
 * over a BroadcastChannel (works even when the provider cuts `window.opener`); only the hook
 * for the same app reacts. If the browser blocks popups, the whole tab goes to the provider.
 */
export function useOAuthPopup({
  app,
  startPath,
  onConnected,
}: {
  app: string;
  startPath: string;
  onConnected: () => void;
}) {
  const queryClient = useQueryClient();
  const [isPending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const done = useRef(onConnected);
  useEffect(() => {
    done.current = onConnected;
  });

  useEffect(() => {
    const channel = new BroadcastChannel(OAUTH_CHANNEL);
    channel.onmessage = ({ data }: MessageEvent<OAuthMessage>) => {
      if (data?.type !== 'result' || (data.app ?? '') !== app) return;
      channel.postMessage({ type: 'ack', app } satisfies OAuthMessage); // the popup may close now
      setPending(false);
      void queryClient.invalidateQueries({ queryKey: keys.all });
      void queryClient.invalidateQueries({ queryKey: ['integrations'] });
      if (data.result === 'ok') done.current();
      else setError(new UserFacingError(data.message));
    };
    return () => channel.close();
  }, [queryClient, app]);

  const start = useCallback(async () => {
    setError(null);
    setPending(true);
    // Open the window inside the click (before any await) so popup blockers allow it.
    const width = 600;
    const height = 720;
    const left = window.screenX + Math.max(0, (window.outerWidth - width) / 2);
    const top = window.screenY + Math.max(0, (window.outerHeight - height) / 2);
    const popup = window.open(
      '',
      'meta-login',
      `popup=yes,width=${width},height=${height},left=${left},top=${top}`,
    );
    try {
      const url = await api.post<{ url: string }>(startPath).then((r) => r.data.url);
      if (!popup || popup.closed) {
        window.location.assign(url);
        return;
      }
      popup.location.href = url;
      popup.focus();
      // Stop the spinner if the person closes the popup without finishing.
      const timer = window.setInterval(() => {
        if (popup.closed) {
          window.clearInterval(timer);
          setPending(false);
        }
      }, 700);
    } catch (err) {
      popup?.close();
      setError(err);
      setPending(false);
    }
  }, [startPath]);

  return { start, isPending, error };
}

export function useMetaPages(enabled: boolean) {
  return useQuery({
    queryKey: keys.pages,
    queryFn: () => api.get<{ pages: MetaPage[] }>('/meta/pages').then((r) => r.data.pages),
    enabled,
  });
}

export function useSelectPage() {
  const invalidate = useInvalidateMeta();
  const autoSync = useAutoSync();
  return useMutation({
    mutationFn: (pageId: string) =>
      api.post<MetaStatus>('/meta/page', { page_id: pageId }).then((r) => r.data),
    onSuccess: () => {
      void invalidate();
      autoSync();
    },
  });
}

export function useCheckAccess() {
  const invalidate = useInvalidateMeta();
  return useMutation({
    mutationFn: () => api.post<MetaStatus>('/meta/check-access').then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useDisconnectMeta() {
  const invalidate = useInvalidateMeta();
  return useMutation({ mutationFn: () => api.delete('/meta/connection'), onSuccess: invalidate });
}

export function useMetaSettings() {
  const invalidate = useInvalidateMeta();
  const autoSync = useAutoSync();
  return useMutation({
    mutationFn: (values: { detect_ad_details?: boolean; auto_connect_forms?: boolean }) =>
      api.patch<MetaStatus>('/meta/settings', values).then((r) => r.data),
    onSuccess: (_data, values) => {
      void invalidate();
      if (values.auto_connect_forms) autoSync(); // every form is on now
    },
  });
}

export const SYNC_DAYS = [1, 7, 30] as const; // last 24 hours, 7 days, 30 days
export type SyncDays = (typeof SYNC_DAYS)[number];

/** "Sync leads now": pull the last N days of leads from connected forms. */
export interface SyncRequest {
  days: SyncDays;
  /** The "Sync leads" button also restores Meta enquiries deleted in the LMS (default). */
  restoreDeleted?: boolean;
  /** Only this form (it was just switched on). */
  form?: number;
}

export interface SyncResult {
  checked: number;
  added: number;
  restored: number;
  errors: string[];
}

/** Lets any screen show "Bringing in your leads…" while a sync runs. */
export const SYNC_MUTATION_KEY = ['meta', 'sync'] as const;

/** "Sync leads": pull the last N days of leads from connected forms. */
export function useSyncNow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: SYNC_MUTATION_KEY,
    mutationFn: ({ days, restoreDeleted = true, form }: SyncRequest) =>
      api
        .post<SyncResult>('/meta/sync', { days, restore_deleted: restoreDeleted, form })
        .then((r) => r.data),
    // New enquiries and contacts appear everywhere (lists, counts, notifications): refetch all.
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

/**
 * Leads arrive without a click: after a Page is chosen, Auto Sync is turned on or a form is
 * switched on, the last 30 days are synced in the background. Deleted enquiries stay deleted.
 */
function useAutoSync() {
  const sync = useSyncNow();
  return (form?: number) => sync.mutate({ days: 30, restoreDeleted: false, form });
}

export type FormListParams = PageParams & { q?: string };

export function useMetaForms(params: FormListParams, enabled: boolean) {
  return useQuery({
    queryKey: keys.forms(params),
    queryFn: () => api.get<Paginated<MetaForm>>('/meta/forms', { params }).then((r) => r.data),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useRefreshForms() {
  const invalidate = useInvalidateMeta();
  return useMutation({
    mutationFn: () => api.post<{ refreshed: number }>('/meta/forms/refresh').then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useToggleForm() {
  const invalidate = useInvalidateMeta();
  const autoSync = useAutoSync();
  return useMutation({
    mutationFn: ({ id, connect }: { id: number; connect: boolean }) =>
      api
        .post<MetaForm>(`/meta/forms/${id}/${connect ? 'connect' : 'disconnect'}`)
        .then((r) => r.data),
    onSuccess: (_form, { id, connect }) => {
      void invalidate();
      if (connect) autoSync(id);
    },
  });
}

export function useFormMapping(id: number) {
  return useQuery({
    queryKey: keys.mapping(id),
    queryFn: () => api.get<FormMapping>(`/meta/forms/${id}/mapping`).then((r) => r.data),
  });
}

export function useSaveFormMapping(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (questions: Pick<MappingQuestion, 'question' | 'target_type' | 'custom_field'>[]) =>
      api.put<FormMapping>(`/meta/forms/${id}/mapping`, { questions }).then((r) => r.data),
    onSuccess: (data) => queryClient.setQueryData(keys.mapping(id), data),
  });
}

export function useSyncLogs(params: PageParams) {
  return useQuery({
    queryKey: keys.syncLogs(params),
    queryFn: () => api.get<Paginated<SyncLog>>('/meta/sync-logs', { params }).then((r) => r.data),
    placeholderData: keepPreviousData,
  });
}

export function useFailedSyncs(params: PageParams) {
  return useQuery({
    queryKey: keys.failed(params),
    queryFn: () =>
      api.get<Paginated<FailedSync>>('/meta/failed-syncs', { params }).then((r) => r.data),
    placeholderData: keepPreviousData,
  });
}

export function useRetrySync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api
        .post<{ status: string; enquiry_id: number | null; message: string }>(
          `/meta/failed-syncs/${id}/retry`,
        )
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.all });
      void queryClient.invalidateQueries({ queryKey: ['enquiries'] });
    },
  });
}

const POLL_MS = 60_000;
const HIDDEN_EVERY = 5; // in a background tab: every 5 minutes

/**
 * While the LMS is open, send the heartbeat about once a minute: new Meta leads, due Exotel
 * auto-calls, new Google Sheets rows, the daily Exotel number refresh. (In production Celery Beat
 * does the same.) Checks Meta for new leads
 * (every 5 minutes in a background tab, and at once when the tab comes back). Works without a
 * public webhook URL; the server runs at most one check per minute per workspace. New
 * enquiries then arrive through the live connection.
 */
export function useMetaLeadPolling() {
  const queryClient = useQueryClient();
  useEffect(() => {
    let stopped = false;
    let ticks = 0;
    const poll = async () => {
      if (stopped) return;
      try {
        const { data } = await api.post<{
          leads_added: number;
          calls_started: number;
          sheet_rows: number;
        }>('/integrations/heartbeat');
        if (data.leads_added || data.sheet_rows) {
          void queryClient.invalidateQueries({ queryKey: ['views', 'counts'] });
          void queryClient.invalidateQueries({ queryKey: ['enquiries'] });
        }
        if (data.calls_started) {
          void queryClient.invalidateQueries({ queryKey: ['integrations', 'exotel', 'calls'] });
        }
      } catch {
        /* offline or logged out: try again later */
      }
    };
    const tick = () => {
      ticks += 1;
      if (document.visibilityState === 'visible' || ticks % HIDDEN_EVERY === 0) void poll();
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible') void poll();
    };
    const first = window.setTimeout(() => void poll(), 5_000);
    const timer = window.setInterval(tick, POLL_MS);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      stopped = true;
      window.clearTimeout(first);
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [queryClient]);
}
