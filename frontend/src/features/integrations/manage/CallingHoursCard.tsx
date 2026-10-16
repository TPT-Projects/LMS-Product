import { Clock } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Button, Card, CardBody, CardHeader, Input, Switch } from '@/components/ui';
import { useSession } from '@/features/auth/useAuth';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';

import { useExotelSettings, type CallWindow } from '../api';

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;

/** Exotel calls only on these days, between these times (workspace time zone), for every form
 * and every scheduled call. */
export function CallingHoursCard({ window: saved }: { window: CallWindow }) {
  const { t } = useTranslation();
  const tz = useSession().workspace.timezone;
  const settings = useExotelSettings();
  const [hours, setHours] = useState<CallWindow>(saved);
  const changed = JSON.stringify(hours) !== JSON.stringify(saved);

  const toggleDay = (day: number) =>
    setHours((h) => ({
      ...h,
      days: h.days.includes(day) ? h.days.filter((d) => d !== day) : [...h.days, day].sort(),
    }));

  return (
    <Card>
      <CardHeader
        title={t('exotel.hours.title')}
        description={t('exotel.hours.description', { tz })}
      />
      <CardBody className="space-y-4">
        <div className="flex items-start gap-3">
          <Clock className="mt-0.5 size-4 shrink-0 text-fg-muted" aria-hidden />
          <div className="min-w-0 flex-1">
            <p id="calling-hours-on" className="font-medium">
              {t('exotel.hours.enabled')}
            </p>
            <p className="text-xs text-fg-muted">
              {hours.enabled ? t('exotel.hours.onHint') : t('exotel.hours.offHint')}
            </p>
          </div>
          <Switch
            checked={hours.enabled}
            aria-labelledby="calling-hours-on"
            onCheckedChange={(enabled) => setHours((h) => ({ ...h, enabled }))}
          />
        </div>

        <fieldset disabled={!hours.enabled} className="space-y-4 disabled:opacity-50">
          <div>
            <legend className="mb-2 text-[13px] font-medium">{t('exotel.hours.days')}</legend>
            <div className="flex flex-wrap gap-2">
              {DAY_KEYS.map((key, day) => (
                <button
                  key={key}
                  type="button"
                  aria-pressed={hours.days.includes(day)}
                  onClick={() => toggleDay(day)}
                  className={cn(
                    'h-8 min-w-12 rounded-full border px-3 text-[13px] transition-colors',
                    hours.days.includes(day)
                      ? 'border-accent bg-accent-soft font-medium'
                      : 'hover:bg-subtle',
                  )}
                >
                  {t(`weekdays.${key}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="grid max-w-sm grid-cols-2 gap-3">
            <label className="space-y-1.5 text-[13px] font-medium">
              <span>{t('exotel.hours.start')}</span>
              <Input
                type="time"
                value={hours.start}
                onChange={(e) => setHours((h) => ({ ...h, start: e.target.value }))}
              />
            </label>
            <label className="space-y-1.5 text-[13px] font-medium">
              <span>{t('exotel.hours.end')}</span>
              <Input
                type="time"
                value={hours.end}
                onChange={(e) => setHours((h) => ({ ...h, end: e.target.value }))}
              />
            </label>
          </div>
        </fieldset>

        <p className="text-xs text-fg-muted">{t('exotel.hours.appliesTo')}</p>
        {settings.isError && <Alert tone="danger">{getErrorMessage(settings.error)}</Alert>}
        <Button
          size="sm"
          disabled={!changed}
          loading={settings.isPending}
          onClick={() => settings.mutate({ call_window: hours })}
        >
          {t('exotel.hours.save')}
        </Button>
      </CardBody>
    </Card>
  );
}
