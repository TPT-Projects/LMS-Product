import type { CustomField, CustomValue } from '@/types/crm';

/**
 * Answers are stored exactly as received (e.g. "yes,_5th_july"). For display,
 * underscores become spaces (spec section 3, rule 5). Never edit the stored value.
 */
export function displayOption(value: string): string {
  return value.replaceAll('_', ' ');
}

const numberFormat = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 });

export function formatCustomValue(
  field: CustomField,
  value: CustomValue | undefined,
  yesNo: { yes: string; no: string },
): string {
  if (value === null || value === undefined || value === '') return '—';
  switch (field.type) {
    case 'number':
      return numberFormat.format(Number(value));
    case 'currency':
      return `₹${numberFormat.format(Number(value))}`;
    case 'checkbox':
      return value ? yesNo.yes : yesNo.no;
    case 'dropdown':
      return displayOption(String(value));
    case 'multi_select':
      return Array.isArray(value) ? value.map(displayOption).join(' · ') : String(value);
    default:
      return String(value);
  }
}

/** Value to send to the API for an empty input. */
export function emptyValue(field: CustomField): CustomValue {
  return field.type === 'multi_select' ? [] : field.type === 'checkbox' ? false : null;
}
