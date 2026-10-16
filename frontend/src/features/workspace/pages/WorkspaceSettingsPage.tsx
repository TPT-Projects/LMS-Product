import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import {
  Alert,
  Button,
  Card,
  CardBody,
  CardHeader,
  FormField,
  Input,
  Skeleton,
} from '@/components/ui';
import { useAuth } from '@/features/auth/useAuth';
import { useFieldError } from '@/hooks/useFieldError';
import { applyApiErrors } from '@/lib/api/errors';

import { useUpdateWorkspace, useWorkspace } from '../api';
import { DedupeKeyField } from '../components/DedupeKeyField';
import { TimezoneSelect } from '../components/TimezoneSelect';

const schema = z.object({
  name: z.string().trim().min(1, 'validation.required'),
  timezone: z.string().min(1, 'validation.required'),
  dedupe_key: z.enum(['phone', 'email']),
  default_country: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{2}$/, 'validation.countryCode')
    .transform((v) => v.toUpperCase()),
});
type Values = z.input<typeof schema>;
type Output = z.output<typeof schema>;
const FIELDS = ['name', 'timezone', 'dedupe_key', 'default_country'] as const;

export default function WorkspaceSettingsPage() {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const { can, reloadSession } = useAuth();
  const canEdit = can('manage_settings');
  const workspace = useWorkspace();
  const update = useUpdateWorkspace();
  const [message, setMessage] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isDirty },
  } = useForm<Values, unknown, Output>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (workspace.data) reset(workspace.data);
  }, [workspace.data, reset]);

  const onSubmit = handleSubmit(async (values) => {
    setMessage(null);
    try {
      const saved = await update.mutateAsync(values);
      reset(saved);
      await reloadSession(); // timezone and name are used across the app
      setMessage({ tone: 'success', text: t('common.saved') });
    } catch (err) {
      const text = applyApiErrors(err, setError, FIELDS);
      if (text) setMessage({ tone: 'danger', text });
    }
  });

  return (
    <Card>
      <CardHeader title={t('workspace.title')} description={t('workspace.description')} />
      <CardBody>
        {workspace.isPending ? (
          <div className="space-y-4">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : (
          <form onSubmit={onSubmit} noValidate className="max-w-lg space-y-4">
            {message && <Alert tone={message.tone}>{message.text}</Alert>}
            {!canEdit && <Alert tone="info">{t('common.readOnly')}</Alert>}
            <fieldset disabled={!canEdit} className="space-y-4">
              <FormField label={t('fields.workspaceName')} error={fieldError(errors.name)}>
                <Input {...register('name')} />
              </FormField>
              <FormField
                label={t('fields.timezone')}
                error={fieldError(errors.timezone)}
                hint={t('workspace.timezoneHint')}
              >
                <TimezoneSelect {...register('timezone')} />
              </FormField>
              <FormField
                label={t('fields.defaultCountry')}
                error={fieldError(errors.default_country)}
                hint={t('workspace.countryHint')}
              >
                <Input maxLength={2} className="w-24 uppercase" {...register('default_country')} />
              </FormField>
              <DedupeKeyField register={register('dedupe_key')} />
            </fieldset>
            {canEdit && (
              <div className="pt-2">
                <Button type="submit" loading={update.isPending} disabled={!isDirty}>
                  {t('common.saveChanges')}
                </Button>
              </div>
            )}
          </form>
        )}
      </CardBody>
    </Card>
  );
}
