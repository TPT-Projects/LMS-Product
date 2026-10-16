import { Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Alert, Switch } from '@/components/ui';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';

import { useMetaSettings } from '../api';

/**
 * On (default): every form of the Page syncs, including forms created later.
 * Off: each form gets its own switch.
 */
export function AutoSyncToggle({ auto }: { auto: boolean }) {
  const { t } = useTranslation();
  const settings = useMetaSettings();

  return (
    <div className="space-y-2">
      <div
        className={cn(
          'flex items-center gap-3 rounded-xl border p-3',
          auto && 'border-accent bg-accent-soft',
        )}
      >
        <Zap
          className={cn('size-4 shrink-0', auto ? 'text-accent' : 'text-fg-muted')}
          aria-hidden
        />
        <div className="min-w-0 flex-1">
          <p id="meta-auto-sync" className="font-medium">
            {t('meta.autoSync.label')}
          </p>
          <p className="text-xs text-fg-muted">
            {auto ? t('meta.autoSync.onHint') : t('meta.autoSync.offHint')}
          </p>
        </div>
        <Switch
          checked={auto}
          aria-labelledby="meta-auto-sync"
          disabled={settings.isPending}
          onCheckedChange={(value) => settings.mutate({ auto_connect_forms: value })}
        />
      </div>
      {settings.isError && <Alert tone="danger">{getErrorMessage(settings.error)}</Alert>}
    </div>
  );
}
