import { Bookmark, MoreHorizontal, Pencil, Pin, PinOff, Trash2, Users } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import {
  Alert,
  Badge,
  Button,
  Card,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  EmptyState,
  Skeleton,
} from '@/components/ui';
import { countRules } from '@/features/enquiries/filters';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';
import type { SavedView } from '@/types/crm';

import { useDeleteView, usePinView, useSavedViews, useViewCounts } from '../api';
import { SaveViewDialog } from '../components/SaveViewDialog';

/** Saved views manager (spec screen 10): open, pin, rename, share, delete. */
export default function ViewsPage() {
  const { t } = useTranslation();
  const views = useSavedViews();
  const counts = useViewCounts();
  const pin = usePinView();
  const remove = useDeleteView();
  const [editing, setEditing] = useState<SavedView | null>(null);
  const error = views.error ?? pin.error ?? remove.error;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title={t('views.title')} description={t('views.description')} />
      <Card>
        {error && (
          <div className="px-4 pt-3 sm:px-5">
            <Alert tone="danger">{getErrorMessage(error)}</Alert>
          </div>
        )}
        {views.isPending ? (
          <div className="space-y-3 p-5">
            <Skeleton className="h-5 w-56" />
            <Skeleton className="h-5 w-40" />
          </div>
        ) : !views.data?.length ? (
          <EmptyState
            icon={Bookmark}
            title={t('views.empty.title')}
            description={t('views.empty.description')}
            action={
              <Link to={paths.enquiries}>
                <Button variant="secondary">{t('views.empty.action')}</Button>
              </Link>
            }
          />
        ) : (
          <ul className="divide-y">
            {views.data.map((view) => (
              <li key={view.id} className="flex items-center gap-3 px-4 py-3 sm:px-5">
                <Link
                  to={`${paths.enquiries}?saved_view=${view.id}`}
                  className="group min-w-0 flex-1"
                >
                  <p className="flex flex-wrap items-center gap-2 font-medium group-hover:underline">
                    {view.name}
                    {view.is_pinned && (
                      <Pin className="size-3.5 text-accent" aria-label={t('views.pinned')} />
                    )}
                    {view.is_shared && (
                      <Badge>
                        <Users className="mr-1 size-3" aria-hidden />
                        {t('views.shared')}
                      </Badge>
                    )}
                  </p>
                  <p className="mt-0.5 text-xs text-fg-muted">
                    {t('views.ruleCount', { count: countRules(view.filters.filter) })}
                    {!view.is_owner && <> · {t('views.by', { name: view.owner.full_name })}</>}
                  </p>
                </Link>
                {counts.data?.saved[String(view.id)] !== undefined && (
                  <span className="text-[13px] text-fg-muted tabular-nums">
                    {counts.data.saved[String(view.id)]}
                  </span>
                )}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t('common.actionsFor', { name: view.name })}
                    >
                      <MoreHorizontal className="size-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onSelect={() => pin.mutate({ id: view.id, pinned: !view.is_pinned })}
                    >
                      {view.is_pinned ? (
                        <PinOff className="size-4" aria-hidden />
                      ) : (
                        <Pin className="size-4" aria-hidden />
                      )}
                      {view.is_pinned ? t('views.unpin') : t('views.pin')}
                    </DropdownMenuItem>
                    {view.is_owner && (
                      <>
                        <DropdownMenuItem onSelect={() => setEditing(view)}>
                          <Pencil className="size-4" aria-hidden /> {t('views.renameShare')}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-danger"
                          onSelect={() => {
                            if (window.confirm(t('views.confirmDelete', { name: view.name }))) {
                              remove.mutate(view.id);
                            }
                          }}
                        >
                          <Trash2 className="size-4" aria-hidden /> {t('common.delete')}
                        </DropdownMenuItem>
                      </>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <SaveViewDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        view={editing}
      />
    </div>
  );
}
