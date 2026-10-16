import { CalendarClock, PhoneCall } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Checkbox, EmptyState, Skeleton, Switch, Button, Dialog } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { useNow } from '@/hooks/useNow';
import { cn } from '@/lib/cn';

import { useCalling, useFollowUpAutoCall, useFollowUps, useToggleFollowUp } from '../api';
import { FollowUpForm } from './forms/FollowUpForm';
import { RescheduleForm } from './forms/RescheduleForm';

/** The lead did not answer the auto-call: show "Call not connected" and Reschedule. */
const NOT_CONNECTED = new Set(['no_answer', 'busy', 'failed']);

export function FollowUpsPanel({
  enquiryId,
  canEdit,
  ownerId,
}: {
  enquiryId: number;
  canEdit: boolean;
  /** The lead's owner: new calls are assigned to them by default. */
  ownerId?: number | null;
}) {
  const { t } = useTranslation();
  const format = useDateFormat();
  const followups = useFollowUps(enquiryId);
  const toggle = useToggleFollowUp(enquiryId);
  const autoCall = useFollowUpAutoCall(enquiryId);
  const calling = useCalling();
  const autoCallAvailable = Boolean(calling.data?.auto_call_followups);
  const [rescheduling, setRescheduling] = useState<number | null>(null);
  const now = useNow();

  return (
    <div className="space-y-4">
      {canEdit && (
        <div className="rounded-lg border bg-subtle p-3">
          <FollowUpForm enquiryId={enquiryId} defaultAssigneeId={ownerId} />
        </div>
      )}
      {followups.isPending ? (
        <Skeleton className="h-14 w-full" />
      ) : !followups.data?.length ? (
        <EmptyState icon={CalendarClock} title={t('followups.empty')} className="py-8" />
      ) : (
        <ul className="divide-y rounded-lg border">
          {followups.data.map((f) => {
            const overdue = !f.is_done && new Date(f.due_at).getTime() < now;
            return (
              <li key={f.id} className="flex items-start gap-3 p-3">
                <Checkbox
                  className="mt-0.5"
                  checked={f.is_done}
                  disabled={!canEdit || toggle.isPending}
                  aria-label={t('followups.markDone', { title: f.title })}
                  onChange={() => toggle.mutate({ followupId: f.id, done: !f.is_done })}
                />
                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      'text-[13px] font-medium',
                      f.is_done && 'text-fg-muted line-through',
                    )}
                  >
                    {f.title}
                  </p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-fg-muted">
                    <span className={cn('tabular-nums', overdue && 'font-medium text-danger')}>
                      {format.dateTime(f.due_at)}
                    </span>
                    {f.assignee && <span>· {f.assignee.full_name}</span>}
                    {overdue && <Badge tone="danger">{t('followups.overdue')}</Badge>}
                    {!f.is_done && NOT_CONNECTED.has(f.auto_call_status ?? '') && (
                      <Badge tone="danger">{t('followups.autoCall.notConnected')}</Badge>
                    )}
                    {f.auto_call_status &&
                      f.auto_call_status !== 'pending' &&
                      !(!f.is_done && NOT_CONNECTED.has(f.auto_call_status)) && (
                        <Badge
                          tone={
                            f.auto_call_status === 'started' || f.auto_call_status === 'completed'
                              ? 'success'
                              : 'neutral'
                          }
                        >
                          {t(`followups.autoCall.status.${f.auto_call_status}`, {
                            defaultValue: f.auto_call_status,
                          })}
                        </Badge>
                      )}
                  </p>
                </div>
                {!f.is_done && canEdit && NOT_CONNECTED.has(f.auto_call_status ?? '') && (
                  <Button variant="secondary" size="sm" onClick={() => setRescheduling(f.id)}>
                    <CalendarClock className="size-3.5" aria-hidden /> {t('followups.reschedule')}
                  </Button>
                )}
                {autoCallAvailable && !f.is_done && canEdit && (
                  <label className="flex shrink-0 items-center gap-2 text-xs text-fg-muted">
                    <PhoneCall className="size-3.5" aria-hidden />
                    {t('followups.autoCall.short')}
                    <Switch
                      checked={f.auto_call_status === 'pending'}
                      disabled={autoCall.isPending && autoCall.variables?.followupId === f.id}
                      aria-label={t('followups.autoCall.toggle', { title: f.title })}
                      onCheckedChange={(on) => autoCall.mutate({ followupId: f.id, autoCall: on })}
                    />
                  </label>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <Dialog
        open={rescheduling !== null}
        onOpenChange={(open) => !open && setRescheduling(null)}
        title={t('followups.rescheduleTitle')}
      >
        {rescheduling !== null && (
          <RescheduleForm
            enquiryId={enquiryId}
            followupId={rescheduling}
            onDone={() => setRescheduling(null)}
          />
        )}
      </Dialog>
    </div>
  );
}
