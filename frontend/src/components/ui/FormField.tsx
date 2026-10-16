import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from 'react';

import { cn } from '@/lib/cn';

interface FormFieldProps {
  label: ReactNode;
  error?: string;
  hint?: ReactNode;
  className?: string;
  /** Optional element shown at the right of the label (e.g. "Forgot password?"). */
  labelAside?: ReactNode;
  children: ReactElement<{ id?: string; invalid?: boolean; 'aria-describedby'?: string }>;
}

/** Label + control + hint/error, wired up for screen readers. */
export function FormField({ label, error, hint, className, labelAside, children }: FormFieldProps) {
  const id = useId();
  const messageId = `${id}-message`;
  const control = isValidElement(children)
    ? cloneElement(children, {
        id,
        invalid: Boolean(error),
        'aria-describedby': error || hint ? messageId : undefined,
      })
    : children;

  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-[13px] font-medium text-fg">
          {label}
        </label>
        {labelAside}
      </div>
      {control}
      {error ? (
        <p id={messageId} role="alert" className="text-[13px] text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={messageId} className="text-[13px] text-fg-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
