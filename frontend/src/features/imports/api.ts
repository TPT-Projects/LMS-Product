import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { PageParams, Paginated } from '@/types/api';

export type ImportStatus =
  'uploaded' | 'mapped' | 'queued' | 'running' | 'completed' | 'completed_with_errors' | 'failed';

export interface ImportJob {
  id: number;
  original_name: string;
  file_type: 'csv' | 'xlsx';
  headers: string[];
  row_count: number;
  mapping: Record<string, string>;
  status: ImportStatus;
  mode: 'live' | 'background' | '';
  processed_count: number;
  created_count: number;
  linked_count: number;
  failed_count: number;
  error: string;
  created_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface UploadedImport extends ImportJob {
  sample: Record<string, string>[];
  targets: string[];
}

export interface ImportDetail extends ImportJob {
  failed_rows: { row_number: number; errors: string[]; data: Record<string, string> }[];
}

export interface ImportPreview {
  rows: { row_number: number; values: Record<string, string>; errors: string[] }[];
  summary: {
    total: number;
    valid: number;
    invalid: number;
    existing_contacts: number;
    duplicates_in_file: number;
  };
  mode: 'live' | 'background';
}

export const RUNNING: ImportStatus[] = ['queued', 'running'];

export function useImports(params: PageParams) {
  return useQuery({
    queryKey: ['imports', 'list', params],
    queryFn: () => api.get<Paginated<ImportJob>>('/imports', { params }).then((r) => r.data),
    placeholderData: keepPreviousData,
    // Keep the log fresh while something is running in the background.
    refetchInterval: (query) =>
      query.state.data?.results.some((j) => RUNNING.includes(j.status)) ? 3000 : false,
  });
}

export function useImport(id: number) {
  return useQuery({
    queryKey: ['imports', 'detail', id],
    queryFn: () => api.get<ImportDetail>(`/imports/${id}`).then((r) => r.data),
    refetchInterval: (query) =>
      query.state.data && RUNNING.includes(query.state.data.status) ? 2000 : false,
  });
}

export function useUploadImport() {
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return api
        .post<UploadedImport>('/imports', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        .then((r) => r.data);
    },
  });
}

export function useSaveMapping(id: number) {
  return useMutation({
    mutationFn: (mapping: Record<string, string>) =>
      api.post<ImportJob>(`/imports/${id}/map`, { mapping }).then((r) => r.data),
  });
}

export function usePreview(id: number | null) {
  return useQuery({
    queryKey: ['imports', 'preview', id],
    queryFn: () => api.get<ImportPreview>(`/imports/${id}/preview`).then((r) => r.data),
    enabled: id !== null,
    staleTime: 0,
    gcTime: 0, // always recompute after the mapping changes
  });
}

export function useRunImport(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<ImportJob>(`/imports/${id}/run`).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['imports'] });
      void queryClient.invalidateQueries({ queryKey: ['enquiries'] });
      void queryClient.invalidateQueries({ queryKey: ['views', 'counts'] });
    },
  });
}

/** Authenticated download of a CSV (template, failed rows, export). */
export async function downloadFile(
  url: string,
  fallbackName: string,
  options: { method?: 'get' | 'post'; body?: unknown } = {},
) {
  const response =
    options.method === 'post'
      ? await api.post<Blob>(url, options.body, { responseType: 'blob' })
      : await api.get<Blob>(url, { responseType: 'blob' });
  const disposition = String(response.headers['content-disposition'] ?? '');
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const href = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = href;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(href), 10_000);
}
