import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui';

import type { AppConnectionState } from '../api';
import type { AppDef } from '../catalog';

const TONE = {
  connected: 'success',
  error: 'danger',
  needs_setup: 'warning',
  not_connected: 'neutral',
} as const;

export function AppStatusBadge({ app, status }: { app: AppDef; status?: AppConnectionState }) {
  const { t } = useTranslation();
  if (app.availability === 'coming_soon') return <Badge>{t('apps.status.coming_soon')}</Badge>;
  const state = status ?? 'not_connected';
  if (state === 'not_connected') return null;
  return <Badge tone={TONE[state]}>{t(`apps.status.${state}`)}</Badge>;
}
