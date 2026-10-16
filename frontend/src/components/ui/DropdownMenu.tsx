import * as Radix from '@radix-ui/react-dropdown-menu';
import { Check } from 'lucide-react';
import type { ComponentPropsWithoutRef, ReactNode } from 'react';

import { cn } from '@/lib/cn';

export const DropdownMenu = Radix.Root;
export const DropdownMenuTrigger = Radix.Trigger;

export function DropdownMenuContent({
  className,
  align = 'start',
  sideOffset = 6,
  ...props
}: ComponentPropsWithoutRef<typeof Radix.Content>) {
  return (
    <Radix.Portal>
      <Radix.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          'z-50 min-w-48 animate-fade-in rounded-xl border bg-surface p-1 shadow-popover',
          className,
        )}
        {...props}
      />
    </Radix.Portal>
  );
}

export function DropdownMenuItem({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof Radix.Item>) {
  return (
    <Radix.Item
      className={cn(
        'flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] outline-none select-none',
        'data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-muted',
        className,
      )}
      {...props}
    />
  );
}

export function DropdownMenuCheckItem({
  checked,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof Radix.Item> & { checked: boolean; children: ReactNode }) {
  return (
    <DropdownMenuItem {...props}>
      <span className="flex-1">{children}</span>
      {checked && <Check className="size-4 text-accent" aria-hidden />}
    </DropdownMenuItem>
  );
}

export function DropdownMenuLabel({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof Radix.Label>) {
  return (
    <Radix.Label
      className={cn('px-2.5 pt-1.5 pb-1 text-xs font-medium text-fg-subtle', className)}
      {...props}
    />
  );
}

export function DropdownMenuSeparator() {
  return <Radix.Separator className="my-1 h-px bg-border" />;
}
