import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { Alert, Avatar, Button, Dialog, FormField, Input, Skeleton } from '@/components/ui';
import { useAllMembers } from '@/features/users/api';
import { useFieldError } from '@/hooks/useFieldError';
import { applyApiErrors } from '@/lib/api/errors';

import { useSaveTeam, type Team } from '../api';

const schema = z.object({
  name: z.string().trim().min(1, 'validation.required').max(80),
  member_ids: z.array(z.number()),
});
type Values = z.infer<typeof schema>;

interface TeamDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  team: Team | null; // null = create
}

export function TeamDialog({ open, onOpenChange, team }: TeamDialogProps) {
  const { t } = useTranslation();
  const fieldError = useFieldError();
  const members = useAllMembers();
  const save = useSaveTeam();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    control,
    handleSubmit,
    reset,
    setError: setFieldError,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', member_ids: [] },
  });

  useEffect(() => {
    if (open) {
      reset({ name: team?.name ?? '', member_ids: team?.members.map((m) => m.id) ?? [] });
    }
  }, [open, team, reset]);

  const handleOpenChange = (next: boolean) => {
    if (!next) setError(null);
    onOpenChange(next);
  };

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      await save.mutateAsync({ id: team?.id, ...values });
      handleOpenChange(false);
    } catch (err) {
      setError(applyApiErrors(err, setFieldError, ['name', 'member_ids']));
    }
  });

  return (
    <Dialog
      open={open}
      onOpenChange={handleOpenChange}
      title={team ? t('teams.editTitle') : t('teams.createTitle')}
      footer={
        <>
          <Button variant="secondary" onClick={() => handleOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="team-form" loading={save.isPending}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="team-form" onSubmit={onSubmit} noValidate className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <FormField label={t('fields.teamName')} error={fieldError(errors.name)}>
          <Input autoFocus {...register('name')} />
        </FormField>

        <fieldset>
          <legend className="mb-1.5 text-[13px] font-medium">{t('teams.members')}</legend>
          {errors.member_ids && (
            <p className="mb-1.5 text-[13px] text-danger">
              {fieldError(errors.member_ids as never)}
            </p>
          )}
          <Controller
            control={control}
            name="member_ids"
            render={({ field }) => (
              <div className="max-h-64 divide-y overflow-y-auto rounded-lg border">
                {members.isPending
                  ? Array.from({ length: 3 }, (_, i) => (
                      <div key={i} className="px-3 py-2.5">
                        <Skeleton className="h-4 w-40" />
                      </div>
                    ))
                  : members.data?.results.map((member) => {
                      const checked = field.value.includes(member.id);
                      return (
                        <label
                          key={member.id}
                          className="flex cursor-pointer items-center gap-2.5 px-3 py-2 hover:bg-subtle"
                        >
                          <input
                            type="checkbox"
                            className="size-4 accent-accent"
                            checked={checked}
                            onChange={() =>
                              field.onChange(
                                checked
                                  ? field.value.filter((id) => id !== member.id)
                                  : [...field.value, member.id],
                              )
                            }
                          />
                          <Avatar name={member.full_name} className="size-6 text-[10px]" />
                          <span className="min-w-0 flex-1 truncate">{member.full_name}</span>
                          <span className="hidden truncate text-xs text-fg-muted sm:inline">
                            {member.email}
                          </span>
                        </label>
                      );
                    })}
              </div>
            )}
          />
        </fieldset>
      </form>
    </Dialog>
  );
}
