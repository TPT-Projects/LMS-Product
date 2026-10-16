import { LayoutGrid, Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui';
import { useAuth } from '@/features/auth/useAuth';
import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';

import { isLive, useIntegrations } from '../api';
import { APPS } from '../catalog';
import { AppLogo } from './AppLogo';

const DOT = {
  connected: 'bg-success',
  error: 'bg-danger',
  needs_setup: 'bg-warning',
  not_connected: 'bg-muted',
} as const;

/** Header "Apps" button: connected apps at a glance, and one click to connect more. */
export function AppsMenu() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const integrations = useIntegrations();
  if (!can('manage_integrations')) return null;

  const statuses = integrations.data ?? {};
  const live = APPS.filter((app) => isLive(statuses[app.key]?.status));
  const attention = live.some((app) => statuses[app.key]?.status !== 'connected');

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="relative inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-[13px] font-medium text-fg-muted hover:bg-muted hover:text-fg"
        aria-label={t('apps.menu.label')}
      >
        <LayoutGrid className="size-[18px]" aria-hidden />
        <span className="hidden md:inline">{t('apps.menu.button')}</span>
        {attention && (
          <span
            className="absolute top-1.5 left-6 size-2 rounded-full bg-warning ring-2 ring-bg"
            aria-hidden
          />
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 max-w-[calc(100vw-2rem)] p-0">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-[13px] font-semibold">{t('apps.menu.connected')}</span>
          <span className="text-xs text-fg-muted">
            {t('apps.menu.count', { count: live.length })}
          </span>
        </div>
        {live.length === 0 ? (
          <p className="px-3 py-5 text-center text-[13px] text-fg-muted">{t('apps.menu.empty')}</p>
        ) : (
          <div className="max-h-80 overflow-y-auto p-1">
            {live.map((app) => {
              const status = statuses[app.key];
              return (
                <DropdownMenuItem
                  key={app.key}
                  className="gap-2.5 py-2"
                  onSelect={() => navigate(`${paths.apps}/${app.key}`)}
                >
                  <AppLogo app={app} size="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">
                      {t(`apps.catalog.${app.key}.name`)}
                    </span>
                    <span className="block truncate text-xs text-fg-muted">
                      {status?.account_label || t(`apps.status.${status?.status ?? 'connected'}`)}
                    </span>
                  </span>
                  <span
                    className={cn(
                      'size-2 shrink-0 rounded-full',
                      DOT[status?.status ?? 'connected'],
                    )}
                    title={t(`apps.status.${status?.status ?? 'connected'}`)}
                  />
                </DropdownMenuItem>
              );
            })}
          </div>
        )}
        <div className="flex items-center gap-2 border-t p-2">
          <Button size="sm" className="flex-1" onClick={() => navigate(paths.apps)}>
            <Plus className="size-4" aria-hidden /> {t('apps.menu.connectApp')}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => navigate(`${paths.apps}?tab=connected`)}
          >
            {t('apps.menu.manage')}
          </Button>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
