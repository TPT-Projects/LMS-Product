import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PhoneCall } from 'lucide-react';

import { Alert, Button, DateInput, FormField, Input, Switch } from '@/components/ui';
import { useSession } from '@/features/auth/useAuth';
import { getErrorMessage } from '@/lib/api/errors';
import { todayDisplay, zonedToUtcIso } from '@/lib/dates';

import { useAddFollowUp, useCalling } from '../../api';
import { describeWindow, insideWindow } from '../../callHours';
import { OwnerSelect } from '../OwnerSelect';

interface Props {
  enquiryId: number;
  onDone?: () => void;
  /** Pre-filled title, e.g. "Call back" from the Schedule call action. */
  defaultTitle?: string;
  /** The lead's owner: the call is assigned to them unless someone picks another person. */
  defaultAssigneeId?: number | null;
  autoFocus?: boolean;
}

/** Schedule a follow-up. Date is DD/MM/YYYY in the workspace timezone. */
export function FollowUpForm({
  enquiryId,
  onDone,
  defaultTitle = '',
  defaultAssigneeId,
  autoFocus,
}: Props) {
  const { t } = useTranslation();
  const session = useSession();
  const tz = session.workspace.timezone;
  const add = useAddFollowUp(enquiryId);
  const [title, setTitle] = useState(defaultTitle);
  const [date, setDate] = useState(() => todayDisplay(tz));
  const [time, setTime] = useState('10:00');
  const [assignee, setAssignee] = useState(String(defaultAssigneeId ?? session.user.id));
  const [formError, setFormError] = useState<string | null>(null);
  const calling = useCalling();
  const autoCallAvailable = Boolean(calling.data?.auto_call_followups);
  const callWindow = calling.data?.call_window;
  const [autoCall, setAutoCall] = useState(true);

  const submit = async () => {
    setFormError(null);
    const due = zonedToUtcIso(date, time, tz);
    if (!title.trim()) return setFormError(t('validation.required'));
    if (!due) return setFormError(t('followups.badDate'));
    if (
      autoCallAvailable &&
      autoCall &&
      callWindow?.enabled &&
      !insideWindow(due, callWindow, tz)
    ) {
      return setFormError(
        t('followups.autoCall.outsideHours', { hours: describeWindow(callWindow, t) }),
      );
    }
    await add.mutateAsync({
      title: title.trim(),
      due_at: due,
      assignee_id: Number(assignee),
      auto_call: autoCallAvailable ? autoCall : undefined,
    });
    setTitle(defaultTitle);
    onDone?.();
  };

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <FormField label={t('followups.title')}>
        <Input
          value={title}
          maxLength={200}
          autoFocus={autoFocus}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t('followups.titlePlaceholder')}
        />
      </FormField>
      <div className="grid gap-3 sm:grid-cols-3">
        <FormField label={t('followups.date')}>
          <DateInput value={date} onChange={(e) => setDate(e.target.value)} />
        </FormField>
        <FormField label={t('followups.time')}>
          <Input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
        </FormField>
        <FormField label={t('followups.assignee')}>
          <OwnerSelect
            allowUnassigned={false}
            value={assignee}
            onChange={(e) => setAssignee(e.target.value)}
          />
        </FormField>
      </div>
      {autoCallAvailable && (
        <div className="flex items-start gap-3 rounded-lg border bg-accent-soft/40 p-3">
          <PhoneCall className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
          <div className="min-w-0 flex-1">
            <p id="followup-auto-call" className="text-[13px] font-medium">
              {t('followups.autoCall.label')}
            </p>
            <p className="text-xs text-fg-muted">
              {autoCall ? t('followups.autoCall.on') : t('followups.autoCall.off')}
            </p>
            {callWindow?.enabled && (
              <p className="mt-1 text-xs text-fg-muted">
                {t('followups.autoCall.hours', { hours: describeWindow(callWindow, t) })}
              </p>
            )}
          </div>
          <Switch
            checked={autoCall}
            aria-labelledby="followup-auto-call"
            onCheckedChange={setAutoCall}
          />
        </div>
      )}
      {(formError || add.isError) && (
        <Alert tone="danger">{formError ?? getErrorMessage(add.error)}</Alert>
      )}
      <div className="flex justify-end">
        <Button type="submit" size="sm" loading={add.isPending}>
          {t('followups.schedule')}
        </Button>
      </div>
    </form>
  );
}
