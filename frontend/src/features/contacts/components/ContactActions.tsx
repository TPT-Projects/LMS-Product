import { ExternalLink, Mail, MessageCircle, MoreHorizontal, Phone } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui';
import { whatsappNumber } from '@/features/enquiries/format';
import { paths } from '@/routes/paths';
import type { Contact } from '@/types/crm';

/** Contacts are read-only, so their actions only reach out or open the record. */
export function ContactActions({ contact }: { contact: Contact }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <div onClick={(e) => e.stopPropagation()} className="inline-flex">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label={t('common.actionsFor', { name: contact.name || contact.phone_e164 || '' })}
          >
            <MoreHorizontal className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {contact.phone_e164 && (
            <>
              <DropdownMenuItem asChild>
                <a href={`tel:${contact.phone_e164}`}>
                  <Phone className="size-4" aria-hidden /> {t('quick.call')}
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <a
                  href={`https://wa.me/${whatsappNumber(contact.phone_e164)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <MessageCircle className="size-4" aria-hidden /> {t('quick.whatsapp')}
                </a>
              </DropdownMenuItem>
            </>
          )}
          {contact.email && (
            <DropdownMenuItem asChild>
              <a href={`mailto:${contact.email}`}>
                <Mail className="size-4" aria-hidden /> {t('quick.email')}
              </a>
            </DropdownMenuItem>
          )}
          <DropdownMenuItem onSelect={() => navigate(`${paths.contacts}/${contact.id}`)}>
            <ExternalLink className="size-4" aria-hidden /> {t('actions.open')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
