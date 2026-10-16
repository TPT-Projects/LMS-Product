import { isAxiosError } from 'axios';
import type { FieldValues, Path, UseFormSetError } from 'react-hook-form';

import i18n from '@/lib/i18n';
import type { ApiErrorBody } from '@/types/api';

/** An error whose message is already written for the user (e.g. Facebook's login reason). */
export class UserFacingError extends Error {}

/** A readable message for any error thrown by the API client. */
export function getErrorMessage(error: unknown): string {
  if (error instanceof UserFacingError && error.message) return error.message;
  if (isAxiosError<ApiErrorBody>(error)) {
    if (!error.response) return i18n.t('errors.network');
    if (error.response.data?.detail) return error.response.data.detail;
    if (error.response.status >= 500) return i18n.t('errors.server');
  }
  return i18n.t('errors.unknown');
}

/**
 * Copy field errors from the API onto a react-hook-form form.
 * Returns the general message (for errors not tied to a visible field).
 */
export function applyApiErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
): string | null {
  if (isAxiosError<ApiErrorBody>(error) && error.response?.data?.errors) {
    let unmatched = false;
    for (const [field, messages] of Object.entries(error.response.data.errors)) {
      if ((fields as readonly string[]).includes(field) && Array.isArray(messages)) {
        setError(field as Path<T>, { type: 'server', message: messages[0] });
      } else {
        unmatched = true;
      }
    }
    return unmatched ? getErrorMessage(error) : null;
  }
  return getErrorMessage(error);
}

/** Messages for a grouped field, e.g. nestedErrors(err, 'custom_fields') -> { budget: '…' }. */
export function nestedErrors(error: unknown, key: string): Record<string, string> {
  if (!isAxiosError<ApiErrorBody>(error)) return {};
  const group = error.response?.data?.errors?.[key];
  if (!group || Array.isArray(group)) return {};
  return Object.fromEntries(Object.entries(group).map(([k, messages]) => [k, messages[0] ?? '']));
}
