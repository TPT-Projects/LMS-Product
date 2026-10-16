import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { PageParams, Paginated } from '@/types/api';
import type { Role } from '@/types/auth';

export interface Member {
  id: number; // user id
  email: string;
  full_name: string;
  /** E.164. Exotel rings this number first for the user's auto-calls. */
  phone: string;
  alternate_phone: string;
  role: Role;
  is_active: boolean;
  last_login: string | null;
  joined_at: string;
}

export type InvitationStatus = 'pending' | 'accepted' | 'revoked' | 'expired';

export interface Invitation {
  id: number;
  email: string;
  role: Role;
  invited_by: string | null;
  status: InvitationStatus;
  expires_at: string;
  created_at: string;
  invite_url?: string; // only in the response to POST /users
}

export interface MemberFilters extends PageParams {
  q?: string;
  role?: Role | '';
}

export const userKeys = {
  all: ['users'] as const,
  list: (filters: MemberFilters) => ['users', 'list', filters] as const,
  invitations: ['users', 'invitations'] as const,
};

export function useMembers(filters: MemberFilters) {
  return useQuery({
    queryKey: userKeys.list(filters),
    queryFn: () =>
      api
        .get<Paginated<Member>>('/users', {
          params: { ...filters, q: filters.q || undefined, role: filters.role || undefined },
        })
        .then((r) => r.data),
    placeholderData: keepPreviousData,
  });
}

/** All active members on one page (for pickers such as team members). */
export function useAllMembers() {
  return useMembers({ page: 1, page_size: 200 });
}

export function usePendingInvitations(enabled: boolean) {
  return useQuery({
    queryKey: userKeys.invitations,
    queryFn: () =>
      api
        .get<Paginated<Invitation>>('/invitations', {
          params: { status: 'pending', page_size: 200 },
        })
        .then((r) => r.data),
    enabled,
  });
}

export function useInviteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: { email: string; role: Role }) =>
      api.post<Invitation>('/users', values).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: userKeys.invitations }),
  });
}

export function useChangeRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: Role }) =>
      api.patch<Member>(`/users/${userId}/role`, { role }).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export interface ProfileChanges {
  full_name?: string;
  phone?: string;
  alternate_phone?: string;
}

/** Your own details, or anyone's with manage_users. */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, ...changes }: ProfileChanges & { userId: number }) =>
      api.patch<Member>(`/users/${userId}/profile`, changes).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export function useRevokeInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/invitations/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: userKeys.invitations }),
  });
}
