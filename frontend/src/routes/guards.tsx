import { ShieldOff } from 'lucide-react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { EmptyState, FullPageSpinner } from '@/components/ui';
import { useAuth } from '@/features/auth/useAuth';
import type { Capability } from '@/types/auth';

import { paths } from './paths';

/** Only for logged-in users; others go to login and come back afterwards. */
export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <FullPageSpinner />;
  if (status === 'anonymous') {
    return (
      <Navigate to={paths.login} replace state={{ from: location.pathname + location.search }} />
    );
  }
  return <Outlet />;
}

/** Only for logged-out users (login, sign up, ...). */
export function GuestRoute() {
  const { status } = useAuth();
  if (status === 'loading') return <FullPageSpinner />;
  if (status === 'authenticated') return <Navigate to={paths.home} replace />;
  return <Outlet />;
}

/** UI-level check only; the API enforces every permission itself. */
export function RequireCapability({
  capability,
  children,
}: {
  capability: Capability;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const { can } = useAuth();
  if (!can(capability)) {
    return (
      <EmptyState
        icon={ShieldOff}
        title={t('errors.forbiddenTitle')}
        description={t('errors.forbidden')}
        className="py-20"
      />
    );
  }
  return children;
}
