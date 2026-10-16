import { cn } from '@/lib/cn';

import type { AppDef } from '../catalog';

const SIZES = {
  sm: 'size-8 rounded-lg text-[13px] [&_svg]:size-4',
  md: 'size-11 rounded-xl text-base [&_svg]:size-5',
  lg: 'size-16 rounded-2xl text-2xl [&_svg]:size-8',
} as const;

/** Brand-coloured tile with an icon or short mark (not the official logo artwork). */
export function AppLogo({ app, size = 'md' }: { app: AppDef; size?: keyof typeof SIZES }) {
  const Icon = app.logo.icon;
  return (
    <span
      aria-hidden
      className={cn(
        'flex shrink-0 items-center justify-center font-bold text-white shadow-sm',
        SIZES[size],
      )}
      style={{ backgroundColor: app.logo.bg }}
    >
      {Icon ? <Icon /> : app.logo.text}
    </span>
  );
}
