import type { LucideIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { PageHeader } from '@/components/layout/PageHeader';
import { Card, EmptyState } from '@/components/ui';

interface ComingSoonPageProps {
  icon: LucideIcon;
  titleKey: string;
  descriptionKey: string;
  emptyKey: string;
}

/** Empty state for modules that are built in later phases (see spec section 12). */
export default function ComingSoonPage({
  icon,
  titleKey,
  descriptionKey,
  emptyKey,
}: ComingSoonPageProps) {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title={t(titleKey)} description={t(descriptionKey)} />
      <Card>
        <EmptyState
          icon={icon}
          title={t(`${emptyKey}.title`)}
          description={t(`${emptyKey}.description`)}
          className="py-20"
        />
      </Card>
    </div>
  );
}
