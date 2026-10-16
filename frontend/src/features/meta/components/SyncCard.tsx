import type { ColumnDef } from '@tanstack/react-table';
import { History, RotateCcw } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { DataTable } from '@/components/data-table';
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { DEFAULT_PAGE_SIZE } from '@/hooks/usePageParams';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { useFailedSyncs, useRetrySync, useSyncLogs, type FailedSync, type SyncLog } from '../api';

const STATUS_TONE = {
  synced: 'success',
  duplicate: 'neutral',
  form_not_connected: 'warning',
  campaign_not_selected: 'warning',
  restored: 'success',
  failed: 'danger',
} as const;

function usePaging() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  return {
    params: { page, page_size: pageSize },
    page,
    pageSize,
    setPage,
    setPageSize: (size: number) => {
      setPageSize(size);
      setPage(1);
    },
  };
}

/** Lead sync history and failed syncs with Retry. */
export function SyncCard() {
  const { t } = useTranslation();
  const format = useDateFormat();
  const historyPaging = usePaging();
  const failedPaging = usePaging();
  const logs = useSyncLogs(historyPaging.params);
  const failed = useFailedSyncs(failedPaging.params);
  const retry = useRetrySync();

  const logColumns = useMemo<ColumnDef<SyncLog, unknown>[]>(
    () => [
      {
        id: 'date',
        header: t('meta.sync.when'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">
            {format.dateTime(row.original.created_at)}
          </span>
        ),
      },
      {
        id: 'status',
        header: t('fields.status'),
        cell: ({ row }) => (
          <Badge tone={STATUS_TONE[row.original.status]}>
            {t(`meta.sync.status.${row.original.status}`)}
          </Badge>
        ),
      },
      {
        id: 'source',
        header: t('meta.sync.source'),
        cell: ({ row }) => t(`meta.sync.sources.${row.original.source}`),
      },
      {
        id: 'lead',
        header: t('meta.sync.lead'),
        cell: ({ row }) =>
          row.original.enquiry_id ? (
            <Link
              to={`${paths.enquiries}/${row.original.enquiry_id}`}
              className="text-accent hover:underline"
            >
              {row.original.leadgen_id}
            </Link>
          ) : (
            <span className="tabular-nums">{row.original.leadgen_id}</span>
          ),
      },
      {
        id: 'message',
        header: t('meta.sync.message'),
        cell: ({ row }) => (
          <span className="block max-w-72 truncate text-fg-muted">
            {row.original.message || '—'}
          </span>
        ),
      },
    ],
    [t, format],
  );

  const failedColumns = useMemo<ColumnDef<FailedSync, unknown>[]>(
    () => [
      {
        id: 'lead',
        header: t('meta.sync.lead'),
        cell: ({ row }) => <span className="tabular-nums">{row.original.leadgen_id}</span>,
      },
      {
        id: 'error',
        header: t('meta.sync.error'),
        cell: ({ row }) => (
          <span className="block max-w-80 truncate text-danger">{row.original.error}</span>
        ),
      },
      { id: 'attempts', header: t('meta.sync.attempts'), cell: ({ row }) => row.original.attempts },
      {
        id: 'last',
        header: t('meta.sync.lastAttempt'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">
            {format.dateTime(row.original.last_attempt_at)}
          </span>
        ),
      },
      {
        id: 'retry',
        header: () => <span className="sr-only">{t('common.actions')}</span>,
        meta: { className: 'text-right' },
        cell: ({ row }) => (
          <Button
            size="sm"
            variant="secondary"
            loading={retry.isPending && retry.variables === row.original.id}
            onClick={() => retry.mutate(row.original.id)}
          >
            <RotateCcw className="size-3.5" aria-hidden /> {t('meta.sync.retry')}
          </Button>
        ),
      },
    ],
    [t, format, retry],
  );

  return (
    <Card>
      <Tabs defaultValue="history">
        <TabsList className="px-2">
          <TabsTrigger value="history">{t('meta.sync.history')}</TabsTrigger>
          <TabsTrigger value="failed">
            {t('meta.sync.failed')}
            {(failed.data?.count ?? 0) > 0 && <Badge tone="danger">{failed.data?.count}</Badge>}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="history" className="pt-0">
          {logs.isError && (
            <Alert tone="danger" className="m-4">
              {getErrorMessage(logs.error)}
            </Alert>
          )}
          <DataTable
            columns={logColumns}
            data={logs.data}
            isLoading={logs.isPending}
            page={historyPaging.page}
            pageSize={historyPaging.pageSize}
            onPageChange={historyPaging.setPage}
            onPageSizeChange={historyPaging.setPageSize}
            getRowId={(l) => String(l.id)}
            empty={<EmptyState icon={History} title={t('meta.sync.emptyHistory')} />}
          />
        </TabsContent>
        <TabsContent value="failed" className="pt-0">
          {retry.data && (
            <Alert tone={retry.data.status === 'failed' ? 'danger' : 'success'} className="m-4">
              {t(`meta.sync.retried.${retry.data.status}`, { defaultValue: retry.data.status })}
            </Alert>
          )}
          <DataTable
            columns={failedColumns}
            data={failed.data}
            isLoading={failed.isPending}
            page={failedPaging.page}
            pageSize={failedPaging.pageSize}
            onPageChange={failedPaging.setPage}
            onPageSizeChange={failedPaging.setPageSize}
            getRowId={(f) => String(f.id)}
            empty={<EmptyState icon={History} title={t('meta.sync.emptyFailed')} />}
          />
        </TabsContent>
      </Tabs>
    </Card>
  );
}
