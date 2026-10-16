import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { Workspace } from '@/types/auth';

export type WorkspaceUpdate = Partial<
  Pick<Workspace, 'name' | 'timezone' | 'dedupe_key' | 'default_country'>
>;

const workspaceKey = ['workspace'] as const;

export function useWorkspace() {
  return useQuery({
    queryKey: workspaceKey,
    queryFn: () => api.get<Workspace>('/workspace').then((r) => r.data),
  });
}

export function useUpdateWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: WorkspaceUpdate) =>
      api.patch<Workspace>('/workspace', values).then((r) => r.data),
    onSuccess: (data) => queryClient.setQueryData(workspaceKey, data),
  });
}
