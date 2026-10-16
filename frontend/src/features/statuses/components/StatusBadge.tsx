import { cn } from '@/lib/cn';
import type { StatusColor } from '@/types/crm';

import { STATUS_COLOR_CLASSES } from '../colors';

export function StatusBadge({
  name,
  color,
  className,
}: {
  name: string;
  color: StatusColor;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex max-w-full items-center gap-1.5 rounded-md px-1.5 py-0.5 text-xs font-medium',
        STATUS_COLOR_CLASSES[color].badge,
        className,
      )}
    >
      <span className={cn('size-1.5 shrink-0 rounded-full', STATUS_COLOR_CLASSES[color].dot)} />
      <span className="truncate">{name}</span>
    </span>
  );
}
