import { Check, ChevronLeft, ExternalLink, LayoutGrid, RefreshCw, Unplug } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Alert, Button, Card, CardBody, CardHeader, EmptyState, Skeleton } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { useCheckApp, useDisconnectApp, useIntegrations, type AppStatus } from '../api';
import { findApp, MANAGED_APPS, type AppDef } from '../catalog';
import { ExotelManage } from '../manage/ExotelManage';
import { GoogleSheetsManage } from '../manage/GoogleSheetsManage';
import { WhatsAppManage } from '../manage/WhatsAppManage';
import { WhatsAppConnectOptions } from '../whatsapp/WhatsAppConnectOptions';
import { AppConnectButton } from '../components/AppConnectButton';
import { AppLogo } from '../components/AppLogo';
import { AppStatusBadge } from '../components/AppStatusBadge';

/** One app's listing (HubSpot style): what it does, how to connect, and its connection. */
export default function AppDetailPage() {
  const { t } = useTranslation();
  const { app: key } = useParams();
  const app = findApp(key);
  const integrations = useIntegrations();

  if (!app) {
    return (
      <EmptyState
        icon={LayoutGrid}
        title={t('apps.notFound.title')}
        description={t('apps.notFound.description')}
        action={
          <Link to={paths.apps}>
            <Button variant="secondary">{t('apps.back')}</Button>
          </Link>
        }
      />
    );
  }
  const status = integrations.data?.[app.key];
  const list = (name: 'features' | 'steps') =>
    t(`apps.catalog.${app.key}.${name}`, { returnObjects: true, defaultValue: [] }) as string[];

  return (
    <div className="mx-auto max-w-5xl">
      <Link
        to={paths.apps}
        className="mb-3 inline-flex items-center gap-1 text-[13px] text-fg-muted hover:text-fg"
      >
        <ChevronLeft className="size-4" aria-hidden /> {t('apps.back')}
      </Link>

      <header className="mb-6 flex flex-col gap-4 rounded-2xl border bg-surface p-5 sm:flex-row sm:items-center">
        <AppLogo app={app} size="lg" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">
              {t(`apps.catalog.${app.key}.name`)}
            </h1>
            <AppStatusBadge app={app} status={status?.status} />
          </div>
          <p className="mt-0.5 text-[13px] text-fg-muted">{t(`apps.categories.${app.category}`)}</p>
          <p className="mt-2 text-[13px]">{t(`apps.catalog.${app.key}.tagline`)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {integrations.isPending ? (
            <Skeleton className="h-9 w-28" />
          ) : (
            <AppConnectButton app={app} status={status} />
          )}
          {app.docsUrl && (
            <a href={app.docsUrl} target="_blank" rel="noreferrer">
              <Button variant="ghost">
                {t('apps.docs')} <ExternalLink className="size-3.5" aria-hidden />
              </Button>
            </a>
          )}
        </div>
      </header>

      {app.connect === 'embedded' &&
        !integrations.isPending &&
        status?.status !== 'connected' &&
        status?.status !== 'error' && (
          <Card className="mb-6">
            <CardHeader
              title={t('whatsappConnect.title')}
              description={t('whatsappConnect.description')}
            />
            <CardBody>
              <WhatsAppConnectOptions />
            </CardBody>
          </Card>
        )}

      {MANAGED_APPS.has(app.key) &&
        (status?.status === 'connected' || status?.status === 'error') && (
          <section aria-label={t('apps.detail.manage')} className="mb-6">
            {app.key === 'exotel' && <ExotelManage />}
            {app.key === 'whatsapp' && <WhatsAppManage />}
            {app.key === 'google_sheets' && <GoogleSheetsManage />}
          </section>
        )}

      <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-5">
          <Card>
            <CardHeader title={t('apps.detail.overview')} />
            <CardBody className="space-y-4">
              <p className="text-[13px] leading-relaxed">
                {t(`apps.catalog.${app.key}.description`)}
              </p>
              {list('features').length > 0 && (
                <ul className="space-y-2">
                  {list('features').map((feature) => (
                    <li key={feature} className="flex gap-2 text-[13px]">
                      <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                      {feature}
                    </li>
                  ))}
                </ul>
              )}
              {app.availability === 'coming_soon' && (
                <Alert tone="info">{t('apps.detail.comingSoon')}</Alert>
              )}
            </CardBody>
          </Card>

          {list('steps').length > 0 && (
            <Card>
              <CardHeader title={t('apps.detail.howToConnect')} />
              <CardBody>
                <ol className="space-y-3">
                  {list('steps').map((step, index) => (
                    <li key={step} className="flex gap-3 text-[13px]">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
                        {index + 1}
                      </span>
                      <span className="pt-0.5">{step}</span>
                    </li>
                  ))}
                </ol>
              </CardBody>
            </Card>
          )}
        </div>

        {app.availability === 'available' && (
          <aside>
            <ConnectionCard app={app} status={status} loading={integrations.isPending} />
          </aside>
        )}
      </div>
    </div>
  );
}

function ConnectionCard({
  app,
  status,
  loading,
}: {
  app: AppDef;
  status?: AppStatus;
  loading: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useDateFormat();
  const check = useCheckApp(app.key);
  const disconnect = useDisconnectApp(app.key);
  const state = status?.status ?? 'not_connected';
  const name = t(`apps.catalog.${app.key}.name`);
  const rows = [
    [t('apps.detail.account'), status?.account_label],
    [t('apps.detail.connectedBy'), status?.connected_by],
    [t('apps.detail.connectedAt'), status?.connected_at && format.dateTime(status.connected_at)],
    [
      t('apps.detail.lastChecked'),
      status?.last_checked_at && format.dateTime(status.last_checked_at),
    ],
  ].filter(([, value]) => value);

  return (
    <Card>
      <CardHeader title={t('apps.detail.connection')} />
      <CardBody className="space-y-4">
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : state === 'not_connected' ? (
          <>
            <p className="text-[13px] text-fg-muted">
              {t('apps.detail.notConnected', { app: name })}
            </p>
            {app.fields && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-fg-muted uppercase">
                  {t('apps.detail.youNeed')}
                </p>
                <ul className="list-disc space-y-1 pl-5 text-[13px]">
                  {app.fields
                    .filter((field) => !field.optional && field.type !== 'select')
                    .map((field) => (
                      <li key={field.key}>{t(`apps.fields.${app.key}.${field.key}.label`)}</li>
                    ))}
                </ul>
              </div>
            )}
          </>
        ) : (
          <>
            <dl className="space-y-2 text-[13px]">
              {rows.map(([label, value]) => (
                <div key={label} className="flex justify-between gap-3">
                  <dt className="text-fg-muted">{label}</dt>
                  <dd className="min-w-0 truncate text-right font-medium" title={String(value)}>
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
            {state === 'error' && (
              <Alert tone="danger">{status?.last_error || t('apps.detail.attention')}</Alert>
            )}
            {state === 'needs_setup' && <Alert tone="info">{t('apps.detail.needsSetup')}</Alert>}
            {check.isError && <Alert tone="danger">{getErrorMessage(check.error)}</Alert>}
            {disconnect.isError && <Alert tone="danger">{getErrorMessage(disconnect.error)}</Alert>}
            {app.connect !== 'meta' && (
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  loading={check.isPending}
                  onClick={() => check.mutate()}
                >
                  <RefreshCw className="size-3.5" aria-hidden /> {t('apps.actions.test')}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  loading={disconnect.isPending}
                  onClick={() => {
                    if (!window.confirm(t('apps.actions.confirmDisconnect', { app: name }))) return;
                    disconnect.mutate(undefined, { onSuccess: () => navigate(paths.apps) });
                  }}
                >
                  <Unplug className="size-3.5" aria-hidden /> {t('apps.actions.disconnect')}
                </Button>
              </div>
            )}
            {app.connect === 'meta' && (
              <p className="text-xs text-fg-muted">{t('apps.detail.metaManage')}</p>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}
