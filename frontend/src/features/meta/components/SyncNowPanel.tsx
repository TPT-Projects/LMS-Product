import { RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert, Button } from '@/components/ui';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';

import { SYNC_DAYS, useSyncNow, type SyncDays } from '../api';

/** Pull recent leads of connected forms now (leads already in the LMS are skipped). */
export function SyncNowPanel() {
  const { t } = useTranslation();
  const sync = useSyncNow();
  const [days, setDays] = useState<SyncDays>(7);

  return (
    <div className="space-y-3">
      <div>
        <p className="mb-1.5 text-[13px] font-medium">{t('meta.syncNow.period')}</p>
        <div
          role="radiogroup"
          aria-label={t('meta.syncNow.period')}
          className="flex flex-wrap gap-2"
        >
          {SYNC_DAYS.map((d) => (
            <button
              key={d}
              type="button"
              role="radio"
              aria-checked={days === d}
              onClick={() => setDays(d)}
              className={cn(
                'h-8 rounded-full border px-3 text-[13px] transition-colors',
                days === d ? 'border-accent bg-accent-soft font-medium' : 'hover:bg-subtle',
              )}
            >
              {t(`meta.syncNow.days.${d}`)}
            </button>
          ))}
        </div>
      </div>
      <Button loading={sync.isPending} onClick={() => sync.mutate({ days })}>
        <RefreshCw className="size-4" aria-hidden /> {t('meta.syncNow.button')}
      </Button>
      {sync.isError && <Alert tone="danger">{getErrorMessage(sync.error)}</Alert>}
      {sync.data && sync.data.errors.length > 0 && (
        <Alert tone="danger">
          <p className="font-medium">{t('meta.syncNow.errors')}</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs">
            {sync.data.errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </Alert>
      )}
      {sync.data && (
        <Alert tone="success">
          {t('meta.syncNow.result', { checked: sync.data.checked, added: sync.data.added })}
          {sync.data.restored > 0 &&
            ` ${t('meta.syncNow.restored', { count: sync.data.restored })}`}{' '}
          {sync.data.added + sync.data.restored > 0 && (
            <Link to={paths.enquiries} className="font-medium underline">
              {t('meta.syncNow.open')}
            </Link>
          )}
        </Alert>
      )}
      <p className="text-xs text-fg-muted">{t('meta.syncNow.hint')}</p>
    </div>
  );
}
