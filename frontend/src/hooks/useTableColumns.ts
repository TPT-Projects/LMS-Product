import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import { resolveColumns, type ColumnOption } from '@/components/data-table/columns';
import { api } from '@/lib/api/client';

export type TableKey = 'enquiries' | 'contacts' | 'users';

interface TablePreference {
  table: TableKey;
  columns: string[];
}

/** The user's saved column layout for a table (stored on the server, per user). */
export function useTableColumns(table: TableKey, options: ColumnOption[]) {
  const queryClient = useQueryClient();
  const key = ['preferences', 'table', table] as const;

  const saved = useQuery({
    queryKey: key,
    queryFn: () => api.get<TablePreference>(`/preferences/tables/${table}`).then((r) => r.data),
    staleTime: Infinity,
  });

  const save = useMutation({
    mutationFn: (columns: string[]) =>
      api.put<TablePreference>(`/preferences/tables/${table}`, { columns }).then((r) => r.data),
    // Apply at once; the server copy follows.
    onMutate: (columns) => queryClient.setQueryData(key, { table, columns }),
    onSuccess: (data) => queryClient.setQueryData(key, data),
  });

  const visible = useMemo(
    () => resolveColumns(options, saved.data?.columns),
    [options, saved.data?.columns],
  );

  return { visible, saved: saved.data?.columns ?? [], save, isLoading: saved.isPending };
}
