import { ArrowLeft, Plus } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { Alert, Badge, Button, Card, Select, Skeleton } from '@/components/ui';
import { activeFields, useCustomFields } from '@/features/customfields/api';
import { displayOption } from '@/features/customfields/values';
import { getErrorMessage, nestedErrors } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { useFormMapping, useSaveFormMapping, type MappingQuestion, type TargetType } from '../api';

/** "custom:<key>" in the select <-> {target_type, custom_field} in the API. */
function toValue(q: Pick<MappingQuestion, 'target_type' | 'custom_field'>): string {
  return q.target_type === 'custom' ? `custom:${q.custom_field ?? ''}` : q.target_type || '';
}
function fromValue(value: string): Pick<MappingQuestion, 'target_type' | 'custom_field'> {
  if (value.startsWith('custom:')) return { target_type: 'custom', custom_field: value.slice(7) };
  return { target_type: value as TargetType, custom_field: null };
}

/** Field mapping: each question -> Name / Phone / Email / a custom field. Many-to-one is fine. */
export default function MetaFormMappingPage() {
  const { t } = useTranslation();
  const id = Number(useParams().id);
  const mapping = useFormMapping(id);
  const save = useSaveFormMapping(id);
  const fields = activeFields(useCustomFields().data);
  const [draft, setDraft] = useState<Record<string, string> | null>(null);
  const [saved, setSaved] = useState(false);

  if (mapping.isPending) return <Skeleton className="h-64 w-full" />;
  if (mapping.isError || !mapping.data)
    return <Alert tone="danger">{getErrorMessage(mapping.error)}</Alert>;

  const current: Record<string, string> =
    draft ?? Object.fromEntries(mapping.data.questions.map((q) => [q.question, toValue(q)]));
  const errors = nestedErrors(save.error, 'mapping');

  const submit = async () => {
    setSaved(false);
    await save.mutateAsync(
      Object.entries(current).map(([question, value]) => ({ question, ...fromValue(value) })),
    );
    setDraft(null);
    setSaved(true);
  };

  return (
    <div className="space-y-4">
      <Link
        to={paths.settingsMeta}
        className="inline-flex items-center gap-1.5 text-[13px] text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="size-4" aria-hidden /> {t('meta.back')}
      </Link>
      <PageHeader
        title={t('meta.mapping.title', { form: mapping.data.name || mapping.data.form_id })}
        description={t('meta.mapping.description')}
      />
      <Card>
        {mapping.data.questions.length === 0 ? (
          <p className="p-5 text-[13px] text-fg-muted">{t('meta.mapping.noQuestions')}</p>
        ) : (
          <ul className="divide-y">
            {mapping.data.questions.map((q) => (
              <li
                key={q.question}
                className="grid gap-3 px-4 py-3 sm:grid-cols-[1fr_16rem] sm:items-center sm:px-5"
              >
                <div className="min-w-0">
                  <p className="font-medium first-letter:uppercase">{q.label}</p>
                  <p className="truncate font-mono text-xs text-fg-subtle">{q.question}</p>
                  {q.samples.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {q.samples.map((s) => (
                        <Badge key={s}>{displayOption(s)}</Badge>
                      ))}
                    </div>
                  )}
                  {errors[q.question] && (
                    <p className="mt-1 text-xs text-danger">{errors[q.question]}</p>
                  )}
                </div>
                <Select
                  aria-label={t('meta.mapping.targetFor', { question: q.label })}
                  value={current[q.question] ?? ''}
                  invalid={Boolean(errors[q.question])}
                  onChange={(e) => {
                    setSaved(false);
                    setDraft({ ...current, [q.question]: e.target.value });
                  }}
                >
                  <option value="">{t('meta.mapping.unmapped')}</option>
                  <option value="ignore">{t('meta.mapping.ignore')}</option>
                  <optgroup label={t('filters.standardFields')}>
                    <option value="name">{t('fields.name')}</option>
                    <option value="phone">{t('fields.phone')}</option>
                    <option value="email">{t('fields.email')}</option>
                  </optgroup>
                  {fields.length > 0 && (
                    <optgroup label={t('filters.customFields')}>
                      {fields.map((f) => (
                        <option key={f.key} value={`custom:${f.key}`}>
                          {f.label}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </Select>
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-center gap-3 border-t px-4 py-3 sm:px-5">
          <Link
            to={paths.settingsCustomFields}
            className="inline-flex items-center gap-1 text-[13px] text-accent hover:underline"
          >
            <Plus className="size-3.5" aria-hidden /> {t('meta.mapping.addField')}
          </Link>
          <span className="flex-1 text-xs text-fg-muted">{t('meta.mapping.newOnly')}</span>
          <Button loading={save.isPending} disabled={!draft} onClick={() => void submit()}>
            {t('common.saveChanges')}
          </Button>
        </div>
        {saved && (
          <Alert tone="success" className="mx-4 mb-4 sm:mx-5">
            {t('common.saved')}
          </Alert>
        )}
        {save.isError && !Object.keys(errors).length && (
          <Alert tone="danger" className="mx-4 mb-4 sm:mx-5">
            {getErrorMessage(save.error)}
          </Alert>
        )}
      </Card>
    </div>
  );
}
