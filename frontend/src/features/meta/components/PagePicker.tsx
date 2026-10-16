import { Check, Flag } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Button } from '@/components/ui';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';

import { useSelectPage, type MetaPage } from '../api';

/** Choose ONE Page (single-select). Pages linked to another workspace cannot be chosen. */
export function PagePicker({ pages, onDone }: { pages: MetaPage[]; onDone?: () => void }) {
  const { t } = useTranslation();
  const select = useSelectPage();
  const [chosen, setChosen] = useState<string | null>(null);

  if (!pages.length) return <Alert tone="info">{t('meta.pages.none')}</Alert>;

  return (
    <div className="space-y-3">
      <div
        role="radiogroup"
        aria-label={t('meta.pages.title')}
        className="grid gap-2 sm:grid-cols-2"
      >
        {pages.map((page) => (
          <button
            key={page.id}
            type="button"
            role="radio"
            aria-checked={chosen === page.id}
            disabled={!page.available}
            onClick={() => setChosen(page.id)}
            className={cn(
              'flex items-center gap-3 rounded-xl border p-3 text-left transition-colors',
              chosen === page.id ? 'border-accent bg-accent-soft' : 'hover:bg-subtle',
              !page.available && 'cursor-not-allowed opacity-50',
            )}
          >
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[#1877F2] text-white">
              <Flag className="size-4" aria-hidden />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{page.name}</span>
              <span className="block text-xs text-fg-muted">
                {page.available ? `ID ${page.id}` : t('meta.pages.taken')}
              </span>
            </span>
            {chosen === page.id && <Check className="size-4 text-accent" aria-hidden />}
          </button>
        ))}
      </div>
      <p className="text-[13px] text-fg-muted">{t('meta.pages.onlyOne')}</p>
      {select.isError && <Alert tone="danger">{getErrorMessage(select.error)}</Alert>}
      <Button
        disabled={!chosen}
        loading={select.isPending}
        onClick={async () => {
          if (!chosen) return;
          await select.mutateAsync(chosen);
          onDone?.();
        }}
      >
        {t('meta.pages.connect')}
      </Button>
    </div>
  );
}
