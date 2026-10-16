import {
  ArrowRightLeft,
  CalendarCheck,
  CalendarClock,
  CircleDot,
  FileText,
  History,
  Paperclip,
  PenLine,
  Phone,
  PhoneCall,
  Plus,
  Repeat,
  StickyNote,
  Trash2,
  Undo2,
  UserCog,
  type LucideIcon,
} from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, EmptyState, Skeleton } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import type { ActivityEvent } from '@/types/crm';

import { useTimeline } from '../api';
import { formatDuration } from '../format';

const ICONS: Record<string, LucideIcon> = {
  enquiry_created: Plus,
  repeat_enquiry: Repeat,
  contact_information_updated: UserCog,
  status_changed: CircleDot,
  field_changed: PenLine,
  assignment_changed: ArrowRightLeft,
  note_added: StickyNote,
  call_logged: Phone,
  followup_scheduled: CalendarClock,
  followup_completed: CalendarCheck,
  attachment_added: Paperclip,
  enquiry_deleted: Trash2,
  enquiry_restored: Undo2,
  auto_call: PhoneCall,
};

type Details = Record<string, unknown>;
const str = (v: unknown) => (v === null || v === undefined || v === '' ? '—' : String(v));

function useDescribe() {
  const { t } = useTranslation();
  const format = useDateFormat();

  return (event: ActivityEvent): { text: string; extra?: string[] } => {
    const d = event.details as Details;
    const actor = event.actor.type === 'system' ? t('timeline.system') : event.actor.name;
    switch (event.type) {
      case 'enquiry_created':
        return { text: t('timeline.created', { actor, source: t(`sources.${str(d.source)}`) }) };
      case 'repeat_enquiry':
        return { text: t('timeline.repeat', { count: Number(d.previous_enquiries ?? 0) }) };
      case 'contact_information_updated':
        return {
          text: t('timeline.contactUpdated', {
            fields: ((d.filled as string[]) ?? [])
              .map((f) => t(`timeline.contactFields.${f}`))
              .join(', '),
          }),
        };
      case 'status_changed':
        return { text: t('timeline.status', { actor, from: str(d.from), to: str(d.to) }) };
      case 'field_changed': {
        const changes =
          (d.changes as { field: string; label?: string; from: unknown; to: unknown }[]) ?? [];
        return {
          text: t('timeline.fields', { actor, count: changes.length }),
          extra: changes.map(
            (c) =>
              `${c.label ?? t(`timeline.fieldNames.${c.field}`, { defaultValue: c.field })}: ${str(c.from)} → ${str(c.to)}`,
          ),
        };
      }
      case 'assignment_changed':
        if ('secondary_added' in d || 'secondary_removed' in d) {
          const added = (d.secondary_added as string[]) ?? [];
          const removed = (d.secondary_removed as string[]) ?? [];
          return {
            text: t('timeline.secondary', { actor }),
            extra: [
              ...(added.length ? [t('timeline.added', { names: added.join(', ') })] : []),
              ...(removed.length ? [t('timeline.removed', { names: removed.join(', ') })] : []),
            ],
          };
        }
        return {
          text: t('timeline.owner', {
            actor,
            from: d.from ? str(d.from) : t('enquiries.unassigned'),
            to: d.to ? str(d.to) : t('enquiries.unassigned'),
          }),
        };
      case 'note_added':
        return {
          text: d.voice
            ? t('timeline.voiceNote', {
                actor,
                duration: formatDuration(Number(d.duration_seconds ?? 0)),
              })
            : t('timeline.note', { actor }),
          extra: d.preview ? [str(d.preview)] : [],
        };
      case 'call_logged':
        return {
          text: t('timeline.call', {
            actor,
            outcome: t(`calls.outcomes.${str(d.outcome)}`),
            duration: formatDuration(Number(d.duration_seconds ?? 0)),
          }),
          extra: d.notes ? [str(d.notes)] : [],
        };
      case 'followup_scheduled':
        return {
          text: t('timeline.followupScheduled', {
            actor,
            title: str(d.title),
            due: format.dateTime(d.due_at as string),
          }),
        };
      case 'followup_completed':
        return { text: t('timeline.followupDone', { actor, title: str(d.title) }) };
      case 'attachment_added':
        return { text: t('timeline.attachment', { actor, file: str(d.file_name) }) };
      case 'enquiry_deleted':
        return { text: t('timeline.deleted', { actor }) };
      case 'enquiry_restored':
        return { text: t('timeline.restored') };
      case 'auto_call':
        return {
          text: t(`timeline.autoCall.${str(d.status)}`, {
            agent: str(d.agent),
            defaultValue: t('timeline.autoCall.other', { status: str(d.status) }),
          }),
          extra: d.error ? [str(d.error)] : undefined,
        };
      default:
        return { text: t('timeline.other', { actor, type: event.type }) };
    }
  };
}

const PAGE = 50;

export function ActivityTimeline({ enquiryId }: { enquiryId: number }) {
  const { t } = useTranslation();
  const format = useDateFormat();
  const describe = useDescribe();
  const [pageSize, setPageSize] = useState(PAGE);
  const timeline = useTimeline(enquiryId, pageSize);

  if (timeline.isPending) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }
  const events = timeline.data?.results ?? [];
  if (!events.length) {
    return <EmptyState icon={History} title={t('timeline.empty')} className="py-10" />;
  }

  return (
    <div>
      <ol className="relative space-y-5 before:absolute before:top-2 before:bottom-2 before:left-3.5 before:w-px before:bg-border">
        {events.map((event) => {
          const Icon = ICONS[event.type] ?? FileText;
          const { text, extra } = describe(event);
          return (
            <li key={event.id} className="relative flex gap-3">
              <span className="z-10 flex size-7 shrink-0 items-center justify-center rounded-full border bg-surface text-fg-muted">
                <Icon className="size-3.5" aria-hidden />
              </span>
              <div className="min-w-0 flex-1 pt-0.5">
                <p className="text-[13px]">{text}</p>
                {extra?.map((line, i) => (
                  <p
                    key={i}
                    className="mt-0.5 text-[13px] break-words whitespace-pre-line text-fg-muted"
                  >
                    {line}
                  </p>
                ))}
                <time
                  className="mt-0.5 block text-xs text-fg-subtle tabular-nums"
                  dateTime={event.created_at}
                >
                  {format.dateTime(event.created_at)}
                </time>
              </div>
            </li>
          );
        })}
      </ol>
      {(timeline.data?.count ?? 0) > events.length && (
        <Button
          variant="ghost"
          size="sm"
          className="mt-4"
          loading={timeline.isFetching}
          onClick={() => setPageSize((n) => Math.min(n + PAGE, 200))}
          disabled={pageSize >= 200}
        >
          {t('timeline.showMore')}
        </Button>
      )}
    </div>
  );
}
