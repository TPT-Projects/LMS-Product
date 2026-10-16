import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { AuthLayout } from '@/components/layout/AuthLayout';
import { Alert, Button, FormField, Input, Spinner } from '@/components/ui';
import { useFieldError } from '@/hooks/useFieldError';
import { applyApiErrors, getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { authApi } from '../api';
import { PasswordInput } from '../components/PasswordInput';
import { acceptInviteSchema, type AcceptInviteValues } from '../schemas';
import { useAuth } from '../useAuth';

export default function AcceptInvitePage() {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const navigate = useNavigate();
  const { startSession, status, logout } = useAuth();
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [error, setError] = useState<string | null>(null);

  const preview = useQuery({
    queryKey: ['invite-preview', token],
    queryFn: () => authApi.invitePreview(token),
    enabled: Boolean(token),
    retry: false,
  });

  const {
    register,
    handleSubmit,
    setError: setFieldError,
    formState: { errors, isSubmitting },
  } = useForm<AcceptInviteValues>({
    resolver: zodResolver(acceptInviteSchema),
    defaultValues: { full_name: '', password: '' },
  });

  const hasAccount = preview.data?.has_account ?? false;

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    if (!hasAccount && !values.full_name) {
      setFieldError('full_name', { type: 'required', message: 'validation.required' });
      return;
    }
    if (!hasAccount && values.password.length < 8) {
      setFieldError('password', { type: 'min', message: 'validation.passwordLength' });
      return;
    }
    try {
      if (status === 'authenticated') await logout(); // join as the invited person, not the current one
      startSession(await authApi.acceptInvite({ ...values, token }));
      navigate(paths.home, { replace: true });
    } catch (err) {
      setError(applyApiErrors(err, setFieldError, ['full_name', 'password']));
    }
  });

  const footer = (
    <Link to={paths.login} className="font-medium text-accent hover:underline">
      {t('auth.backToLogin')}
    </Link>
  );

  if (!token || preview.isError) {
    return (
      <AuthLayout title={t('auth.invite.titleInvalid')} footer={footer}>
        <Alert tone="danger">
          {token ? getErrorMessage(preview.error) : t('auth.invite.invalid')}
        </Alert>
      </AuthLayout>
    );
  }

  if (preview.isPending) {
    return (
      <AuthLayout title={t('auth.invite.loading')}>
        <div className="flex justify-center py-6 text-fg-muted">
          <Spinner />
        </div>
      </AuthLayout>
    );
  }

  const invite = preview.data;
  return (
    <AuthLayout
      title={t('auth.invite.title', { workspace: invite.workspace_name })}
      subtitle={t('auth.invite.subtitle', {
        inviter: invite.invited_by ?? t('auth.invite.someone'),
        role: t(`roles.${invite.role}`),
      })}
      footer={footer}
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <FormField label={t('fields.email')}>
          <Input value={invite.email} readOnly disabled />
        </FormField>
        {hasAccount ? (
          <Alert tone="info">{t('auth.invite.existingAccount')}</Alert>
        ) : (
          <FormField label={t('fields.fullName')} error={fieldError(errors.full_name)}>
            <Input autoComplete="name" autoFocus {...register('full_name')} />
          </FormField>
        )}
        <FormField
          label={hasAccount ? t('fields.password') : t('fields.choosePassword')}
          error={fieldError(errors.password)}
          hint={hasAccount ? undefined : t('auth.passwordHint')}
        >
          <PasswordInput
            autoComplete={hasAccount ? 'current-password' : 'new-password'}
            autoFocus={hasAccount}
            {...register('password')}
          />
        </FormField>
        <Button type="submit" className="w-full" loading={isSubmitting}>
          {t('auth.invite.submit')}
        </Button>
      </form>
    </AuthLayout>
  );
}
