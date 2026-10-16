import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { PageParams, Paginated } from '@/types/api';

export interface AppNotification {
  id: number;
  kind: string;
  title: string;
  body: string;
  link: string;
  data: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
}

type NotificationPage = Paginated<AppNotification> & { unread_count: number };

export function useNotifications(params: PageParams) {
  return useQuery({
    queryKey: ['notifications', params],
    queryFn: () => api.get<NotificationPage>('/notifications', { params }).then((r) => r.data),
    placeholderData: keepPreviousData,
    refetchInterval: 120_000, // the WebSocket refreshes it sooner when connected
  });
}

export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number | 'all') =>
      id === 'all' ? api.post('/notifications/read-all') : api.post(`/notifications/${id}/read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });
}
