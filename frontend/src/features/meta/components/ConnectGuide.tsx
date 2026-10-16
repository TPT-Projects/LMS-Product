import { BookOpen } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Card } from '@/components/ui';

const STEPS = ['login', 'page', 'access', 'forms', 'mapping', 'test'] as const;

/** The in-app "How to connect" guide (spec F5 step 9). */
export function ConnectGuide({ defaultOpen }: { defaultOpen: boolean }) {
  const { t } = useTranslation();
  return (
    <Card>
      <details open={defaultOpen} className="group">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 font-medium sm:px-5">
          <BookOpen className="size-4 text-accent" aria-hidden />
          {t('meta.guide.title')}
          <span className="ml-auto text-xs text-fg-muted group-open:hidden">
            {t('meta.guide.show')}
          </span>
        </summary>
        <ol className="space-y-3 border-t px-4 py-4 sm:px-5">
          {STEPS.map((step, index) => (
            <li key={step} className="flex gap-3">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
                {index + 1}
              </span>
              <div>
                <p className="text-[13px] font-medium">{t(`meta.guide.${step}.title`)}</p>
                <p className="text-[13px] text-fg-muted">{t(`meta.guide.${step}.body`)}</p>
              </div>
            </li>
          ))}
        </ol>
      </details>
    </Card>
  );
}
