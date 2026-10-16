import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';

import { AuthLayout } from '@/components/layout/AuthLayout';
import { Alert, Button, FormField } from '@/components/ui';
import { useFieldError } from '@/hooks/useFieldError';
import { applyApiErrors } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { authApi } from '../api';
import { PasswordInput } from '../components/PasswordInput';
import { resetPasswordSchema, type ResetPasswordValues } from '../schemas';

export default function ResetPasswordPage() {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const [params] = useSearchParams();
  const uid = params.get('uid') ?? '';
  const token = params.get('token') ?? '';
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError: setFieldError,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: '', confirm: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      await authApi.resetPassword({ ...values, uid, token });
      setDone(true);
    } catch (err) {
      setError(applyApiErrors(err, setFieldError, ['password']));
    }
  });

  const footer = (
    <Link to={paths.login} className="font-medium text-accent hover:underline">
      {t('auth.backToLogin')}
    </Link>
  );

  if (!uid || !token) {
    return (
      <AuthLayout title={t('auth.reset.title')} footer={footer}>
        <Alert tone="danger">{t('auth.reset.invalidLink')}</Alert>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={t('auth.reset.title')} subtitle={t('auth.reset.subtitle')} footer={footer}>
      {done ? (
        <Alert tone="success">{t('auth.reset.done')}</Alert>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          <FormField
            label={t('fields.newPassword')}
            error={fieldError(errors.password)}
            hint={t('auth.passwordHint')}
          >
            <PasswordInput autoComplete="new-password" autoFocus {...register('password')} />
          </FormField>
          <FormField label={t('fields.confirmPassword')} error={fieldError(errors.confirm)}>
            <PasswordInput autoComplete="new-password" {...register('confirm')} />
          </FormField>
          <Button type="submit" className="w-full" loading={isSubmitting}>
            {t('auth.reset.submit')}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
