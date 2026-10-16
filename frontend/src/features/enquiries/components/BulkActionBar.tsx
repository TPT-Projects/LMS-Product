import { Trash2, UserPlus, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui';
import { useAuth } from '@/features/auth/useAuth';
import { useStatuses } from '@/features/statuses/api';
import { StatusBadge } from '@/features/statuses/components/StatusBadge';
import { useAllMembers } from '@/features/users/api';

import { useBulkAction, type BulkAction } from '../api';

interface Props {
  ids: number[];
  onDone: (message: string) => void;
  onClear: () => void;
}

export function BulkActionBar({ ids, onDone, onClear }: Props) {
  const { t } = useTranslation();
  const { can } = useAuth();
  const statuses = useStatuses();
  const members = useAllMembers();
  const bulk = useBulkAction();

  const run = async (action: BulkAction, value?: number | null) => {
    try {
      const result = await bulk.mutateAsync({ ids, action, value });
      onDone(t('enquiries.bulk.done', { count: result.updated }));
      onClear();
    } catch {
      onDone(t('enquiries.bulk.failed'));
    }
  };

  return (
    <div
      role="region"
      aria-label={t('enquiries.bulk.label')}
      className="flex flex-wrap items-center gap-2 border-b bg-accent-soft/50 px-4 py-2 sm:px-5"
    >
      <span className="text-[13px] font-medium">
        {t('enquiries.bulk.selected', { count: ids.length })}
      </span>
      {can('edit_enquiries') && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="secondary" size="sm" loading={bulk.isPending}>
              {t('enquiries.bulk.setStatus')}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {statuses.data?.map((s) => (
              <DropdownMenuItem key={s.id} onSelect={() => void run('set_status', s.id)}>
                <StatusBadge name={s.name} color={s.color} />
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
      {can('reassign_owners') && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="secondary" size="sm">
              <UserPlus className="size-3.5" aria-hidden /> {t('enquiries.bulk.assign')}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="max-h-80 overflow-y-auto">
            <DropdownMenuLabel>{t('enquiries.bulk.primaryOwner')}</DropdownMenuLabel>
            <DropdownMenuItem onSelect={() => void run('assign', null)}>
              {t('enquiries.unassigned')}
            </DropdownMenuItem>
            {members.data?.results.map((m) => (
              <DropdownMenuItem key={m.id} onSelect={() => void run('assign', m.id)}>
                {m.full_name}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
      {can('delete_enquiries') && (
        <Button
          variant="ghost"
          size="sm"
          className="text-danger"
          onClick={() => {
            if (window.confirm(t('enquiries.bulk.confirmDelete', { count: ids.length }))) {
              void run('delete');
            }
          }}
        >
          <Trash2 className="size-3.5" aria-hidden /> {t('common.delete')}
        </Button>
      )}
      <Button variant="ghost" size="sm" className="ml-auto" onClick={onClear}>
        <X className="size-3.5" aria-hidden /> {t('enquiries.bulk.clear')}
      </Button>
    </div>
  );
}
