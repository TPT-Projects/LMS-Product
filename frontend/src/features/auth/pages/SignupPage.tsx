import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { AuthLayout } from '@/components/layout/AuthLayout';
import { Alert, Button, FormField, Input } from '@/components/ui';
import { DedupeKeyField } from '@/features/workspace/components/DedupeKeyField';
import { TimezoneSelect } from '@/features/workspace/components/TimezoneSelect';
import { normalizeTimezone } from '@/features/workspace/timezones';
import { useFieldError } from '@/hooks/useFieldError';
import { applyApiErrors } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { authApi } from '../api';
import { PasswordInput } from '../components/PasswordInput';
import { signupSchema, type SignupValues } from '../schemas';
import { useAuth } from '../useAuth';

const FIELDS = [
  'full_name',
  'email',
  'password',
  'workspace_name',
  'timezone',
  'dedupe_key',
] as const;

function browserTimezone(): string {
  try {
    return normalizeTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata');
  } catch {
    return 'Asia/Kolkata';
  }
}

export default function SignupPage() {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const { startSession } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError: setFieldError,
    formState: { errors, isSubmitting },
  } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      full_name: '',
      email: '',
      password: '',
      workspace_name: '',
      timezone: browserTimezone(),
      dedupe_key: 'phone',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      startSession(await authApi.signup(values));
      navigate(paths.home, { replace: true });
    } catch (err) {
      setError(applyApiErrors(err, setFieldError, FIELDS));
    }
  });

  return (
    <AuthLayout
      title={t('auth.signup.title')}
      subtitle={t('auth.signup.subtitle')}
      footer={
        <>
          {t('auth.signup.haveAccount')}{' '}
          <Link to={paths.login} className="font-medium text-accent hover:underline">
            {t('auth.signup.login')}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <FormField label={t('fields.fullName')} error={fieldError(errors.full_name)}>
          <Input autoComplete="name" autoFocus {...register('full_name')} />
        </FormField>
        <FormField label={t('fields.workEmail')} error={fieldError(errors.email)}>
          <Input type="email" autoComplete="email" {...register('email')} />
        </FormField>
        <FormField
          label={t('fields.password')}
          error={fieldError(errors.password)}
          hint={t('auth.passwordHint')}
        >
          <PasswordInput autoComplete="new-password" {...register('password')} />
        </FormField>
        <FormField label={t('fields.workspaceName')} error={fieldError(errors.workspace_name)}>
          <Input
            placeholder={t('auth.signup.workspacePlaceholder')}
            {...register('workspace_name')}
          />
        </FormField>
        <FormField label={t('fields.timezone')} error={fieldError(errors.timezone)}>
          <TimezoneSelect {...register('timezone')} />
        </FormField>
        <DedupeKeyField register={register('dedupe_key')} />
        <Button type="submit" className="w-full" loading={isSubmitting}>
          {t('auth.signup.submit')}
        </Button>
      </form>
    </AuthLayout>
  );
}
