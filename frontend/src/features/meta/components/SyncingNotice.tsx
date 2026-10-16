import { useIsMutating } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { Spinner } from '@/components/ui';

import { SYNC_MUTATION_KEY } from '../api';

/** Shown while leads are being synced in the background (e.g. right after choosing a Page). */
export function SyncingNotice({ className }: { className?: string }) {
  const { t } = useTranslation();
  const syncing = useIsMutating({ mutationKey: SYNC_MUTATION_KEY }) > 0;
  if (!syncing) return null;
  return (
    <div
      role="status"
      className={`flex items-center gap-2 rounded-xl bg-accent-soft px-3 py-2 text-[13px] ${className ?? ''}`}
    >
      <Spinner className="size-4 shrink-0" />
      {t('meta.autoSync.syncing')}
    </div>
  );
}
