import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  FormField,
  Input,
  Select,
  Textarea,
} from '@/components/ui';
import { useFieldError } from '@/hooks/useFieldError';
import { applyApiErrors } from '@/lib/api/errors';
import { FIELD_TYPES, type CustomField } from '@/types/crm';

import { useSaveCustomField } from '../api';

const schema = z.object({
  label: z.string().trim().min(1, 'validation.required').max(100),
  type: z.enum(FIELD_TYPES).optional(), // disabled (undefined) when editing: type is locked
  options: z.string(), // one option per line
  is_required: z.boolean(),
  is_active: z.boolean(),
});
type Values = z.infer<typeof schema>;

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  field: CustomField | null;
}

export function CustomFieldDialog({ open, onOpenChange, field }: Props) {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const save = useSaveCustomField();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    control,
    setError: setFieldError,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open) {
      reset({
        label: field?.label ?? '',
        type: field?.type ?? 'text',
        options: field?.options.join('\n') ?? '',
        is_required: field?.is_required ?? false,
        is_active: field?.is_active ?? true,
      });
    }
  }, [open, field, reset]);

  const close = (next: boolean) => {
    if (!next) setError(null);
    onOpenChange(next);
  };

  const watchedType = useWatch({ control, name: 'type' });
  const type = field?.type ?? watchedType;
  const hasOptions = type === 'dropdown' || type === 'multi_select';

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    const options = values.options
      .split('\n')
      .map((o) => o.trim())
      .filter(Boolean);
    try {
      await save.mutateAsync({
        id: field?.id,
        label: values.label,
        options,
        is_required: values.is_required,
        is_active: values.is_active,
        ...(field ? {} : { type: values.type ?? 'text' }),
      });
      close(false);
    } catch (err) {
      setError(applyApiErrors(err, setFieldError, ['label', 'type', 'options']));
    }
  });

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title={field ? t('customFields.editTitle') : t('customFields.addTitle')}
      footer={
        <>
          <Button variant="secondary" onClick={() => close(false)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="custom-field-form" loading={save.isPending}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="custom-field-form" onSubmit={onSubmit} noValidate className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <FormField label={t('customFields.label')} error={fieldError(errors.label)}>
          <Input autoFocus {...register('label')} />
        </FormField>
        <FormField
          label={t('customFields.type')}
          hint={field ? t('customFields.typeLocked') : undefined}
          error={fieldError(errors.type)}
        >
          <Select {...register('type')} disabled={Boolean(field)}>
            {FIELD_TYPES.map((ft) => (
              <option key={ft} value={ft}>
                {t(`customFields.types.${ft}`)}
              </option>
            ))}
          </Select>
        </FormField>
        {hasOptions && (
          <FormField
            label={t('customFields.options')}
            hint={t('customFields.optionsHint')}
            error={fieldError(errors.options)}
          >
            <Textarea rows={5} {...register('options')} />
          </FormField>
        )}
        <label className="flex items-center gap-2.5">
          <Checkbox {...register('is_required')} />
          {t('customFields.required')}
        </label>
        {field && (
          <label className="flex items-center gap-2.5">
            <Checkbox {...register('is_active')} />
            {t('customFields.active')}
          </label>
        )}
      </form>
    </Dialog>
  );
}
