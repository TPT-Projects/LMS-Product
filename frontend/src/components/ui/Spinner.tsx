import { Loader2 } from 'lucide-react';

import { cn } from '@/lib/cn';

export function Spinner({ className }: { className?: string }) {
  return <Loader2 aria-hidden className={cn('size-5 animate-spin text-current', className)} />;
}

export function FullPageSpinner() {
  return (
    <div className="flex min-h-dvh items-center justify-center text-fg-muted" role="status">
      <Spinner className="size-6" />
    </div>
  );
}
