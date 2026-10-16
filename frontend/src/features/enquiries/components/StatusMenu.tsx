import { ChevronDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import {
  DropdownMenu,
  DropdownMenuCheckItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui';
import { useStatuses } from '@/features/statuses/api';
import { StatusBadge } from '@/features/statuses/components/StatusBadge';
import type { StatusRef } from '@/types/crm';

interface StatusMenuProps {
  status: StatusRef;
  onChange: (statusId: number, status?: StatusRef) => void;
  disabled?: boolean;
}

/** The status badge; click to change status. */
export function StatusMenu({ status, onChange, disabled }: StatusMenuProps) {
  const { t } = useTranslation();
  const statuses = useStatuses();

  if (disabled) return <StatusBadge name={status.name} color={status.color} />;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={t('enquiries.changeStatus', { status: status.name })}
        className="inline-flex items-center gap-1 rounded-md p-0.5 hover:bg-muted"
        onClick={(e) => e.stopPropagation()}
      >
        <StatusBadge name={status.name} color={status.color} />
        <ChevronDown className="size-3.5 text-fg-subtle" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent onClick={(e) => e.stopPropagation()}>
        {statuses.data?.map((s) => (
          <DropdownMenuCheckItem
            key={s.id}
            checked={s.id === status.id}
            onSelect={() => s.id !== status.id && onChange(s.id, s)}
          >
            <StatusBadge name={s.name} color={s.color} />
          </DropdownMenuCheckItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
