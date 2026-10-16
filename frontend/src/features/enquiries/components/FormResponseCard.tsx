import { useTranslation } from 'react-i18next';

import { Card } from '@/components/ui';

import { useFormResponse } from '../api';
import { SectionTitle } from './DetailsCard';

/** The Meta lead answers exactly as received (MongoDB), shown with spaces for underscores. */
export function FormResponseCard({ enquiryId }: { enquiryId: number }) {
  const { t } = useTranslation();
  const response = useFormResponse(enquiryId);
  if (!response.data) return null; // manual and imported enquiries have no form response

  return (
    <Card>
      <SectionTitle>{t('enquiry.formResponse')}</SectionTitle>
      <dl className="divide-y px-4">
        {response.data.answers.map((answer) => (
          <div key={answer.question} className="py-2.5 text-[13px]">
            <dt className="text-fg-muted first-letter:uppercase">{answer.label}</dt>
            <dd className="mt-0.5 font-medium break-words">{answer.display || '—'}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
