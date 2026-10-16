import { Pencil, Plus, SlidersHorizontal } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Badge, Button, Card, CardHeader, EmptyState, Skeleton } from '@/components/ui';
import { useAuth } from '@/features/auth/useAuth';
import { getErrorMessage } from '@/lib/api/errors';
import type { CustomField } from '@/types/crm';

import { useCustomFields } from '../api';
import { CustomFieldDialog } from '../components/CustomFieldDialog';
import { displayOption } from '../values';

export default function CustomFieldsSettingsPage() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const canEdit = can('manage_settings');
  const fields = useCustomFields();
  const [dialog, setDialog] = useState<{ open: boolean; field: CustomField | null }>({
    open: false,
    field: null,
  });

  const addButton = canEdit && (
    <Button onClick={() => setDialog({ open: true, field: null })}>
      <Plus className="size-4" aria-hidden />
      {t('customFields.add')}
    </Button>
  );

  return (
    <Card>
      <CardHeader
        title={t('customFields.title')}
        description={t('customFields.description')}
        actions={addButton}
      />
      {fields.isError && (
        <div className="px-4 pt-3 sm:px-5">
          <Alert tone="danger">{getErrorMessage(fields.error)}</Alert>
        </div>
      )}
      {fields.isPending ? (
        <div className="space-y-3 p-5">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-5 w-40" />
        </div>
      ) : fields.data?.length === 0 ? (
        <EmptyState
          icon={SlidersHorizontal}
          title={t('customFields.empty.title')}
          description={t('customFields.empty.description')}
          action={addButton}
        />
      ) : (
        <ul className="divide-y">
          {fields.data?.map((field) => (
            <li key={field.id} className="flex items-center gap-3 px-4 py-3 sm:px-5">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 font-medium">
                  {field.label}
                  <Badge>{t(`customFields.types.${field.type}`)}</Badge>
                  {field.is_required && (
                    <Badge tone="accent">{t('customFields.requiredBadge')}</Badge>
                  )}
                  {!field.is_active && <Badge tone="warning">{t('customFields.inactive')}</Badge>}
                </p>
                <p className="mt-0.5 truncate text-xs text-fg-muted">
                  <code>{field.key}</code>
                  {field.options.length > 0 && (
                    <> · {field.options.map(displayOption).join('  ·  ')}</>
                  )}
                </p>
              </div>
              {canEdit && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t('common.editName', { name: field.label })}
                  onClick={() => setDialog({ open: true, field })}
                >
                  <Pencil className="size-4" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <CustomFieldDialog
          open={dialog.open}
          field={dialog.field}
          onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        />
      )}
    </Card>
  );
}
