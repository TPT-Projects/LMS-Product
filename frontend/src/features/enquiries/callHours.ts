import type { CallWindow } from './api';

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;

/** "Mon, Tue, Wed 09:00-19:00" in the workspace's words. */
export function describeWindow(hours: CallWindow, t: (key: string) => string): string {
  const days = hours.days.map((d) => t(`weekdays.${DAY_KEYS[d]}`)).join(', ');
  return `${days} ${hours.start}-${hours.end}`;
}

/** Is this UTC time inside the calling hours (workspace time zone)? */
export function insideWindow(utcIso: string, hours: CallWindow, tz: string): boolean {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: tz,
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(utcIso));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  const weekday = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].indexOf(get('weekday'));
  const minutes = `${get('hour')}:${get('minute')}`;
  return hours.days.includes(weekday) && minutes >= hours.start && minutes < hours.end;
}
