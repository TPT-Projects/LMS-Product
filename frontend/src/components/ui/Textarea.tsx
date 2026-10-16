import { forwardRef, type TextareaHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, invalid, rows = 3, ...props },
  ref,
) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      aria-invalid={invalid || undefined}
      className={cn(
        'block w-full resize-y rounded-lg border bg-surface px-3 py-2 text-fg placeholder:text-fg-subtle',
        'focus:border-ring focus:ring-2 focus:ring-ring/20 focus:outline-none disabled:opacity-60',
        invalid && 'border-danger',
        className,
      )}
      {...props}
    />
  );
});
