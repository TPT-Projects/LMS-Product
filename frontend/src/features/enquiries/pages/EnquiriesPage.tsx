import type { ColumnDef } from '@tanstack/react-table';
import {
  BookmarkPlus,
  Download,
  Inbox,
  LayoutGrid,
  ListFilter,
  Plus,
  RefreshCw,
  Search,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { ColumnsButton, DataTable } from '@/components/data-table';
import { PageHeader } from '@/components/layout/PageHeader';
import { Alert, Badge, Button, Card, Checkbox, EmptyState, Input, Select } from '@/components/ui';
import { useAuth } from '@/features/auth/useAuth';
import { activeFields, useCustomFields } from '@/features/customfields/api';
import { useStatuses } from '@/features/statuses/api';
import { StatusBadge } from '@/features/statuses/components/StatusBadge';
import { useAllMembers } from '@/features/users/api';
import { downloadFile } from '@/features/imports/api';
import { useLive } from '@/features/live/liveContext';
import { useSavedViews, useViewCounts } from '@/features/views/api';
import { SaveViewDialog } from '@/features/views/components/SaveViewDialog';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';
import { paths, smartViews } from '@/routes/paths';
import { SOURCES, type Enquiry } from '@/types/crm';

import { useEnquiries } from '../api';
import { BulkActionBar } from '../components/BulkActionBar';
import { FilterBuilderDialog } from '../components/FilterBuilderDialog';
import { QuickFilterMenu } from '../components/QuickFilterMenu';
import { countRules, toSavableFilters } from '../filters';
import { useEnquiryListParams } from '../useEnquiryListParams';
import { useEnquiryColumns } from '../useEnquiryColumns';
import { useQuickAdd } from '../useQuickAdd';

const SORTS = ['-created_at', 'created_at', '-updated_at', 'name', 'status', 'owner'] as const;

export default function EnquiriesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const { params, update, clearFilters } = useEnquiryListParams();
  const enquiries = useEnquiries(params);
  const statuses = useStatuses();
  const members = useAllMembers();
  const customFields = activeFields(useCustomFields().data);
  const savedViews = useSavedViews();
  const counts = useViewCounts();
  const quickAdd = useQuickAdd();
  const live = useLive();
  const [exporting, setExporting] = useState(false);

  const [search, setSearch] = useState(params.q ?? '');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [filterOpen, setFilterOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // New leads appear on their own on page 1 when nothing is selected; otherwise the pill offers them.
  const autoRefresh = (params.page ?? 1) === 1 && selected.size === 0;
  const { subscribe, clearNewLeads } = live;
  const { refetch } = enquiries;
  useEffect(() => {
    if (!autoRefresh) return;
    let timer: number | undefined;
    const unsubscribe = subscribe((event) => {
      if (event.event !== 'enquiry.created') return;
      window.clearTimeout(timer); // a sync brings many leads at once: refetch once
      timer = window.setTimeout(() => {
        clearNewLeads();
        void refetch();
      }, 800);
    });
    return () => {
      unsubscribe();
      window.clearTimeout(timer);
    };
  }, [autoRefresh, subscribe, clearNewLeads, refetch]);

  useEffect(() => {
    if ((params.q ?? '') !== debouncedSearch) update({ q: debouncedSearch });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to typing
  }, [debouncedSearch]);

  // A search started elsewhere (top bar "See all results") lands in the box too.
  const [urlQ, setUrlQ] = useState(params.q ?? '');
  if ((params.q ?? '') !== urlQ) {
    setUrlQ(params.q ?? '');
    if ((params.q ?? '') !== debouncedSearch) setSearch(params.q ?? '');
  }

  // A different list means a different selection.
  const listKey = JSON.stringify({ ...params, page: 0 });
  const [selectionKey, setSelectionKey] = useState(listKey);
  if (selectionKey !== listKey) {
    setSelectionKey(listKey);
    setSelected(new Set());
  }

  const savedView = savedViews.data?.find((v) => v.id === params.saved_view) ?? null;
  const systemView = smartViews.find((v) => v.id === params.view) ?? smartViews[0];
  const title = savedView ? savedView.name : t(systemView.labelKey);
  const builderCount = countRules(params.filter);
  const hasFilters = Boolean(
    params.q ||
    params.status?.length ||
    params.owner?.length ||
    params.source?.length ||
    builderCount,
  );
  const rows = useMemo(() => enquiries.data?.results ?? [], [enquiries.data]);
  const allOnPage = rows.length > 0 && rows.every((r) => selected.has(r.id));

  const columnLayout = useEnquiryColumns(customFields);

  const columns = useMemo<ColumnDef<Enquiry, unknown>[]>(() => {
    const toggle = (id: number) =>
      setSelected((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
    const select: ColumnDef<Enquiry, unknown> = {
      id: 'select',
      meta: { className: 'w-10 pr-0' },
      header: () => (
        <Checkbox
          aria-label={t('enquiries.selectAll')}
          checked={allOnPage}
          indeterminate={!allOnPage && rows.some((r) => selected.has(r.id))}
          onChange={() => setSelected(allOnPage ? new Set() : new Set(rows.map((r) => r.id)))}
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          aria-label={t('enquiries.select', { name: row.original.name })}
          checked={selected.has(row.original.id)}
          onClick={(e) => e.stopPropagation()}
          onChange={() => toggle(row.original.id)}
        />
      ),
    };
    return [select, ...columnLayout.defs];
  }, [t, selected, rows, allOnPage, columnLayout.defs]);

  const tabs = [
    ...smartViews.map((v) => ({
      key: v.id,
      label: t(v.labelKey),
      count: counts.data?.system[v.id],
      active: !params.saved_view && params.view === v.id,
      to: v.id === 'all' ? paths.enquiries : `${paths.enquiries}?view=${v.id}`,
    })),
    ...(savedViews.data ?? [])
      .filter((v) => v.is_pinned)
      .map((v) => ({
        key: `saved-${v.id}`,
        label: v.name,
        count: counts.data?.saved[String(v.id)],
        active: params.saved_view === v.id,
        to: `${paths.enquiries}?saved_view=${v.id}`,
      })),
  ];

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title={title}
        description={t('enquiries.description')}
        actions={
          <>
            {hasFilters && (
              <Button variant="secondary" onClick={() => setSaveOpen(true)}>
                <BookmarkPlus className="size-4" aria-hidden />
                {t('views.saveAs')}
              </Button>
            )}
            {can('export') && (
              <Button
                variant="secondary"
                loading={exporting}
                onClick={async () => {
                  setExporting(true);
                  try {
                    await downloadFile('/exports', 'enquiries.csv', {
                      method: 'post',
                      body: {
                        ...params,
                        filter: params.filter ?? undefined,
                        columns: columnLayout.visible.filter((c) => c !== 'action'),
                      },
                    });
                  } catch (err) {
                    setMessage(getErrorMessage(err));
                  } finally {
                    setExporting(false);
                  }
                }}
              >
                <Download className="size-4" aria-hidden />
                {t('enquiries.export')}
              </Button>
            )}
            {can('edit_enquiries') && (
              <Button onClick={quickAdd.open}>
                <Plus className="size-4" aria-hidden />
                {t('enquiries.new')}
              </Button>
            )}
          </>
        }
      />

      <Card>
        <nav
          aria-label={t('nav.smartViews')}
          className="scrollbar-none overflow-x-auto overflow-y-hidden border-b px-2 sm:px-3"
        >
          <ul className="flex gap-1">
            {tabs.map((tab) => (
              <li key={tab.key}>
                <Link
                  to={tab.to}
                  aria-current={tab.active ? 'page' : undefined}
                  className={cn(
                    '-mb-px inline-flex h-11 items-center gap-1.5 border-b-2 px-2.5 text-[13px] font-medium whitespace-nowrap',
                    tab.active
                      ? 'border-accent text-fg'
                      : 'border-transparent text-fg-muted hover:text-fg',
                  )}
                >
                  {tab.label}
                  {tab.count !== undefined && (
                    <span className="rounded bg-muted px-1.5 text-[11px] text-fg-muted tabular-nums">
                      {tab.count}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex flex-col gap-2 border-b px-4 py-3 sm:px-5 lg:flex-row lg:items-center">
          <div className="relative lg:w-72">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle"
              aria-hidden
            />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('enquiries.searchPlaceholder')}
              aria-label={t('enquiries.searchPlaceholder')}
              className="h-8 pl-9"
            />
          </div>
          <div className="scrollbar-none flex items-center gap-2 overflow-x-auto lg:flex-1">
            <QuickFilterMenu
              label={t('fields.status')}
              options={(statuses.data ?? []).map((s) => ({
                value: String(s.id),
                label: <StatusBadge name={s.name} color={s.color} />,
              }))}
              selected={(params.status ?? []).map(String)}
              onChange={(values) => update({ status: values.map(Number) })}
            />
            <QuickFilterMenu
              label={t('fields.owner')}
              options={[
                { value: 'me', label: t('filters.me') },
                ...(members.data?.results ?? []).map((m) => ({
                  value: String(m.id),
                  label: m.full_name,
                })),
              ]}
              selected={params.owner ?? []}
              onChange={(values) => update({ owner: values })}
            />
            <QuickFilterMenu
              label={t('fields.source')}
              options={SOURCES.map((s) => ({ value: s, label: t(`sources.${s}`) }))}
              selected={params.source ?? []}
              onChange={(values) => update({ source: values as typeof params.source })}
            />
            <Button
              variant={builderCount ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setFilterOpen(true)}
              className={cn(builderCount > 0 && 'border-accent text-accent')}
            >
              <ListFilter className="size-3.5" aria-hidden />
              {t('filters.button')}
              {builderCount > 0 && <Badge tone="accent">{builderCount}</Badge>}
            </Button>
            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearch('');
                  clearFilters();
                }}
              >
                <X className="size-3.5" aria-hidden />
                {t('filters.clear')}
              </Button>
            )}
          </div>
          <ColumnsButton
            options={columnLayout.options}
            visible={columnLayout.visible}
            onSave={columnLayout.save}
          />
          <Select
            aria-label={t('enquiries.sortBy')}
            className="h-8 lg:w-48"
            value={params.sort || '-created_at'}
            onChange={(e) =>
              update({ sort: e.target.value === '-created_at' ? '' : e.target.value })
            }
          >
            {SORTS.map((sort) => (
              <option key={sort} value={sort}>
                {t(`enquiries.sorts.${sort}`)}
              </option>
            ))}
          </Select>
        </div>

        {live.newLeads > 0 && !autoRefresh && (
          <div className="flex justify-center border-b bg-accent-soft/40 px-4 py-2">
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-full bg-accent px-3 py-1 text-[13px] font-medium text-accent-fg shadow-popover"
              onClick={() => {
                live.clearNewLeads();
                update({ page: 1 });
                void enquiries.refetch();
              }}
            >
              <RefreshCw className="size-3.5" aria-hidden />
              {t('enquiries.newLeads', { count: live.newLeads })}
            </button>
          </div>
        )}
        {selected.size > 0 && (
          <BulkActionBar
            ids={[...selected]}
            onDone={setMessage}
            onClear={() => setSelected(new Set())}
          />
        )}
        {message && (
          <div className="px-4 pt-3 sm:px-5">
            <Alert tone="info">{message}</Alert>
          </div>
        )}
        {enquiries.isError && (
          <div className="px-4 pt-3 sm:px-5">
            <Alert tone="danger">{getErrorMessage(enquiries.error)}</Alert>
          </div>
        )}

        <DataTable
          columns={columns}
          data={enquiries.data}
          isLoading={enquiries.isPending}
          page={params.page}
          pageSize={params.page_size}
          onPageChange={(page) => update({ page }, { keepPage: true })}
          onPageSizeChange={(page_size) => update({ page_size })}
          getRowId={(e) => String(e.id)}
          onRowClick={(e) => navigate(`${paths.enquiries}/${e.id}`)}
          isRowSelected={(e) => selected.has(e.id)}
          empty={
            <EmptyState
              icon={Inbox}
              title={hasFilters ? t('enquiries.emptyFiltered.title') : t('enquiries.empty.title')}
              description={
                hasFilters
                  ? t('enquiries.emptyFiltered.description')
                  : t('enquiries.empty.description')
              }
              action={
                !hasFilters && (
                  <div className="flex flex-wrap justify-center gap-2">
                    {can('manage_integrations') && (
                      <Button variant="secondary" onClick={() => navigate(paths.apps)}>
                        <LayoutGrid className="size-4" aria-hidden />
                        {t('enquiries.empty.connectApps')}
                      </Button>
                    )}
                    {can('edit_enquiries') && (
                      <Button onClick={quickAdd.open}>
                        <Plus className="size-4" aria-hidden />
                        {t('enquiries.new')}
                      </Button>
                    )}
                  </div>
                )
              }
            />
          }
        />
      </Card>

      <FilterBuilderDialog
        open={filterOpen}
        onOpenChange={setFilterOpen}
        value={params.filter ?? null}
        onApply={(tree) => update({ filter: tree })}
      />
      <SaveViewDialog
        open={saveOpen}
        onOpenChange={setSaveOpen}
        filters={toSavableFilters(params, savedView?.filters.filter ?? null)}
        sort={params.sort}
      />
    </div>
  );
}
