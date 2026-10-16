import { useQuery } from '@tanstack/react-query';
import { Contact, Loader2, Search } from 'lucide-react';
import { forwardRef, useEffect, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { StatusBadge } from '@/features/statuses/components/StatusBadge';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { api } from '@/lib/api/client';
import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';
import type { SearchResults } from '@/types/crm';

type Item = { key: string; to: string };

/**
 * Top bar search: name, phone (any format), email, campaign, form and custom
 * text fields. Arrow keys move, Enter opens, Esc closes. "/" focuses it.
 */
export const GlobalSearch = forwardRef<HTMLInputElement>(function GlobalSearch(_props, ref) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const listId = useId();
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const q = useDebouncedValue(text.trim(), 250);

  const results = useQuery({
    queryKey: ['search', q],
    queryFn: () => api.get<SearchResults>('/search', { params: { q } }).then((r) => r.data),
    enabled: q.length >= 2,
    staleTime: 15_000,
  });

  const data = q.length >= 2 ? results.data : undefined;
  const items: Item[] = [
    ...(data?.enquiries ?? []).map((e) => ({ key: `e${e.id}`, to: `${paths.enquiries}/${e.id}` })),
    ...(data?.contacts ?? []).map((c) => ({ key: `c${c.id}`, to: `${paths.contacts}/${c.id}` })),
    ...(q.length >= 2 ? [{ key: 'all', to: `${paths.enquiries}?q=${encodeURIComponent(q)}` }] : []),
  ];

  useEffect(() => setActive(0), [q]);

  const go = (item: Item | undefined) => {
    if (!item) return;
    setOpen(false);
    setText('');
    navigate(item.to);
  };

  const optionClass = (key: string) =>
    cn(
      'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-[13px]',
      items[active]?.key === key ? 'bg-muted' : 'hover:bg-muted/70',
    );

  const showPanel = open && q.length >= 2;

  return (
    <div className="relative max-w-md flex-1">
      <Search
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle"
        aria-hidden
      />
      <input
        ref={ref}
        type="search"
        value={text}
        role="combobox"
        aria-expanded={showPanel}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-label={t('search.label')}
        placeholder={t('search.placeholder')}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActive((i) => Math.min(i + 1, items.length - 1));
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === 'Enter') {
            e.preventDefault();
            go(items[active]);
          } else if (e.key === 'Escape') {
            setOpen(false);
            (e.target as HTMLInputElement).blur();
          }
        }}
        className="h-9 w-full rounded-lg border bg-subtle pr-8 pl-9 text-[13px] placeholder:text-fg-subtle focus:border-ring focus:bg-surface focus:ring-2 focus:ring-ring/20 focus:outline-none"
      />
      {results.isFetching && q.length >= 2 ? (
        <Loader2
          className="absolute top-1/2 right-2.5 size-4 -translate-y-1/2 animate-spin text-fg-subtle"
          aria-hidden
        />
      ) : (
        <kbd className="pointer-events-none absolute top-1/2 right-2.5 hidden -translate-y-1/2 rounded border bg-surface px-1.5 text-[11px] text-fg-subtle sm:block">
          /
        </kbd>
      )}

      {showPanel && (
        <div
          id={listId}
          role="listbox"
          className="absolute inset-x-0 top-11 z-40 max-h-[70vh] animate-fade-in overflow-y-auto rounded-xl border bg-surface p-1 shadow-popover sm:min-w-96"
        >
          {data && !data.enquiries.length && !data.contacts.length && (
            <p className="px-3 py-4 text-center text-[13px] text-fg-muted">
              {t('search.noResults', { q })}
            </p>
          )}
          {!!data?.enquiries.length && (
            <p className="px-2.5 pt-1.5 pb-1 text-xs font-medium text-fg-subtle">
              {t('search.enquiries')}
            </p>
          )}
          {data?.enquiries.map((e) => (
            <button
              key={e.id}
              type="button"
              role="option"
              aria-selected={items[active]?.key === `e${e.id}`}
              className={optionClass(`e${e.id}`)}
              onMouseDown={(ev) => ev.preventDefault()}
              onClick={() => go({ key: `e${e.id}`, to: `${paths.enquiries}/${e.id}` })}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">
                  {e.name || t('enquiries.noName')}
                </span>
                <span className="block truncate text-xs text-fg-muted">
                  {[e.phone_e164, e.email, e.campaign_name].filter(Boolean).join(' · ')}
                </span>
              </span>
              <StatusBadge name={e.status.name} color={e.status.color} />
            </button>
          ))}
          {!!data?.contacts.length && (
            <p className="px-2.5 pt-2 pb-1 text-xs font-medium text-fg-subtle">
              {t('search.contacts')}
            </p>
          )}
          {data?.contacts.map((c) => (
            <button
              key={c.id}
              type="button"
              role="option"
              aria-selected={items[active]?.key === `c${c.id}`}
              className={optionClass(`c${c.id}`)}
              onMouseDown={(ev) => ev.preventDefault()}
              onClick={() => go({ key: `c${c.id}`, to: `${paths.contacts}/${c.id}` })}
            >
              <Contact className="size-4 shrink-0 text-fg-subtle" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">
                  {c.name || t('enquiries.noName')}
                </span>
                <span className="block truncate text-xs text-fg-muted">
                  {[c.phone_e164, c.email].filter(Boolean).join(' · ')}
                </span>
              </span>
              <span className="text-xs text-fg-muted">
                {t('search.enquiryCount', { count: c.enquiry_count })}
              </span>
            </button>
          ))}
          <button
            type="button"
            role="option"
            aria-selected={items[active]?.key === 'all'}
            className={cn(optionClass('all'), 'mt-1 border-t text-accent')}
            onMouseDown={(ev) => ev.preventDefault()}
            onClick={() => go({ key: 'all', to: `${paths.enquiries}?q=${encodeURIComponent(q)}` })}
          >
            <Search className="size-4" aria-hidden />
            {t('search.seeAll', { q })}
          </button>
        </div>
      )}
    </div>
  );
});
