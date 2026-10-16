import { STORAGE_KEYS, storage } from './storage';

export type ThemePreference = 'light' | 'dark' | 'system';

export function getThemePreference(): ThemePreference {
  const value = storage.get(STORAGE_KEYS.theme);
  return value === 'light' || value === 'dark' ? value : 'system';
}

export function applyTheme(preference: ThemePreference): void {
  const dark =
    preference === 'dark' ||
    (preference === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', dark);
  if (preference === 'system') storage.remove(STORAGE_KEYS.theme);
  else storage.set(STORAGE_KEYS.theme, preference);
}
