import type { ColumnDef } from '@tanstack/react-table';
import { FileSpreadsheet, Plus } from 'lucide-react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { DataTable } from '@/components/data-table';
import { PageHeader } from '@/components/layout/PageHeader';
import { Alert, Button, Card, EmptyState } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { usePageParams } from '@/hooks/usePageParams';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { useImports, type ImportJob } from '../api';
import { ImportStatusBadge } from '../components/ImportStatusBadge';

/** Import log: every file, its status and counts. */
export default function ImportsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useDateFormat();
  const { page, page_size, setPage, setPageSize } = usePageParams();
  const imports = useImports({ page, page_size });

  const columns = useMemo<ColumnDef<ImportJob, unknown>[]>(
    () => [
      {
        id: 'file',
        header: t('imports.file'),
        cell: ({ row }) => (
          <Link
            to={`${paths.imports}/${row.original.id}`}
            onClick={(e) => e.stopPropagation()}
            className="flex max-w-72 items-center gap-2 font-medium hover:underline"
          >
            <FileSpreadsheet className="size-4 shrink-0 text-fg-subtle" aria-hidden />
            <span className="truncate">{row.original.original_name}</span>
          </Link>
        ),
      },
      {
        id: 'status',
        header: t('fields.status'),
        cell: ({ row }) => <ImportStatusBadge status={row.original.status} />,
      },
      {
        id: 'rows',
        header: t('imports.rows'),
        cell: ({ row }) => <span className="tabular-nums">{row.original.row_count}</span>,
      },
      {
        id: 'result',
        header: t('imports.result'),
        cell: ({ row }) => {
          const j = row.original;
          if (j.processed_count === 0) return <span className="text-fg-subtle">—</span>;
          return (
            <span className="text-[13px] whitespace-nowrap text-fg-muted">
              {t('imports.resultShort', {
                created: j.created_count,
                linked: j.linked_count,
                failed: j.failed_count,
              })}
            </span>
          );
        },
      },
      {
        id: 'by',
        header: t('imports.by'),
        cell: ({ row }) => <span className="text-fg-muted">{row.original.created_by ?? '—'}</span>,
      },
      {
        id: 'date',
        header: t('common.created'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">
            {format.dateTime(row.original.created_at)}
          </span>
        ),
      },
    ],
    [t, format],
  );

  const newButton = (
    <Link to={paths.importNew}>
      <Button>
        <Plus className="size-4" aria-hidden />
        {t('imports.new')}
      </Button>
    </Link>
  );

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title={t('nav.imports')}
        description={t('imports.description')}
        actions={newButton}
      />
      <Card>
        {imports.isError && (
          <div className="p-4">
            <Alert tone="danger">{getErrorMessage(imports.error)}</Alert>
          </div>
        )}
        <DataTable
          columns={columns}
          data={imports.data}
          isLoading={imports.isPending}
          page={page}
          pageSize={page_size}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
          getRowId={(j) => String(j.id)}
          onRowClick={(j) => navigate(`${paths.imports}/${j.id}`)}
          empty={
            <EmptyState
              icon={FileSpreadsheet}
              title={t('imports.empty.title')}
              description={t('imports.empty.description')}
              action={newButton}
            />
          }
        />
      </Card>
    </div>
  );
}
