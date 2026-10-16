import { zodResolver } from '@hookform/resolvers/zod';
import { Check, Copy } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { Alert, Button, Dialog, FormField, Input, Select } from '@/components/ui';
import { useSession } from '@/features/auth/useAuth';
import { useFieldError } from '@/hooks/useFieldError';
import { applyApiErrors } from '@/lib/api/errors';
import { ROLES } from '@/types/auth';

import { useInviteUser } from '../api';
import { assignableRoles } from '../roles';

const schema = z.object({
  email: z.string().trim().min(1, 'validation.required').email('validation.email'),
  role: z.enum(ROLES),
});
type Values = z.infer<typeof schema>;

export function InviteUserDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const { role: myRole } = useSession();
  const invite = useInviteUser();
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setError: setFieldError,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', role: 'agent' },
  });

  const close = (next: boolean) => {
    onOpenChange(next);
    if (!next) {
      reset();
      setInviteUrl(null);
      setCopied(false);
      setError(null);
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      const created = await invite.mutateAsync(values);
      setInviteUrl(created.invite_url ?? null);
    } catch (err) {
      setError(applyApiErrors(err, setFieldError, ['email', 'role']));
    }
  });

  const copy = async () => {
    if (!inviteUrl) return;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopied(true);
    } catch {
      /* clipboard blocked: the link is still visible to copy by hand */
    }
  };

  if (inviteUrl) {
    return (
      <Dialog
        open={open}
        onOpenChange={close}
        title={t('users.invite.sentTitle')}
        description={t('users.invite.sentDescription')}
        footer={<Button onClick={() => close(false)}>{t('common.done')}</Button>}
      >
        <div className="flex gap-2">
          <Input
            value={inviteUrl}
            readOnly
            onFocus={(e) => e.currentTarget.select()}
            aria-label={t('users.invite.link')}
          />
          <Button variant="secondary" size="icon" onClick={copy} aria-label={t('common.copy')}>
            {copied ? <Check className="size-4 text-success" /> : <Copy className="size-4" />}
          </Button>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title={t('users.invite.title')}
      description={t('users.invite.description')}
      footer={
        <>
          <Button variant="secondary" onClick={() => close(false)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="invite-form" loading={invite.isPending}>
            {t('users.invite.submit')}
          </Button>
        </>
      }
    >
      <form id="invite-form" onSubmit={onSubmit} noValidate className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <FormField label={t('fields.email')} error={fieldError(errors.email)}>
          <Input type="email" autoFocus placeholder="name@company.com" {...register('email')} />
        </FormField>
        <FormField
          label={t('fields.role')}
          error={fieldError(errors.role)}
          hint={t('users.invite.roleHint')}
        >
          <Select {...register('role')}>
            {assignableRoles(myRole).map((role) => (
              <option key={role} value={role}>
                {t(`roles.${role}`)}
              </option>
            ))}
          </Select>
        </FormField>
      </form>
    </Dialog>
  );
}
