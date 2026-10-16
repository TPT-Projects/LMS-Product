import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Button, DateInput, FormField, Input } from '@/components/ui';
import { useSession } from '@/features/auth/useAuth';
import { getErrorMessage } from '@/lib/api/errors';
import { todayDisplay, zonedToUtcIso } from '@/lib/dates';

import { useRescheduleFollowUp } from '../../api';

/** New date and time for a scheduled call (e.g. after "Call not connected"). */
export function RescheduleForm({
  enquiryId,
  followupId,
  onDone,
}: {
  enquiryId: number;
  followupId: number;
  onDone?: () => void;
}) {
  const { t } = useTranslation();
  const tz = useSession().workspace.timezone;
  const reschedule = useRescheduleFollowUp(enquiryId);
  const [date, setDate] = useState(() => todayDisplay(tz));
  const [time, setTime] = useState('11:00');
  const [formError, setFormError] = useState<string | null>(null);

  const submit = () => {
    setFormError(null);
    const due = zonedToUtcIso(date, time, tz);
    if (!due) return setFormError(t('followups.badDate'));
    reschedule.mutate({ followupId, dueAt: due }, { onSuccess: () => onDone?.() });
  };

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <FormField label={t('followups.date')}>
          <DateInput value={date} onChange={(e) => setDate(e.target.value)} />
        </FormField>
        <FormField label={t('followups.time')}>
          <Input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
        </FormField>
      </div>
      {(formError || reschedule.isError) && (
        <Alert tone="danger">{formError ?? getErrorMessage(reschedule.error)}</Alert>
      )}
      <div className="flex justify-end">
        <Button type="submit" size="sm" loading={reschedule.isPending}>
          {t('followups.reschedule')}
        </Button>
      </div>
    </form>
  );
}
