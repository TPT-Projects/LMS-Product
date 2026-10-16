import { ChevronDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import {
  DropdownMenu,
  DropdownMenuCheckItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui';
import type { Role } from '@/types/auth';

import { RoleBadge } from './RoleBadge';

interface RoleMenuProps {
  role: Role;
  options: Role[];
  onChange: (role: Role) => void;
  disabled?: boolean;
}

/** The role badge, which opens a menu to change the role. */
export function RoleMenu({ role, options, onChange, disabled }: RoleMenuProps) {
  const { t } = useTranslation();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={disabled}
        aria-label={t('users.changeRole')}
        className="inline-flex items-center gap-1 rounded-md p-0.5 hover:bg-muted disabled:opacity-60"
      >
        <RoleBadge role={role} />
        <ChevronDown className="size-3.5 text-fg-subtle" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {options.map((option) => (
          <DropdownMenuCheckItem
            key={option}
            checked={option === role}
            onSelect={() => option !== role && onChange(option)}
          >
            {t(`roles.${option}`)}
          </DropdownMenuCheckItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
