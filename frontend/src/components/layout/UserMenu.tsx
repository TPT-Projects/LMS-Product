import { Download, Keyboard, LogOut, Monitor, Moon, Share, Sun } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Avatar,
  DropdownMenu,
  DropdownMenuCheckItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui';
import { useAuth, useSession } from '@/features/auth/useAuth';
import { usePwaInstall } from '@/lib/pwa';
import { applyTheme, getThemePreference, type ThemePreference } from '@/lib/theme';

const THEMES: { value: ThemePreference; icon: typeof Sun }[] = [
  { value: 'light', icon: Sun },
  { value: 'dark', icon: Moon },
  { value: 'system', icon: Monitor },
];

export function UserMenu({ onShowShortcuts }: { onShowShortcuts: () => void }) {
  const pwa = usePwaInstall();
  const { t } = useTranslation();
  const { logout } = useAuth();
  const { user } = useSession();
  const [theme, setTheme] = useState<ThemePreference>(getThemePreference);

  const chooseTheme = (value: ThemePreference) => {
    applyTheme(value);
    setTheme(value);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="rounded-full" aria-label={t('nav.userMenu')}>
        <Avatar name={user.full_name} className="size-8" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <div className="px-2.5 py-2">
          <p className="truncate font-medium">{user.full_name}</p>
          <p className="truncate text-xs text-fg-muted">{user.email}</p>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>{t('theme.label')}</DropdownMenuLabel>
        {THEMES.map(({ value, icon: Icon }) => (
          <DropdownMenuCheckItem
            key={value}
            checked={theme === value}
            onSelect={() => chooseTheme(value)}
          >
            <span className="flex items-center gap-2">
              <Icon className="size-4" aria-hidden />
              {t(`theme.${value}`)}
            </span>
          </DropdownMenuCheckItem>
        ))}
        <DropdownMenuSeparator />
        {pwa.canInstall && (
          <DropdownMenuItem onSelect={() => void pwa.install()}>
            <Download className="size-4" aria-hidden />
            {t('pwa.install')}
          </DropdownMenuItem>
        )}
        {pwa.showIosHint && (
          <div className="flex gap-2 px-2.5 py-2 text-xs text-fg-muted">
            <Share className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            {t('pwa.iosHint')}
          </div>
        )}
        <DropdownMenuItem onSelect={onShowShortcuts}>
          <Keyboard className="size-4" aria-hidden />
          {t('shortcuts.title')}
          <kbd className="ml-auto text-xs text-fg-subtle">?</kbd>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void logout()}>
          <LogOut className="size-4" aria-hidden />
          {t('auth.logout')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
