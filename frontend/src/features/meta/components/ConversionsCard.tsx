import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Send, XCircle } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  FormField,
  Input,
  Switch,
} from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { useStatuses } from '@/features/statuses/api';
import { api } from '@/lib/api/client';
import { getErrorMessage } from '@/lib/api/errors';

interface ConversionEvent {
  id: number;
  enquiry_id: number | null;
  leadgen_id: string;
  event_name: string;
  success: boolean;
  error: string;
  test: boolean;
  sent_at: string;
}

interface Conversions {
  enabled: boolean;
  dataset_id: string;
  token_set: boolean;
  connected: boolean;
  events: ConversionEvent[];
}

const KEY = ['meta', 'conversions'] as const;

/**
 * Lead quality feedback (Meta Conversions API for CRM): each status change of a Meta lead is
 * sent to Meta, which then optimises ads for leads that turn into customers.
 */
export function ConversionsCard() {
  const { t } = useTranslation();
  const format = useDateFormat();
  const queryClient = useQueryClient();
  const statuses = useStatuses();
  const data = useQuery({
    queryKey: KEY,
    queryFn: () => api.get<Conversions>('/meta/conversions').then((r) => r.data),
  });
  const save = useMutation({
    mutationFn: (body: { enabled?: boolean; dataset_id?: string; token?: string }) =>
      api.patch<Conversions>('/meta/conversions', body).then((r) => r.data),
    onSuccess: (result) => queryClient.setQueryData(KEY, result),
  });
  const test = useMutation({
    mutationFn: (code: string) =>
      api
        .post<ConversionEvent>('/meta/conversions/test', { test_event_code: code })
        .then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  });
  const [dataset, setDataset] = useState<string | null>(null);
  const [token, setToken] = useState('');
  const [code, setCode] = useState('');

  if (!data.data) return null;
  const settings = data.data;
  const datasetValue = dataset ?? settings.dataset_id;

  return (
    <Card>
      <CardHeader
        title={t('capi.title')}
        description={t('capi.description')}
        actions={
          <Switch
            checked={settings.enabled}
            aria-label={t('capi.enable')}
            disabled={save.isPending}
            onCheckedChange={(enabled) => save.mutate({ enabled })}
          />
        }
      />
      <CardBody className="space-y-4">
        {save.isError && <Alert tone="danger">{getErrorMessage(save.error)}</Alert>}
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label={t('capi.dataset')} hint={t('capi.datasetHint')}>
            <Input
              inputMode="numeric"
              value={datasetValue}
              placeholder="1234567890123456"
              onChange={(e) => setDataset(e.target.value)}
            />
          </FormField>
          <FormField
            label={t('capi.token')}
            hint={settings.token_set ? t('apps.connect.secretSaved') : t('capi.tokenHint')}
          >
            <Input
              type="password"
              autoComplete="off"
              value={token}
              placeholder={settings.token_set ? '••••••••••••' : 'EAAG…'}
              onChange={(e) => setToken(e.target.value)}
            />
          </FormField>
        </div>
        <Button
          size="sm"
          variant="secondary"
          loading={save.isPending}
          disabled={datasetValue === settings.dataset_id && !token}
          onClick={() =>
            save.mutate(
              { dataset_id: datasetValue, ...(token ? { token } : {}) },
              { onSuccess: () => setToken('') },
            )
          }
        >
          {t('capi.save')}
        </Button>

        <div className="rounded-xl bg-subtle p-3 text-[13px]">
          <p className="font-medium">{t('capi.stagesTitle')}</p>
          <p className="mt-0.5 text-xs text-fg-muted">{t('capi.stagesHint')}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(statuses.data ?? []).map((s) => (
              <Badge key={s.id}>{s.name}</Badge>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-2">
          <FormField label={t('capi.testCode')} hint={t('capi.testHint')} className="flex-1">
            <Input value={code} placeholder="TEST12345" onChange={(e) => setCode(e.target.value)} />
          </FormField>
          <Button
            size="sm"
            variant="secondary"
            loading={test.isPending}
            disabled={!settings.enabled}
            onClick={() => test.mutate(code.trim())}
          >
            <Send className="size-3.5" aria-hidden /> {t('capi.sendTest')}
          </Button>
        </div>
        {test.isError && <Alert tone="danger">{getErrorMessage(test.error)}</Alert>}

        <div>
          <p className="mb-1.5 text-[13px] font-medium">{t('capi.recent')}</p>
          {settings.events.length === 0 ? (
            <p className="text-xs text-fg-muted">{t('capi.none')}</p>
          ) : (
            <ul className="divide-y rounded-xl border text-[13px]">
              {settings.events.map((event) => (
                <li key={event.id} className="flex flex-wrap items-center gap-2 px-3 py-2">
                  {event.success ? (
                    <CheckCircle2 className="size-4 text-success" aria-hidden />
                  ) : (
                    <XCircle className="size-4 text-danger" aria-hidden />
                  )}
                  <span className="font-medium">{event.event_name}</span>
                  <span className="text-xs text-fg-muted tabular-nums">
                    {t('capi.lead', { id: event.leadgen_id })} · {format.dateTime(event.sent_at)}
                  </span>
                  {event.test && <Badge>{t('capi.testBadge')}</Badge>}
                  {event.error && <p className="w-full text-xs text-danger">{event.error}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardBody>
    </Card>
  );
}
