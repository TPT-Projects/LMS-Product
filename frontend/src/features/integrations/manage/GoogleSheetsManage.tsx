import { ChevronLeft, FileSpreadsheet, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  FormField,
  Input,
  Select,
  Skeleton,
  Switch,
} from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { useMetaForms, type MetaForm } from '@/features/meta/api';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';

import {
  useChangeSheetForm,
  useCreateSheetExport,
  useCreateSheetLink,
  useDeleteSheetLink,
  useSheetLinks,
  useSheetTabs,
  useSpreadsheets,
  useSyncSheetLink,
  useUpdateSheetLink,
  type SheetField,
  type SheetLink,
  type SheetMapping,
  type SheetTab,
  type Spreadsheet,
} from '../api';
import { utc } from '../time';

const FIELDS: SheetField[] = ['name', 'phone', 'email'];

/** Google Sheets' Manage page: send leads to a sheet, and turn sheet rows into leads. */
export function GoogleSheetsManage() {
  const links = useSheetLinks();
  return (
    <div className="space-y-5">
      {links.isError && <Alert tone="danger">{getErrorMessage(links.error)}</Alert>}
      <ExportSection
        links={(links.data ?? []).filter((l) => l.direction === 'export')}
        loading={links.isPending}
      />
      <ImportSection
        links={(links.data ?? []).filter((l) => l.direction !== 'export')}
        loading={links.isPending}
      />
    </div>
  );
}

function ExportSection({ links, loading }: { links: SheetLink[]; loading: boolean }) {
  const { t } = useTranslation();
  const [adding, setAdding] = useState(false);
  const empty = !loading && links.length === 0;
  return (
    <Card>
      <CardHeader
        title={t('sheets.export.title')}
        description={t('sheets.export.description')}
        actions={
          !adding && (
            <Button size="sm" onClick={() => setAdding(true)}>
              <Plus className="size-3.5" aria-hidden /> {t('sheets.export.add')}
            </Button>
          )
        }
      />
      <CardBody className="space-y-4">
        {loading ? (
          <Skeleton className="h-16 w-full" />
        ) : empty && !adding ? (
          <Alert tone="info">{t('sheets.export.empty')}</Alert>
        ) : (
          <ul className="divide-y rounded-xl border empty:hidden">
            {links.map((link) => (
              <LinkRow key={link.id} link={link} />
            ))}
          </ul>
        )}
        {(adding || empty) && <SendToSheet onDone={() => setAdding(false)} />}
      </CardBody>
    </Card>
  );
}

function ImportSection({ links, loading }: { links: SheetLink[]; loading: boolean }) {
  const { t } = useTranslation();
  const [picking, setPicking] = useState(false);
  const empty = !loading && links.length === 0;
  return (
    <>
      <Card>
        <CardHeader
          title={t('sheets.connected.title')}
          description={t('sheets.connected.description')}
          actions={
            !picking && (
              <Button size="sm" variant="secondary" onClick={() => setPicking(true)}>
                <Plus className="size-3.5" aria-hidden /> {t('sheets.connected.add')}
              </Button>
            )
          }
        />
        <CardBody>
          {loading ? (
            <Skeleton className="h-16 w-full" />
          ) : empty ? (
            <Alert tone="info">{t('sheets.connected.empty')}</Alert>
          ) : (
            <ul className="divide-y rounded-xl border">
              {links.map((link) => (
                <LinkRow key={link.id} link={link} />
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
      {picking && <ConnectSheet onDone={() => setPicking(false)} />}
    </>
  );
}

/** Pick what to send (a Meta form's leads, or all) and where (new spreadsheet or new tab). */
function SendToSheet({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const forms = useMetaForms({ page: 1, page_size: 100 }, true);
  const create = useCreateSheetExport();
  const [form, setForm] = useState<string>('');
  const [target, setTarget] = useState<'new' | 'existing'>('new');
  const [title, setTitle] = useState('');
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const files = useSpreadsheets(q, target === 'existing');
  const [file, setFile] = useState<Spreadsheet | null>(null);
  const sortedForms = sortForms(forms.data?.results ?? []);
  const chosenForm = sortedForms.find((f) => String(f.id) === form);
  const formOption = (f: MetaForm) =>
    `${f.name || f.form_id} · ${t('sheets.export.leads', { count: f.leads_received })}${
      f.is_connected ? '' : ` · ${t('sheets.export.off')}`
    }`;
  const formName = chosenForm?.name;
  const defaultTitle = `LMS - ${formName ?? t('sheets.export.allEnquiries')}`;

  return (
    <div className="space-y-4 rounded-xl border border-dashed p-4">
      <FormField label={t('sheets.export.which')} hint={t('sheets.export.whichHint')}>
        <Select value={form} onChange={(e) => setForm(e.target.value)}>
          <option value="">{t('sheets.export.allEnquiries')}</option>
          {sortedForms.map((f) => (
            <option key={f.id} value={f.id}>
              {formOption(f)}
            </option>
          ))}
        </Select>
      </FormField>
      {chosenForm && !chosenForm.is_connected && (
        <Alert tone="info">{t('sheets.export.willConnect', { form: chosenForm.name })}</Alert>
      )}
      {chosenForm && chosenForm.is_connected && chosenForm.leads_received === 0 && (
        <Alert tone="info">{t('sheets.export.noLeadsYet')}</Alert>
      )}

      <div role="radiogroup" aria-label={t('sheets.export.where')} className="space-y-2">
        <p className="text-[13px] font-medium">{t('sheets.export.where')}</p>
        {(['new', 'existing'] as const).map((value) => (
          <label key={value} className="flex items-center gap-2 text-[13px]">
            <input
              type="radio"
              className="accent-[var(--accent)]"
              checked={target === value}
              onChange={() => setTarget(value)}
            />
            {t(`sheets.export.target.${value}`)}
          </label>
        ))}
      </div>

      {target === 'new' ? (
        <FormField label={t('sheets.export.newTitle')}>
          <Input
            value={title}
            placeholder={defaultTitle}
            onChange={(e) => setTitle(e.target.value)}
          />
        </FormField>
      ) : (
        <div className="space-y-2">
          <Input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('sheets.pick.search')}
            aria-label={t('sheets.pick.search')}
          />
          {files.isPending ? (
            <Skeleton className="h-20 w-full" />
          ) : files.isError ? (
            <Alert tone="danger">{getErrorMessage(files.error)}</Alert>
          ) : (
            <ul className="max-h-56 divide-y overflow-y-auto rounded-xl border">
              {(files.data ?? []).map((f) => (
                <li key={f.id}>
                  <button
                    type="button"
                    onClick={() => setFile(f)}
                    className={cn(
                      'flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-subtle',
                      file?.id === f.id && 'bg-accent-soft',
                    )}
                  >
                    <FileSpreadsheet className="size-4 shrink-0 text-[#0F9D58]" aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{f.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-fg-muted">{t('sheets.export.newTabHint')}</p>
        </div>
      )}

      <p className="text-xs text-fg-muted">{t('sheets.export.columns')}</p>
      {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
      <Button
        loading={create.isPending}
        disabled={target === 'existing' && !file}
        onClick={() =>
          create.mutate(
            {
              form: form ? Number(form) : null,
              spreadsheet_id: target === 'existing' ? file?.id : undefined,
              new_title: target === 'new' ? title.trim() || defaultTitle : undefined,
            },
            { onSuccess: onDone },
          )
        }
      >
        {t('sheets.export.connect')}
      </Button>
    </div>
  );
}

function LinkRow({ link }: { link: SheetLink }) {
  const { t } = useTranslation();
  const format = useDateFormat();
  const sync = useSyncSheetLink();
  const update = useUpdateSheetLink();
  const remove = useDeleteSheetLink();
  const error = sync.error ?? update.error ?? remove.error;

  return (
    <li className="space-y-2 px-3 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <FileSpreadsheet className="size-4 shrink-0 text-[#0F9D58]" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">
            {link.spreadsheet_name} <span className="text-fg-muted">› {link.sheet_title}</span>
          </p>
          {link.direction === 'export' && (
            <p className="text-xs font-medium text-accent">
              {t('sheets.export.sending', {
                what: link.form_name || t('sheets.export.allEnquiries'),
              })}
            </p>
          )}
          <p className="text-xs text-fg-muted" title={utc(link.last_synced_at)}>
            {link.direction === 'export'
              ? t('sheets.export.stats', { count: link.rows_imported })
              : t('sheets.connected.stats', { count: link.rows_imported })}
            {link.last_synced_at &&
              ` · ${t('sheets.connected.synced', { when: format.dateTime(link.last_synced_at) })}`}
          </p>
          <p className="text-xs text-fg-muted">
            {FIELDS.filter((f) => link.mapping[f])
              .map((f) => `${t(`sheets.fields.${f}`)}: ${link.mapping[f]}`)
              .join(' · ')}
          </p>
        </div>
        {!link.is_active && <Badge>{t('sheets.connected.paused')}</Badge>}
        <Switch
          checked={link.is_active}
          aria-label={t('sheets.connected.autoSync', { sheet: link.sheet_title })}
          disabled={update.isPending}
          onCheckedChange={(isActive) => update.mutate({ id: link.id, isActive })}
        />
        <Button
          variant="secondary"
          size="sm"
          loading={sync.isPending}
          onClick={() => sync.mutate(link.id)}
        >
          <RefreshCw className="size-3.5" aria-hidden /> {t('sheets.connected.syncNow')}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          aria-label={t('sheets.connected.remove', { sheet: link.sheet_title })}
          loading={remove.isPending}
          onClick={() => {
            if (window.confirm(t('sheets.connected.confirmRemove'))) remove.mutate(link.id);
          }}
        >
          <Trash2 className="size-3.5" aria-hidden />
        </Button>
      </div>
      {link.direction === 'export' && <ChangeForm link={link} />}
      {link.last_error && <Alert tone="danger">{link.last_error}</Alert>}
      {error != null && <Alert tone="danger">{getErrorMessage(error)}</Alert>}
      {sync.data && link.direction !== 'export' && (
        <p className="text-xs text-success">
          {t('sheets.connected.imported', { count: sync.data.imported })}
        </p>
      )}
    </li>
  );
}

/** Pick a spreadsheet, then a tab, check the columns, connect. */
function ConnectSheet({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const files = useSpreadsheets(q, true);
  const [file, setFile] = useState<Spreadsheet | null>(null);

  return (
    <Card>
      <CardHeader
        title={file ? file.name : t('sheets.pick.title')}
        description={file ? t('sheets.pick.tabHint') : t('sheets.pick.description')}
        actions={
          file && (
            <Button variant="ghost" size="sm" onClick={() => setFile(null)}>
              <ChevronLeft className="size-4" aria-hidden /> {t('sheets.pick.back')}
            </Button>
          )
        }
      />
      <CardBody className="space-y-3">
        {file ? (
          <PickTab file={file} onDone={onDone} />
        ) : (
          <>
            <label className="relative block">
              <span className="sr-only">{t('sheets.pick.search')}</span>
              <Search
                className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-muted"
                aria-hidden
              />
              <Input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t('sheets.pick.search')}
                className="pl-9"
              />
            </label>
            {files.isPending ? (
              <Skeleton className="h-32 w-full" />
            ) : files.isError ? (
              <Alert tone="danger">{getErrorMessage(files.error)}</Alert>
            ) : (files.data ?? []).length === 0 ? (
              <Alert tone="info">{t('sheets.pick.none')}</Alert>
            ) : (
              <ul className="max-h-80 divide-y overflow-y-auto rounded-xl border">
                {(files.data ?? []).map((f) => (
                  <li key={f.id}>
                    <button
                      type="button"
                      onClick={() => setFile(f)}
                      className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-subtle"
                    >
                      <FileSpreadsheet className="size-4 shrink-0 text-[#0F9D58]" aria-hidden />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{f.name}</span>
                        {f.owner && <span className="block text-xs text-fg-muted">{f.owner}</span>}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}

function PickTab({ file, onDone }: { file: Spreadsheet; onDone: () => void }) {
  const { t } = useTranslation();
  const tabs = useSheetTabs(file.id);
  const [tab, setTab] = useState<SheetTab | null>(null);

  if (tabs.isPending) return <Skeleton className="h-24 w-full" />;
  if (tabs.isError) return <Alert tone="danger">{getErrorMessage(tabs.error)}</Alert>;
  const list = tabs.data ?? [];
  const chosen = tab ?? (list.length === 1 ? list[0] : null);

  return (
    <div className="space-y-4">
      <div role="radiogroup" aria-label={t('sheets.pick.tabs')} className="flex flex-wrap gap-2">
        {list.map((item) => (
          <button
            key={item.title}
            type="button"
            role="radio"
            aria-checked={chosen?.title === item.title}
            onClick={() => setTab(item)}
            className={cn(
              'h-8 rounded-full border px-3 text-[13px] transition-colors',
              chosen?.title === item.title
                ? 'border-accent bg-accent-soft font-medium'
                : 'hover:bg-subtle',
            )}
          >
            {item.title}
          </button>
        ))}
      </div>
      {chosen && <MapColumns key={chosen.title} file={file} tab={chosen} onDone={onDone} />}
    </div>
  );
}

function MapColumns({
  file,
  tab,
  onDone,
}: {
  file: Spreadsheet;
  tab: SheetTab;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const create = useCreateSheetLink();
  const [mapping, setMapping] = useState<SheetMapping>(tab.mapping);
  const [importExisting, setImportExisting] = useState(true);

  if (tab.headers.length === 0) return <Alert tone="info">{t('sheets.pick.noHeader')}</Alert>;

  return (
    <div className="space-y-4">
      <p className="text-[13px] text-fg-muted">{t('sheets.pick.mapHint')}</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {FIELDS.map((field) => (
          <FormField key={field} label={t(`sheets.fields.${field}`)}>
            <Select
              value={mapping[field] ?? ''}
              onChange={(e) => setMapping((m) => ({ ...m, [field]: e.target.value || undefined }))}
            >
              <option value="">{t('sheets.pick.notInSheet')}</option>
              {tab.headers.filter(Boolean).map((header) => (
                <option key={header} value={header}>
                  {header}
                </option>
              ))}
            </Select>
          </FormField>
        ))}
      </div>
      <p className="text-xs text-fg-muted">{t('sheets.pick.otherColumns')}</p>
      <label className="flex items-center gap-2 text-[13px]">
        <Checkbox checked={importExisting} onChange={(e) => setImportExisting(e.target.checked)} />
        {t('sheets.pick.importExisting')}
      </label>
      {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
      {create.data && (
        <Alert tone="success">
          {t('sheets.connected.imported', { count: create.data.imported })}
        </Alert>
      )}
      <Button
        loading={create.isPending}
        disabled={!mapping.phone && !mapping.email}
        onClick={() =>
          create.mutate(
            {
              spreadsheet_id: file.id,
              spreadsheet_name: file.name,
              sheet_title: tab.title,
              mapping,
              import_existing: importExisting,
            },
            { onSuccess: onDone },
          )
        }
      >
        {t('sheets.pick.connect')}
      </Button>
    </div>
  );
}

/** Connected forms with the most leads first: the ones that really receive leads. */
function sortForms(forms: MetaForm[]): MetaForm[] {
  return [...forms].sort(
    (a, b) =>
      Number(b.is_connected) - Number(a.is_connected) || b.leads_received - a.leads_received,
  );
}

function ChangeForm({ link }: { link: SheetLink }) {
  const { t } = useTranslation();
  const forms = useMetaForms({ page: 1, page_size: 100 }, true);
  const change = useChangeSheetForm();
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <label htmlFor={`sheet-form-${link.id}`} className="text-fg-muted">
        {t('sheets.export.changeForm')}
      </label>
      <Select
        id={`sheet-form-${link.id}`}
        className="h-8 w-auto max-w-72 text-xs"
        value={link.form ?? ''}
        disabled={change.isPending}
        onChange={(e) =>
          change.mutate({ id: link.id, form: e.target.value ? Number(e.target.value) : null })
        }
      >
        <option value="">{t('sheets.export.allEnquiries')}</option>
        {sortForms(forms.data?.results ?? []).map((f) => (
          <option key={f.id} value={f.id}>
            {`${f.name || f.form_id} · ${t('sheets.export.leads', { count: f.leads_received })}`}
          </option>
        ))}
      </Select>
      {change.isError && <span className="text-danger">{getErrorMessage(change.error)}</span>}
    </div>
  );
}
