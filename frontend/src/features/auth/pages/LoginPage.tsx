import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { AuthLayout } from '@/components/layout/AuthLayout';
import { Alert, Button, FormField, Input } from '@/components/ui';
import { useFieldError } from '@/hooks/useFieldError';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { authApi } from '../api';
import { PasswordInput } from '../components/PasswordInput';
import { loginSchema, type LoginValues } from '../schemas';
import { useAuth } from '../useAuth';

export default function LoginPage() {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const { startSession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      startSession(await authApi.login(values));
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? paths.home, { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  });

  return (
    <AuthLayout
      title={t('auth.login.title')}
      subtitle={t('auth.login.subtitle')}
      footer={
        <>
          {t('auth.login.noAccount')}{' '}
          <Link to={paths.signup} className="font-medium text-accent hover:underline">
            {t('auth.login.createWorkspace')}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <FormField label={t('fields.email')} error={fieldError(errors.email)}>
          <Input type="email" autoComplete="email" autoFocus {...register('email')} />
        </FormField>
        <FormField
          label={t('fields.password')}
          error={fieldError(errors.password)}
          labelAside={
            <Link to={paths.forgotPassword} className="text-[13px] text-accent hover:underline">
              {t('auth.login.forgot')}
            </Link>
          }
        >
          <PasswordInput autoComplete="current-password" {...register('password')} />
        </FormField>
        <Button type="submit" className="w-full" loading={isSubmitting}>
          {t('auth.login.submit')}
        </Button>
      </form>
    </AuthLayout>
  );
}
