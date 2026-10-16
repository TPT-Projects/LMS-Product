import { Bell, CheckCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Pagination } from '@/components/data-table';
import { PageHeader } from '@/components/layout/PageHeader';
import { Alert, Button, Card, EmptyState, Skeleton } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { usePageParams } from '@/hooks/usePageParams';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';

import { useMarkRead, useNotifications } from '../api';

export default function NotificationsPage() {
  const { t } = useTranslation();
  const format = useDateFormat();
  const { page, page_size, setPage, setPageSize } = usePageParams();
  const notifications = useNotifications({ page, page_size });
  const markRead = useMarkRead();
  const data = notifications.data;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={t('notifications.title')}
        description={t('notifications.description')}
        actions={
          (data?.unread_count ?? 0) > 0 && (
            <Button variant="secondary" onClick={() => markRead.mutate('all')}>
              <CheckCheck className="size-4" aria-hidden /> {t('notifications.markAll')}
            </Button>
          )
        }
      />
      <Card>
        {notifications.isError && (
          <div className="p-4">
            <Alert tone="danger">{getErrorMessage(notifications.error)}</Alert>
          </div>
        )}
        {notifications.isPending ? (
          <div className="space-y-3 p-5">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : !data?.results.length ? (
          <EmptyState
            icon={Bell}
            title={t('notifications.emptyTitle')}
            description={t('notifications.emptyDescription')}
          />
        ) : (
          <>
            <ul className="divide-y">
              {data.results.map((n) => (
                <li
                  key={n.id}
                  className={cn('flex gap-3 px-4 py-3 sm:px-5', !n.is_read && 'bg-accent-soft/40')}
                >
                  <span
                    className={cn('mt-1.5 size-2 shrink-0 rounded-full', !n.is_read && 'bg-accent')}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <p className={cn('text-[13px]', !n.is_read && 'font-semibold')}>
                      {n.link ? (
                        <Link
                          to={n.link}
                          className="hover:underline"
                          onClick={() => !n.is_read && markRead.mutate(n.id)}
                        >
                          {n.title}
                        </Link>
                      ) : (
                        n.title
                      )}
                    </p>
                    {n.body && <p className="text-[13px] text-fg-muted">{n.body}</p>}
                    <p className="text-xs text-fg-subtle tabular-nums">
                      {format.dateTime(n.created_at)}
                    </p>
                  </div>
                  {!n.is_read && (
                    <Button variant="ghost" size="sm" onClick={() => markRead.mutate(n.id)}>
                      {t('notifications.markRead')}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
            <Pagination
              page={page}
              pageSize={page_size}
              count={data.count}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          </>
        )}
      </Card>
    </div>
  );
}
