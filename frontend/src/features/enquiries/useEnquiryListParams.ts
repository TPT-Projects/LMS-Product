import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

import { DEFAULT_PAGE_SIZE, PAGE_SIZES } from '@/hooks/usePageParams';
import { smartViews } from '@/routes/paths';
import { SOURCES, type FilterGroup, type Source } from '@/types/crm';

import type { EnquiryListParams } from './api';

const list = (raw: string | null) => (raw ? raw.split(',').filter(Boolean) : []);

function parseFilter(raw: string | null): FilterGroup | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as FilterGroup;
    return value && Array.isArray(value.rules) ? value : null;
  } catch {
    return null;
  }
}

/** All list state lives in the URL, so views can be bookmarked and shared. */
export function useEnquiryListParams() {
  const [search, setSearch] = useSearchParams();

  const params: EnquiryListParams = useMemo(() => {
    const view = search.get('view') ?? 'all';
    const size = Number(search.get('page_size'));
    const savedView = Number(search.get('saved_view'));
    return {
      view: smartViews.some((v) => v.id === view) ? view : 'all',
      saved_view: Number.isInteger(savedView) && savedView > 0 ? savedView : null,
      page: Math.max(1, Number(search.get('page')) || 1),
      page_size: (PAGE_SIZES as readonly number[]).includes(size) ? size : DEFAULT_PAGE_SIZE,
      q: search.get('q') ?? '',
      sort: search.get('sort') ?? '',
      status: list(search.get('status')).map(Number).filter(Number.isFinite),
      owner: list(search.get('owner')),
      source: list(search.get('source')).filter((s): s is Source => SOURCES.includes(s as Source)),
      filter: parseFilter(search.get('filter')),
    };
  }, [search]);

  const update = useCallback(
    (changes: Partial<EnquiryListParams>, { keepPage = false } = {}) => {
      setSearch(
        (prev) => {
          const next = new URLSearchParams(prev);
          const set = (key: string, value: string | null | undefined) => {
            if (value === null || value === undefined || value === '') next.delete(key);
            else next.set(key, value);
          };
          for (const [key, value] of Object.entries(changes)) {
            if (key === 'filter') {
              const tree = value as FilterGroup | null;
              set('filter', tree && tree.rules.length ? JSON.stringify(tree) : null);
            } else if (Array.isArray(value)) {
              set(key, value.join(','));
            } else if (key === 'page_size') {
              set(key, value === DEFAULT_PAGE_SIZE ? null : String(value));
            } else if (key === 'page') {
              set(key, Number(value) <= 1 ? null : String(value));
            } else if (key === 'view') {
              set(key, value === 'all' ? null : String(value));
            } else {
              set(key, value === null || value === undefined ? null : String(value));
            }
          }
          if (!keepPage && !('page' in changes)) next.delete('page');
          return next;
        },
        { replace: true },
      );
    },
    [setSearch],
  );

  const clearFilters = useCallback(
    () => update({ q: '', status: [], owner: [], source: [], filter: null }),
    [update],
  );

  return { params, update, clearFilters };
}
