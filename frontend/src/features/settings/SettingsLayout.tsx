import { useTranslation } from 'react-i18next';
import { NavLink, Outlet } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { useAuth } from '@/features/auth/useAuth';
import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';

const TABS = [
  { to: paths.settingsWorkspace, labelKey: 'settings.tabs.workspace' },
  { to: paths.settingsUsers, labelKey: 'settings.tabs.users' },
  { to: paths.settingsTeams, labelKey: 'settings.tabs.teams' },
  { to: paths.settingsStatuses, labelKey: 'settings.tabs.statuses' },
  { to: paths.settingsCustomFields, labelKey: 'settings.tabs.customFields' },
  { to: paths.settingsMeta, labelKey: 'settings.tabs.meta', capability: 'manage_meta' },
] as const;

export default function SettingsLayout() {
  const { t } = useTranslation();
  const { can } = useAuth();
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={t('settings.title')} description={t('settings.description')} />
      <nav
        aria-label={t('settings.title')}
        className="-mx-4 mb-5 scrollbar-none overflow-x-auto overflow-y-hidden border-b px-4 sm:mx-0 sm:px-0"
      >
        <ul className="flex gap-1">
          {TABS.filter((tab) => !('capability' in tab) || can(tab.capability)).map((tab) => (
            <li key={tab.to}>
              <NavLink
                to={tab.to}
                className={({ isActive }) =>
                  cn(
                    '-mb-px inline-flex h-10 items-center border-b-2 px-3 text-[13px] font-medium whitespace-nowrap transition-colors',
                    isActive
                      ? 'border-accent text-fg'
                      : 'border-transparent text-fg-muted hover:text-fg',
                  )
                }
              >
                {t(tab.labelKey)}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <Outlet />
    </div>
  );
}
