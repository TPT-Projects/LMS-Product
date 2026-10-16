import { describe, expect, it } from 'vitest';

import { move, resolveColumns, type ColumnOption } from './columns';

const options: ColumnOption[] = [
  { id: 'name', label: 'Name', fixed: 'start' },
  { id: 'status', label: 'Status', fixed: 'start' },
  { id: 'a', label: 'A', defaultVisible: true },
  { id: 'b', label: 'B', defaultVisible: true },
  { id: 'c', label: 'C' },
  { id: 'action', label: 'Action', fixed: 'end' },
];

describe('column layouts', () => {
  it('uses the defaults until the user saves a layout', () => {
    expect(resolveColumns(options, [])).toEqual(['name', 'status', 'a', 'b', 'action']);
  });

  it('keeps the user order and the fixed columns in place', () => {
    expect(resolveColumns(options, ['a', 'c', 'b'])).toEqual([
      'name',
      'status',
      'a',
      'c',
      'b',
      'action',
    ]);
  });

  it('ignores unknown ids and never lets fixed columns move', () => {
    expect(resolveColumns(options, ['gone', 'action', 'c'])).toEqual([
      'name',
      'status',
      'c',
      'action',
    ]);
  });

  it('moves items', () => {
    expect(move(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b']);
    expect(move(['a', 'b'], 0, 5)).toEqual(['a', 'b']);
  });
});
