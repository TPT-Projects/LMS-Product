import { Phone } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { EmptyState, Skeleton } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';

import { useCalls } from '../api';
import { formatDuration } from '../format';
import { CallForm } from './forms/CallForm';

export function CallsPanel({ enquiryId, canEdit }: { enquiryId: number; canEdit: boolean }) {
  const { t } = useTranslation();
  const format = useDateFormat();
  const calls = useCalls(enquiryId);

  return (
    <div className="space-y-4">
      {canEdit && (
        <div className="rounded-lg border bg-subtle p-3">
          <CallForm enquiryId={enquiryId} />
        </div>
      )}
      {calls.isPending ? (
        <Skeleton className="h-14 w-full" />
      ) : !calls.data?.length ? (
        <EmptyState icon={Phone} title={t('calls.empty')} className="py-8" />
      ) : (
        <ul className="divide-y rounded-lg border">
          {calls.data.map((call) => (
            <li key={call.id} className="p-3">
              <div className="flex flex-wrap items-center gap-x-2 text-[13px]">
                <span className="font-medium">{t(`calls.outcomes.${call.outcome}`)}</span>
                <span className="text-fg-muted">· {formatDuration(call.duration_seconds)}</span>
                <span className="ml-auto text-xs text-fg-muted tabular-nums">
                  {format.dateTime(call.called_at)}
                </span>
              </div>
              {call.notes && (
                <p className="mt-1 text-[13px] break-words whitespace-pre-line text-fg-muted">
                  {call.notes}
                </p>
              )}
              <p className="mt-1 text-xs text-fg-subtle">{call.user?.full_name}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
