import { Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Input } from '@/components/ui';

/** Search the Page's forms by name or form ID. */
export function FormSearch({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { t } = useTranslation();
  return (
    <label className="relative block">
      <span className="sr-only">{t('meta.forms.search')}</span>
      <Search
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-muted"
        aria-hidden
      />
      <Input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={t('meta.forms.search')}
        className="pl-9"
      />
    </label>
  );
}
