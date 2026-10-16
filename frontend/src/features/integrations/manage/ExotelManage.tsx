import { PhoneCall, Plus, RefreshCw, Star, Trash2 } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  Select,
  Skeleton,
  Switch,
} from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { useAllMembers } from '@/features/users/api';
import { getErrorMessage, nestedErrors } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import {
  useAddExotelNumber,
  useAutoCallForms,
  useAutoCalls,
  useDeleteExotelNumber,
  useExotel,
  useExotelSettings,
  useRefreshExotel,
  useToggleAutoCallForm,
  type ExotelManage as ExotelData,
} from '../api';
import { utc } from '../time';
import { CallingHoursCard } from './CallingHoursCard';

/** Exotel's Manage page: numbers, auto-calling rules, forms that call at once, recent calls. */
export function ExotelManage() {
  const { t } = useTranslation();
  const exotel = useExotel();
  if (exotel.isPending) return <Skeleton className="h-64 w-full" />;
  if (exotel.isError) return <Alert tone="danger">{getErrorMessage(exotel.error)}</Alert>;
  return (
    <div className="space-y-5">
      <NumbersCard data={exotel.data} />
      <CallingHoursCard window={exotel.data.settings.call_window} />
      <AutoCallingCard data={exotel.data} />
      <FormsCard delay={exotel.data.settings.new_lead_delay} />
      <RecentCallsCard />
      <p className="text-xs text-fg-muted">{t('exotel.howItWorks')}</p>
    </div>
  );
}

function NumbersCard({ data }: { data: ExotelData }) {
  const { t } = useTranslation();
  const format = useDateFormat();
  const refresh = useRefreshExotel();
  const settings = useExotelSettings();
  const remove = useDeleteExotelNumber();
  const [adding, setAdding] = useState(false);
  const active = data.numbers.filter((n) => n.is_active);
  const inactive = data.numbers.filter((n) => !n.is_active);
  const error = refresh.error ?? settings.error ?? remove.error;

  return (
    <Card>
      <CardHeader
        title={t('exotel.numbers.title')}
        description={
          data.refreshed_at
            ? t('exotel.numbers.refreshed', { when: format.dateTime(data.refreshed_at) })
            : t('exotel.numbers.notRefreshed')
        }
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => setAdding((v) => !v)}>
              <Plus className="size-3.5" aria-hidden /> {t('exotel.numbers.add')}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              loading={refresh.isPending}
              onClick={() => refresh.mutate(undefined)}
            >
              <RefreshCw className="size-3.5" aria-hidden /> {t('exotel.numbers.refresh')}
            </Button>
          </>
        }
      />
      <CardBody className="space-y-3">
        {error != null && <Alert tone="danger">{getErrorMessage(error)}</Alert>}
        {adding && <AddNumberForm onDone={() => setAdding(false)} />}
        {active.length === 0 ? (
          <Alert tone="info">{t('exotel.numbers.empty')}</Alert>
        ) : (
          <ul className="divide-y rounded-xl border">
            {active.map((n) => {
              const isDefault = data.settings.default_caller === n.phone_number;
              return (
                <li key={n.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                  <PhoneCall className="size-4 shrink-0 text-fg-muted" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium tabular-nums">
                      {n.phone_number}
                      {n.friendly_name && (
                        <span className="ml-2 text-xs font-normal text-fg-muted">
                          {n.friendly_name}
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-fg-muted" title={utc(n.active_since)}>
                      {t('exotel.numbers.activeSince', { when: format.dateTime(n.active_since) })}
                      {n.region && ` · ${n.region}`}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {n.capabilities.voice !== false && <Badge>{t('exotel.numbers.voice')}</Badge>}
                    {n.capabilities.sms && <Badge>{t('exotel.numbers.sms')}</Badge>}
                    {n.added_manually && <Badge tone="accent">{t('exotel.numbers.manual')}</Badge>}
                  </div>
                  {isDefault ? (
                    <Badge tone="success">
                      <Star className="mr-1 size-3" aria-hidden /> {t('exotel.numbers.default')}
                    </Badge>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      loading={
                        settings.isPending && settings.variables?.default_caller === n.phone_number
                      }
                      onClick={() => settings.mutate({ default_caller: n.phone_number })}
                    >
                      {t('exotel.numbers.makeDefault')}
                    </Button>
                  )}
                  {n.added_manually && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      aria-label={t('exotel.numbers.remove', { number: n.phone_number })}
                      onClick={() => remove.mutate(n.id)}
                    >
                      <Trash2 className="size-3.5" aria-hidden />
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {inactive.length > 0 && (
          <p className="text-xs text-fg-muted">
            {t('exotel.numbers.inactive', {
              numbers: inactive.map((n) => n.phone_number).join(', '),
            })}
          </p>
        )}
        <p className="text-xs text-fg-muted">{t('exotel.numbers.autoRefresh')}</p>
      </CardBody>
    </Card>
  );
}

function AddNumberForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const add = useAddExotelNumber();
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const errors = nestedErrors(add.error, 'phone_number');
  const fieldError =
    (add.error && getErrorMessage(add.error)) || Object.values(errors)[0] || undefined;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    add.mutate({ phone_number: phone, friendly_name: name }, { onSuccess: onDone });
  };

  return (
    <form onSubmit={submit} className="space-y-2 rounded-xl border border-dashed p-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          type="tel"
          placeholder={t('exotel.numbers.phonePlaceholder')}
          aria-label={t('exotel.numbers.phoneLabel')}
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="sm:flex-1"
        />
        <Input
          placeholder={t('exotel.numbers.namePlaceholder')}
          aria-label={t('exotel.numbers.nameLabel')}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="sm:w-48"
        />
        <Button type="submit" loading={add.isPending} disabled={!phone.trim()}>
          {t('exotel.numbers.addButton')}
        </Button>
      </div>
      {add.isError && fieldError && <p className="text-[13px] text-danger">{fieldError}</p>}
      <p className="text-xs text-fg-muted">{t('exotel.numbers.addHint')}</p>
    </form>
  );
}

function AutoCallingCard({ data }: { data: ExotelData }) {
  const { t } = useTranslation();
  const settings = useExotelSettings();
  const members = useAllMembers();
  const rules = data.settings;
  const noPhone = (members.data?.results ?? []).filter((m) => !m.phone);

  return (
    <Card>
      <CardHeader title={t('exotel.auto.title')} description={t('exotel.auto.description')} />
      <CardBody className="space-y-5">
        {!rules.default_caller && <Alert tone="info">{t('exotel.auto.noCaller')}</Alert>}
        {settings.isError && <Alert tone="danger">{getErrorMessage(settings.error)}</Alert>}

        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <p id="auto-followups" className="font-medium">
              {t('exotel.auto.followups')}
            </p>
            <p className="text-xs text-fg-muted">{t('exotel.auto.followupsHint')}</p>
          </div>
          <Switch
            checked={rules.auto_call_followups}
            aria-labelledby="auto-followups"
            disabled={settings.isPending}
            onCheckedChange={(value) => settings.mutate({ auto_call_followups: value })}
          />
        </div>

        <div className="grid gap-1.5 sm:max-w-sm">
          <label htmlFor="fallback-agent" className="font-medium">
            {t('exotel.auto.fallback')}
          </label>
          <Select
            id="fallback-agent"
            value={rules.fallback_agent ?? ''}
            disabled={settings.isPending}
            onChange={(e) =>
              settings.mutate({ fallback_agent: e.target.value ? Number(e.target.value) : null })
            }
          >
            <option value="">{t('exotel.auto.fallbackNone')}</option>
            {(members.data?.results ?? []).map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name}
                {m.phone ? '' : ` (${t('exotel.auto.noPhoneShort')})`}
              </option>
            ))}
          </Select>
          <p className="text-xs text-fg-muted">{t('exotel.auto.fallbackHint')}</p>
        </div>

        {noPhone.length > 0 && (
          <Alert tone="info">
            {t('exotel.auto.missingPhones', { names: noPhone.map((m) => m.full_name).join(', ') })}{' '}
            <Link to={paths.people} className="font-medium underline">
              {t('exotel.auto.addPhones')}
            </Link>
          </Alert>
        )}
      </CardBody>
    </Card>
  );
}

const DELAYS = [1, 2, 5] as const;

function FormsCard({ delay }: { delay: number }) {
  const { t } = useTranslation();
  const forms = useAutoCallForms();
  const toggle = useToggleAutoCallForm();
  const settings = useExotelSettings();
  const list = forms.data?.forms ?? [];

  return (
    <Card>
      <CardHeader
        title={t('exotel.forms.title')}
        description={
          forms.data?.page_name
            ? t('exotel.forms.descriptionPage', { page: forms.data.page_name })
            : t('exotel.forms.description')
        }
      />
      <CardBody className="space-y-4">
        <div>
          <p className="font-medium">{t('exotel.forms.delay')}</p>
          <p className="mb-2 text-xs text-fg-muted">{t('exotel.forms.delayHint')}</p>
          <div
            role="radiogroup"
            aria-label={t('exotel.forms.delay')}
            className="flex flex-wrap gap-2"
          >
            {DELAYS.map((minutes) => (
              <button
                key={minutes}
                type="button"
                role="radio"
                aria-checked={delay === minutes}
                disabled={settings.isPending}
                onClick={() => settings.mutate({ new_lead_delay: minutes })}
                className={
                  delay === minutes
                    ? 'h-8 rounded-full border border-accent bg-accent-soft px-3 text-[13px] font-medium'
                    : 'h-8 rounded-full border px-3 text-[13px] hover:bg-subtle'
                }
              >
                {t('exotel.forms.minutes', { count: minutes })}
              </button>
            ))}
          </div>
          {settings.isError && (
            <Alert tone="danger" className="mt-2">
              {getErrorMessage(settings.error)}
            </Alert>
          )}
        </div>
        {forms.isPending ? (
          <Skeleton className="h-20 w-full" />
        ) : list.length === 0 ? (
          <Alert tone="info">
            {t('exotel.forms.empty')}{' '}
            <Link to={paths.settingsMeta} className="font-medium underline">
              {t('exotel.forms.openMeta')}
            </Link>
          </Alert>
        ) : (
          <ul className="divide-y rounded-xl border">
            {list.map((form) => (
              <li key={form.id} className="flex items-center gap-3 px-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{form.name}</p>
                  <p className="text-xs text-fg-muted tabular-nums">
                    {form.form_id} · {t('meta.setup.leadsCount', { count: form.leads_received })}
                  </p>
                </div>
                <span className="text-xs text-fg-muted">{t('exotel.forms.autoCall')}</span>
                <Switch
                  checked={form.auto_call}
                  aria-label={t('exotel.forms.toggle', { form: form.name })}
                  disabled={toggle.isPending && toggle.variables?.id === form.id}
                  onCheckedChange={(autoCall) => toggle.mutate({ id: form.id, autoCall })}
                />
              </li>
            ))}
          </ul>
        )}
        {toggle.isError && (
          <Alert tone="danger" className="mt-3">
            {getErrorMessage(toggle.error)}
          </Alert>
        )}
      </CardBody>
    </Card>
  );
}

const CALL_TONE: Record<string, 'success' | 'danger' | 'warning' | 'accent' | 'neutral'> = {
  completed: 'success',
  started: 'accent',
  pending: 'neutral',
  no_answer: 'warning',
  busy: 'warning',
  failed: 'danger',
  skipped: 'warning',
  cancelled: 'neutral',
};

function RecentCallsCard() {
  const { t } = useTranslation();
  const format = useDateFormat();
  const calls = useAutoCalls();
  const list = calls.data ?? [];

  return (
    <Card>
      <CardHeader title={t('exotel.calls.title')} description={t('exotel.calls.description')} />
      <CardBody>
        {calls.isPending ? (
          <Skeleton className="h-20 w-full" />
        ) : list.length === 0 ? (
          <p className="text-[13px] text-fg-muted">{t('exotel.calls.empty')}</p>
        ) : (
          <ul className="divide-y rounded-xl border">
            {list.map((call) => (
              <li
                key={call.id}
                className="flex flex-wrap items-center gap-3 px-3 py-2.5 text-[13px]"
              >
                <div className="min-w-0 flex-1">
                  <Link
                    to={`${paths.enquiries}/${call.enquiry_id}`}
                    className="font-medium hover:underline"
                  >
                    {call.enquiry_name || call.customer_phone}
                  </Link>
                  <p className="text-xs text-fg-muted" title={utc(call.scheduled_at)}>
                    {t(`exotel.calls.reasons.${call.reason}`)} ·{' '}
                    {format.dateTime(call.started_at ?? call.scheduled_at)}
                    {call.agent && ` · ${call.agent}`}
                  </p>
                  {call.error && <p className="text-xs text-danger">{call.error}</p>}
                </div>
                <Badge tone={CALL_TONE[call.status] ?? 'neutral'}>
                  {t(`exotel.calls.status.${call.status}`, { defaultValue: call.status })}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
