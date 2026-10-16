import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { PageParams, Paginated } from '@/types/api';

export interface TeamMember {
  id: number;
  full_name: string;
  email: string;
}

export interface Team {
  id: number;
  name: string;
  members: TeamMember[];
  created_at: string;
}

export interface TeamInput {
  name: string;
  member_ids: number[];
}

const teamKeys = {
  all: ['teams'] as const,
  list: (params: PageParams) => ['teams', 'list', params] as const,
};

export function useTeams(params: PageParams) {
  return useQuery({
    queryKey: teamKeys.list(params),
    queryFn: () => api.get<Paginated<Team>>('/teams', { params }).then((r) => r.data),
    placeholderData: keepPreviousData,
  });
}

export function useSaveTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...values }: TeamInput & { id?: number }) =>
      (id ? api.patch<Team>(`/teams/${id}`, values) : api.post<Team>('/teams', values)).then(
        (r) => r.data,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: teamKeys.all }),
  });
}

export function useDeleteTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/teams/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: teamKeys.all }),
  });
}
