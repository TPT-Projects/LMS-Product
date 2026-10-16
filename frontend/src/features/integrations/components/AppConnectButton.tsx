import { ArrowRight, Settings2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { Alert, Button, type ButtonProps } from '@/components/ui';
import { useConnectMeta, useOAuthPopup } from '@/features/meta/api';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import type { AppStatus } from '../api';
import type { AppDef } from '../catalog';
import { ConnectAppDialog } from './ConnectAppDialog';

interface Props {
  app: AppDef;
  status?: AppStatus;
  size?: ButtonProps['size'];
  /** On a card: "Manage" opens the app page. On the app page: it opens the editor. */
  manageHref?: string;
}

/**
 * One click to connect, like HubSpot: Meta, WhatsApp and Google Sheets open their login popup
 * straight away, Exotel opens a short form. Connected apps show "Manage".
 */
export function AppConnectButton({ app, status, size = 'md', manageHref }: Props) {
  if (app.availability === 'coming_soon') return <ComingSoonButton size={size} />;
  if (app.connect === 'meta') return <MetaButton status={status} size={size} />;
  if (app.connect === 'embedded') {
    return <EmbeddedButton app={app} status={status} size={size} manageHref={manageHref} />;
  }
  if (app.connect === 'facebook' || app.connect === 'google') {
    return <LoginButton app={app} status={status} size={size} manageHref={manageHref} />;
  }
  return <CredentialsButton app={app} status={status} size={size} manageHref={manageHref} />;
}

/** WhatsApp: the connect options (new number / Business app number) live on its app page. */
function EmbeddedButton({ status, size, manageHref }: Props) {
  const { t } = useTranslation();
  const connected = status?.status === 'connected' || status?.status === 'error';
  if (!manageHref) return null; // on the app page the options are shown in the page itself
  return (
    <Link to={manageHref}>
      <Button variant={connected ? 'secondary' : 'primary'} size={size}>
        {connected ? (
          <>
            <Settings2 className="size-4" aria-hidden /> {t('apps.actions.manage')}
          </>
        ) : (
          t('apps.actions.connect')
        )}
      </Button>
    </Link>
  );
}

/** Google Sheets (Google login): popup, then Manage. */
function LoginButton({ app, status, size, manageHref }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const appHref = `${paths.apps}/${app.key}`;
  const login = useOAuthPopup({
    app: app.key,
    startPath: `/integrations/${app.key}/connect`,
    onConnected: () => navigate(appHref),
  });
  const connected = status?.status === 'connected' || status?.status === 'error';

  if (connected && manageHref) {
    return (
      <Link to={manageHref}>
        <Button variant="secondary" size={size}>
          <Settings2 className="size-4" aria-hidden /> {t('apps.actions.manage')}
        </Button>
      </Link>
    );
  }
  return (
    <div className="space-y-2">
      <Button
        variant={connected ? 'secondary' : 'primary'}
        size={size}
        loading={login.isPending}
        onClick={() => void login.start()}
      >
        {connected
          ? t('apps.actions.reconnect')
          : t(`apps.actions.connectWith.${app.connect ?? 'facebook'}`)}
      </Button>
      {login.error != null && <Alert tone="danger">{getErrorMessage(login.error)}</Alert>}
    </div>
  );
}

function ComingSoonButton({ size }: { size: ButtonProps['size'] }) {
  const { t } = useTranslation();
  return (
    <Button variant="secondary" size={size} disabled>
      {t('apps.status.coming_soon')}
    </Button>
  );
}

function MetaButton({ status, size }: { status?: AppStatus; size: ButtonProps['size'] }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const connect = useConnectMeta({ onConnected: () => navigate(paths.settingsMetaSetup) });
  const state = status?.status ?? 'not_connected';

  if (state === 'needs_setup') {
    return (
      <Link to={paths.settingsMetaSetup}>
        <Button size={size}>
          {t('apps.actions.finishSetup')} <ArrowRight className="size-4" aria-hidden />
        </Button>
      </Link>
    );
  }
  if (state !== 'not_connected') {
    return (
      <Link to={paths.settingsMeta}>
        <Button variant="secondary" size={size}>
          <Settings2 className="size-4" aria-hidden /> {t('apps.actions.manage')}
        </Button>
      </Link>
    );
  }
  return (
    <div className="space-y-2">
      <Button size={size} loading={connect.isPending} onClick={() => void connect.start()}>
        {t('apps.actions.connect')}
      </Button>
      {connect.error != null && <Alert tone="danger">{getErrorMessage(connect.error)}</Alert>}
    </div>
  );
}

function CredentialsButton({
  app,
  status,
  size,
  manageHref,
}: {
  app: AppDef;
  status?: AppStatus;
  size: ButtonProps['size'];
  manageHref?: string;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const connected = status?.status === 'connected' || status?.status === 'error';

  if (connected && manageHref) {
    return (
      <Link to={manageHref}>
        <Button variant="secondary" size={size}>
          <Settings2 className="size-4" aria-hidden /> {t('apps.actions.manage')}
        </Button>
      </Link>
    );
  }
  return (
    <>
      <Button
        variant={connected ? 'secondary' : 'primary'}
        size={size}
        onClick={() => setOpen(true)}
      >
        {connected ? t('apps.actions.editDetails') : t('apps.actions.connect')}
      </Button>
      {open && <ConnectAppDialog app={app} status={status} open onOpenChange={setOpen} />}
    </>
  );
}
