import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Button, Dialog, FormField, Input } from '@/components/ui';
import { applyApiErrors, getErrorMessage } from '@/lib/api/errors';

import { useUpdateProfile, type Member } from '../api';

interface Props {
  member: Member;
  onClose: () => void;
}

/** Name and phone numbers of one user. Mount it only while open (fresh values each time). */
export function EditProfileDialog({ member, onClose }: Props) {
  const { t } = useTranslation();
  const update = useUpdateProfile();
  const [values, setValues] = useState({
    full_name: member.full_name,
    phone: member.phone,
    alternate_phone: member.alternate_phone,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [general, setGeneral] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setErrors({});
    setGeneral(null);
    update.mutate(
      { userId: member.id, ...values },
      {
        onSuccess: onClose,
        onError: (error) => {
          const found: Record<string, string> = {};
          const message = applyApiErrors<typeof values>(
            error,
            (field, { message: text }) => {
              found[field] = text ?? '';
            },
            ['full_name', 'phone', 'alternate_phone'],
          );
          setErrors(found);
          setGeneral(message ?? (Object.keys(found).length ? null : getErrorMessage(error)));
        },
      },
    );
  };

  const field = (key: keyof typeof values) => ({
    value: values[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      setValues((v) => ({ ...v, [key]: e.target.value })),
  });

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t('people.editTitle', { name: member.full_name })}
      description={member.email}
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="edit-profile" loading={update.isPending}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="edit-profile" onSubmit={submit} className="space-y-4" noValidate>
        <FormField label={t('people.name')} error={errors.full_name}>
          <Input autoComplete="name" {...field('full_name')} />
        </FormField>
        <FormField label={t('people.phone')} error={errors.phone} hint={t('people.phoneHint')}>
          <Input type="tel" autoComplete="tel" placeholder="+91 98250 12345" {...field('phone')} />
        </FormField>
        <FormField label={t('people.alternatePhone')} error={errors.alternate_phone}>
          <Input type="tel" placeholder="+971 50 123 4567" {...field('alternate_phone')} />
        </FormField>
        {general && <Alert tone="danger">{general}</Alert>}
      </form>
    </Dialog>
  );
}
