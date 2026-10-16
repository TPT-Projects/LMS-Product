import { STORAGE_KEYS, storage } from '@/lib/storage';

/**
 * Access token: memory only (short-lived, never persisted).
 * Refresh token: localStorage, rotated on every refresh and blacklisted on logout.
 */
let accessToken: string | null = null;

export const tokens = {
  getAccess: () => accessToken,
  getRefresh: () => storage.get(STORAGE_KEYS.refreshToken),
  set(access: string, refresh: string) {
    accessToken = access;
    storage.set(STORAGE_KEYS.refreshToken, refresh);
  },
  clear() {
    accessToken = null;
    storage.remove(STORAGE_KEYS.refreshToken);
  },
};
