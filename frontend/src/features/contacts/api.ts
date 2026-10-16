import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { PageParams, Paginated } from '@/types/api';
import type { Contact, ContactDetail } from '@/types/crm';

/** Contacts are read-only: the system creates them from enquiries. */
export function useContacts(params: PageParams & { q?: string }) {
  return useQuery({
    queryKey: ['contacts', 'list', params],
    queryFn: () =>
      api
        .get<Paginated<Contact>>('/contacts', { params: { ...params, q: params.q || undefined } })
        .then((r) => r.data),
    placeholderData: keepPreviousData,
  });
}

export function useContact(id: number) {
  return useQuery({
    queryKey: ['contacts', 'detail', id],
    queryFn: () => api.get<ContactDetail>(`/contacts/${id}`).then((r) => r.data),
  });
}
