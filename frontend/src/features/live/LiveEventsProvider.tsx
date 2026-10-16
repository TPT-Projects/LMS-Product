import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { refreshAccessToken } from '@/lib/api/client';
import { tokens } from '@/lib/api/tokens';
import { env } from '@/lib/env';

import { LiveContext, type LiveEvent, type LiveStatus } from './liveContext';

const MAX_DELAY = 30_000;

/**
 * One WebSocket per tab for live updates (spec: new-lead alert, notifications).
 * Reconnects with back-off; refreshes the access token if the server rejects it.
 * Everything still works without it: pages refetch on their own.
 */
export function LiveEventsProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<LiveStatus>('connecting');
  const [newLeads, setNewLeads] = useState(0);
  const listeners = useRef(new Set<(event: LiveEvent) => void>());

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry = 0;
    let timer: number | undefined;
    let stopped = false;
    let ping: number | undefined;

    const handle = (event: LiveEvent) => {
      if (event.event === 'notification') {
        void queryClient.invalidateQueries({ queryKey: ['notifications'] });
      }
      if (event.event === 'enquiry.created') {
        setNewLeads((n) => n + 1);
        void queryClient.invalidateQueries({ queryKey: ['views', 'counts'] });
      }
      listeners.current.forEach((listener) => listener(event));
    };

    const connect = async () => {
      if (stopped) return;
      let access = tokens.getAccess();
      if (!access) {
        try {
          access = await refreshAccessToken();
        } catch {
          return; // logged out: AuthProvider takes care of it
        }
      }
      setStatus('connecting');
      socket = new WebSocket(`${env.wsUrl}/tenant/?token=${encodeURIComponent(access)}`);
      socket.onopen = () => {
        retry = 0;
        setStatus('open');
        ping = window.setInterval(() => socket?.send(JSON.stringify({ type: 'ping' })), 25_000);
      };
      socket.onmessage = (message) => {
        try {
          handle(JSON.parse(message.data as string) as LiveEvent);
        } catch {
          /* ignore malformed messages */
        }
      };
      socket.onclose = (close) => {
        window.clearInterval(ping);
        if (stopped) return;
        setStatus('closed');
        const reconnect = async () => {
          if (close.code === 4401) {
            try {
              await refreshAccessToken(); // the token expired while the tab was open
            } catch {
              return;
            }
          }
          void connect();
        };
        const delay = Math.min(MAX_DELAY, 1000 * 2 ** retry++);
        timer = window.setTimeout(() => void reconnect(), delay);
      };
    };

    void connect();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      window.clearInterval(ping);
      socket?.close();
    };
  }, [queryClient]);

  const value = useMemo(
    () => ({
      status,
      newLeads,
      clearNewLeads: () => setNewLeads(0),
      subscribe: (listener: (event: LiveEvent) => void) => {
        listeners.current.add(listener);
        return () => void listeners.current.delete(listener);
      },
    }),
    [status, newLeads],
  );

  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}
