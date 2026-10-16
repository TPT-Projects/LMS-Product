import { Check, ChevronLeft, Flag, RefreshCw } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { Alert, Badge, Button, Card, CardBody, Skeleton, Switch } from '@/components/ui';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';

import {
  useConnectMeta,
  useMetaForms,
  useMetaPages,
  useMetaStatus,
  useRefreshForms,
  useToggleForm,
  type MetaForm,
} from '../api';
import { AutoSyncToggle } from '../components/AutoSyncToggle';
import { FormSearch } from '../components/FormSearch';
import { MetaLogoutButton } from '../components/MetaLogoutButton';
import { PagePicker } from '../components/PagePicker';
import { SyncingNotice } from '../components/SyncingNotice';
import { SyncNowPanel } from '../components/SyncNowPanel';

const STEPS = ['page', 'forms', 'sync'] as const;
type Step = (typeof STEPS)[number];

/**
 * After the Facebook login (popup): 1. choose the Page, 2. its forms (Auto Sync for all, or
 * form by form), 3. sync the leads, then open Enquiries.
 */
export default function MetaSetupPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const status = useMetaStatus();
  const state = status.data?.status;

  const asked = params.get('step') as Step | null;
  const step: Step =
    state === 'pending_page'
      ? 'page'
      : asked && asked !== 'page' && STEPS.includes(asked)
        ? asked
        : 'forms';
  const goTo = (next: Step) => setParams({ step: next }, { replace: true });
  const finish = () => navigate(`${paths.enquiries}?view=all`);

  useEffect(() => {
    // Nothing to set up without a Facebook login.
    if (state === 'not_connected' || state === 'disconnected') navigate(paths.settingsMeta);
  }, [navigate, state]);

  const index = STEPS.indexOf(step);
  return (
    <div className="mx-auto max-w-3xl">
      <Link
        to={paths.settingsMeta}
        className="mb-2 inline-flex items-center gap-1 text-[13px] text-fg-muted hover:text-fg"
      >
        <ChevronLeft className="size-4" aria-hidden /> {t('meta.back')}
      </Link>
      <PageHeader
        title={t('meta.setup.title')}
        description={
          status.data?.page_name
            ? t('meta.setup.connectedPage', { page: status.data.page_name })
            : t('meta.setup.description')
        }
        actions={state && <MetaLogoutButton pageName={status.data?.page_name} />}
      />

      <ol className="mb-4 grid grid-cols-3 gap-2" aria-label={t('meta.setup.steps')}>
        {STEPS.map((s, i) => (
          <li
            key={s}
            aria-current={s === step ? 'step' : undefined}
            className={cn(
              'flex items-center gap-2 rounded-lg border px-3 py-2 text-[13px]',
              s === step ? 'border-accent bg-accent-soft font-medium' : 'text-fg-muted',
            )}
          >
            <span
              className={cn(
                'flex size-5 shrink-0 items-center justify-center rounded-full text-[11px]',
                i <= index ? 'bg-accent text-accent-fg' : 'bg-muted',
              )}
            >
              {i < index ? <Check className="size-3" aria-hidden /> : i + 1}
            </span>
            <span className="truncate">{t(`meta.setup.step.${s}`)}</span>
          </li>
        ))}
      </ol>

      <SyncingNotice className="mb-4" />
      <Card>
        <CardBody>
          {status.isPending ? (
            <Skeleton className="h-40 w-full" />
          ) : status.isError ? (
            <Alert tone="danger">{getErrorMessage(status.error)}</Alert>
          ) : step === 'page' ? (
            <PageStep onDone={() => goTo('forms')} />
          ) : step === 'forms' ? (
            <FormsStep auto={status.data.auto_connect_forms ?? true} onNext={() => goTo('sync')} />
          ) : (
            <SyncStep onBack={() => goTo('forms')} onDone={finish} />
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function StepTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-[15px] font-semibold">{title}</h2>
      <p className="mt-0.5 text-[13px] text-fg-muted">{hint}</p>
    </div>
  );
}

function StepButtons({ onBack, next }: { onBack?: () => void; next: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t pt-4">
      {onBack ? (
        <Button variant="secondary" onClick={onBack}>
          {t('meta.setup.back')}
        </Button>
      ) : (
        <span />
      )}
      {next}
    </div>
  );
}

function PageStep({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const pages = useMetaPages(true);
  // Log in again (popup) to tick more Pages; the list reloads when the popup reports back.
  const connect = useConnectMeta({ onConnected: () => void pages.refetch() });
  return (
    <>
      <StepTitle title={t('meta.pages.title')} hint={t('meta.setup.pageHint')} />
      {pages.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : pages.isError ? (
        <Alert tone="danger">{getErrorMessage(pages.error)}</Alert>
      ) : (
        <PagePicker pages={pages.data ?? []} onDone={onDone} />
      )}
      <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-dashed p-3">
        <p className="min-w-0 flex-1 text-[13px] text-fg-muted">{t('meta.setup.missingPage')}</p>
        <Button
          variant="secondary"
          loading={connect.isPending}
          onClick={() => void connect.start()}
        >
          <Flag className="size-4" aria-hidden /> {t('meta.setup.loginAgain')}
        </Button>
      </div>
      {connect.error != null && (
        <Alert tone="danger" className="mt-3">
          {getErrorMessage(connect.error)}
        </Alert>
      )}
    </>
  );
}

function FormStatus({ form }: { form: MetaForm }) {
  const { t } = useTranslation();
  if (!form.status_on_meta) return null;
  return (
    <Badge tone={form.status_on_meta === 'ACTIVE' ? 'success' : 'neutral'}>
      {t(`meta.forms.metaStatus.${form.status_on_meta.toLowerCase()}`, {
        defaultValue: form.status_on_meta,
      })}
    </Badge>
  );
}

function FormsStep({ auto, onNext }: { auto: boolean; onNext: () => void }) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const forms = useMetaForms({ page: 1, page_size: 100, q }, true);
  const toggle = useToggleForm();
  const refresh = useRefreshForms();
  const list = forms.data?.results ?? [];
  const connectedCount = list.filter((f) => f.is_connected).length;

  return (
    <>
      <StepTitle title={t('meta.setup.formsTitle')} hint={t('meta.setup.formsHint')} />
      <AutoSyncToggle auto={auto} />
      <div className="mt-4">
        <FormSearch value={search} onChange={setSearch} />
      </div>

      <div className="mt-4">
        {forms.isPending ? (
          <Skeleton className="h-32 w-full" />
        ) : forms.isError ? (
          <Alert tone="danger">{getErrorMessage(forms.error)}</Alert>
        ) : !list.length ? (
          <div className="space-y-3">
            <Alert tone="info">{t('meta.setup.noForms')}</Alert>
            <Button
              variant="secondary"
              loading={refresh.isPending}
              onClick={() => refresh.mutate()}
            >
              <RefreshCw className="size-4" aria-hidden /> {t('meta.setup.refreshForms')}
            </Button>
            {refresh.isError && <Alert tone="danger">{getErrorMessage(refresh.error)}</Alert>}
          </div>
        ) : (
          <ul className="divide-y rounded-xl border">
            {list.map((form) => {
              const busy = toggle.isPending && toggle.variables?.id === form.id;
              return (
                <li key={form.id} className="flex items-center gap-3 px-3 py-2.5">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{form.name || form.form_id}</span>
                    <span className="block text-xs text-fg-muted tabular-nums">
                      {form.form_id} · {t('meta.setup.leadsCount', { count: form.leads_received })}
                    </span>
                  </span>
                  <FormStatus form={form} />
                  <Switch
                    checked={form.is_connected}
                    disabled={auto || busy}
                    aria-label={t('meta.setup.connectForm', { form: form.name || form.form_id })}
                    title={auto ? t('meta.autoSync.lockedHint') : undefined}
                    onCheckedChange={(connect) => toggle.mutate({ id: form.id, connect })}
                  />
                </li>
              );
            })}
          </ul>
        )}
        {toggle.isError && (
          <Alert tone="danger" className="mt-3">
            {getErrorMessage(toggle.error)}
          </Alert>
        )}
      </div>

      <StepButtons
        next={
          <div className="flex items-center gap-3">
            <span className="text-[13px] text-fg-muted">
              {t('meta.setup.formsSelected', { count: connectedCount })}
            </span>
            <Button disabled={forms.isPending} onClick={onNext}>
              {t('meta.setup.next')}
            </Button>
          </div>
        }
      />
    </>
  );
}

function SyncStep({ onBack, onDone }: { onBack: () => void; onDone: () => void }) {
  const { t } = useTranslation();
  return (
    <>
      <StepTitle title={t('meta.setup.syncTitle')} hint={t('meta.setup.syncHint')} />
      <SyncNowPanel />
      <StepButtons
        onBack={onBack}
        next={<Button onClick={onDone}>{t('meta.setup.finish')}</Button>}
      />
    </>
  );
}
