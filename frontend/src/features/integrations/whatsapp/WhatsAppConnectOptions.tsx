import { Info, MessageCircle, Smartphone } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Alert, Button, Skeleton } from '@/components/ui';
import { useOAuthPopup } from '@/features/meta/api';
import { getErrorMessage } from '@/lib/api/errors';

import { useEmbeddedSignup, type SignupFlow } from './useEmbeddedSignup';

const OPTIONS: { flow: SignupFlow; icon: typeof MessageCircle }[] = [
  { flow: 'new', icon: MessageCircle },
  { flow: 'coexistence', icon: Smartphone },
];

/** The two ways to connect WhatsApp (like Make.com): a new/API number, or the Business app number. */
export function WhatsAppConnectOptions({ onConnected }: { onConnected?: () => void }) {
  const { t } = useTranslation();
  const signup = useEmbeddedSignup({ onConnected });
  const simple = useOAuthPopup({
    app: 'whatsapp',
    startPath: '/integrations/whatsapp/connect',
    onConnected: () => onConnected?.(),
  });

  if (signup.loading) return <Skeleton className="h-28 w-full" />;

  return (
    <div className="space-y-3">
      {signup.available ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {OPTIONS.map(({ flow, icon: Icon }) => (
            <div key={flow} className="flex flex-col gap-3 rounded-xl border bg-surface p-4">
              <div className="flex items-start gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[#25D366] text-white">
                  <Icon className="size-4" aria-hidden />
                </span>
                <div>
                  <p className="font-medium">{t(`whatsappConnect.${flow}.title`)}</p>
                  <p className="text-xs text-fg-muted">{t(`whatsappConnect.${flow}.hint`)}</p>
                </div>
              </div>
              <Button
                className="mt-auto"
                variant={flow === 'new' ? 'primary' : 'secondary'}
                loading={signup.running}
                onClick={() => void signup.start(flow)}
              >
                {t(`whatsappConnect.${flow}.button`)}
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <>
          <Alert tone="info">
            <span className="inline-flex items-start gap-1.5">
              <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
              {t('whatsappConnect.notSetUp')}
            </span>
          </Alert>
          <Button loading={simple.isPending} onClick={() => void simple.start()}>
            {t('whatsappConnect.simple')}
          </Button>
        </>
      )}
      {signup.error != null && <Alert tone="danger">{getErrorMessage(signup.error)}</Alert>}
      {simple.error != null && <Alert tone="danger">{getErrorMessage(simple.error)}</Alert>}
    </div>
  );
}
