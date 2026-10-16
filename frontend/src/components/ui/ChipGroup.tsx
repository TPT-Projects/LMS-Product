import { cn } from '@/lib/cn';

export interface ChipChoice {
  value: string;
  label: string;
}

/** Toggle chips for picking several values (filters, owners). */
export function ChipGroup({
  choices,
  selected,
  onChange,
}: {
  choices: ChipChoice[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {choices.map((choice) => {
        const on = selected.includes(choice.value);
        return (
          <button
            key={choice.value}
            type="button"
            aria-pressed={on}
            onClick={() =>
              onChange(
                on ? selected.filter((v) => v !== choice.value) : [...selected, choice.value],
              )
            }
            className={cn(
              'rounded-md border px-2 py-1 text-[13px] transition-colors',
              on ? 'border-accent bg-accent-soft text-accent' : 'text-fg-muted hover:bg-muted',
            )}
          >
            {choice.label}
          </button>
        );
      })}
    </div>
  );
}
