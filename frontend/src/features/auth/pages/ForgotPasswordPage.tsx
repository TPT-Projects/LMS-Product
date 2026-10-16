import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { AuthLayout } from '@/components/layout/AuthLayout';
import { Alert, Button, FormField, Input } from '@/components/ui';
import { useFieldError } from '@/hooks/useFieldError';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { authApi } from '../api';
import { forgotPasswordSchema, type ForgotPasswordValues } from '../schemas';

export default function ForgotPasswordPage() {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      await authApi.forgotPassword(values);
      setSent(true);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  });

  return (
    <AuthLayout
      title={t('auth.forgot.title')}
      subtitle={t('auth.forgot.subtitle')}
      footer={
        <Link to={paths.login} className="font-medium text-accent hover:underline">
          {t('auth.backToLogin')}
        </Link>
      }
    >
      {sent ? (
        <Alert tone="success">{t('auth.forgot.sent')}</Alert>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          <FormField label={t('fields.email')} error={fieldError(errors.email)}>
            <Input type="email" autoComplete="email" autoFocus {...register('email')} />
          </FormField>
          <Button type="submit" className="w-full" loading={isSubmitting}>
            {t('auth.forgot.submit')}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
