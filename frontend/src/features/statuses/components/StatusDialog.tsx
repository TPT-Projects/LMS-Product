import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { Alert, Button, Checkbox, Dialog, FormField, Input } from '@/components/ui';
import { useFieldError } from '@/hooks/useFieldError';
import { applyApiErrors } from '@/lib/api/errors';
import { cn } from '@/lib/cn';
import type { Status } from '@/types/crm';

import { useSaveStatus } from '../api';
import { STATUS_COLOR_CLASSES, STATUS_COLORS } from '../colors';

const schema = z.object({
  name: z.string().trim().min(1, 'validation.required').max(60),
  color: z.enum(['gray', 'blue', 'amber', 'violet', 'green', 'red']),
  // Disabled checkboxes leave the form values (undefined): treat as "unchanged".
  is_default: z.boolean().optional(),
  is_closed: z.boolean().optional(),
  is_won: z.boolean().optional(),
});
type Values = z.infer<typeof schema>;

interface StatusDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  status: Status | null;
}

export function StatusDialog({ open, onOpenChange, status }: StatusDialogProps) {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const save = useSaveStatus();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    reset,
    setError: setFieldError,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open) {
      reset({
        name: status?.name ?? '',
        color: status?.color ?? 'gray',
        is_default: status?.is_default ?? false,
        is_closed: status?.is_closed ?? false,
        is_won: status?.is_won ?? false,
      });
    }
  }, [open, status, reset]);

  const close = (next: boolean) => {
    if (!next) setError(null);
    onOpenChange(next);
  };

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      await save.mutateAsync({
        id: status?.id,
        ...values,
        is_closed: Boolean(values.is_closed || values.is_won),
      });
      close(false);
    } catch (err) {
      setError(applyApiErrors(err, setFieldError, ['name', 'color', 'is_default', 'is_won']));
    }
  });

  const isWon = useWatch({ control, name: 'is_won' });

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title={status ? t('statuses.editTitle') : t('statuses.addTitle')}
      footer={
        <>
          <Button variant="secondary" onClick={() => close(false)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="status-form" loading={save.isPending}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="status-form" onSubmit={onSubmit} noValidate className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <FormField label={t('fields.name')} error={fieldError(errors.name)}>
          <Input autoFocus {...register('name')} />
        </FormField>
        <fieldset>
          <legend className="mb-1.5 text-[13px] font-medium">{t('statuses.color')}</legend>
          <Controller
            control={control}
            name="color"
            render={({ field }) => (
              <div className="flex flex-wrap gap-2">
                {STATUS_COLORS.map((color) => (
                  <button
                    key={color}
                    type="button"
                    aria-label={t(`statuses.colors.${color}`)}
                    aria-pressed={field.value === color}
                    onClick={() => field.onChange(color)}
                    className={cn(
                      'flex size-8 items-center justify-center rounded-full border-2',
                      field.value === color ? 'border-fg' : 'border-transparent',
                    )}
                  >
                    <span className={cn('size-5 rounded-full', STATUS_COLOR_CLASSES[color].dot)} />
                  </button>
                ))}
              </div>
            )}
          />
        </fieldset>
        <div className="space-y-2.5">
          <label className="flex items-start gap-2.5">
            <Checkbox
              className="mt-0.5"
              {...register('is_default')}
              disabled={status?.is_default}
            />
            <span>
              <span className="block font-medium">{t('statuses.defaultLabel')}</span>
              <span className="text-[13px] text-fg-muted">{t('statuses.defaultHint')}</span>
            </span>
          </label>
          <label className="flex items-start gap-2.5">
            <Checkbox className="mt-0.5" {...register('is_closed')} disabled={isWon} />
            <span>
              <span className="block font-medium">{t('statuses.closedLabel')}</span>
              <span className="text-[13px] text-fg-muted">{t('statuses.closedHint')}</span>
            </span>
          </label>
          <label className="flex items-start gap-2.5">
            <Checkbox className="mt-0.5" {...register('is_won')} />
            <span>
              <span className="block font-medium">{t('statuses.wonLabel')}</span>
              <span className="text-[13px] text-fg-muted">{t('statuses.wonHint')}</span>
            </span>
          </label>
        </div>
      </form>
    </Dialog>
  );
}
