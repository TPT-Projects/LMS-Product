import {
  Bookmark,
  Inbox,
  PanelLeftClose,
  PanelLeftOpen,
  PhoneCall,
  Settings2,
  UserRound,
  UserX,
  type LucideIcon,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, useLocation, useSearchParams } from 'react-router-dom';

import { useAuth } from '@/features/auth/useAuth';
import { useSavedViews, useViewCounts } from '@/features/views/api';
import { cn } from '@/lib/cn';
import { paths, smartViews, type SmartViewId } from '@/routes/paths';

import { workspaceNav } from './navigation';
import { WorkspaceSwitcher } from './WorkspaceSwitcher';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapsed?: () => void;
  onNavigate?: () => void;
}

const VIEW_ICONS: Record<SmartViewId, LucideIcon> = {
  all: Inbox,
  mine: UserRound,
  unassigned: UserX,
  'calls-today': PhoneCall,
};

const itemClass = (active: boolean, collapsed: boolean) =>
  cn(
    'flex h-8 items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-medium transition-colors',
    active ? 'bg-muted text-fg' : 'text-fg-muted hover:bg-muted/70 hover:text-fg',
    collapsed && 'justify-center px-0',
  );

function Count({ value }: { value: number | undefined }) {
  if (value === undefined) return null;
  return <span className="ml-auto text-xs text-fg-subtle tabular-nums">{value}</span>;
}

function SectionTitle({ collapsed, children }: { collapsed: boolean; children: ReactNode }) {
  if (collapsed) return <div className="mx-auto my-2 h-px w-6 bg-border" />;
  return <h2 className="mb-1 px-2.5 text-xs font-medium text-fg-subtle">{children}</h2>;
}

export function Sidebar({ collapsed, onToggleCollapsed, onNavigate }: SidebarProps) {
  const { t } = useTranslation();
  const { can } = useAuth();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const counts = useViewCounts();
  const savedViews = useSavedViews();
  const onEnquiries = location.pathname === paths.enquiries;
  const activeView = searchParams.get('view') ?? 'all';
  const activeSaved = Number(searchParams.get('saved_view'));
  const pinned = (savedViews.data ?? []).filter((v) => v.is_pinned);

  return (
    <nav aria-label={t('nav.main')} className="flex h-full flex-col gap-4 p-3">
      <WorkspaceSwitcher collapsed={collapsed} />

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto">
        <section>
          <SectionTitle collapsed={collapsed}>{t('nav.smartViews')}</SectionTitle>
          <ul className="space-y-0.5">
            {smartViews.map((view) => {
              const active = onEnquiries && !activeSaved && activeView === view.id;
              const Icon = VIEW_ICONS[view.id];
              return (
                <li key={view.id}>
                  <NavLink
                    to={view.id === 'all' ? paths.enquiries : `${paths.enquiries}?view=${view.id}`}
                    onClick={onNavigate}
                    className={itemClass(active, collapsed)}
                    aria-current={active ? 'page' : undefined}
                    title={collapsed ? t(view.labelKey) : undefined}
                  >
                    <Icon className="size-4 shrink-0" aria-hidden />
                    {!collapsed && (
                      <>
                        <span className="truncate">{t(view.labelKey)}</span>
                        <Count value={counts.data?.system[view.id]} />
                      </>
                    )}
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </section>

        <section>
          <SectionTitle collapsed={collapsed}>{t('nav.myViews')}</SectionTitle>
          <ul className="space-y-0.5">
            {pinned.map((view) => {
              const active = onEnquiries && activeSaved === view.id;
              return (
                <li key={view.id}>
                  <NavLink
                    to={`${paths.enquiries}?saved_view=${view.id}`}
                    onClick={onNavigate}
                    className={itemClass(active, collapsed)}
                    aria-current={active ? 'page' : undefined}
                    title={collapsed ? view.name : undefined}
                  >
                    <Bookmark className="size-4 shrink-0" aria-hidden />
                    {!collapsed && (
                      <>
                        <span className="truncate">{view.name}</span>
                        <Count value={counts.data?.saved[String(view.id)]} />
                      </>
                    )}
                  </NavLink>
                </li>
              );
            })}
            <li>
              <NavLink
                to={paths.views}
                onClick={onNavigate}
                className={({ isActive }) => itemClass(isActive, collapsed)}
                title={collapsed ? t('nav.manageViews') : undefined}
              >
                <Settings2 className="size-4 shrink-0" aria-hidden />
                {!collapsed && <span className="truncate">{t('nav.manageViews')}</span>}
              </NavLink>
            </li>
          </ul>
        </section>

        <section>
          <SectionTitle collapsed={collapsed}>{t('nav.workspace')}</SectionTitle>
          <ul className="space-y-0.5">
            {workspaceNav
              .filter((item) => !item.capability || can(item.capability))
              .map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    onClick={onNavigate}
                    className={({ isActive }) => itemClass(isActive, collapsed)}
                    title={collapsed ? t(item.labelKey) : undefined}
                  >
                    <item.icon className="size-4 shrink-0" aria-hidden />
                    {!collapsed && <span className="truncate">{t(item.labelKey)}</span>}
                  </NavLink>
                </li>
              ))}
          </ul>
        </section>
      </div>

      {onToggleCollapsed && (
        <button
          type="button"
          onClick={onToggleCollapsed}
          className={itemClass(false, collapsed)}
          aria-label={collapsed ? t('nav.expand') : t('nav.collapse')}
          title={`${collapsed ? t('nav.expand') : t('nav.collapse')} ( [ )`}
        >
          {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          {!collapsed && <span>{t('nav.collapse')}</span>}
        </button>
      )}
    </nav>
  );
}
