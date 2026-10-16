import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { Alert, Button, Dialog, FormField, Input, Select, Textarea } from '@/components/ui';
import { useAuth } from '@/features/auth/useAuth';
import { activeFields, useCustomFields } from '@/features/customfields/api';
import { CustomFieldInput } from '@/features/customfields/components/CustomFieldInput';
import { useStatuses } from '@/features/statuses/api';
import { useFieldError } from '@/hooks/useFieldError';
import { applyApiErrors, nestedErrors } from '@/lib/api/errors';
import { paths } from '@/routes/paths';
import type { CustomValue } from '@/types/crm';

import { useCreateEnquiry } from '../api';
import { OwnerSelect } from './OwnerSelect';

const schema = z
  .object({
    name: z.string().trim().min(1, 'validation.required').max(200),
    phone: z.string().trim().max(50),
    email: z.union([z.literal(''), z.string().trim().email('validation.email')]),
    status_id: z.string(),
    primary_owner_id: z.string(),
    campaign_name: z.string().max(255),
    note: z.string().max(5000),
  })
  .refine((v) => v.phone || v.email, { message: 'enquiries.form.phoneOrEmail', path: ['phone'] });
type Values = z.infer<typeof schema>;

const DEFAULTS: Values = {
  name: '',
  phone: '',
  email: '',
  status_id: '',
  primary_owner_id: '',
  campaign_name: '',
  note: '',
};

export function EnquiryFormDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const navigate = useNavigate();
  const { can } = useAuth();
  const canReassign = can('reassign_owners');
  const statuses = useStatuses();
  const fields = activeFields(useCustomFields().data);
  const create = useCreateEnquiry();
  const [custom, setCustom] = useState<Record<string, CustomValue>>({});
  const [customErrors, setCustomErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setError: setFieldError,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: DEFAULTS });

  useEffect(() => {
    if (open) reset(DEFAULTS);
  }, [open, reset]);

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setCustom({});
      setCustomErrors({});
      setError(null);
    }
    onOpenChange(next);
  };

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    setCustomErrors({});
    try {
      const created = await create.mutateAsync({
        name: values.name,
        phone: values.phone,
        email: values.email,
        campaign_name: values.campaign_name,
        note: values.note,
        status_id: values.status_id ? Number(values.status_id) : null,
        ...(canReassign
          ? { primary_owner_id: values.primary_owner_id ? Number(values.primary_owner_id) : null }
          : {}),
        custom_fields: Object.fromEntries(
          Object.entries(custom).filter(
            ([, v]) => v !== null && v !== '' && !(Array.isArray(v) && !v.length),
          ),
        ),
      });
      handleOpenChange(false);
      navigate(`${paths.enquiries}/${created.id}`);
    } catch (err) {
      const message = applyApiErrors(err, setFieldError, ['name', 'phone', 'email', 'status_id']);
      const fieldErrors = nestedErrors(err, 'custom_fields');
      setCustomErrors(fieldErrors);
      if (message && !Object.keys(fieldErrors).length) setError(message);
    }
  });

  return (
    <Dialog
      open={open}
      onOpenChange={handleOpenChange}
      title={t('enquiries.form.title')}
      description={t('enquiries.form.description')}
      className="sm:max-w-lg"
      footer={
        <>
          <Button variant="secondary" onClick={() => handleOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="enquiry-form" loading={create.isPending}>
            {t('enquiries.form.submit')}
          </Button>
        </>
      }
    >
      <form id="enquiry-form" onSubmit={onSubmit} noValidate className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <FormField label={t('fields.name')} error={fieldError(errors.name)}>
          <Input autoFocus autoComplete="off" {...register('name')} />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            label={t('fields.phone')}
            error={fieldError(errors.phone)}
            hint={t('enquiries.form.phoneHint')}
          >
            <Input
              type="tel"
              inputMode="tel"
              placeholder="+91 98765 43210"
              {...register('phone')}
            />
          </FormField>
          <FormField label={t('fields.email')} error={fieldError(errors.email)}>
            <Input type="email" {...register('email')} />
          </FormField>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label={t('fields.status')} error={fieldError(errors.status_id)}>
            <Select {...register('status_id')}>
              <option value="">{t('enquiries.form.defaultStatus')}</option>
              {statuses.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </FormField>
          {canReassign ? (
            <FormField label={t('fields.owner')}>
              <OwnerSelect {...register('primary_owner_id')} />
            </FormField>
          ) : (
            <FormField label={t('fields.owner')} hint={t('enquiries.form.ownerSelf')}>
              <Input value={t('enquiries.form.you')} disabled readOnly />
            </FormField>
          )}
        </div>
        <FormField label={t('fields.campaign')}>
          <Input {...register('campaign_name')} />
        </FormField>
        {fields.map((field) => (
          <FormField
            key={field.id}
            label={field.is_required ? `${field.label} *` : field.label}
            error={customErrors[field.key]}
          >
            <CustomFieldInput
              field={field}
              value={custom[field.key]}
              onChange={(value) => setCustom((c) => ({ ...c, [field.key]: value }))}
            />
          </FormField>
        ))}
        <FormField label={t('enquiries.form.note')}>
          <Textarea rows={3} {...register('note')} />
        </FormField>
      </form>
    </Dialog>
  );
}
