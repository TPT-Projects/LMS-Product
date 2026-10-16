import { ExternalLink, Lock } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Button, Dialog, FormField, Input, Select } from '@/components/ui';
import { getErrorMessage, nestedErrors } from '@/lib/api/errors';

import { useConnectApp, type AppStatus } from '../api';
import type { AppDef } from '../catalog';
import { AppLogo } from './AppLogo';

interface Props {
  app: AppDef;
  status?: AppStatus;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * The short form for apps that connect with an API key / token. Checked live before saving.
 * Mount it only while open, so each opening starts from the latest saved details.
 */
export function ConnectAppDialog({ app, status, open, onOpenChange }: Props) {
  const { t } = useTranslation();
  const connect = useConnectApp(app.key);
  const editing = status?.status === 'connected' || status?.status === 'error';
  const [values, setValues] = useState<Record<string, string>>(() => initialValues(app, status));
  const fieldErrors = nestedErrors(connect.error, 'values');
  const name = t(`apps.catalog.${app.key}.name`);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    connect.mutate(values, { onSuccess: () => onOpenChange(false) });
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={
        editing
          ? t('apps.connect.editTitle', { app: name })
          : t('apps.connect.title', { app: name })
      }
      description={t(`apps.catalog.${app.key}.connectHint`)}
      footer={
        <>
          <Button variant="secondary" type="button" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={`connect-${app.key}`} loading={connect.isPending}>
            {editing ? t('apps.connect.save') : t('apps.connect.submit')}
          </Button>
        </>
      }
    >
      <form id={`connect-${app.key}`} onSubmit={submit} className="space-y-4" noValidate>
        <div className="flex items-center gap-3 rounded-xl bg-subtle p-3">
          <AppLogo app={app} size="sm" />
          <p className="text-[13px] text-fg-muted">
            {t('apps.connect.checkedFirst', { app: name })}
          </p>
        </div>

        {app.fields?.map((field) => {
          const base = `apps.fields.${app.key}.${field.key}`;
          const saved = field.type === 'secret' && status?.secrets_set.includes(field.key);
          const label = (
            <>
              {t(`${base}.label`)}
              {field.optional && (
                <span className="ml-1 font-normal text-fg-muted">{t('apps.connect.optional')}</span>
              )}
            </>
          );
          const onChange = (value: string) => setValues((v) => ({ ...v, [field.key]: value }));
          return (
            <FormField
              key={field.key}
              label={label}
              error={fieldErrors[field.key]}
              hint={saved ? t('apps.connect.secretSaved') : t(`${base}.hint`)}
            >
              {field.type === 'select' ? (
                <Select value={values[field.key] ?? ''} onChange={(e) => onChange(e.target.value)}>
                  {field.options?.map((option) => (
                    <option key={option} value={option}>
                      {t(`${base}.options.${option}`)}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  type={field.type === 'secret' ? 'password' : 'text'}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder={saved ? '••••••••••••' : t(`${base}.placeholder`)}
                  value={values[field.key] ?? ''}
                  onChange={(e) => onChange(e.target.value)}
                />
              )}
            </FormField>
          );
        })}

        {connect.isError && Object.keys(fieldErrors).length === 0 && (
          <Alert tone="danger">{getErrorMessage(connect.error)}</Alert>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-fg-muted">
          <span className="inline-flex items-center gap-1.5">
            <Lock className="size-3.5" aria-hidden /> {t('apps.connect.encrypted')}
          </span>
          {app.docsUrl && (
            <a
              href={app.docsUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-accent hover:underline"
            >
              {t('apps.connect.whereToFind')} <ExternalLink className="size-3" aria-hidden />
            </a>
          )}
        </div>
      </form>
    </Dialog>
  );
}

function initialValues(app: AppDef, status?: AppStatus): Record<string, string> {
  const values: Record<string, string> = {};
  for (const field of app.fields ?? []) {
    if (field.type === 'secret') values[field.key] = '';
    else values[field.key] = status?.config[field.key] ?? field.options?.[0] ?? '';
  }
  return values;
}
