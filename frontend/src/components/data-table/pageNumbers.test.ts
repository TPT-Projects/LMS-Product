import { describe, expect, it } from 'vitest';

import { pageNumbers } from './pageNumbers';

describe('pageNumbers', () => {
  it('handles small page counts', () => {
    expect(pageNumbers(1, 1)).toEqual([1]);
    expect(pageNumbers(2, 3)).toEqual([1, 2, 3]);
  });

  it('adds gaps around the current page', () => {
    expect(pageNumbers(6, 20)).toEqual([1, 'gap', 5, 6, 7, 'gap', 20]);
    expect(pageNumbers(1, 20)).toEqual([1, 2, 'gap', 20]);
    expect(pageNumbers(20, 20)).toEqual([1, 'gap', 19, 20]);
  });
});
