/**
 * Date rules (spec 0.8): the API sends UTC ISO strings; the UI always shows
 * DD/MM/YYYY in the workspace timezone.
 */

type DateInput = string | number | Date | null | undefined;

function toDate(value: DateInput): Date | null {
  if (value === null || value === undefined || value === '') return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function parts(date: Date, timeZone: string, withTime: boolean) {
  const formatter = new Intl.DateTimeFormat('en-GB', {
    timeZone,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' as const } : {}),
  });
  const map: Record<string, string> = {};
  for (const p of formatter.formatToParts(date)) map[p.type] = p.value;
  return map;
}

/** "30/06/2026" */
export function formatDate(value: DateInput, timeZone: string, fallback = '—'): string {
  const date = toDate(value);
  if (!date) return fallback;
  const p = parts(date, timeZone, false);
  return `${p.day}/${p.month}/${p.year}`;
}

/** "30/06/2026 01:30" */
export function formatDateTime(value: DateInput, timeZone: string, fallback = '—'): string {
  const date = toDate(value);
  if (!date) return fallback;
  const p = parts(date, timeZone, true);
  return `${p.day}/${p.month}/${p.year} ${p.hour}:${p.minute}`;
}

/** Parse "DD/MM/YYYY" into { year, month, day }, or null if invalid. */
export function parseDisplayDate(
  value: string,
): { year: number; month: number; day: number } | null {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim());
  if (!match) return null;
  const [, d, m, y] = match;
  const day = Number(d);
  const month = Number(m);
  const year = Number(y);
  const check = new Date(Date.UTC(year, month - 1, day));
  if (
    check.getUTCFullYear() !== year ||
    check.getUTCMonth() !== month - 1 ||
    check.getUTCDate() !== day
  ) {
    return null;
  }
  return { year, month, day };
}

/** Minutes the zone is ahead of UTC at a given instant (e.g. +330 for Asia/Kolkata). */
function zoneOffsetMinutes(instant: Date, timeZone: string): number {
  const p = parts(instant, timeZone, true);
  const asUtc = Date.UTC(
    Number(p.year),
    Number(p.month) - 1,
    Number(p.day),
    Number(p.hour),
    Number(p.minute),
  );
  return Math.round((asUtc - instant.getTime()) / 60_000);
}

/**
 * A wall-clock date and time in the workspace timezone -> UTC ISO string.
 * e.g. ("05/07/2026", "10:30", "Asia/Kolkata") -> "2026-07-05T05:00:00.000Z"
 */
export function zonedToUtcIso(date: string, time: string, timeZone: string): string | null {
  const d = parseDisplayDate(date);
  const t = /^(\d{1,2}):(\d{2})$/.exec(time.trim());
  if (!d || !t) return null;
  const hour = Number(t[1]);
  const minute = Number(t[2]);
  if (hour > 23 || minute > 59) return null;
  const wall = Date.UTC(d.year, d.month - 1, d.day, hour, minute);
  // Two passes handle a DST change between the guess and the answer.
  let utc = wall - zoneOffsetMinutes(new Date(wall), timeZone) * 60_000;
  utc = wall - zoneOffsetMinutes(new Date(utc), timeZone) * 60_000;
  return new Date(utc).toISOString();
}

/** Today's date in the workspace timezone as DD/MM/YYYY. */
export function todayDisplay(timeZone: string): string {
  return formatDate(new Date(), timeZone);
}

/** Inserts the slashes as the user types: "05072026" -> "05/07/2026". */
export function maskDisplayDate(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}
