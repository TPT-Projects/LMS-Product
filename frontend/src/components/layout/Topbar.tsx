import { Menu, Plus } from 'lucide-react';
import type { RefObject } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui';
import { useAuth } from '@/features/auth/useAuth';
import { useQuickAdd } from '@/features/enquiries/useQuickAdd';
import { AppsMenu } from '@/features/integrations/components/AppsMenu';
import { GlobalSearch } from '@/features/search/GlobalSearch';

import { NotificationBell } from './NotificationBell';
import { UserMenu } from './UserMenu';

interface TopbarProps {
  onOpenMobileNav: () => void;
  onShowShortcuts: () => void;
  searchRef: RefObject<HTMLInputElement | null>;
}

export function Topbar({ onOpenMobileNav, onShowShortcuts, searchRef }: TopbarProps) {
  const { t } = useTranslation();
  const { can } = useAuth();
  const quickAdd = useQuickAdd();
  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b bg-bg/90 px-3 backdrop-blur sm:px-5">
      <button
        type="button"
        onClick={onOpenMobileNav}
        className="inline-flex size-9 items-center justify-center rounded-lg text-fg-muted hover:bg-muted lg:hidden"
        aria-label={t('nav.openMenu')}
      >
        <Menu className="size-5" />
      </button>

      <GlobalSearch ref={searchRef} />

      <div className="ml-auto flex items-center gap-1">
        {can('edit_enquiries') && (
          <Button
            size="icon"
            className="size-9"
            onClick={quickAdd.open}
            aria-label={t('enquiries.new')}
            title={`${t('enquiries.new')} (Q)`}
          >
            <Plus className="size-4" />
          </Button>
        )}
        <AppsMenu />
        <NotificationBell />
        <UserMenu onShowShortcuts={onShowShortcuts} />
      </div>
    </header>
  );
}
