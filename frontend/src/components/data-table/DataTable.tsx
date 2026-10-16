import { flexRender, getCoreRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table';
import type { ReactNode } from 'react';

import { Skeleton } from '@/components/ui';
import { cn } from '@/lib/cn';
import type { Paginated } from '@/types/api';

import { Pagination } from './Pagination';

export interface ColumnMeta {
  /** Extra classes for the <th> and <td> of this column (e.g. width, hide on mobile). */
  className?: string;
}

interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];
  data: Paginated<T> | undefined;
  isLoading: boolean;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  empty: ReactNode;
  getRowId?: (row: T) => string;
  /** Click anywhere on a row (controls inside the row should stop propagation). */
  onRowClick?: (row: T) => void;
  isRowSelected?: (row: T) => boolean;
}

/**
 * Server-paginated table (spec 6, "Tables"): 25 rows by default, 50/100/200
 * options, first/previous/page numbers/next/last and a total count.
 * Scrolls sideways on small screens instead of squashing columns.
 */
export function DataTable<T>({
  columns,
  data,
  isLoading,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  empty,
  getRowId,
  onRowClick,
  isRowSelected,
}: DataTableProps<T>) {
  // TanStack Table is not React Compiler friendly yet; this only skips that optimisation.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: data?.results ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    rowCount: data?.count ?? 0,
    getRowId,
  });

  const rows = table.getRowModel().rows;
  const showEmpty = !isLoading && rows.length === 0;

  return (
    <div>
      <div className="relative overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id} className="border-b">
                {group.headers.map((header) => (
                  <th
                    key={header.id}
                    scope="col"
                    className={cn(
                      'px-3 py-2 text-xs font-medium whitespace-nowrap text-fg-muted first:pl-4 last:pr-4 sm:first:pl-5 sm:last:pr-5',
                      (header.column.columnDef.meta as ColumnMeta | undefined)?.className,
                    )}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 5 }, (_, i) => (
                  <tr key={i} className="border-b last:border-0">
                    {columns.map((_c, j) => (
                      <td
                        key={j}
                        className="px-3 py-3 first:pl-4 last:pr-4 sm:first:pl-5 sm:last:pr-5"
                      >
                        <Skeleton className="h-4 w-full max-w-40" />
                      </td>
                    ))}
                  </tr>
                ))
              : rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                    className={cn(
                      'group border-b transition-colors last:border-0 hover:bg-subtle',
                      onRowClick && 'cursor-pointer',
                      isRowSelected?.(row.original) && 'bg-accent-soft/60 hover:bg-accent-soft',
                    )}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className={cn(
                          'px-3 py-2.5 align-middle whitespace-nowrap first:pl-4 last:pr-4 sm:first:pl-5 sm:last:pr-5',
                          (cell.column.columnDef.meta as ColumnMeta | undefined)?.className,
                        )}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      {showEmpty && empty}

      {!showEmpty && data && (
        <Pagination
          page={page}
          pageSize={pageSize}
          count={data.count}
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
        />
      )}
    </div>
  );
}
