import { Lock, Pencil } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Button, Card, ChipGroup, FormField, Input } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { useAllMembers } from '@/features/users/api';
import { getErrorMessage } from '@/lib/api/errors';
import type { EnquiryDetail } from '@/types/crm';

import { useUpdateEnquiry } from '../api';
import { OwnerSelect } from './OwnerSelect';

function Row({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_1fr] gap-3 py-1.5 text-[13px]">
      <dt className="text-fg-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b px-4 py-2.5">
      <h2 className="text-[13px] font-semibold">{children}</h2>
      {action}
    </div>
  );
}

/** Enquiry details and owners. Phone is locked after creation (spec 6.6). */
export function DetailsCard({ enquiry }: { enquiry: EnquiryDetail }) {
  const { t } = useTranslation();
  const format = useDateFormat();
  const members = useAllMembers();
  const update = useUpdateEnquiry(enquiry.id);
  const { can_edit: canEdit, can_reassign: canReassign } = enquiry.permissions;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({
    name: enquiry.name,
    email: enquiry.email,
    campaign_name: enquiry.campaign_name,
    adset_name: enquiry.adset_name,
    ad_name: enquiry.ad_name,
    primary_owner_id: enquiry.primary_owner ? String(enquiry.primary_owner.id) : '',
    secondary: enquiry.secondary_owners.map((o) => String(o.id)),
  });

  const start = () => {
    setDraft({
      name: enquiry.name,
      email: enquiry.email,
      campaign_name: enquiry.campaign_name,
      adset_name: enquiry.adset_name,
      ad_name: enquiry.ad_name,
      primary_owner_id: enquiry.primary_owner ? String(enquiry.primary_owner.id) : '',
      secondary: enquiry.secondary_owners.map((o) => String(o.id)),
    });
    update.reset();
    setEditing(true);
  };

  const save = async () => {
    await update.mutateAsync({
      name: draft.name,
      email: draft.email,
      campaign_name: draft.campaign_name,
      adset_name: draft.adset_name,
      ad_name: draft.ad_name,
      ...(canReassign
        ? {
            primary_owner_id: draft.primary_owner_id ? Number(draft.primary_owner_id) : null,
            secondary_owner_ids: draft.secondary.map(Number),
          }
        : {}),
    });
    setEditing(false);
  };

  const set = (key: keyof typeof draft) => (e: { target: { value: string } }) =>
    setDraft((d) => ({ ...d, [key]: e.target.value }));

  return (
    <Card>
      <SectionTitle
        action={
          canEdit &&
          !editing && (
            <Button variant="ghost" size="sm" onClick={start}>
              <Pencil className="size-3.5" aria-hidden /> {t('common.edit')}
            </Button>
          )
        }
      >
        {t('enquiry.details')}
      </SectionTitle>
      {editing ? (
        <form
          className="space-y-3 p-4"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          {update.isError && <Alert tone="danger">{getErrorMessage(update.error)}</Alert>}
          <FormField label={t('fields.name')}>
            <Input value={draft.name} onChange={set('name')} maxLength={200} />
          </FormField>
          <FormField label={t('fields.phone')} hint={t('enquiry.phoneLocked')}>
            <Input value={enquiry.phone_e164 || enquiry.phone} disabled readOnly />
          </FormField>
          <FormField label={t('fields.email')}>
            <Input type="email" value={draft.email} onChange={set('email')} />
          </FormField>
          <FormField label={t('fields.campaign')}>
            <Input value={draft.campaign_name} onChange={set('campaign_name')} />
          </FormField>
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label={t('fields.adset')}>
              <Input value={draft.adset_name} onChange={set('adset_name')} />
            </FormField>
            <FormField label={t('fields.ad')}>
              <Input value={draft.ad_name} onChange={set('ad_name')} />
            </FormField>
          </div>
          {canReassign && (
            <>
              <FormField label={t('fields.owner')}>
                <OwnerSelect value={draft.primary_owner_id} onChange={set('primary_owner_id')} />
              </FormField>
              <fieldset>
                <legend className="mb-1.5 text-[13px] font-medium">
                  {t('enquiry.secondaryOwners')}
                </legend>
                <ChipGroup
                  choices={(members.data?.results ?? [])
                    .filter((m) => String(m.id) !== draft.primary_owner_id)
                    .map((m) => ({ value: String(m.id), label: m.full_name }))}
                  selected={draft.secondary}
                  onChange={(secondary) => setDraft((d) => ({ ...d, secondary }))}
                />
              </fieldset>
            </>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="secondary" size="sm" onClick={() => setEditing(false)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" size="sm" loading={update.isPending}>
              {t('common.save')}
            </Button>
          </div>
        </form>
      ) : (
        <dl className="px-4 py-2">
          <Row label={t('fields.phone')}>
            <span className="inline-flex items-center gap-1.5">
              {enquiry.phone_e164 || enquiry.phone || '—'}
              <Lock className="size-3 text-fg-subtle" aria-label={t('enquiry.phoneLocked')} />
            </span>
          </Row>
          <Row label={t('fields.email')}>{enquiry.email || '—'}</Row>
          <Row label={t('fields.owner')}>
            {enquiry.primary_owner?.full_name ?? (
              <span className="text-fg-subtle">{t('enquiries.unassigned')}</span>
            )}
          </Row>
          <Row label={t('enquiry.secondaryOwners')}>
            {enquiry.secondary_owners.length
              ? enquiry.secondary_owners.map((o) => o.full_name).join(', ')
              : '—'}
          </Row>
          <Row label={t('fields.source')}>{t(`sources.${enquiry.source}`)}</Row>
          <Row label={t('fields.campaign')}>{enquiry.campaign_name || '—'}</Row>
          <Row label={t('fields.adset')}>{enquiry.adset_name || '—'}</Row>
          <Row label={t('fields.ad')}>{enquiry.ad_name || '—'}</Row>
          {enquiry.form_id && <Row label={t('fields.form')}>{enquiry.form_id}</Row>}
          <Row label={t('common.created')}>
            {format.dateTime(enquiry.created_at)}
            {enquiry.created_by && (
              <span className="text-fg-muted"> · {enquiry.created_by.full_name}</span>
            )}
          </Row>
        </dl>
      )}
    </Card>
  );
}
