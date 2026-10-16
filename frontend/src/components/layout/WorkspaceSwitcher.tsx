import { ChevronsUpDown } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import {
  DropdownMenu,
  DropdownMenuCheckItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui';
import { useAuth, useSession } from '@/features/auth/useAuth';
import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';

export function WorkspaceSwitcher({ collapsed }: { collapsed: boolean }) {
  const { t } = useTranslation();
  const { switchWorkspace } = useAuth();
  const session = useSession();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const initial = session.workspace.name.trim()[0]?.toUpperCase() ?? 'W';

  const select = async (id: number) => {
    if (id === session.workspace.id) return;
    setBusy(true);
    try {
      await switchWorkspace(id);
      navigate(paths.home);
    } finally {
      setBusy(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={busy}
        className={cn(
          'flex w-full items-center gap-2 rounded-lg p-1.5 text-left hover:bg-muted',
          collapsed && 'justify-center',
        )}
        aria-label={t('nav.switchWorkspace')}
      >
        <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-accent text-[13px] font-semibold text-accent-fg">
          {initial}
        </span>
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-semibold">{session.workspace.name}</span>
              <span className="block truncate text-xs text-fg-muted">
                {t(`roles.${session.role}`)}
              </span>
            </span>
            <ChevronsUpDown className="size-4 shrink-0 text-fg-subtle" aria-hidden />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-64">
        <DropdownMenuLabel>{t('nav.workspaces')}</DropdownMenuLabel>
        {session.workspaces.map((ws) => (
          <DropdownMenuCheckItem
            key={ws.id}
            checked={ws.id === session.workspace.id}
            onSelect={() => void select(ws.id)}
          >
            <span className="block truncate">{ws.name}</span>
            <span className="block text-xs text-fg-muted">{t(`roles.${ws.role}`)}</span>
          </DropdownMenuCheckItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
