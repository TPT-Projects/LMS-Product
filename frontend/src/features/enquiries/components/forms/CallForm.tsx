import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Button, FormField, Input, Select, Textarea } from '@/components/ui';
import { getErrorMessage } from '@/lib/api/errors';
import { CALL_OUTCOMES, type CallOutcome } from '@/types/crm';

import { useLogCall } from '../../api';

/** Log a call: outcome, duration and notes. */
export function CallForm({ enquiryId, onDone }: { enquiryId: number; onDone?: () => void }) {
  const { t } = useTranslation();
  const log = useLogCall(enquiryId);
  const [outcome, setOutcome] = useState<CallOutcome>('connected');
  const [minutes, setMinutes] = useState('');
  const [seconds, setSeconds] = useState('');
  const [notes, setNotes] = useState('');

  const submit = async () => {
    const duration = (Number(minutes) || 0) * 60 + (Number(seconds) || 0);
    await log.mutateAsync({ outcome, duration_seconds: duration, notes: notes.trim() });
    setMinutes('');
    setSeconds('');
    setNotes('');
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
      <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
        <FormField label={t('calls.outcome')}>
          <Select value={outcome} onChange={(e) => setOutcome(e.target.value as CallOutcome)}>
            {CALL_OUTCOMES.map((o) => (
              <option key={o} value={o}>
                {t(`calls.outcomes.${o}`)}
              </option>
            ))}
          </Select>
        </FormField>
        <fieldset>
          <legend className="mb-1.5 text-[13px] font-medium">{t('calls.duration')}</legend>
          <div className="flex items-center gap-1.5">
            <Input
              aria-label={t('calls.minutes')}
              inputMode="numeric"
              className="w-16"
              placeholder="0"
              value={minutes}
              onChange={(e) => setMinutes(e.target.value.replace(/\D/g, '').slice(0, 3))}
            />
            <span className="text-xs text-fg-muted">{t('calls.min')}</span>
            <Input
              aria-label={t('calls.seconds')}
              inputMode="numeric"
              className="w-16"
              placeholder="0"
              value={seconds}
              onChange={(e) => setSeconds(e.target.value.replace(/\D/g, '').slice(0, 2))}
            />
            <span className="text-xs text-fg-muted">{t('calls.sec')}</span>
          </div>
        </fieldset>
      </div>
      <Textarea
        rows={2}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder={t('calls.notesPlaceholder')}
        aria-label={t('calls.notes')}
      />
      {log.isError && <Alert tone="danger">{getErrorMessage(log.error)}</Alert>}
      <div className="flex justify-end">
        <Button type="submit" size="sm" loading={log.isPending}>
          {t('calls.log')}
        </Button>
      </div>
    </form>
  );
}
