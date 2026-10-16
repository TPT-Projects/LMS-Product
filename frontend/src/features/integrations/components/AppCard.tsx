import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';

import type { AppStatus } from '../api';
import type { AppDef } from '../catalog';
import { AppConnectButton } from './AppConnectButton';
import { AppLogo } from './AppLogo';
import { AppStatusBadge } from './AppStatusBadge';

/** Marketplace tile: the whole card opens the app page; the button connects directly. */
export function AppCard({ app, status }: { app: AppDef; status?: AppStatus }) {
  const { t } = useTranslation();
  const href = `${paths.apps}/${app.key}`;
  return (
    <article
      className={cn(
        'relative flex flex-col gap-3 rounded-xl border bg-surface p-4 transition-shadow',
        'focus-within:ring-2 focus-within:ring-ring hover:shadow-md',
        app.availability === 'coming_soon' && 'bg-subtle/40',
      )}
    >
      <div className="flex items-start gap-3">
        <AppLogo app={app} />
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-semibold">
            <Link
              to={href}
              className="outline-none after:absolute after:inset-0 after:content-['']"
            >
              {t(`apps.catalog.${app.key}.name`)}
            </Link>
          </h3>
          <p className="text-xs text-fg-muted">{t(`apps.categories.${app.category}`)}</p>
        </div>
        <AppStatusBadge app={app} status={status?.status} />
      </div>
      <p className="line-clamp-2 min-h-10 text-[13px] text-fg-muted">
        {t(`apps.catalog.${app.key}.tagline`)}
      </p>
      {status?.account_label && (
        <p className="truncate text-xs text-fg-muted" title={status.account_label}>
          {status.account_label}
        </p>
      )}
      <div className="relative z-10 mt-auto">
        <AppConnectButton app={app} status={status} size="sm" manageHref={href} />
      </div>
    </article>
  );
}
