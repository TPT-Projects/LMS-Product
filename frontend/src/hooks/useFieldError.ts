import { useCallback } from 'react';
import type { FieldError } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

/**
 * Message for a form field error.
 * Client-side (zod) messages are i18n keys and get translated; server
 * messages (type "server") are already human-readable and shown as-is.
 */
export function useFieldError() {
  const { t } = useTranslation();
  return useCallback(
    (error: FieldError | undefined): string | undefined => {
      if (!error?.message) return undefined;
      return error.type === 'server' ? error.message : t(error.message);
    },
    [t],
  );
}
