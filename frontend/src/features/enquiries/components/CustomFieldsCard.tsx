import { Pencil } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert, Button, Card, FormField } from '@/components/ui';
import { useAuth } from '@/features/auth/useAuth';
import { activeFields, useCustomFields } from '@/features/customfields/api';
import { CustomFieldInput } from '@/features/customfields/components/CustomFieldInput';
import { emptyValue, formatCustomValue } from '@/features/customfields/values';
import { getErrorMessage, nestedErrors } from '@/lib/api/errors';
import { paths } from '@/routes/paths';
import type { CustomValue, EnquiryDetail } from '@/types/crm';

import { useUpdateEnquiry } from '../api';
import { SectionTitle } from './DetailsCard';

export function CustomFieldsCard({ enquiry }: { enquiry: EnquiryDetail }) {
  const { t } = useTranslation();
  const { can } = useAuth();
  const fields = activeFields(useCustomFields().data);
  const update = useUpdateEnquiry(enquiry.id);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, CustomValue>>({});
  const errors = nestedErrors(update.error, 'custom_fields');

  if (!fields.length) {
    if (!can('manage_settings')) return null;
    return (
      <Card>
        <SectionTitle>{t('customFields.title')}</SectionTitle>
        <p className="px-4 py-3 text-[13px] text-fg-muted">
          {t('enquiry.noCustomFields')}{' '}
          <Link to={paths.settingsCustomFields} className="text-accent hover:underline">
            {t('enquiry.addCustomFields')}
          </Link>
        </p>
      </Card>
    );
  }

  const start = () => {
    setDraft({ ...enquiry.custom_fields });
    update.reset();
    setEditing(true);
  };

  const save = async () => {
    // Send every field; cleared ones go as empty so the API removes them.
    const payload = Object.fromEntries(
      fields.map((f) => {
        const v = draft[f.key];
        const isEmpty = v === undefined || v === '' || (Array.isArray(v) && !v.length);
        return [f.key, isEmpty ? (f.type === 'checkbox' ? false : emptyValue(f)) : v];
      }),
    );
    await update.mutateAsync({ custom_fields: payload });
    setEditing(false);
  };

  return (
    <Card>
      <SectionTitle
        action={
          enquiry.permissions.can_edit &&
          !editing && (
            <Button variant="ghost" size="sm" onClick={start}>
              <Pencil className="size-3.5" aria-hidden /> {t('common.edit')}
            </Button>
          )
        }
      >
        {t('customFields.title')}
      </SectionTitle>
      {editing ? (
        <form
          className="space-y-3 p-4"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          {update.isError && !Object.keys(errors).length && (
            <Alert tone="danger">{getErrorMessage(update.error)}</Alert>
          )}
          {fields.map((field) => (
            <FormField
              key={field.id}
              label={field.is_required ? `${field.label} *` : field.label}
              error={errors[field.key]}
            >
              <CustomFieldInput
                field={field}
                value={draft[field.key]}
                onChange={(value) => setDraft((d) => ({ ...d, [field.key]: value }))}
              />
            </FormField>
          ))}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="secondary" size="sm" onClick={() => setEditing(false)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" size="sm" loading={update.isPending}>
              {t('common.save')}
            </Button>
          </div>
        </form>
      ) : (
        <dl className="px-4 py-2">
          {fields.map((field) => (
            <div key={field.id} className="grid grid-cols-[7.5rem_1fr] gap-3 py-1.5 text-[13px]">
              <dt className="text-fg-muted">{field.label}</dt>
              <dd className="min-w-0 break-words">
                {formatCustomValue(field, enquiry.custom_fields[field.key], {
                  yes: t('common.yes'),
                  no: t('common.no'),
                })}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  );
}
