import { CheckCircle2, Rocket } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { paths } from '@/routes/paths';

import type { AppStatus } from '../api';
import { APPS } from '../catalog';
import { AppConnectButton } from './AppConnectButton';
import { AppLogo } from './AppLogo';

const RECOMMENDED = APPS.filter((app) => app.recommended);

/** HubSpot-style onboarding: the three apps that get leads, messages and calls flowing. */
export function GetStartedChecklist({ statuses }: { statuses: Record<string, AppStatus> }) {
  const { t } = useTranslation();
  const done = RECOMMENDED.filter((app) => statuses[app.key]?.status === 'connected').length;
  if (done === RECOMMENDED.length) return null;
  const percent = Math.round((done / RECOMMENDED.length) * 100);

  return (
    <section
      aria-labelledby="apps-get-started"
      className="mb-6 overflow-hidden rounded-2xl border bg-gradient-to-br from-accent-soft via-surface to-surface"
    >
      <div className="flex flex-wrap items-center gap-4 border-b p-4 sm:p-5">
        <span className="flex size-10 items-center justify-center rounded-xl bg-accent text-accent-fg">
          <Rocket className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 id="apps-get-started" className="text-[15px] font-semibold">
            {t('apps.getStarted.title')}
          </h2>
          <p className="text-[13px] text-fg-muted">{t('apps.getStarted.description')}</p>
        </div>
        <div className="w-full sm:w-48">
          <p className="mb-1 text-xs font-medium text-fg-muted">
            {t('apps.getStarted.progress', { done, total: RECOMMENDED.length })}
          </p>
          <div
            className="h-2 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            aria-label={t('apps.getStarted.title')}
          >
            <div
              className="h-full rounded-full bg-accent transition-all"
              style={{ width: `${percent}%` }}
            />
          </div>
        </div>
      </div>
      <ol className="divide-y">
        {RECOMMENDED.map((app, index) => {
          const connected = statuses[app.key]?.status === 'connected';
          return (
            <li key={app.key} className="flex flex-wrap items-center gap-3 px-4 py-3 sm:px-5">
              <span className="w-5 text-center text-xs font-semibold text-fg-muted">
                {index + 1}
              </span>
              <AppLogo app={app} size="sm" />
              <div className="min-w-0 flex-1">
                <Link to={`${paths.apps}/${app.key}`} className="font-medium hover:underline">
                  {t(`apps.catalog.${app.key}.name`)}
                </Link>
                <p className="text-xs text-fg-muted">{t(`apps.catalog.${app.key}.getStarted`)}</p>
              </div>
              {connected ? (
                <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-success">
                  <CheckCircle2 className="size-4" aria-hidden /> {t('apps.status.connected')}
                </span>
              ) : (
                <AppConnectButton
                  app={app}
                  status={statuses[app.key]}
                  size="sm"
                  manageHref={`${paths.apps}/${app.key}`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
