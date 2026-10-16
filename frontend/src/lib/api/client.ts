import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';

import { env } from '@/lib/env';

import { tokens } from './tokens';

export const api = axios.create({
  baseURL: env.apiBaseUrl,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

/** Fired when the session cannot be refreshed; AuthProvider listens and logs out. */
export const SESSION_EXPIRED_EVENT = 'lms:session-expired';

api.interceptors.request.use((config) => {
  const access = tokens.getAccess();
  if (access) config.headers.Authorization = `Bearer ${access}`;
  return config;
});

// One refresh at a time: parallel 401s wait for the same promise.
let refreshing: Promise<string> | null = null;

export async function refreshAccessToken(): Promise<string> {
  const refresh = tokens.getRefresh();
  if (!refresh) throw new Error('No refresh token');
  refreshing ??= axios
    .post<{ access: string; refresh: string }>(`${env.apiBaseUrl}/auth/refresh`, { refresh })
    .then(({ data }) => {
      tokens.set(data.access, data.refresh);
      return data.access;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

const NO_RETRY = ['/auth/login', '/auth/signup', '/auth/refresh', '/auth/accept-invite'];

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as
      (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const isAuthCall = NO_RETRY.some((path) => original?.url?.includes(path));

    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      try {
        const access = await refreshAccessToken();
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      } catch {
        tokens.clear();
        window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
      }
    }
    return Promise.reject(error);
  },
);
