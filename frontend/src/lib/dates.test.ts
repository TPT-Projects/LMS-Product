import { describe, expect, it } from 'vitest';

import { formatDate, formatDateTime, parseDisplayDate, zonedToUtcIso } from './dates';

describe('dates', () => {
  it('shows DD/MM/YYYY in the workspace timezone', () => {
    const lateUtc = '2026-06-29T20:00:00Z'; // already 30 June in India
    expect(formatDate(lateUtc, 'Asia/Kolkata')).toBe('30/06/2026');
    expect(formatDate(lateUtc, 'UTC')).toBe('29/06/2026');
    expect(formatDateTime(lateUtc, 'Asia/Kolkata')).toBe('30/06/2026 01:30');
  });

  it('returns a fallback for empty or invalid input', () => {
    expect(formatDate(null, 'UTC')).toBe('—');
    expect(formatDate('not a date', 'UTC', '')).toBe('');
  });

  it('parses DD/MM/YYYY strictly', () => {
    expect(parseDisplayDate('05/07/2026')).toEqual({ year: 2026, month: 7, day: 5 });
    expect(parseDisplayDate('31/02/2026')).toBeNull();
    expect(parseDisplayDate('2026-07-05')).toBeNull();
  });
});

describe('zonedToUtcIso', () => {
  it('converts a workspace wall-clock time to UTC', () => {
    expect(zonedToUtcIso('05/07/2026', '10:30', 'Asia/Kolkata')).toBe('2026-07-05T05:00:00.000Z');
    expect(zonedToUtcIso('05/07/2026', '10:30', 'UTC')).toBe('2026-07-05T10:30:00.000Z');
    expect(zonedToUtcIso('15/01/2026', '09:00', 'America/New_York')).toBe(
      '2026-01-15T14:00:00.000Z',
    );
  });

  it('rejects bad input', () => {
    expect(zonedToUtcIso('31/02/2026', '10:00', 'UTC')).toBeNull();
    expect(zonedToUtcIso('05/07/2026', '25:00', 'UTC')).toBeNull();
  });
});
