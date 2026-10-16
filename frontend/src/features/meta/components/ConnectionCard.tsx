import { AlertTriangle, CheckCircle2, Flag, RefreshCw, Settings2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  Dialog,
} from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { useCheckAccess, useConnectMeta, useMetaSettings, type MetaStatus } from '../api';
import { MetaLogoutButton } from './MetaLogoutButton';
import { SyncNowPanel } from './SyncNowPanel';

const TOKEN_TONE = {
  ok: 'success',
  expiring: 'warning',
  expired: 'danger',
  none: 'neutral',
} as const;

export function ConnectionCard({ status }: { status: MetaStatus }) {
  const { t } = useTranslation();
  const format = useDateFormat();
  const navigate = useNavigate();
  const connect = useConnectMeta({ onConnected: () => navigate(paths.settingsMetaSetup) });
  const [syncOpen, setSyncOpen] = useState(false);
  const check = useCheckAccess();
  const settings = useMetaSettings();
  const isConnected = status.status === 'connected';
  const error = connect.error ?? check.error ?? settings.error;

  return (
    <Card>
      <CardHeader
        title={t('meta.connection.title')}
        description={t('meta.connection.description')}
        actions={
          isConnected ? (
            <>
              <Button onClick={() => setSyncOpen(true)}>
                <RefreshCw className="size-4" aria-hidden /> {t('meta.syncNow.button')}
              </Button>
              <Link to={`${paths.settingsMetaSetup}?step=forms`}>
                <Button variant="secondary">
                  <Settings2 className="size-4" aria-hidden /> {t('meta.setup.open')}
                </Button>
              </Link>
              <MetaLogoutButton pageName={status.page_name} />
            </>
          ) : status.status === 'pending_page' ? (
            <MetaLogoutButton />
          ) : (
            <Button
              className="bg-[#1877F2] hover:bg-[#166FE5]"
              loading={connect.isPending}
              disabled={!status.app_configured}
              onClick={() => void connect.start()}
            >
              <Flag className="size-4" aria-hidden /> {t('meta.connection.connect')}
            </Button>
          )
        }
      />
      <CardBody className="space-y-4">
        {error && <Alert tone="danger">{getErrorMessage(error)}</Alert>}

        {!status.app_configured && !isConnected && (
          <Alert tone="info">
            <p className="font-medium">{t('meta.connection.notConfigured')}</p>
            <p className="mt-1">{t('meta.connection.notConfiguredHint')}</p>
            <p className="mt-2 font-mono text-xs break-all">
              {t('meta.connection.redirect')}: {status.redirect_uri}
              <br />
              {t('meta.connection.webhook')}: {status.webhook_url}
            </p>
          </Alert>
        )}

        {(status.status === 'not_connected' || status.status === 'disconnected') && (
          <p className="text-[13px] text-fg-muted">{t('meta.connection.notConnected')}</p>
        )}

        {connect.isPending && <Alert tone="info">{t('meta.connection.popupOpen')}</Alert>}

        {status.status === 'pending_page' && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
            <p className="text-[13px]">{t('meta.setup.pendingPage')}</p>
            <Link to={paths.settingsMetaSetup}>
              <Button>{t('meta.setup.continue')}</Button>
            </Link>
          </div>
        )}

        {isConnected && (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-lg bg-[#1877F2] text-white">
                <Flag className="size-5" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{status.page_name}</p>
                <p className="text-xs text-fg-muted">
                  {t('meta.connection.connectedOn', { date: format.dateTime(status.connected_at) })}
                </p>
              </div>
              <Badge tone={TOKEN_TONE[status.token_state]}>
                {t(`meta.token.${status.token_state}`)}
              </Badge>
            </div>

            {status.leads_access_ok ? (
              <Alert tone="success">
                <span className="inline-flex items-center gap-1.5">
                  <CheckCircle2 className="size-4" aria-hidden /> {t('meta.access.ok')}
                </span>
              </Alert>
            ) : (
              <Alert tone="danger">
                <p className="flex items-center gap-1.5 font-medium">
                  <AlertTriangle className="size-4" aria-hidden /> {t('meta.access.missing')}
                </p>
                <ol className="mt-2 list-decimal space-y-0.5 pl-5">
                  <li>{t('meta.access.step1')}</li>
                  <li>{t('meta.access.step2')}</li>
                  <li>{t('meta.access.step3')}</li>
                </ol>
                {status.leads_access_error && (
                  <p className="mt-2 text-xs opacity-80">{status.leads_access_error}</p>
                )}
              </Alert>
            )}
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                loading={check.isPending}
                onClick={() => check.mutate()}
              >
                <RefreshCw className="size-3.5" aria-hidden /> {t('meta.access.checkAgain')}
              </Button>
              <label className="flex items-center gap-2 text-[13px]">
                <Checkbox
                  checked={status.detect_ad_details ?? true}
                  disabled={settings.isPending}
                  onChange={(e) => settings.mutate({ detect_ad_details: e.target.checked })}
                />
                {t('meta.connection.detectAds')}
              </label>
            </div>
          </>
        )}
      </CardBody>
      <Dialog
        open={syncOpen}
        onOpenChange={setSyncOpen}
        title={t('meta.syncNow.title')}
        description={t('meta.syncNow.description')}
      >
        <SyncNowPanel />
      </Dialog>
    </Card>
  );
}
