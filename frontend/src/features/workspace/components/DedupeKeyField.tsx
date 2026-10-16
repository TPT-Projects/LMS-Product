import type { UseFormRegisterReturn } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import type { DedupeKey } from '@/types/auth';

const OPTIONS: DedupeKey[] = ['phone', 'email'];

/** How duplicate contacts are matched: by phone (default) or by email. */
export function DedupeKeyField({
  register,
  disabled,
}: {
  register: UseFormRegisterReturn;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <fieldset className="space-y-1.5" disabled={disabled}>
      <legend className="text-[13px] font-medium">{t('fields.dedupeKey')}</legend>
      <div className="grid grid-cols-2 gap-2">
        {OPTIONS.map((option) => (
          <label
            key={option}
            className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 has-checked:border-accent has-checked:bg-accent-soft"
          >
            <input type="radio" value={option} className="accent-accent" {...register} />
            <span>{t(`workspace.dedupe.${option}`)}</span>
          </label>
        ))}
      </div>
      <p className="text-[13px] text-fg-muted">{t('workspace.dedupe.hint')}</p>
    </fieldset>
  );
}
