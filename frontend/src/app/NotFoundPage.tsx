import { Compass } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Button, EmptyState } from '@/components/ui';
import { paths } from '@/routes/paths';

export default function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <EmptyState
      icon={Compass}
      title={t('errors.notFoundTitle')}
      description={t('errors.notFound')}
      className="py-24"
      action={
        <Link to={paths.home}>
          <Button variant="secondary">{t('errors.goHome')}</Button>
        </Link>
      }
    />
  );
}
