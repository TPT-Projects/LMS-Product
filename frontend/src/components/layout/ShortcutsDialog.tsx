import { useTranslation } from 'react-i18next';

import { Dialog } from '@/components/ui';

const SHORTCUTS = [
  { keys: '?', labelKey: 'shortcuts.help' },
  { keys: '/', labelKey: 'shortcuts.search' },
  { keys: 'Q', labelKey: 'shortcuts.quickAdd' },
  { keys: '[', labelKey: 'shortcuts.sidebar' },
  { keys: 'Ctrl + Enter', labelKey: 'shortcuts.saveNote' },
] as const;

export function ShortcutsDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={t('shortcuts.title')}>
      <ul className="divide-y">
        {SHORTCUTS.map((s) => (
          <li key={s.keys} className="flex items-center justify-between py-2.5">
            <span>{t(s.labelKey)}</span>
            <kbd className="rounded-md border bg-subtle px-2 py-0.5 text-xs font-medium">
              {s.keys}
            </kbd>
          </li>
        ))}
      </ul>
    </Dialog>
  );
}
