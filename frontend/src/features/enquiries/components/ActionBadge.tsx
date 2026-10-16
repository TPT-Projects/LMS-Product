import {
  CalendarCheck,
  CalendarClock,
  CalendarPlus,
  ExternalLink,
  Mail,
  MessageCircle,
  Phone,
  PhoneCall,
  StickyNote,
} from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import {
  Dialog,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui';
import { useAuth, useSession } from '@/features/auth/useAuth';
import { cn } from '@/lib/cn';
import { formatDate, formatDateTime } from '@/lib/dates';
import { paths } from '@/routes/paths';
import type { Enquiry } from '@/types/crm';

import { useToggleFollowUp } from '../api';
import { whatsappNumber } from '../format';
import { CallForm } from './forms/CallForm';
import { FollowUpForm } from './forms/FollowUpForm';
import { NoteForm } from './forms/NoteForm';
import { RescheduleForm } from './forms/RescheduleForm';

type Tone = 'overdue' | 'today' | 'upcoming' | 'missed' | 'called' | 'none';
type DialogKind = 'followup' | 'call' | 'note' | 'reschedule' | null;

const TONES: Record<Tone, string> = {
  overdue: 'border-danger/30 bg-danger-soft text-danger',
  today: 'border-warning/30 bg-warning-soft text-warning',
  upcoming: 'border-accent/30 bg-accent-soft text-accent',
  missed: 'border-danger/40 bg-danger-soft text-danger',
  called: 'border-success/30 bg-success-soft text-success',
  none: 'border-dashed text-fg-muted hover:border-solid hover:text-fg',
};

/** Today / overdue / upcoming, judged by the calendar day in the workspace timezone. */
function toneFor(dueAt: string | undefined, tz: string): Tone {
  if (!dueAt) return 'none';
  const due = new Date(dueAt);
  if (due.getTime() < Date.now()) return 'overdue';
  return formatDate(due, tz) === formatDate(new Date(), tz) ? 'today' : 'upcoming';
}

/**
 * The Action column: shows the next step (overdue / today / upcoming follow-up,
 * or "Schedule call") and opens the quick actions for that enquiry.
 */
export function ActionBadge({ enquiry }: { enquiry: Enquiry }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const { workspace } = useSession();
  const tz = workspace.timezone;
  const canEdit = can('edit_enquiries');
  const toggle = useToggleFollowUp(enquiry.id);
  const [dialog, setDialog] = useState<DialogKind>(null);

  const next = enquiry.next_followup;
  const notConnected = ['no_answer', 'busy', 'failed'].includes(next?.auto_call_status ?? '');
  const lastCall = !next ? enquiry.last_call : null;
  const lastConnected = lastCall?.outcome === 'connected';
  const tone: Tone = notConnected
    ? 'missed'
    : lastCall
      ? lastConnected
        ? 'called'
        : 'missed'
      : toneFor(next?.due_at, tz);
  const phone = enquiry.phone_e164;

  const label = !next
    ? lastCall
      ? t(lastConnected ? 'actions.called' : 'actions.lastNotConnected', {
          when:
            formatDateTime(lastCall.at, tz).slice(0, 5) +
            ' ' +
            formatDateTime(lastCall.at, tz).slice(-5),
        })
      : t('actions.scheduleCall')
    : notConnected
      ? t('actions.notConnected')
      : tone === 'overdue'
        ? t('actions.overdue', { title: next.title })
        : tone === 'today'
          ? t('actions.today', { time: formatDateTime(next.due_at, tz).slice(-5) })
          : t('actions.upcoming', { date: formatDate(next.due_at, tz).slice(0, 5) });

  const titles: Record<Exclude<DialogKind, null>, string> = {
    followup: t('actions.scheduleTitle', { name: enquiry.name || t('enquiries.noName') }),
    call: t('actions.logCallTitle', { name: enquiry.name || t('enquiries.noName') }),
    note: t('actions.noteTitle', { name: enquiry.name || t('enquiries.noName') }),
    reschedule: t('followups.rescheduleTitle'),
  };

  return (
    // Clicks inside must not open the row.
    <div onClick={(e) => e.stopPropagation()} className="inline-flex">
      <DropdownMenu>
        <DropdownMenuTrigger
          className={cn(
            'inline-flex max-w-48 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium whitespace-nowrap transition-colors',
            TONES[tone],
          )}
          title={next ? `${next.title} · ${formatDateTime(next.due_at, tz)}` : undefined}
        >
          {next || lastCall ? (
            <PhoneCall className="size-3.5 shrink-0" aria-hidden />
          ) : (
            <CalendarPlus className="size-3.5 shrink-0" aria-hidden />
          )}
          <span className="truncate">{label}</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          {next && (
            <>
              <DropdownMenuLabel className="truncate">
                {next.title} · {formatDateTime(next.due_at, tz)}
              </DropdownMenuLabel>
              {canEdit && next.id && notConnected && (
                <DropdownMenuItem onSelect={() => setDialog('reschedule')}>
                  <CalendarClock className="size-4" aria-hidden /> {t('followups.reschedule')}
                </DropdownMenuItem>
              )}
              {canEdit && next.id && (
                <DropdownMenuItem
                  onSelect={() => toggle.mutate({ followupId: next.id!, done: true })}
                >
                  <CalendarCheck className="size-4" aria-hidden /> {t('actions.markDone')}
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
            </>
          )}
          {canEdit && (
            <>
              <DropdownMenuItem onSelect={() => setDialog('followup')}>
                <CalendarPlus className="size-4" aria-hidden /> {t('actions.scheduleCall')}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setDialog('call')}>
                <PhoneCall className="size-4" aria-hidden /> {t('actions.logCall')}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setDialog('note')}>
                <StickyNote className="size-4" aria-hidden /> {t('actions.addNote')}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          )}
          {phone && (
            <>
              <DropdownMenuItem asChild>
                <a href={`tel:${phone}`}>
                  <Phone className="size-4" aria-hidden /> {t('quick.call')}
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <a href={`https://wa.me/${whatsappNumber(phone)}`} target="_blank" rel="noreferrer">
                  <MessageCircle className="size-4" aria-hidden /> {t('quick.whatsapp')}
                </a>
              </DropdownMenuItem>
            </>
          )}
          {enquiry.email && (
            <DropdownMenuItem asChild>
              <a href={`mailto:${enquiry.email}`}>
                <Mail className="size-4" aria-hidden /> {t('quick.email')}
              </a>
            </DropdownMenuItem>
          )}
          <DropdownMenuItem onSelect={() => navigate(`${paths.enquiries}/${enquiry.id}`)}>
            <ExternalLink className="size-4" aria-hidden /> {t('actions.open')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog
        open={dialog !== null}
        onOpenChange={(open) => !open && setDialog(null)}
        title={dialog ? titles[dialog] : ''}
      >
        {dialog === 'followup' && (
          <FollowUpForm
            enquiryId={enquiry.id}
            defaultTitle={t('actions.defaultCallTitle')}
            defaultAssigneeId={enquiry.primary_owner?.id}
            autoFocus
            onDone={() => setDialog(null)}
          />
        )}
        {dialog === 'call' && <CallForm enquiryId={enquiry.id} onDone={() => setDialog(null)} />}
        {dialog === 'reschedule' && next?.id && (
          <RescheduleForm
            enquiryId={enquiry.id}
            followupId={next.id}
            onDone={() => setDialog(null)}
          />
        )}
        {dialog === 'note' && (
          <NoteForm enquiryId={enquiry.id} autoFocus onDone={() => setDialog(null)} />
        )}
      </Dialog>
    </div>
  );
}
