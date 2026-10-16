import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

import type { PageParams } from '@/types/api';

export const PAGE_SIZES = [25, 50, 100, 200] as const;
export const DEFAULT_PAGE_SIZE = 25;

/** Keeps `page` and `page_size` in the URL so paging survives reloads and can be shared. */
export function usePageParams() {
  const [searchParams, setSearchParams] = useSearchParams();

  const params: PageParams = useMemo(() => {
    const page = Math.max(1, Number(searchParams.get('page')) || 1);
    const size = Number(searchParams.get('page_size'));
    const page_size = (PAGE_SIZES as readonly number[]).includes(size) ? size : DEFAULT_PAGE_SIZE;
    return { page, page_size };
  }, [searchParams]);

  const update = useCallback(
    (changes: Partial<PageParams>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (changes.page !== undefined) {
            if (changes.page <= 1) next.delete('page');
            else next.set('page', String(changes.page));
          }
          if (changes.page_size !== undefined) {
            if (changes.page_size === DEFAULT_PAGE_SIZE) next.delete('page_size');
            else next.set('page_size', String(changes.page_size));
            next.delete('page'); // new page size: back to page 1
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  return {
    ...params,
    setPage: (page: number) => update({ page }),
    setPageSize: (page_size: number) => update({ page_size }),
  };
}
