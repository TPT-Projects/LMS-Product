export type PageItem = number | 'gap';

/**
 * Page numbers with gaps, e.g. for page 6 of 20: [1, 'gap', 5, 6, 7, 'gap', 20].
 * Always shows the first and last page and `siblings` pages on each side.
 */
export function pageNumbers(current: number, total: number, siblings = 1): PageItem[] {
  if (total <= 1) return [1];
  const start = Math.max(2, current - siblings);
  const end = Math.min(total - 1, current + siblings);
  const items: PageItem[] = [1];
  if (start > 2) items.push('gap');
  for (let page = start; page <= end; page += 1) items.push(page);
  if (end < total - 1) items.push('gap');
  items.push(total);
  return items;
}
