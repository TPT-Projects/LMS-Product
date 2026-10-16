/**
 * Column layouts that each user can change.
 *
 * A table declares every column it can show. Fixed columns are always shown in
 * their place (start or end) and cannot be hidden or moved. The user chooses
 * which of the other columns to show and in which order; that list is saved
 * per user and per table on the server.
 */
export interface ColumnOption {
  id: string;
  label: string;
  /** Always shown: "start" columns before the user's columns, "end" after. */
  fixed?: 'start' | 'end';
  /** Shown when the user has not saved a layout yet. */
  defaultVisible?: boolean;
}

export function defaultLayout(options: ColumnOption[]): string[] {
  return options.filter((o) => !o.fixed && o.defaultVisible).map((o) => o.id);
}

/** The ids to render, in order: fixed start, the user's columns, fixed end. */
export function resolveColumns(options: ColumnOption[], saved: string[] | undefined): string[] {
  const known = new Set(options.filter((o) => !o.fixed).map((o) => o.id));
  const chosen =
    saved && saved.length ? saved.filter((id) => known.has(id)) : defaultLayout(options);
  return [
    ...options.filter((o) => o.fixed === 'start').map((o) => o.id),
    ...chosen,
    ...options.filter((o) => o.fixed === 'end').map((o) => o.id),
  ];
}

/** Move an item inside a list (used by drag and drop and the arrow buttons). */
export function move<T>(list: T[], from: number, to: number): T[] {
  if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) return list;
  const next = [...list];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item as T);
  return next;
}
