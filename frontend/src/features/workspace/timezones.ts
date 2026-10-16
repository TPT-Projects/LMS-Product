/** Some browsers still report old IANA names. */
const ALIASES: Record<string, string> = {
  'Asia/Calcutta': 'Asia/Kolkata',
  'Asia/Saigon': 'Asia/Ho_Chi_Minh',
};

export function normalizeTimezone(tz: string): string {
  return ALIASES[tz] ?? tz;
}

/** Every IANA timezone the browser knows, plus the ones we always need. */
export function allTimezones(): string[] {
  let zones: string[] = [];
  try {
    zones = Intl.supportedValuesOf('timeZone');
  } catch {
    /* very old browser: fall back to a short list */
  }
  return [
    ...new Set([...zones.map(normalizeTimezone), 'Asia/Kolkata', 'Asia/Dubai', 'UTC']),
  ].sort();
}
