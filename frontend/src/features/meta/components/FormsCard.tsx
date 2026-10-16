import type { ColumnDef } from '@tanstack/react-table';
import { ClipboardList, RefreshCw, SlidersHorizontal } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { DataTable } from '@/components/data-table';
import { Alert, Badge, Button, Card, CardHeader, EmptyState } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { DEFAULT_PAGE_SIZE } from '@/hooks/usePageParams';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { FormSearch } from './FormSearch';
import { useMetaForms, useMetaStatus, useRefreshForms, useToggleForm, type MetaForm } from '../api';
import { AutoSyncToggle } from './AutoSyncToggle';

/** Manage Forms: every Instant Form of the Page; only connected forms create enquiries. */
export function FormsCard() {
  const { t } = useTranslation();
  const format = useDateFormat();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const forms = useMetaForms({ page, page_size: pageSize, q }, true);
  const refresh = useRefreshForms();
  const toggle = useToggleForm();
  const auto = useMetaStatus().data?.auto_connect_forms ?? true;
  const error = forms.error ?? refresh.error ?? toggle.error;

  const columns = useMemo<ColumnDef<MetaForm, unknown>[]>(
    () => [
      {
        id: 'name',
        header: t('meta.forms.name'),
        cell: ({ row }) => (
          <div className="max-w-64">
            <p className="truncate font-medium">{row.original.name || '—'}</p>
            <p className="text-xs text-fg-muted tabular-nums">{row.original.form_id}</p>
          </div>
        ),
      },
      {
        id: 'meta_status',
        header: t('meta.forms.statusOnMeta'),
        cell: ({ row }) => (
          <Badge tone={row.original.status_on_meta === 'ACTIVE' ? 'success' : 'neutral'}>
            {row.original.status_on_meta
              ? t(`meta.forms.metaStatus.${row.original.status_on_meta.toLowerCase()}`, {
                  defaultValue: row.original.status_on_meta,
                })
              : '—'}
          </Badge>
        ),
      },
      {
        id: 'created',
        header: t('common.created'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">
            {format.date(row.original.created_time)}
          </span>
        ),
      },
      {
        id: 'connection',
        header: t('meta.forms.connection'),
        cell: ({ row }) =>
          row.original.is_connected ? (
            <Badge tone="accent">{t('meta.forms.connected')}</Badge>
          ) : (
            <Badge>{t('meta.forms.notConnected')}</Badge>
          ),
      },
      {
        id: 'leads',
        header: t('meta.forms.leads'),
        cell: ({ row }) => <span className="tabular-nums">{row.original.leads_received}</span>,
      },
      {
        id: 'actions',
        header: () => <span className="sr-only">{t('common.actions')}</span>,
        meta: { className: 'text-right' },
        cell: ({ row }) => {
          const form = row.original;
          return (
            <div className="flex justify-end gap-1.5">
              {form.is_connected && (
                <Link to={`${paths.settingsMeta}/forms/${form.id}`}>
                  <Button variant="ghost" size="sm">
                    <SlidersHorizontal className="size-3.5" aria-hidden />{' '}
                    {t('meta.forms.mapFields')}
                  </Button>
                </Link>
              )}
              <Button
                size="sm"
                variant={form.is_connected ? 'secondary' : 'primary'}
                loading={toggle.isPending && toggle.variables?.id === form.id}
                disabled={auto}
                title={auto ? t('meta.autoSync.lockedHint') : undefined}
                onClick={() => toggle.mutate({ id: form.id, connect: !form.is_connected })}
              >
                {form.is_connected ? t('meta.forms.disconnect') : t('meta.forms.connect')}
              </Button>
            </div>
          );
        },
      },
    ],
    [t, format, toggle, auto],
  );

  return (
    <Card>
      <CardHeader
        title={t('meta.forms.title')}
        description={t('meta.forms.description')}
        actions={
          <Button variant="secondary" loading={refresh.isPending} onClick={() => refresh.mutate()}>
            <RefreshCw className="size-4" aria-hidden /> {t('meta.forms.refresh')}
          </Button>
        }
      />
      <div className="px-4 pt-4 sm:px-5">
        <AutoSyncToggle auto={auto} />
        <div className="mt-3">
          <FormSearch
            value={search}
            onChange={(value) => {
              setSearch(value);
              setPage(1);
            }}
          />
        </div>
      </div>
      {error && (
        <div className="px-4 pt-3 sm:px-5">
          <Alert tone="danger">{getErrorMessage(error)}</Alert>
        </div>
      )}
      <DataTable
        columns={columns}
        data={forms.data}
        isLoading={forms.isPending}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        getRowId={(f) => String(f.id)}
        empty={
          <EmptyState
            icon={ClipboardList}
            title={t('meta.forms.empty.title')}
            description={t('meta.forms.empty.description')}
          />
        }
      />
    </Card>
  );
}
