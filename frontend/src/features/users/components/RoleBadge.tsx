import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui';
import type { Role } from '@/types/auth';

const TONE = {
  owner: 'accent',
  admin: 'accent',
  manager: 'success',
  agent: 'neutral',
  viewer: 'neutral',
} as const;

export function RoleBadge({ role }: { role: Role }) {
  const { t } = useTranslation();
  return <Badge tone={TONE[role]}>{t(`roles.${role}`)}</Badge>;
}
