import type { ColumnDef } from '@tanstack/react-table';
import { MoreHorizontal, Pencil, Plus, Trash2, UsersRound } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DataTable } from '@/components/data-table';
import {
  Alert,
  Avatar,
  Button,
  Card,
  CardHeader,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  EmptyState,
} from '@/components/ui';
import { useAuth, useDateFormat } from '@/features/auth/useAuth';
import { usePageParams } from '@/hooks/usePageParams';
import { getErrorMessage } from '@/lib/api/errors';

import { useDeleteTeam, useTeams, type Team } from '../api';
import { TeamDialog } from '../components/TeamDialog';

const MAX_AVATARS = 4;

export default function TeamsPage() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const format = useDateFormat();
  const canManage = can('manage_users');
  const { page, page_size, setPage, setPageSize } = usePageParams();
  const teams = useTeams({ page, page_size });
  const remove = useDeleteTeam();
  const [dialog, setDialog] = useState<{ open: boolean; team: Team | null }>({
    open: false,
    team: null,
  });

  const columns = useMemo<ColumnDef<Team, unknown>[]>(
    () => [
      {
        id: 'name',
        header: t('fields.teamName'),
        cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
      },
      {
        id: 'members',
        header: t('teams.members'),
        cell: ({ row }) => {
          const { members } = row.original;
          if (members.length === 0)
            return <span className="text-fg-subtle">{t('teams.noMembers')}</span>;
          return (
            <div className="flex items-center gap-2">
              <div className="flex -space-x-1.5">
                {members.slice(0, MAX_AVATARS).map((m) => (
                  <Avatar key={m.id} name={m.full_name} className="ring-2 ring-surface" />
                ))}
              </div>
              <span className="text-[13px] text-fg-muted">
                {t('teams.memberCount', { count: members.length })}
              </span>
            </div>
          );
        },
      },
      {
        id: 'created',
        header: t('common.created'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">{format.date(row.original.created_at)}</span>
        ),
        meta: { className: 'hidden md:table-cell' },
      },
      ...(canManage
        ? [
            {
              id: 'actions',
              header: () => <span className="sr-only">{t('common.actions')}</span>,
              meta: { className: 'w-12 text-right' },
              cell: ({ row }) => (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t('common.actionsFor', { name: row.original.name })}
                    >
                      <MoreHorizontal className="size-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onSelect={() => setDialog({ open: true, team: row.original })}
                    >
                      <Pencil className="size-4" aria-hidden /> {t('common.edit')}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="text-danger"
                      onSelect={() => {
                        if (window.confirm(t('teams.confirmDelete', { name: row.original.name }))) {
                          remove.mutate(row.original.id);
                        }
                      }}
                    >
                      <Trash2 className="size-4" aria-hidden /> {t('common.delete')}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ),
            } satisfies ColumnDef<Team, unknown>,
          ]
        : []),
    ],
    [t, format, canManage, remove],
  );

  const createButton = canManage && (
    <Button onClick={() => setDialog({ open: true, team: null })}>
      <Plus className="size-4" aria-hidden />
      {t('teams.create')}
    </Button>
  );

  return (
    <Card>
      <CardHeader
        title={t('teams.title')}
        description={t('teams.description')}
        actions={createButton}
      />
      {(teams.isError || remove.isError) && (
        <div className="px-4 pt-3 sm:px-5">
          <Alert tone="danger">{getErrorMessage(teams.error ?? remove.error)}</Alert>
        </div>
      )}
      <DataTable
        columns={columns}
        data={teams.data}
        isLoading={teams.isPending}
        page={page}
        pageSize={page_size}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        getRowId={(team) => String(team.id)}
        empty={
          <EmptyState
            icon={UsersRound}
            title={t('teams.empty.title')}
            description={t('teams.empty.description')}
            action={createButton}
          />
        }
      />
      {canManage && (
        <TeamDialog
          open={dialog.open}
          team={dialog.team}
          onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        />
      )}
    </Card>
  );
}
