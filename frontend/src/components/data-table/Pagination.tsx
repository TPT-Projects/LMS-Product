import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { useId, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { PAGE_SIZES } from '@/hooks/usePageParams';
import { cn } from '@/lib/cn';

import { pageNumbers } from './pageNumbers';

interface PaginationProps {
  page: number;
  pageSize: number;
  count: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

function NavButton({
  label,
  disabled,
  onClick,
  children,
  className,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'inline-flex size-8 items-center justify-center rounded-md text-fg-muted hover:bg-muted hover:text-fg disabled:pointer-events-none disabled:opacity-40',
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Pagination({
  page,
  pageSize,
  count,
  onPageChange,
  onPageSizeChange,
}: PaginationProps) {
  const { t } = useTranslation();
  const sizeId = useId();
  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  const from = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);
  const isFirst = page <= 1;
  const isLast = page >= totalPages;

  return (
    <div className="flex flex-col gap-3 border-t px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:px-4">
      <div className="flex items-center justify-between gap-4 text-[13px] text-fg-muted sm:justify-start">
        <span aria-live="polite">{t('table.showing', { from, to, count })}</span>
        <span className="flex items-center gap-2">
          <label htmlFor={sizeId}>{t('table.rowsPerPage')}</label>
          <select
            id={sizeId}
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="h-8 rounded-md border bg-surface px-2 text-fg"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </span>
      </div>

      <nav aria-label={t('table.pagination')} className="flex items-center justify-center gap-0.5">
        <NavButton label={t('table.first')} disabled={isFirst} onClick={() => onPageChange(1)}>
          <ChevronsLeft className="size-4" />
        </NavButton>
        <NavButton
          label={t('table.previous')}
          disabled={isFirst}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft className="size-4" />
        </NavButton>

        {/* Page numbers on wider screens, "3 / 12" on phones */}
        <span className="px-2 text-[13px] text-fg-muted sm:hidden">
          {t('table.pageOf', { page, total: totalPages })}
        </span>
        <span className="hidden items-center gap-0.5 sm:flex">
          {pageNumbers(page, totalPages).map((item, index) =>
            item === 'gap' ? (
              <span key={`gap-${index}`} className="px-1.5 text-fg-subtle">
                …
              </span>
            ) : (
              <button
                key={item}
                type="button"
                onClick={() => onPageChange(item)}
                aria-current={item === page ? 'page' : undefined}
                className={cn(
                  'h-8 min-w-8 rounded-md px-2 text-[13px] tabular-nums',
                  item === page
                    ? 'bg-accent-soft font-semibold text-accent'
                    : 'text-fg-muted hover:bg-muted hover:text-fg',
                )}
              >
                {item}
              </button>
            ),
          )}
        </span>

        <NavButton label={t('table.next')} disabled={isLast} onClick={() => onPageChange(page + 1)}>
          <ChevronRight className="size-4" />
        </NavButton>
        <NavButton
          label={t('table.last')}
          disabled={isLast}
          onClick={() => onPageChange(totalPages)}
        >
          <ChevronsRight className="size-4" />
        </NavButton>
      </nav>
    </div>
  );
}
