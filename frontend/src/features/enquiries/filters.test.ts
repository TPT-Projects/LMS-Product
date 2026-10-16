import { describe, expect, it } from 'vitest';

import { cleanTree, countRules, newRule, STANDARD_FIELDS, valueInputFor } from './filters';

describe('filter builder model', () => {
  it('drops unfinished rules and empty groups', () => {
    const tree = cleanTree({
      op: 'and',
      rules: [
        { field: 'name', operator: 'contains', value: '' },
        { field: 'status', operator: 'in', value: [1] },
        { op: 'or', rules: [{ field: 'campaign', operator: 'contains', value: '' }] },
        { field: 'is_repeat', operator: 'is_true' },
      ],
    });
    expect(tree).toEqual({
      op: 'and',
      rules: [
        { field: 'status', operator: 'in', value: [1] },
        { field: 'is_repeat', operator: 'is_true' },
      ],
    });
    expect(countRules(tree)).toBe(2);
  });

  it('picks the right input for each operator', () => {
    expect(valueInputFor('datetime', 'between')).toBe('date_range');
    expect(valueInputFor('currency', 'gt')).toBe('number');
    expect(valueInputFor('dropdown', 'in')).toBe('options');
    expect(valueInputFor('text', 'is_empty')).toBe('none');
  });

  it('creates a usable default rule for every standard field', () => {
    for (const field of STANDARD_FIELDS) {
      expect(newRule(field).field).toBe(field.id);
    }
  });
});
