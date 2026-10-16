import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { Alert, Button, Checkbox, Dialog, FormField, Input } from '@/components/ui';
import { useFieldError } from '@/hooks/useFieldError';
import { applyApiErrors } from '@/lib/api/errors';
import { paths } from '@/routes/paths';
import type { SavedView, SavedViewFilters } from '@/types/crm';

import { useSaveView } from '../api';

const schema = z.object({
  name: z.string().trim().min(1, 'validation.required').max(80),
  is_shared: z.boolean(),
});
type Values = z.infer<typeof schema>;

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Create a new view from these filters, or rename/share an existing one. */
  filters?: SavedViewFilters;
  sort?: string;
  view?: SavedView | null;
}

export function SaveViewDialog({ open, onOpenChange, filters, sort, view }: Props) {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const navigate = useNavigate();
  const save = useSaveView();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError: setFieldError,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open) reset({ name: view?.name ?? '', is_shared: view?.is_shared ?? false });
  }, [open, view, reset]);

  const close = (next: boolean) => {
    if (!next) setError(null);
    onOpenChange(next);
  };

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      const saved = await save.mutateAsync(
        view ? { id: view.id, ...values } : { ...values, filters, sort: sort || '-created_at' },
      );
      close(false);
      if (!view) navigate(`${paths.enquiries}?saved_view=${saved.id}`);
    } catch (err) {
      setError(applyApiErrors(err, setFieldError, ['name']));
    }
  });

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title={view ? t('views.editTitle') : t('views.saveTitle')}
      description={view ? undefined : t('views.saveDescription')}
      footer={
        <>
          <Button variant="secondary" onClick={() => close(false)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="save-view-form" loading={save.isPending}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="save-view-form" onSubmit={onSubmit} noValidate className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <FormField label={t('fields.name')} error={fieldError(errors.name)}>
          <Input autoFocus placeholder={t('views.namePlaceholder')} {...register('name')} />
        </FormField>
        <label className="flex items-start gap-2.5">
          <Checkbox className="mt-0.5" {...register('is_shared')} />
          <span>
            <span className="block font-medium">{t('views.share')}</span>
            <span className="text-[13px] text-fg-muted">{t('views.shareHint')}</span>
          </span>
        </label>
      </form>
    </Dialog>
  );
}
