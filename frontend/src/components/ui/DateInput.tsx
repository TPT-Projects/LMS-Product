import { CalendarDays } from 'lucide-react';
import { forwardRef, useRef, type ChangeEvent } from 'react';

import { maskDisplayDate } from '@/lib/dates';

import { Input, type InputProps } from './Input';

/** DD/MM/YYYY -> YYYY-MM-DD for the native calendar (empty when not a full date). */
function toIso(display: string): string {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(display);
  return match ? `${match[3]}-${match[2]}-${match[1]}` : '';
}

/**
 * Date field that always shows DD/MM/YYYY (spec: dates in DD/MM/YYYY everywhere,
 * including date pickers), whatever the browser's locale. Type the date, or pick it
 * from the calendar button.
 */
export const DateInput = forwardRef<HTMLInputElement, Omit<InputProps, 'type'>>(function DateInput(
  { onChange, className, ...props },
  forwarded,
) {
  const text = useRef<HTMLInputElement | null>(null);
  const picker = useRef<HTMLInputElement | null>(null);

  /** Put the picked date in the text field as if typed, so the form's onChange runs. */
  const pick = (iso: string) => {
    const [year, month, day] = iso.split('-');
    if (!text.current || !year || !month || !day) return;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
    setter?.call(text.current, `${day}/${month}/${year}`);
    text.current.dispatchEvent(new Event('input', { bubbles: true }));
  };

  return (
    <div className="relative">
      <Input
        ref={(node) => {
          text.current = node;
          if (typeof forwarded === 'function') forwarded(node);
          else if (forwarded) forwarded.current = node;
        }}
        type="text"
        inputMode="numeric"
        placeholder="DD/MM/YYYY"
        maxLength={10}
        autoComplete="off"
        className={['pr-10', className].filter(Boolean).join(' ')}
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          event.target.value = maskDisplayDate(event.target.value);
          onChange?.(event);
        }}
        {...props}
      />
      <button
        type="button"
        aria-label="Open calendar"
        disabled={props.disabled}
        onClick={() => {
          const native = picker.current;
          if (!native) return;
          native.value = toIso(text.current?.value ?? '');
          if (typeof native.showPicker === 'function') native.showPicker();
          else native.click();
        }}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-fg-muted hover:text-fg disabled:opacity-50"
      >
        <CalendarDays className="size-4" aria-hidden />
      </button>
      <input
        ref={picker}
        type="date"
        tabIndex={-1}
        aria-hidden
        className="pointer-events-none absolute right-0 bottom-0 h-0 w-0 opacity-0"
        onChange={(e) => pick(e.target.value)}
      />
    </div>
  );
});
