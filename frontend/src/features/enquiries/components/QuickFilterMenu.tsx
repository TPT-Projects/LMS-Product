import { Check, ChevronDown } from 'lucide-react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui';
import { cn } from '@/lib/cn';

export interface QuickOption {
  value: string;
  label: ReactNode;
}

interface Props {
  label: string;
  options: QuickOption[];
  selected: string[];
  onChange: (values: string[]) => void;
}

/** A small "Status ▾" style multi-select used in the list toolbar. */
export function QuickFilterMenu({ label, options, selected, onChange }: Props) {
  const { t } = useTranslation();
  const active = selected.length > 0;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          'inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border px-2.5 text-[13px] font-medium whitespace-nowrap',
          active
            ? 'border-accent bg-accent-soft text-accent'
            : 'bg-surface text-fg-muted hover:bg-subtle',
        )}
      >
        {label}
        {active && (
          <span className="rounded bg-accent px-1 text-[11px] text-accent-fg">
            {selected.length}
          </span>
        )}
        <ChevronDown className="size-3.5" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="max-h-80 overflow-y-auto">
        {options.map((option) => {
          const on = selected.includes(option.value);
          return (
            <DropdownMenuItem
              key={option.value}
              role="menuitemcheckbox"
              aria-checked={on}
              onSelect={(event) => {
                event.preventDefault(); // keep the menu open for multi-select
                onChange(
                  on ? selected.filter((v) => v !== option.value) : [...selected, option.value],
                );
              }}
            >
              <span
                className={cn(
                  'flex size-4 shrink-0 items-center justify-center rounded border',
                  on && 'border-accent bg-accent text-accent-fg',
                )}
              >
                {on && <Check className="size-3" aria-hidden />}
              </span>
              <span className="min-w-0 flex-1">{option.label}</span>
            </DropdownMenuItem>
          );
        })}
        {active && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => onChange([])}>{t('filters.clear')}</DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
