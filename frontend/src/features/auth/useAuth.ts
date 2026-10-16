import { useContext } from 'react';

import { formatDate, formatDateTime } from '@/lib/dates';

import { AuthContext } from './authContext';

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

/** The logged-in session. Only use inside protected routes. */
export function useSession() {
  const { session } = useAuth();
  if (!session) throw new Error('useSession called without a session');
  return session;
}

/** Date formatters bound to the workspace timezone (DD/MM/YYYY). */
export function useDateFormat() {
  const { workspace } = useSession();
  const tz = workspace.timezone;
  return {
    date: (value: string | null | undefined) => formatDate(value, tz),
    dateTime: (value: string | null | undefined) => formatDateTime(value, tz),
  };
}
