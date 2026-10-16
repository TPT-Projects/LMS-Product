import { CheckCircle2, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { Button, Spinner } from '@/components/ui';
import { paths } from '@/routes/paths';

import { OAUTH_CHANNEL, type OAuthMessage } from '../api';

/**
 * The backend sends the Facebook login popup here. Tell the main window, which answers
 * "ack", then close. With no main window listening (popup was blocked and the whole tab
 * went to Facebook), continue in this tab.
 */
export default function MetaOAuthDonePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const ok = params.get('result') === 'ok';
  const message = params.get('message') ?? '';
  const app = params.get('app') ?? ''; // '' = Meta lead ads
  const next = app ? `${paths.apps}/${app}` : paths.settingsMetaSetup;
  const [stuck, setStuck] = useState(false);

  useEffect(() => {
    const channel = new BroadcastChannel(OAUTH_CHANNEL);
    let acknowledged = false;
    channel.onmessage = ({ data }: MessageEvent<OAuthMessage>) => {
      if (data?.type !== 'ack' || (data.app ?? '') !== app) return;
      acknowledged = true;
      window.close();
      setStuck(true); // still here: the browser refused to close the window
    };
    channel.postMessage({
      type: 'result',
      app,
      result: ok ? 'ok' : 'error',
      message,
    } satisfies OAuthMessage);
    const timer = window.setTimeout(() => {
      if (acknowledged) return;
      if (ok) navigate(next, { replace: true });
      else setStuck(true);
    }, 1200);
    return () => {
      window.clearTimeout(timer);
      channel.close();
    };
  }, [app, message, navigate, next, ok]);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-subtle p-6">
      <div className="w-full max-w-sm rounded-2xl border bg-surface p-6 text-center shadow-sm">
        {ok ? (
          <CheckCircle2 className="mx-auto size-10 text-success" aria-hidden />
        ) : (
          <XCircle className="mx-auto size-10 text-danger" aria-hidden />
        )}
        <h1 className="mt-3 text-lg font-semibold">
          {ok ? t('meta.oauthDone.ok') : t('meta.oauthDone.error')}
        </h1>
        {message && <p className="mt-1 text-[13px] text-fg-muted">{message}</p>}
        {stuck ? (
          <div className="mt-4 space-y-3">
            <p className="text-[13px] text-fg-muted">{t('meta.oauthDone.closeHint')}</p>
            <Link to={ok ? next : app ? `${paths.apps}/${app}` : paths.settingsMeta}>
              <Button variant="secondary" className="w-full">
                {ok ? t('meta.oauthDone.continue') : t('meta.back')}
              </Button>
            </Link>
          </div>
        ) : (
          <p className="mt-4 flex items-center justify-center gap-2 text-[13px] text-fg-muted">
            <Spinner className="size-4" /> {t('meta.oauthDone.returning')}
          </p>
        )}
      </div>
    </main>
  );
}
