import type { ReactNode } from 'react';

import { Logo } from './Logo';

interface AuthLayoutProps {
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}

/** Centered card used by login, sign up, invite and password pages. */
export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="flex min-h-dvh flex-col bg-subtle px-4 py-10 sm:justify-center">
      <div className="mx-auto w-full max-w-sm">
        <Logo className="mb-8 justify-center" />
        <div className="rounded-2xl border bg-surface p-6 sm:p-7">
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1.5 text-[13px] text-fg-muted">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
        {footer && <div className="mt-5 text-center text-[13px] text-fg-muted">{footer}</div>}
      </div>
    </div>
  );
}
