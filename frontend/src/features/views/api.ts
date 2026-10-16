import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { SavedView, SavedViewFilters, ViewCounts } from '@/types/crm';

export const viewKeys = {
  all: ['views'] as const,
  list: ['views', 'list'] as const,
  counts: ['views', 'counts'] as const,
};

export interface SavedViewInput {
  name?: string;
  filters?: SavedViewFilters;
  sort?: string;
  is_shared?: boolean;
}

export function useSavedViews() {
  return useQuery({
    queryKey: viewKeys.list,
    queryFn: () => api.get<SavedView[]>('/views').then((r) => r.data),
  });
}

/** Sidebar counts. Refreshed in the background, never blocks the page. */
export function useViewCounts() {
  return useQuery({
    queryKey: viewKeys.counts,
    queryFn: () => api.get<ViewCounts>('/views/counts').then((r) => r.data),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
}

export function useSaveView() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...values }: SavedViewInput & { id?: number }) =>
      (id
        ? api.patch<SavedView>(`/views/${id}`, values)
        : api.post<SavedView>('/views', values)
      ).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: viewKeys.all }),
  });
}

export function useDeleteView() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/views/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: viewKeys.all }),
  });
}

export function usePinView() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, pinned }: { id: number; pinned: boolean }) =>
      pinned ? api.post(`/views/${id}/pin`) : api.delete(`/views/${id}/pin`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: viewKeys.all }),
  });
}
