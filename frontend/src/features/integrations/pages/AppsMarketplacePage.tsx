import { LayoutGrid, Search } from 'lucide-react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { Alert, EmptyState, Input, Skeleton } from '@/components/ui';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';

import { isLive, useIntegrations } from '../api';
import { APPS, CATEGORIES, type Category } from '../catalog';
import { AppCard } from '../components/AppCard';
import { GetStartedChecklist } from '../components/GetStartedChecklist';

type Tab = 'all' | 'connected';

/** Apps (HubSpot "App Marketplace" style): browse, search and connect in one click. */
export default function AppsMarketplacePage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const integrations = useIntegrations();
  const statuses = useMemo(() => integrations.data ?? {}, [integrations.data]);

  const tab: Tab = params.get('tab') === 'connected' ? 'connected' : 'all';
  const category = (CATEGORIES as readonly string[]).includes(params.get('category') ?? '')
    ? (params.get('category') as Category)
    : null;
  const query = params.get('q') ?? '';
  const set = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { replace: true });
  };

  const connectedCount = APPS.filter((app) => isLive(statuses[app.key]?.status)).length;
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return APPS.filter((app) => tab === 'all' || isLive(statuses[app.key]?.status))
      .filter((app) => !category || app.category === category)
      .filter((app) => {
        if (!needle) return true;
        const text = `${t(`apps.catalog.${app.key}.name`)} ${t(`apps.catalog.${app.key}.tagline`)} ${t(`apps.categories.${app.category}`)}`;
        return text.toLowerCase().includes(needle);
      })
      .sort(
        (a, b) =>
          Number(a.availability === 'coming_soon') - Number(b.availability === 'coming_soon'),
      );
  }, [category, query, statuses, t, tab]);

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title={t('apps.title')} description={t('apps.description')} />

      {integrations.isError && (
        <Alert tone="danger" className="mb-4">
          {getErrorMessage(integrations.error)}
        </Alert>
      )}
      {integrations.isPending ? (
        <Skeleton className="mb-6 h-40 w-full rounded-2xl" />
      ) : (
        <GetStartedChecklist statuses={statuses} />
      )}

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div
          role="tablist"
          aria-label={t('apps.title')}
          className="inline-flex rounded-lg bg-muted p-1"
        >
          {(['all', 'connected'] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => set({ tab: value === 'all' ? null : value })}
              className={cn(
                'h-8 rounded-md px-3 text-[13px] font-medium transition-colors',
                tab === value ? 'bg-surface text-fg shadow-sm' : 'text-fg-muted hover:text-fg',
              )}
            >
              {value === 'all'
                ? t('apps.tabs.all', { count: APPS.length })
                : t('apps.tabs.connected', { count: connectedCount })}
            </button>
          ))}
        </div>
        <label className="relative block sm:w-72">
          <span className="sr-only">{t('apps.search')}</span>
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-muted"
            aria-hidden
          />
          <Input
            type="search"
            value={query}
            onChange={(e) => set({ q: e.target.value })}
            placeholder={t('apps.search')}
            className="pl-9"
          />
        </label>
      </div>

      <div className="lg:grid lg:grid-cols-[13rem_1fr] lg:gap-6">
        <nav aria-label={t('apps.categoriesLabel')} className="mb-4 lg:mb-0">
          <ul className="-mx-4 scrollbar-none flex gap-2 overflow-x-auto px-4 lg:mx-0 lg:flex-col lg:gap-0.5 lg:px-0">
            {[null, ...CATEGORIES].map((value) => {
              const count = APPS.filter(
                (app) =>
                  (!value || app.category === value) &&
                  (tab === 'all' || isLive(statuses[app.key]?.status)),
              ).length;
              const active = category === value;
              return (
                <li key={value ?? 'all'} className="shrink-0">
                  <button
                    type="button"
                    aria-current={active ? 'true' : undefined}
                    onClick={() => set({ category: value })}
                    className={cn(
                      'flex w-full items-center justify-between gap-3 rounded-full border px-3 py-1.5 text-[13px] whitespace-nowrap transition-colors lg:rounded-lg lg:border-0',
                      active
                        ? 'border-accent bg-accent-soft font-medium text-fg'
                        : 'text-fg-muted hover:bg-subtle hover:text-fg',
                    )}
                  >
                    {value ? t(`apps.categories.${value}`) : t('apps.allCategories')}
                    <span className="text-xs text-fg-muted tabular-nums">{count}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {visible.length === 0 ? (
          <EmptyState
            icon={LayoutGrid}
            title={
              tab === 'connected' && !query
                ? t('apps.emptyConnected.title')
                : t('apps.emptySearch.title')
            }
            description={
              tab === 'connected' && !query
                ? t('apps.emptyConnected.description')
                : t('apps.emptySearch.description')
            }
            className="rounded-xl border"
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {visible.map((app) => (
              <AppCard key={app.key} app={app} status={statuses[app.key]} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
