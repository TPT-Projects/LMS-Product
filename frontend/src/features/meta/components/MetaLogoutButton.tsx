import { LogOut } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui';
import { paths } from '@/routes/paths';

import { useDisconnectMeta } from '../api';

/** Log out of the Facebook account: stops new leads; enquiries already created stay. */
export function MetaLogoutButton({ pageName }: { pageName?: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const logout = useDisconnectMeta();

  return (
    <Button
      variant="secondary"
      loading={logout.isPending}
      onClick={() => {
        const question = pageName
          ? t('meta.connection.confirmDisconnect', { page: pageName })
          : t('meta.logout.confirm');
        if (!window.confirm(question)) return;
        logout.mutate(undefined, { onSuccess: () => navigate(paths.settingsMeta) });
      }}
    >
      <LogOut className="size-4" aria-hidden /> {t('meta.logout.button')}
    </Button>
  );
}
