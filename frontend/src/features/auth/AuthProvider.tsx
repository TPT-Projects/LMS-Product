import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { refreshAccessToken, SESSION_EXPIRED_EVENT } from '@/lib/api/client';
import { tokens } from '@/lib/api/tokens';
import type { AuthResponse, Capability, Session } from '@/types/auth';

import { authApi } from './api';
import { AuthContext, type AuthContextValue, type AuthStatus } from './authContext';

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>(() =>
    tokens.getRefresh() ? 'loading' : 'anonymous',
  );
  const [session, setSession] = useState<Session | null>(null);

  const clear = useCallback(() => {
    tokens.clear();
    setSession(null);
    setStatus('anonymous');
    queryClient.clear(); // never show one workspace's cached data in another
  }, [queryClient]);

  // On first load: turn the stored refresh token into a session.
  useEffect(() => {
    if (!tokens.getRefresh()) return;
    let cancelled = false;
    refreshAccessToken()
      .then(() => authApi.me())
      .then((me) => {
        if (cancelled) return;
        setSession(me);
        setStatus('authenticated');
      })
      .catch(() => {
        if (!cancelled) clear();
      });
    return () => {
      cancelled = true;
    };
  }, [clear]);

  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED_EVENT, clear);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, clear);
  }, [clear]);

  const startSession = useCallback(
    (response: AuthResponse) => {
      queryClient.clear();
      tokens.set(response.access, response.refresh);
      setSession(response.session);
      setStatus('authenticated');
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    const refresh = tokens.getRefresh();
    try {
      if (refresh) await authApi.logout(refresh);
    } finally {
      clear();
    }
  }, [clear]);

  const switchWorkspace = useCallback(
    async (tenantId: number) => startSession(await authApi.switchWorkspace(tenantId)),
    [startSession],
  );

  const reloadSession = useCallback(async () => setSession(await authApi.me()), []);

  const can = useCallback(
    (capability: Capability) => Boolean(session?.capabilities.includes(capability)),
    [session],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ status, session, startSession, logout, switchWorkspace, reloadSession, can }),
    [status, session, startSession, logout, switchWorkspace, reloadSession, can],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
