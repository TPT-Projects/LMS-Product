import * as Radix from '@radix-ui/react-tabs';
import type { ComponentPropsWithoutRef } from 'react';

import { cn } from '@/lib/cn';

export const Tabs = Radix.Root;

export function TabsList({ className, ...props }: ComponentPropsWithoutRef<typeof Radix.List>) {
  return (
    <Radix.List
      className={cn(
        '-mb-px scrollbar-none flex gap-1 overflow-x-auto overflow-y-hidden border-b',
        className,
      )}
      {...props}
    />
  );
}

export function TabsTrigger({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof Radix.Trigger>) {
  return (
    <Radix.Trigger
      className={cn(
        'inline-flex h-10 shrink-0 items-center gap-1.5 border-b-2 border-transparent px-3 text-[13px] font-medium whitespace-nowrap text-fg-muted transition-colors hover:text-fg',
        'data-[state=active]:border-accent data-[state=active]:text-fg',
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof Radix.Content>) {
  return <Radix.Content className={cn('pt-4 focus:outline-none', className)} {...props} />;
}
