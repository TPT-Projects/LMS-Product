import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { Status } from '@/types/crm';

export const statusKeys = { all: ['statuses'] as const };

export type StatusInput = Partial<
  Pick<Status, 'name' | 'color' | 'is_default' | 'is_closed' | 'is_won'>
>;

export function useStatuses() {
  return useQuery({
    queryKey: statusKeys.all,
    queryFn: () => api.get<Status[]>('/statuses').then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

export function useSaveStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...values }: StatusInput & { id?: number }) =>
      (id
        ? api.patch<Status>(`/statuses/${id}`, values)
        : api.post<Status>('/statuses', values)
      ).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: statusKeys.all }),
  });
}

export function useReorderStatuses() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: number[]) =>
      api.post<Status[]>('/statuses/reorder', { ids }).then((r) => r.data),
    onMutate: async (ids) => {
      // Optimistic: move rows at once, roll back if the server says no.
      await queryClient.cancelQueries({ queryKey: statusKeys.all });
      const previous = queryClient.getQueryData<Status[]>(statusKeys.all);
      if (previous) {
        const byId = new Map(previous.map((s) => [s.id, s]));
        queryClient.setQueryData(
          statusKeys.all,
          ids.map((id, order) => ({ ...byId.get(id)!, order })),
        );
      }
      return { previous };
    },
    onError: (_err, _ids, context) => {
      if (context?.previous) queryClient.setQueryData(statusKeys.all, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: statusKeys.all }),
  });
}
