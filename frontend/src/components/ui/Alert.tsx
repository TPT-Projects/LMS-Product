import { AlertCircle, CheckCircle2, Info } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@/lib/cn';

type Tone = 'info' | 'success' | 'danger';

const tones: Record<Tone, { box: string; Icon: typeof Info }> = {
  info: { box: 'bg-accent-soft text-fg', Icon: Info },
  success: { box: 'bg-success-soft text-fg', Icon: CheckCircle2 },
  danger: { box: 'bg-danger-soft text-danger', Icon: AlertCircle },
};

export function Alert({
  tone = 'info',
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  const { box, Icon } = tones[tone];
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={cn('flex gap-2.5 rounded-lg px-3 py-2.5', box, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 text-[13px] leading-5">{children}</div>
    </div>
  );
}
