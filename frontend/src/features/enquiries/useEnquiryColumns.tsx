import type { ColumnDef } from '@tanstack/react-table';
import { Repeat } from 'lucide-react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import type { ColumnOption } from '@/components/data-table';
import { useDateFormat } from '@/features/auth/useAuth';
import { formatCustomValue } from '@/features/customfields/values';
import { useTableColumns } from '@/hooks/useTableColumns';
import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';
import type { CustomField, Enquiry } from '@/types/crm';

import { ActionBadge } from './components/ActionBadge';
import { StatusCell } from './components/StatusCell';

type Col = ColumnDef<Enquiry, unknown>;

const muted = (text: string | null | undefined) =>
  text ? (
    <span className="block max-w-56 truncate text-fg-muted">{text}</span>
  ) : (
    <span className="text-fg-subtle">—</span>
  );

/**
 * Every column the enquiry table can show, and the user's chosen layout.
 * Name, Action and Status are always the first three columns. Owner, Source, Campaign and
 * Created show by default; everything else (custom fields too) can be added and reordered.
 */
export function useEnquiryColumns(customFields: CustomField[]) {
  const { t } = useTranslation();
  const format = useDateFormat();

  const options = useMemo<ColumnOption[]>(
    () => [
      { id: 'name', label: t('fields.name'), fixed: 'start' },
      { id: 'action', label: t('columns.action'), fixed: 'start' },
      { id: 'status', label: t('fields.status'), fixed: 'start' },
      { id: 'owner', label: t('fields.owner'), defaultVisible: true },
      { id: 'source', label: t('fields.source'), defaultVisible: true },
      { id: 'campaign', label: t('fields.campaign'), defaultVisible: true },
      { id: 'created', label: t('common.created'), defaultVisible: true },
      ...customFields.map((f) => ({ id: `cf:${f.key}`, label: f.label })),
      { id: 'phone', label: t('fields.phone') },
      { id: 'email', label: t('fields.email') },
      { id: 'secondary_owners', label: t('enquiry.secondaryOwners') },
      { id: 'adset', label: t('fields.adset') },
      { id: 'ad', label: t('fields.ad') },
      { id: 'form', label: t('fields.form') },
      { id: 'next_followup', label: t('enquiries.nextFollowUp') },
      { id: 'repeat', label: t('enquiries.repeat') },
      { id: 'updated', label: t('columns.updated') },
    ],
    [t, customFields],
  );

  const layout = useTableColumns('enquiries', options);

  const defs = useMemo(() => {
    const byId: Record<string, Col> = {
      name: {
        id: 'name',
        header: t('fields.name'),
        meta: { className: 'sticky left-0 z-[1] bg-surface group-hover:bg-subtle' },
        cell: ({ row }) => {
          const e = row.original;
          return (
            <div className="max-w-64 min-w-0">
              <Link
                to={`${paths.enquiries}/${e.id}`}
                onClick={(ev) => ev.stopPropagation()}
                className="flex items-center gap-1.5 font-medium hover:underline"
              >
                <span className="truncate">{e.name || t('enquiries.noName')}</span>
                {e.is_repeat && (
                  <Repeat
                    className="size-3.5 shrink-0 text-accent"
                    aria-label={t('enquiries.repeat')}
                  />
                )}
              </Link>
              <p className="truncate text-xs text-fg-muted">{e.phone_e164 || e.phone || e.email}</p>
            </div>
          );
        },
      },
      status: {
        id: 'status',
        header: t('fields.status'),
        cell: ({ row }) => <StatusCell enquiry={row.original} />,
      },
      owner: {
        id: 'owner',
        header: t('fields.owner'),
        cell: ({ row }) =>
          row.original.primary_owner ? (
            <span className="whitespace-nowrap">{row.original.primary_owner.full_name}</span>
          ) : (
            <span className="text-fg-subtle">{t('enquiries.unassigned')}</span>
          ),
      },
      secondary_owners: {
        id: 'secondary_owners',
        header: t('enquiry.secondaryOwners'),
        cell: ({ row }) => muted(row.original.secondary_owners.map((o) => o.full_name).join(', ')),
      },
      source: {
        id: 'source',
        header: t('fields.source'),
        cell: ({ row }) => (
          <span className="text-fg-muted">{t(`sources.${row.original.source}`)}</span>
        ),
      },
      campaign: {
        id: 'campaign',
        header: t('fields.campaign'),
        cell: ({ row }) => muted(row.original.campaign_name),
      },
      adset: {
        id: 'adset',
        header: t('fields.adset'),
        cell: ({ row }) => muted(row.original.adset_name),
      },
      ad: { id: 'ad', header: t('fields.ad'), cell: ({ row }) => muted(row.original.ad_name) },
      form: {
        id: 'form',
        header: t('fields.form'),
        cell: ({ row }) => muted(row.original.form_id),
      },
      phone: {
        id: 'phone',
        header: t('fields.phone'),
        cell: ({ row }) => (
          <span className="tabular-nums">
            {row.original.phone_e164 || row.original.phone || '—'}
          </span>
        ),
      },
      email: {
        id: 'email',
        header: t('fields.email'),
        cell: ({ row }) => muted(row.original.email),
      },
      next_followup: {
        id: 'next_followup',
        header: t('enquiries.nextFollowUp'),
        cell: ({ row }) => {
          const due = row.original.next_followup_at;
          if (!due) return <span className="text-fg-subtle">—</span>;
          return (
            <span
              className={cn(
                'tabular-nums',
                new Date(due) < new Date() ? 'text-danger' : 'text-fg-muted',
              )}
            >
              {format.dateTime(due)}
            </span>
          );
        },
      },
      repeat: {
        id: 'repeat',
        header: t('enquiries.repeat'),
        cell: ({ row }) =>
          row.original.is_repeat ? (
            t('common.yes')
          ) : (
            <span className="text-fg-subtle">{t('common.no')}</span>
          ),
      },
      created: {
        id: 'created',
        header: t('common.created'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">{format.date(row.original.created_at)}</span>
        ),
      },
      updated: {
        id: 'updated',
        header: t('columns.updated'),
        cell: ({ row }) => (
          <span className="text-fg-muted tabular-nums">
            {format.dateTime(row.original.updated_at)}
          </span>
        ),
      },
      action: {
        id: 'action',
        header: t('columns.action'),
        // Pinned to the right edge so actions stay reachable when the table scrolls sideways.
        meta: { className: 'sticky right-0 z-[1] bg-surface text-right group-hover:bg-subtle' },
        cell: ({ row }) => <ActionBadge enquiry={row.original} />,
      },
    };
    for (const field of customFields) {
      byId[`cf:${field.key}`] = {
        id: `cf:${field.key}`,
        header: field.label,
        cell: ({ row }) =>
          muted(
            formatCustomValue(field, row.original.custom_fields[field.key], {
              yes: t('common.yes'),
              no: t('common.no'),
            }).replace(/^—$/, ''),
          ),
      };
    }
    return layout.visible.map((id) => byId[id]).filter((c): c is Col => Boolean(c));
  }, [t, format, customFields, layout.visible]);

  return {
    options,
    defs,
    visible: layout.visible,
    save: (cols: string[]) => layout.save.mutate(cols),
  };
}
