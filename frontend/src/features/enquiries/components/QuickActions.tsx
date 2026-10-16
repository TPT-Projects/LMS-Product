import { Mail, MessageCircle, Phone, StickyNote } from 'lucide-react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { cn } from '@/lib/cn';
import type { EnquiryDetail } from '@/types/crm';

import { whatsappNumber } from '../format';

function Action({
  href,
  onClick,
  icon,
  label,
  disabled,
}: {
  href?: string;
  onClick?: () => void;
  icon: ReactNode;
  label: string;
  disabled?: boolean;
}) {
  const className = cn(
    'flex min-w-0 flex-1 flex-col items-center gap-1 rounded-lg px-2 py-2 text-xs font-medium sm:flex-none sm:flex-row sm:gap-2 sm:px-3 sm:text-[13px]',
    disabled ? 'pointer-events-none text-fg-subtle opacity-50' : 'text-fg hover:bg-muted',
  );
  if (href && !disabled) {
    return (
      <a
        href={href}
        className={className}
        target={href.startsWith('http') ? '_blank' : undefined}
        rel="noreferrer"
      >
        {icon}
        <span className="truncate">{label}</span>
      </a>
    );
  }
  return (
    <button
      type="button"
      className={className}
      onClick={onClick}
      disabled={disabled}
      aria-disabled={disabled}
    >
      {icon}
      <span className="truncate">{label}</span>
    </button>
  );
}

/** Call, WhatsApp, Email and Add note: one tap each, also on phones. */
export function QuickActions({
  enquiry,
  onAddNote,
  canEdit,
}: {
  enquiry: EnquiryDetail;
  onAddNote: () => void;
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const phone = enquiry.phone_e164 || enquiry.contact.phone_e164 || '';
  const email = enquiry.email || enquiry.contact.email || '';
  return (
    <div
      role="toolbar"
      aria-label={t('quick.label')}
      className="flex gap-1 rounded-xl border bg-surface p-1"
    >
      <Action
        href={phone ? `tel:${phone}` : undefined}
        disabled={!phone}
        icon={<Phone className="size-4 text-success" />}
        label={t('quick.call')}
      />
      <Action
        href={phone ? `https://wa.me/${whatsappNumber(phone)}` : undefined}
        disabled={!phone}
        icon={<MessageCircle className="size-4 text-success" />}
        label={t('quick.whatsapp')}
      />
      <Action
        href={email ? `mailto:${email}` : undefined}
        disabled={!email}
        icon={<Mail className="size-4 text-accent" />}
        label={t('quick.email')}
      />
      <Action
        onClick={onAddNote}
        disabled={!canEdit}
        icon={<StickyNote className="size-4 text-warning" />}
        label={t('quick.note')}
      />
    </div>
  );
}
