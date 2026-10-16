import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { CustomField } from '@/types/crm';

export const customFieldKeys = { all: ['custom-fields'] as const };

export type CustomFieldInput = Partial<
  Pick<CustomField, 'label' | 'key' | 'type' | 'options' | 'is_required' | 'is_active'>
>;

/** All fields (active and inactive). Use `activeFields()` for forms and tables. */
export function useCustomFields() {
  return useQuery({
    queryKey: customFieldKeys.all,
    queryFn: () => api.get<CustomField[]>('/custom-fields').then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

export function activeFields(fields: CustomField[] | undefined): CustomField[] {
  return (fields ?? []).filter((f) => f.is_active);
}

export function useSaveCustomField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...values }: CustomFieldInput & { id?: number }) =>
      (id
        ? api.patch<CustomField>(`/custom-fields/${id}`, values)
        : api.post<CustomField>('/custom-fields', values)
      ).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: customFieldKeys.all }),
  });
}
