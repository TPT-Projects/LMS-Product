import { Bell, CheckCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  EmptyState,
} from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { useMarkRead, useNotifications } from '@/features/notifications/api';
import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';

/** In-app notification bell: finished imports now, @mentions later. */
export function NotificationBell() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useDateFormat();
  const notifications = useNotifications({ page: 1, page_size: 25 });
  const markRead = useMarkRead();
  const unread = notifications.data?.unread_count ?? 0;
  const items = notifications.data?.results.slice(0, 8) ?? [];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="relative inline-flex size-9 items-center justify-center rounded-lg text-fg-muted hover:bg-muted hover:text-fg"
        aria-label={
          unread ? t('notifications.titleUnread', { count: unread }) : t('notifications.title')
        }
      >
        <Bell className="size-[18px]" />
        {unread > 0 && (
          <span className="absolute top-1 right-1 flex min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] leading-4 font-semibold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 max-w-[calc(100vw-2rem)] p-0">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-[13px] font-semibold">{t('notifications.title')}</span>
          {unread > 0 && (
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
              onClick={() => markRead.mutate('all')}
            >
              <CheckCheck className="size-3.5" aria-hidden /> {t('notifications.markAll')}
            </button>
          )}
        </div>
        {items.length === 0 ? (
          <EmptyState
            icon={Bell}
            title={t('notifications.emptyTitle')}
            description={t('notifications.emptyDescription')}
            className="py-8"
          />
        ) : (
          <div className="max-h-96 overflow-y-auto p-1">
            {items.map((n) => (
              <DropdownMenuItem
                key={n.id}
                className="items-start gap-2.5 py-2"
                onSelect={() => {
                  if (!n.is_read) markRead.mutate(n.id);
                  if (n.link) navigate(n.link);
                }}
              >
                <span
                  className={cn(
                    'mt-1.5 size-2 shrink-0 rounded-full',
                    n.is_read ? 'bg-transparent' : 'bg-accent',
                  )}
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className={cn('block truncate', !n.is_read && 'font-semibold')}>
                    {n.title}
                  </span>
                  {n.body && <span className="block text-xs text-fg-muted">{n.body}</span>}
                  <span className="block text-xs text-fg-subtle tabular-nums">
                    {format.dateTime(n.created_at)}
                  </span>
                </span>
              </DropdownMenuItem>
            ))}
          </div>
        )}
        <DropdownMenuSeparator />
        <div className="p-1">
          <DropdownMenuItem asChild>
            <Link to={paths.notifications} className="justify-center text-accent">
              {t('notifications.viewAll')}
            </Link>
          </DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
