import { useTranslation } from 'react-i18next';

import { Checkbox, DateInput, Input, Select } from '@/components/ui';
import type { CustomField, CustomValue } from '@/types/crm';

import { displayOption } from '../values';

interface CustomFieldInputProps {
  field: CustomField;
  value: CustomValue | undefined;
  onChange: (value: CustomValue) => void;
  id?: string;
  invalid?: boolean;
  'aria-describedby'?: string;
}

/** The right control for each custom field type. Values are what the API expects. */
export function CustomFieldInput({ field, value, onChange, ...aria }: CustomFieldInputProps) {
  const { t } = useTranslation();

  switch (field.type) {
    case 'number':
    case 'currency':
      return (
        <Input
          {...aria}
          inputMode="decimal"
          value={value === null || value === undefined ? '' : String(value)}
          onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
          placeholder={field.type === 'currency' ? '₹' : undefined}
        />
      );
    case 'date':
      return (
        <DateInput
          {...aria}
          value={(value as string | null) ?? ''}
          onChange={(e) => onChange(e.target.value || null)}
        />
      );
    case 'dropdown':
      return (
        <Select
          {...aria}
          value={(value as string | null) ?? ''}
          onChange={(e) => onChange(e.target.value || null)}
        >
          <option value="">{t('common.choose')}</option>
          {field.options.map((option) => (
            <option key={option} value={option}>
              {displayOption(option)}
            </option>
          ))}
        </Select>
      );
    case 'multi_select': {
      const selected = Array.isArray(value) ? value : [];
      return (
        <div
          id={aria.id}
          role="group"
          aria-describedby={aria['aria-describedby']}
          className="flex flex-wrap gap-x-4 gap-y-2 rounded-lg border px-3 py-2"
        >
          {field.options.map((option) => (
            <label key={option} className="flex items-center gap-2">
              <Checkbox
                checked={selected.includes(option)}
                onChange={(e) =>
                  onChange(
                    e.target.checked ? [...selected, option] : selected.filter((v) => v !== option),
                  )
                }
              />
              {displayOption(option)}
            </label>
          ))}
        </div>
      );
    }
    case 'checkbox':
      return (
        <label className="flex h-9 items-center gap-2">
          <Checkbox
            id={aria.id}
            checked={value === true}
            onChange={(e) => onChange(e.target.checked)}
          />
          {t('common.yes')}
        </label>
      );
    default:
      return (
        <Input
          {...aria}
          value={(value as string | null) ?? ''}
          onChange={(e) => onChange(e.target.value)}
          maxLength={1000}
        />
      );
  }
}
