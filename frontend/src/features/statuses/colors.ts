import type { StatusColor } from '@/types/crm';

export const STATUS_COLORS: StatusColor[] = ['gray', 'blue', 'amber', 'violet', 'green', 'red'];

/** Status colours (light and dark). Full class names so Tailwind can find them. */
export const STATUS_COLOR_CLASSES: Record<StatusColor, { badge: string; dot: string }> = {
  gray: { badge: 'bg-muted text-fg-muted', dot: 'bg-fg-subtle' },
  blue: { badge: 'bg-blue-500/12 text-blue-700 dark:text-blue-300', dot: 'bg-blue-500' },
  amber: { badge: 'bg-amber-500/15 text-amber-700 dark:text-amber-300', dot: 'bg-amber-500' },
  violet: { badge: 'bg-violet-500/12 text-violet-700 dark:text-violet-300', dot: 'bg-violet-500' },
  green: { badge: 'bg-green-500/12 text-green-700 dark:text-green-300', dot: 'bg-green-500' },
  red: { badge: 'bg-red-500/12 text-red-700 dark:text-red-300', dot: 'bg-red-500' },
};
