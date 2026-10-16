import type { ColumnDef } from '@tanstack/react-table';
import { Pencil, Search, Users } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DataTable } from '@/components/data-table';
import { PageHeader } from '@/components/layout/PageHeader';
import { Alert, Avatar, Button, Card, EmptyState, Input } from '@/components/ui';
import { useAuth, useSession } from '@/features/auth/useAuth';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { usePageParams } from '@/hooks/usePageParams';
import { getErrorMessage } from '@/lib/api/errors';

import { useMembers, type Member } from '../api';
import { EditProfileDialog } from '../components/EditProfileDialog';
import { RoleBadge } from '../components/RoleBadge';

const dash = <span className="text-fg-subtle">—</span>;

/** Users (sidebar): everyone's contact details. Owners/Admins edit anyone; others themselves. */
export default function PeoplePage() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const session = useSession();
  const { page, page_size, setPage, setPageSize } = usePageParams();
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const members = useMembers({ page, page_size, q, role: '' });
  const [editing, setEditing] = useState<Member | null>(null);

  const columns = useMemo<ColumnDef<Member, unknown>[]>(
    () => [
      {
        id: 'name',
        header: t('people.username'),
        cell: ({ row }) => (
          <div className="flex min-w-0 items-center gap-2.5">
            <Avatar name={row.original.full_name} />
            <span className="truncate font-medium">
              {row.original.full_name}
              {row.original.id === session.user.id && (
                <span className="ml-1.5 text-xs font-normal text-fg-subtle">{t('users.you')}</span>
              )}
            </span>
          </div>
        ),
      },
      {
        id: 'phone',
        header: t('people.phone'),
        cell: ({ row }) =>
          row.original.phone ? (
            <a href={`tel:${row.original.phone}`} className="tabular-nums hover:underline">
              {row.original.phone}
            </a>
          ) : (
            dash
          ),
      },
      {
        id: 'email',
        header: t('people.email'),
        cell: ({ row }) => (
          <a href={`mailto:${row.original.email}`} className="text-fg-muted hover:underline">
            {row.original.email}
          </a>
        ),
      },
      {
        id: 'alternate_phone',
        header: t('people.alternatePhone'),
        cell: ({ row }) =>
          row.original.alternate_phone ? (
            <span className="tabular-nums">{row.original.alternate_phone}</span>
          ) : (
            dash
          ),
      },
      {
        id: 'role',
        header: t('people.role'),
        cell: ({ row }) => <RoleBadge role={row.original.role} />,
      },
      {
        id: 'actions',
        header: () => <span className="sr-only">{t('common.actions')}</span>,
        meta: { className: 'text-right' },
        cell: ({ row }) =>
          (can('manage_users') || row.original.id === session.user.id) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                setEditing(row.original);
              }}
              aria-label={t('people.editTitle', { name: row.original.full_name })}
            >
              <Pencil className="size-3.5" aria-hidden /> {t('common.edit')}
            </Button>
          ),
      },
    ],
    [t, can, session.user.id],
  );

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title={t('people.title')} description={t('people.description')} />
      {members.isError && (
        <Alert tone="danger" className="mb-4">
          {getErrorMessage(members.error)}
        </Alert>
      )}
      <Card>
        <div className="border-b p-3 sm:p-4">
          <label className="relative block sm:max-w-sm">
            <span className="sr-only">{t('people.search')}</span>
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-muted"
              aria-hidden
            />
            <Input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder={t('people.search')}
              className="pl-9"
            />
          </label>
        </div>
        <DataTable
          columns={columns}
          data={members.data}
          isLoading={members.isPending}
          page={page}
          pageSize={page_size}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
          getRowId={(m) => String(m.id)}
          empty={<EmptyState icon={Users} title={t('people.empty')} />}
        />
      </Card>
      {editing && <EditProfileDialog member={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
