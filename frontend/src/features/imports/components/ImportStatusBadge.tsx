import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui';

import type { ImportStatus } from '../api';

const TONE = {
  uploaded: 'neutral',
  mapped: 'neutral',
  queued: 'accent',
  running: 'accent',
  completed: 'success',
  completed_with_errors: 'warning',
  failed: 'danger',
} as const;

export function ImportStatusBadge({ status }: { status: ImportStatus }) {
  const { t } = useTranslation();
  return <Badge tone={TONE[status]}>{t(`imports.statuses.${status}`)}</Badge>;
}
