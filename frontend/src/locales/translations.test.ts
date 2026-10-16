import { describe, expect, it } from 'vitest';

import en from './en.json';

/** Guards the "no hardcoded text" rule: every t('key') used in code must exist. */
const sources = import.meta.glob(['/src/**/*.{ts,tsx}', '!/src/**/*.test.ts'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

function has(key: string): boolean {
  let node: unknown = en;
  for (const part of key.split('.')) {
    if (typeof node !== 'object' || node === null) return false;
    node = (node as Record<string, unknown>)[part];
  }
  return node !== undefined;
}

describe('translations', () => {
  it('has every static key used in code', () => {
    const missing = new Set<string>();
    for (const code of Object.values(sources)) {
      for (const match of code.matchAll(/\bt\('([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)'/g)) {
        const key = match[1]!;
        if (!has(key) && !has(`${key}_one`)) missing.add(key); // `_one` = pluralised key
      }
      for (const match of code.matchAll(
        /'((?:validation|nav\.views|settings\.tabs|shortcuts)\.[a-zA-Z]+)'/g,
      )) {
        if (!has(match[1]!)) missing.add(match[1]!);
      }
    }
    expect([...missing]).toEqual([]);
  });

  it('has pluralised keys for counts', () => {
    expect(has('teams.memberCount_one') && has('teams.memberCount_other')).toBe(true);
  });
});
