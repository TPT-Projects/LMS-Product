import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';

import { api } from '@/lib/api/client';
import { UserFacingError } from '@/lib/api/errors';

import { integrationKeys, type WhatsAppManage } from '../api';

/** "new": a new number (or one already on the Cloud API). "coexistence": WhatsApp Business app number. */
export type SignupFlow = 'new' | 'coexistence';

interface SignupConfig {
  available: boolean;
  app_id: string;
  config_id: string;
  graph_version: string;
}

interface FacebookSdk {
  init: (options: Record<string, unknown>) => void;
  login: (
    callback: (response: { authResponse?: { code?: string } | null; status?: string }) => void,
    options: Record<string, unknown>,
  ) => void;
}

declare global {
  interface Window {
    FB?: FacebookSdk;
    fbAsyncInit?: () => void;
  }
}

const SDK_URL = 'https://connect.facebook.net/en_US/sdk.js';
let sdkPromise: Promise<FacebookSdk> | null = null;

/** Load Meta's JavaScript SDK once (Embedded Signup must be started with FB.login). */
function loadSdk(config: SignupConfig): Promise<FacebookSdk> {
  if (!sdkPromise) {
    sdkPromise = new Promise((resolve, reject) => {
      window.fbAsyncInit = () => {
        window.FB!.init({
          appId: config.app_id,
          autoLogAppEvents: true,
          xfbml: false,
          version: config.graph_version,
        });
        resolve(window.FB!);
      };
      const script = document.createElement('script');
      script.src = SDK_URL;
      script.async = true;
      script.crossOrigin = 'anonymous';
      script.onerror = () => {
        sdkPromise = null;
        reject(new UserFacingError('Could not load Facebook. Check your connection.'));
      };
      document.body.appendChild(script);
    });
  }
  return sdkPromise;
}

export function useWhatsAppSignupConfig() {
  return useQuery({
    queryKey: ['integrations', 'whatsapp', 'signup-config'],
    queryFn: () =>
      api.get<SignupConfig>('/integrations/whatsapp/signup-config').then((r) => r.data),
    staleTime: Infinity,
  });
}

interface SessionInfo {
  waba_id?: string;
  phone_number_id?: string;
}

/**
 * Meta's WhatsApp Embedded Signup (the flow Make.com uses): a Facebook popup where the person
 * picks or creates their WhatsApp Business Account and adds a new number or connects their
 * WhatsApp Business app number. The popup reports the account and number ids; the code is
 * sent to the server, which finishes the setup (subscribe, register).
 */
export function useEmbeddedSignup({ onConnected }: { onConnected?: () => void } = {}) {
  const config = useWhatsAppSignupConfig();
  const queryClient = useQueryClient();
  const session = useRef<SessionInfo>({});
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (!event.origin.endsWith('facebook.com')) return;
      try {
        const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
        if (data?.type !== 'WA_EMBEDDED_SIGNUP') return;
        if (data.event === 'CANCEL') {
          setRunning(false);
          if (data.data?.error_message) setError(new UserFacingError(data.data.error_message));
          return;
        }
        session.current = {
          waba_id: data.data?.waba_id ?? data.data?.waba_ids?.[0],
          phone_number_id: data.data?.phone_number_id,
        };
      } catch {
        /* not a signup message */
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  const finish = useMutation({
    mutationFn: (body: { code: string; flow: SignupFlow } & SessionInfo) =>
      api.post<WhatsAppManage>('/integrations/whatsapp/embedded', body).then((r) => r.data),
    onSuccess: (data) => {
      queryClient.setQueryData(['integrations', 'whatsapp', 'manage'], data);
      void queryClient.invalidateQueries({ queryKey: integrationKeys.all, exact: true });
      onConnected?.();
    },
  });

  const start = useCallback(
    async (flow: SignupFlow) => {
      setError(null);
      if (!config.data?.available) return;
      setRunning(true);
      session.current = {};
      try {
        const FB = await loadSdk(config.data);
        FB.login(
          (response) => {
            const code = response.authResponse?.code;
            if (!code) {
              setRunning(false);
              return; // closed or cancelled
            }
            // The account / number message can arrive just after the callback: wait briefly.
            window.setTimeout(() => {
              finish.mutate(
                { code, flow, ...session.current },
                { onSettled: () => setRunning(false) },
              );
            }, 800);
          },
          {
            config_id: config.data.config_id,
            response_type: 'code',
            override_default_response_type: true,
            extras: {
              setup: {},
              sessionInfoVersion: '3',
              ...(flow === 'coexistence'
                ? { featureType: 'whatsapp_business_app_onboarding' }
                : {}),
            },
          },
        );
      } catch (err) {
        setError(err);
        setRunning(false);
      }
    },
    [config.data, finish],
  );

  return {
    available: Boolean(config.data?.available),
    loading: config.isPending,
    start,
    running: running || finish.isPending,
    error: error ?? finish.error,
  };
}
