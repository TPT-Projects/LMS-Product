import type { ColumnDef } from '@tanstack/react-table';
import { Contact as ContactIcon, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { ColumnsButton, DataTable, type ColumnOption } from '@/components/data-table';
import { PageHeader } from '@/components/layout/PageHeader';
import { Alert, Avatar, Badge, Card, EmptyState, Input } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { StatusBadge } from '@/features/statuses/components/StatusBadge';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { useTableColumns } from '@/hooks/useTableColumns';
import { usePageParams } from '@/hooks/usePageParams';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';
import type { Contact } from '@/types/crm';

import { useContacts } from '../api';
import { ContactActions } from '../components/ContactActions';

export default function ContactsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useDateFormat();
  const { page, page_size, setPage, setPageSize } = usePageParams();
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const contacts = useContacts({ page, page_size, q });

  const options = useMemo<ColumnOption[]>(
    () => [
      { id: 'name', label: t('fields.name'), fixed: 'start' },
      { id: 'action', label: t('columns.actions'), fixed: 'start' },
      { id: 'status', label: t('fields.status'), fixed: 'start' },
      { id: 'phone', label: t('fields.phone'), defaultVisible: true },
      { id: 'email', label: t('fields.email'), defaultVisible: true },
      { id: 'enquiries', label: t('contacts.enquiries'), defaultVisible: true },
      { id: 'created', label: t('contacts.firstSeen'), defaultVisible: true },
      { id: 'updated', label: t('columns.updated') },
    ],
    [t],
  );
  const layout = useTableColumns('contacts', options);

  const columns = useMemo<ColumnDef<Contact, unknown>[]>(() => {
    const byId: Record<string, ColumnDef<Contact, unknown>> = {
      name: {
        id: 'name',
        header: t('fields.name'),
        cell: ({ row }) => (
          <Link
            to={`${paths.contacts}/${row.original.id}`}
            onClick={(e) => e.stopPropagation()}
            className="flex min-w-0 items-center gap-2.5 font-medium hover:underline"
          >
            <Avatar name={row.original.name || '?'} />
            <span className="truncate">{row.original.name || t('enquiries.noName')}</span>
          </Link>
        ),
      },
      status: {
        id: 'status',
        header: t('fields.status'),
        cell: ({ row }) =>
          row.original.status ? (
            <StatusBadge name={row.original.status.name} color={row.original.status.color} />
          ) : (
            <span className="text-fg-subtle">—</span>
          ),
      },
      phone: {
        id: 'phone',
        header: t('fields.phone'),
        cell: ({ row }) => <span className="tabular-nums">{row.original.phone_e164 ?? '—'}</span>,
      },
      email: {
        id: 'email',
        header: t('fields.email'),
        cell: ({ row }) => <span className="text-fg-muted">{row.original.email ?? '—'}</span>,
      },
      enquiries: {
        id: 'enquiries',
        header: t('contacts.enquiries'),
        cell: ({ row }) => (
          <Badge tone={row.original.enquiry_count > 1 ? 'accent' : 'neutral'}>
            {row.original.enquiry_count}
          </Badge>
        ),
      },
      created: {
        id: 'created',
        header: t('contacts.firstSeen'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">{format.date(row.original.created_at)}</span>
        ),
      },
      updated: {
        id: 'updated',
        header: t('columns.updated'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">
            {format.dateTime(row.original.updated_at)}
          </span>
        ),
      },
      action: {
        id: 'action',
        header: () => <span className="sr-only">{t('columns.actions')}</span>,
        meta: { className: 'w-12 text-right' },
        cell: ({ row }) => <ContactActions contact={row.original} />,
      },
    };
    return layout.visible
      .map((id) => byId[id])
      .filter((c): c is ColumnDef<Contact, unknown> => Boolean(c));
  }, [t, format, layout.visible]);

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title={t('nav.contacts')} description={t('contacts.description')} />
      <Card>
        <div className="flex items-center gap-2 border-b px-4 py-3 sm:px-5">
          <div className="relative flex-1 sm:max-w-xs">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle"
              aria-hidden
            />
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder={t('contacts.search')}
              aria-label={t('contacts.search')}
              className="h-8 pl-9"
            />
          </div>
          <div className="ml-auto">
            <ColumnsButton
              options={options}
              visible={layout.visible}
              onSave={(c) => layout.save.mutate(c)}
            />
          </div>
        </div>
        {contacts.isError && (
          <div className="px-4 pt-3 sm:px-5">
            <Alert tone="danger">{getErrorMessage(contacts.error)}</Alert>
          </div>
        )}
        <DataTable
          columns={columns}
          data={contacts.data}
          isLoading={contacts.isPending}
          page={page}
          pageSize={page_size}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
          getRowId={(c) => String(c.id)}
          onRowClick={(c) => navigate(`${paths.contacts}/${c.id}`)}
          empty={
            <EmptyState
              icon={ContactIcon}
              title={t('contacts.empty.title')}
              description={t('contacts.empty.description')}
            />
          }
        />
      </Card>
    </div>
  );
}
