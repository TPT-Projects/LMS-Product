import type { ColumnDef } from '@tanstack/react-table';
import { Search, UserPlus, Users } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ColumnsButton, DataTable, type ColumnOption } from '@/components/data-table';
import {
  Alert,
  Avatar,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Input,
  Select,
} from '@/components/ui';
import { useAuth, useDateFormat, useSession } from '@/features/auth/useAuth';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { usePageParams } from '@/hooks/usePageParams';
import { useTableColumns } from '@/hooks/useTableColumns';
import { getErrorMessage } from '@/lib/api/errors';
import { ROLES, type Role } from '@/types/auth';

import { useChangeRole, useMembers, type Member } from '../api';
import { InviteUserDialog } from '../components/InviteUserDialog';
import { PendingInvitations } from '../components/PendingInvitations';
import { RoleBadge } from '../components/RoleBadge';
import { RoleMenu } from '../components/RoleMenu';
import { assignableRoles, canChangeRoleOf } from '../roles';

export default function UsersPage() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const session = useSession();
  const format = useDateFormat();
  const canManage = can('manage_users');
  const { page, page_size, setPage, setPageSize } = usePageParams();

  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<Role | ''>('');
  const [inviteOpen, setInviteOpen] = useState(false);
  const q = useDebouncedValue(search.trim(), 300);

  const members = useMembers({ page, page_size, q, role: roleFilter });
  const changeRole = useChangeRole();

  const allColumns = useMemo<ColumnDef<Member, unknown>[]>(
    () => [
      {
        id: 'name',
        header: t('fields.name'),
        cell: ({ row }) => (
          <div className="flex min-w-0 items-center gap-2.5">
            <Avatar name={row.original.full_name} />
            <div className="min-w-0">
              <p className="truncate font-medium">
                {row.original.full_name}
                {row.original.id === session.user.id && (
                  <span className="ml-1.5 text-xs font-normal text-fg-subtle">
                    {t('users.you')}
                  </span>
                )}
              </p>
              <p className="truncate text-xs text-fg-muted">{row.original.email}</p>
            </div>
          </div>
        ),
      },
      {
        id: 'role',
        header: t('fields.role'),
        cell: ({ row }) => {
          const member = row.original;
          const editable =
            canManage && canChangeRoleOf(session.role, member.role, member.id === session.user.id);
          return editable ? (
            <RoleMenu
              role={member.role}
              options={assignableRoles(session.role)}
              disabled={changeRole.isPending}
              onChange={(role) => changeRole.mutate({ userId: member.id, role })}
            />
          ) : (
            <RoleBadge role={member.role} />
          );
        },
      },
      {
        id: 'joined',
        header: t('users.joined'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">{format.date(row.original.joined_at)}</span>
        ),
      },
      {
        id: 'lastLogin',
        header: t('users.lastLogin'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">
            {format.dateTime(row.original.last_login)}
          </span>
        ),
      },
    ],
    [t, session, canManage, changeRole, format],
  );

  const options = useMemo<ColumnOption[]>(
    () => [
      { id: 'name', label: t('fields.name'), fixed: 'start' },
      { id: 'role', label: t('fields.role'), fixed: 'start' },
      { id: 'joined', label: t('users.joined'), defaultVisible: true },
      { id: 'lastLogin', label: t('users.lastLogin'), defaultVisible: true },
    ],
    [t],
  );
  const layout = useTableColumns('users', options);
  const columns = useMemo(
    () =>
      layout.visible
        .map((id) => allColumns.find((c) => c.id === id))
        .filter((c): c is ColumnDef<Member, unknown> => Boolean(c)),
    [allColumns, layout.visible],
  );

  return (
    <div className="space-y-5">
      {canManage && <PendingInvitations />}

      <Card>
        <CardHeader
          title={t('users.title')}
          description={t('users.description')}
          actions={
            canManage && (
              <Button onClick={() => setInviteOpen(true)}>
                <UserPlus className="size-4" aria-hidden />
                {t('users.inviteButton')}
              </Button>
            )
          }
        />

        <div className="flex flex-col gap-2 border-b px-4 py-3 sm:flex-row sm:px-5">
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
              placeholder={t('users.searchPlaceholder')}
              aria-label={t('users.searchPlaceholder')}
              className="pl-9"
            />
          </div>
          <Select
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value as Role | '');
              setPage(1);
            }}
            aria-label={t('users.filterRole')}
            className="sm:w-44"
          >
            <option value="">{t('users.allRoles')}</option>
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {t(`roles.${role}`)}
              </option>
            ))}
          </Select>
          <div className="sm:ml-auto">
            <ColumnsButton
              options={options}
              visible={layout.visible}
              onSave={(c) => layout.save.mutate(c)}
            />
          </div>
        </div>

        {changeRole.isError && (
          <div className="px-4 pt-3 sm:px-5">
            <Alert tone="danger">{getErrorMessage(changeRole.error)}</Alert>
          </div>
        )}
        {members.isError && (
          <div className="px-4 pt-3 sm:px-5">
            <Alert tone="danger">{getErrorMessage(members.error)}</Alert>
          </div>
        )}

        <DataTable
          columns={columns}
          data={members.data}
          isLoading={members.isPending}
          page={page}
          pageSize={page_size}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
          getRowId={(m) => String(m.id)}
          empty={
            <EmptyState
              icon={Users}
              title={t('users.empty.title')}
              description={t('users.empty.description')}
            />
          }
        />
      </Card>

      {canManage && <InviteUserDialog open={inviteOpen} onOpenChange={setInviteOpen} />}
    </div>
  );
}
