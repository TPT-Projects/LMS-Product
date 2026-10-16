import { CheckCircle2, MessageCircle, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Badge, Button, Card, CardBody, CardHeader, Skeleton } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { getErrorMessage } from '@/lib/api/errors';

import {
  useChooseWhatsAppNumber,
  useRefreshWhatsApp,
  useRegisterWhatsAppNumber,
  useWhatsApp,
} from '../api';
import { WhatsAppConnectOptions } from '../whatsapp/WhatsAppConnectOptions';

const QUALITY: Record<string, 'success' | 'warning' | 'danger'> = {
  GREEN: 'success',
  YELLOW: 'warning',
  RED: 'danger',
};

/** WhatsApp's Manage page: the accounts and numbers shared in the Facebook popup. */
export function WhatsAppManage() {
  const { t } = useTranslation();
  const format = useDateFormat();
  const whatsapp = useWhatsApp();
  const choose = useChooseWhatsAppNumber();
  const refresh = useRefreshWhatsApp();
  const register = useRegisterWhatsAppNumber();
  const [adding, setAdding] = useState(false);

  if (whatsapp.isPending) return <Skeleton className="h-48 w-full" />;
  if (whatsapp.isError) return <Alert tone="danger">{getErrorMessage(whatsapp.error)}</Alert>;
  const data = whatsapp.data;
  const error = choose.error ?? refresh.error ?? register.error;

  return (
    <Card>
      <CardHeader
        title={t('whatsappManage.title')}
        description={t('whatsappManage.description')}
        actions={
          <Button
            variant="secondary"
            size="sm"
            loading={refresh.isPending}
            onClick={() => refresh.mutate(undefined)}
          >
            <RefreshCw className="size-3.5" aria-hidden /> {t('whatsappManage.refresh')}
          </Button>
        }
      />
      <CardBody className="space-y-4">
        {error != null && <Alert tone="danger">{getErrorMessage(error)}</Alert>}
        {data.accounts.map((account) => (
          <section key={account.id}>
            <h3 className="mb-1.5 text-xs font-medium tracking-wide text-fg-muted uppercase">
              {account.name || account.id}
            </h3>
            {account.numbers.length === 0 ? (
              <p className="text-[13px] text-fg-muted">{t('whatsappManage.noNumbers')}</p>
            ) : (
              <ul className="divide-y rounded-xl border">
                {account.numbers.map((number) => {
                  const selected = data.phone_number_id === number.id;
                  return (
                    <li key={number.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                      <MessageCircle className="size-4 shrink-0 text-[#25D366]" aria-hidden />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium tabular-nums">{number.display_phone_number}</p>
                        <p className="text-xs text-fg-muted">{number.verified_name}</p>
                      </div>
                      {number.quality_rating && (
                        <Badge tone={QUALITY[number.quality_rating] ?? 'neutral'}>
                          {t('whatsappManage.quality', {
                            rating: t(`whatsappManage.ratings.${number.quality_rating}`, {
                              defaultValue: number.quality_rating,
                            }),
                          })}
                        </Badge>
                      )}
                      {number.platform_type === 'NOT_APPLICABLE' ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          loading={register.isPending && register.variables === number.id}
                          onClick={() => register.mutate(number.id)}
                        >
                          {t('whatsappManage.register')}
                        </Button>
                      ) : (
                        number.platform_type && (
                          <Badge tone="success">{t('whatsappManage.registered')}</Badge>
                        )
                      )}
                      {selected ? (
                        <span className="inline-flex items-center gap-1 text-[13px] font-medium text-success">
                          <CheckCircle2 className="size-4" aria-hidden />{' '}
                          {t('whatsappManage.inUse')}
                        </span>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          loading={choose.isPending && choose.variables === number.id}
                          onClick={() => choose.mutate(number.id)}
                        >
                          {t('whatsappManage.use')}
                        </Button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        ))}
        {data.setup_issues.length > 0 && (
          <Alert tone="danger">
            <ul className="list-disc space-y-0.5 pl-5">
              {data.setup_issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </Alert>
        )}
        {data.flow === 'coexistence' && (
          <Alert tone="info">{t('whatsappManage.coexistence')}</Alert>
        )}
        {data.two_step_pin && (
          <p className="text-xs text-fg-muted">
            {t('whatsappManage.pin')}{' '}
            <span className="font-mono font-medium text-fg">{data.two_step_pin}</span>
          </p>
        )}
        <div className="border-t pt-4">
          {adding ? (
            <WhatsAppConnectOptions onConnected={() => setAdding(false)} />
          ) : (
            <Button variant="secondary" size="sm" onClick={() => setAdding(true)}>
              {t('whatsappManage.addNumber')}
            </Button>
          )}
        </div>
        <p className="text-xs text-fg-muted">
          {data.token_expires_at
            ? t('whatsappManage.expires', { when: format.date(data.token_expires_at) })
            : t('whatsappManage.reconnectHint')}
        </p>
      </CardBody>
    </Card>
  );
}
