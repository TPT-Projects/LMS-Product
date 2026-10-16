import { AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';

import { useMetaStatus } from '../api';

/** Shown to Owners and Admins when the Meta token is expiring or expired (spec 6). */
export function MetaTokenBanner() {
  const { t } = useTranslation();
  const status = useMetaStatus();
  const state = status.data?.status === 'connected' ? status.data.token_state : null;
  if (state !== 'expiring' && state !== 'expired') return null;

  return (
    <div
      role="alert"
      className={cn(
        'flex flex-wrap items-center gap-2 px-4 py-2 text-[13px] sm:px-6',
        state === 'expired' ? 'bg-danger-soft text-danger' : 'bg-warning-soft text-warning',
      )}
    >
      <AlertTriangle className="size-4 shrink-0" aria-hidden />
      <span className="flex-1">{t(`meta.banner.${state}`)}</span>
      <Link to={paths.settingsMeta} className="font-medium underline">
        {t('meta.banner.action')}
      </Link>
    </div>
  );
}
