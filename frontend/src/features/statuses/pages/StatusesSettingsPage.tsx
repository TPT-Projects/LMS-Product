import { ArrowDown, ArrowUp, Pencil, Plus } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Badge, Button, Card, CardHeader, Skeleton } from '@/components/ui';
import { useAuth } from '@/features/auth/useAuth';
import { getErrorMessage } from '@/lib/api/errors';
import type { Status } from '@/types/crm';

import { useReorderStatuses, useStatuses } from '../api';
import { StatusBadge } from '../components/StatusBadge';
import { StatusDialog } from '../components/StatusDialog';

export default function StatusesSettingsPage() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const canEdit = can('manage_settings');
  const statuses = useStatuses();
  const reorder = useReorderStatuses();
  const [dialog, setDialog] = useState<{ open: boolean; status: Status | null }>({
    open: false,
    status: null,
  });
  const rows = statuses.data ?? [];

  const move = (index: number, delta: number) => {
    const ids = rows.map((s) => s.id);
    const target = index + delta;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target]!, ids[index]!];
    reorder.mutate(ids);
  };

  return (
    <Card>
      <CardHeader
        title={t('statuses.title')}
        description={t('statuses.description')}
        actions={
          canEdit && (
            <Button onClick={() => setDialog({ open: true, status: null })}>
              <Plus className="size-4" aria-hidden />
              {t('statuses.add')}
            </Button>
          )
        }
      />
      {(statuses.isError || reorder.isError) && (
        <div className="px-4 pt-3 sm:px-5">
          <Alert tone="danger">{getErrorMessage(statuses.error ?? reorder.error)}</Alert>
        </div>
      )}
      <ul className="divide-y">
        {statuses.isPending &&
          Array.from({ length: 5 }, (_, i) => (
            <li key={i} className="px-4 py-3 sm:px-5">
              <Skeleton className="h-5 w-40" />
            </li>
          ))}
        {rows.map((status, index) => (
          <li key={status.id} className="flex items-center gap-3 px-4 py-2.5 sm:px-5">
            <StatusBadge name={status.name} color={status.color} />
            <div className="flex min-w-0 flex-1 flex-wrap gap-1.5">
              {status.is_default && <Badge tone="accent">{t('statuses.default')}</Badge>}
              {status.is_won && <Badge tone="success">{t('statuses.won')}</Badge>}
              {status.is_closed && !status.is_won && <Badge>{t('statuses.closed')}</Badge>}
            </div>
            {canEdit && (
              <div className="flex items-center gap-0.5">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t('statuses.moveUp', { name: status.name })}
                  disabled={index === 0 || reorder.isPending}
                  onClick={() => move(index, -1)}
                >
                  <ArrowUp className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t('statuses.moveDown', { name: status.name })}
                  disabled={index === rows.length - 1 || reorder.isPending}
                  onClick={() => move(index, 1)}
                >
                  <ArrowDown className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t('common.editName', { name: status.name })}
                  onClick={() => setDialog({ open: true, status })}
                >
                  <Pencil className="size-4" />
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {canEdit && (
        <StatusDialog
          open={dialog.open}
          status={dialog.status}
          onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        />
      )}
    </Card>
  );
}
