import { ArrowLeft, Lock, Repeat, UserRound } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import { Alert, Avatar, Badge, Button, Card, EmptyState, Skeleton } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { StatusBadge } from '@/features/statuses/components/StatusBadge';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { useContact } from '../api';

export default function ContactDetailPage() {
  const { t } = useTranslation();
  const format = useDateFormat();
  const id = Number(useParams().id);
  const contact = useContact(id);

  if (contact.isPending) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (contact.isError || !contact.data) {
    return (
      <EmptyState
        icon={UserRound}
        title={t('contacts.notFound')}
        description={getErrorMessage(contact.error)}
        className="py-24"
        action={
          <Link to={paths.contacts}>
            <Button variant="secondary">{t('contacts.back')}</Button>
          </Link>
        }
      />
    );
  }

  const c = contact.data;
  return (
    <div className="mx-auto max-w-4xl">
      <Link
        to={paths.contacts}
        className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="size-4" aria-hidden /> {t('contacts.back')}
      </Link>

      <div className="mb-5 flex items-center gap-3">
        <Avatar name={c.name || '?'} className="size-11 text-sm" />
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold tracking-tight sm:text-2xl">
            {c.name || t('enquiries.noName')}
          </h1>
          <p className="text-[13px] text-fg-muted">
            {[c.phone_e164, c.email].filter(Boolean).join(' · ') || '—'}
          </p>
        </div>
      </div>

      <Alert tone="info" className="mb-5">
        <span className="inline-flex items-center gap-1.5">
          <Lock className="size-3.5" aria-hidden /> {t('contacts.readOnly')}
        </span>
      </Alert>

      <Card>
        <div className="flex items-center justify-between border-b px-4 py-3 sm:px-5">
          <h2 className="text-[15px] font-semibold">{t('contacts.enquiries')}</h2>
          <span className="text-[13px] text-fg-muted">
            {t('contacts.firstSeenOn', { date: format.date(c.created_at) })}
          </span>
        </div>
        {c.enquiries.length === 0 ? (
          <EmptyState icon={UserRound} title={t('contacts.noVisibleEnquiries')} className="py-10" />
        ) : (
          <ul className="divide-y">
            {c.enquiries.map((e) => (
              <li key={e.id}>
                <Link
                  to={`${paths.enquiries}/${e.id}`}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 hover:bg-subtle sm:px-5"
                >
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5 font-medium">
                      {e.name || t('enquiries.noName')}
                      {e.is_repeat && <Repeat className="size-3.5 text-accent" aria-hidden />}
                    </span>
                    <span className="block truncate text-xs text-fg-muted">
                      {e.campaign_name || t(`sources.${e.source}`)}
                    </span>
                  </span>
                  <StatusBadge name={e.status.name} color={e.status.color} />
                  <span className="text-xs text-fg-muted tabular-nums">
                    {format.date(e.created_at)}
                  </span>
                  {e.primary_owner && <Badge>{e.primary_owner.full_name}</Badge>}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
