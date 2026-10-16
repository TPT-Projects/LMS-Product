import { Mail, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Button, Card, CardHeader } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';

import { usePendingInvitations, useRevokeInvitation } from '../api';
import { RoleBadge } from './RoleBadge';

/** Shown only to users who can manage users, and only when invites are pending. */
export function PendingInvitations() {
  const { t } = useTranslation();
  const format = useDateFormat();
  const invitations = usePendingInvitations(true);
  const revoke = useRevokeInvitation();
  const rows = invitations.data?.results ?? [];

  if (rows.length === 0) return null;

  return (
    <Card>
      <CardHeader title={t('users.pending.title')} description={t('users.pending.description')} />
      <ul className="divide-y">
        {rows.map((invite) => (
          <li key={invite.id} className="flex items-center gap-3 px-4 py-2.5 sm:px-5">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-subtle text-fg-muted">
              <Mail className="size-3.5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{invite.email}</p>
              <p className="text-xs text-fg-muted">
                {t('users.pending.expires', { date: format.date(invite.expires_at) })}
              </p>
            </div>
            <RoleBadge role={invite.role} />
            <Button
              variant="ghost"
              size="icon"
              aria-label={t('users.pending.revoke', { email: invite.email })}
              title={t('users.pending.revokeShort')}
              loading={revoke.isPending && revoke.variables === invite.id}
              onClick={() => revoke.mutate(invite.id)}
            >
              <X className="size-4" />
            </Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
