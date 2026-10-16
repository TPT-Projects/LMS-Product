import * as RadixDialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet } from 'react-router-dom';

import { useHotkeys } from '@/hooks/useHotkeys';
import { cn } from '@/lib/cn';
import { QuickAddProvider } from '@/features/enquiries/QuickAddProvider';
import { LiveEventsProvider } from '@/features/live/LiveEventsProvider';
import { useMetaLeadPolling } from '@/features/meta/api';
import { MetaTokenBanner } from '@/features/meta/components/MetaTokenBanner';
import { STORAGE_KEYS, storage } from '@/lib/storage';

import { ShortcutsDialog } from './ShortcutsDialog';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

/**
 * Superlist-style shell: a calm left sidebar, a slim top bar, and the main pane.
 * Desktop (lg+): fixed sidebar that can collapse to icons.
 * Tablet/phone: the sidebar becomes a slide-in drawer.
 */
export function AppShell() {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(
    () => storage.get(STORAGE_KEYS.sidebarCollapsed) === '1',
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const toggleCollapsed = () =>
    setCollapsed((value) => {
      storage.set(STORAGE_KEYS.sidebarCollapsed, value ? '0' : '1');
      return !value;
    });

  useHotkeys({
    '?': () => setShortcutsOpen(true),
    '/': () => searchRef.current?.focus(),
    '[': toggleCollapsed,
  });

  useMetaLeadPolling(); // new Meta leads about every minute, even without a webhook

  return (
    <LiveEventsProvider>
      <QuickAddProvider>
        <div className="flex min-h-dvh">
          <a
            href="#main"
            className="sr-only z-50 rounded-lg bg-accent px-3 py-2 text-accent-fg focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
          >
            {t('nav.skipToContent')}
          </a>

          {/* Desktop sidebar */}
          <aside
            className={cn(
              'sticky top-0 hidden h-dvh shrink-0 border-r bg-subtle transition-[width] duration-200 lg:block',
              collapsed ? 'w-16' : 'w-60',
            )}
          >
            <Sidebar collapsed={collapsed} onToggleCollapsed={toggleCollapsed} />
          </aside>

          {/* Mobile drawer */}
          <RadixDialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
            <RadixDialog.Portal>
              <RadixDialog.Overlay className="fixed inset-0 z-40 animate-fade-in bg-overlay lg:hidden" />
              <RadixDialog.Content className="fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] animate-slide-in-left border-r bg-subtle focus:outline-none lg:hidden">
                <RadixDialog.Title className="sr-only">{t('nav.main')}</RadixDialog.Title>
                <RadixDialog.Description className="sr-only">
                  {t('nav.main')}
                </RadixDialog.Description>
                <RadixDialog.Close
                  className="absolute top-3.5 right-3 rounded-md p-1.5 text-fg-muted hover:bg-muted"
                  aria-label={t('common.close')}
                >
                  <X className="size-4" />
                </RadixDialog.Close>
                <Sidebar collapsed={false} onNavigate={() => setMobileOpen(false)} />
              </RadixDialog.Content>
            </RadixDialog.Portal>
          </RadixDialog.Root>

          <div className="flex min-w-0 flex-1 flex-col">
            <Topbar
              onOpenMobileNav={() => setMobileOpen(true)}
              onShowShortcuts={() => setShortcutsOpen(true)}
              searchRef={searchRef}
            />
            <MetaTokenBanner />
            <main id="main" className="min-w-0 flex-1 px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
              <Outlet />
            </main>
          </div>

          <ShortcutsDialog open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
        </div>
      </QuickAddProvider>
    </LiveEventsProvider>
  );
}
