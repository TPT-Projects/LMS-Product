import { ArrowLeft, ArrowRight, Download, FileSpreadsheet, Upload } from 'lucide-react';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { Alert, Button, Card, CardBody, Select, Skeleton } from '@/components/ui';
import { activeFields, useCustomFields } from '@/features/customfields/api';
import { getErrorMessage, nestedErrors } from '@/lib/api/errors';
import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';

import {
  downloadFile,
  usePreview,
  useRunImport,
  useSaveMapping,
  useUploadImport,
  type UploadedImport,
} from '../api';

type Step = 'upload' | 'map' | 'preview';
const STEPS: Step[] = ['upload', 'map', 'preview'];
const STANDARD = [
  'name',
  'phone',
  'email',
  'status',
  'owner',
  'campaign',
  'adset',
  'ad',
  'form',
  'created_at',
];
const ACCEPT = '.csv,.xlsx';

/** Upload -> map columns -> preview (nothing saved) -> run. Spec flow F4. */
export default function ImportWizardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const fields = activeFields(useCustomFields().data);
  const fileInput = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>('upload');
  const [job, setJob] = useState<UploadedImport | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const upload = useUploadImport();
  const saveMapping = useSaveMapping(job?.id ?? 0);
  const preview = usePreview(step === 'preview' && job ? job.id : null);
  const run = useRunImport(job?.id ?? 0);

  const targetLabel = (target: string) =>
    target.startsWith('cf:')
      ? (fields.find((f) => `cf:${f.key}` === target)?.label ?? target)
      : t(`imports.targets.${target}`);
  const targets = [...STANDARD, ...fields.map((f) => `cf:${f.key}`)];
  const used = new Set(Object.values(mapping).filter(Boolean));
  const mappingErrors = nestedErrors(saveMapping.error, 'mapping');

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    const uploaded = await upload.mutateAsync(file).catch(() => null);
    if (uploaded) {
      setJob(uploaded);
      setMapping(uploaded.mapping);
      setStep('map');
    }
  };

  const toPreview = async () => {
    await saveMapping.mutateAsync(mapping);
    setStep('preview');
  };

  const start = async () => {
    const result = await run.mutateAsync();
    navigate(`${paths.imports}/${result.id}`);
  };

  return (
    <div className="mx-auto max-w-5xl">
      <Link
        to={paths.imports}
        className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="size-4" aria-hidden /> {t('imports.back')}
      </Link>
      <PageHeader title={t('imports.new')} description={t('imports.wizardDescription')} />

      <ol className="mb-5 flex gap-2 text-[13px]" aria-label={t('imports.steps')}>
        {STEPS.map((s, i) => (
          <li
            key={s}
            aria-current={step === s ? 'step' : undefined}
            className={cn(
              'flex items-center gap-2 rounded-full border px-3 py-1',
              step === s ? 'border-accent bg-accent-soft font-medium text-accent' : 'text-fg-muted',
            )}
          >
            <span className="tabular-nums">{i + 1}</span> {t(`imports.stepNames.${s}`)}
          </li>
        ))}
      </ol>

      {step === 'upload' && (
        <Card>
          <CardBody className="space-y-4">
            <div
              className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                void onFile(e.dataTransfer.files[0]);
              }}
            >
              <Upload className="size-6 text-fg-subtle" aria-hidden />
              <p className="font-medium">{t('imports.dropTitle')}</p>
              <p className="max-w-md text-[13px] text-fg-muted">{t('imports.dropHint')}</p>
              <input
                ref={fileInput}
                type="file"
                accept={ACCEPT}
                className="sr-only"
                onChange={(e) => void onFile(e.target.files?.[0])}
              />
              <Button loading={upload.isPending} onClick={() => fileInput.current?.click()}>
                <FileSpreadsheet className="size-4" aria-hidden /> {t('imports.chooseFile')}
              </Button>
            </div>
            {upload.isError && <Alert tone="danger">{getErrorMessage(upload.error)}</Alert>}
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                void downloadFile('/imports/template', 'enquiries-import-template.csv')
              }
            >
              <Download className="size-3.5" aria-hidden /> {t('imports.template')}
            </Button>
          </CardBody>
        </Card>
      )}

      {step === 'map' && job && (
        <Card>
          <div className="border-b px-4 py-3 sm:px-5">
            <p className="font-medium">{job.original_name}</p>
            <p className="text-[13px] text-fg-muted">
              {t('imports.rowCount', { count: job.row_count })}
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b text-xs text-fg-muted">
                  <th className="px-4 py-2 font-medium sm:pl-5">{t('imports.column')}</th>
                  <th className="px-3 py-2 font-medium">{t('imports.example')}</th>
                  <th className="px-4 py-2 font-medium sm:pr-5">{t('imports.importAs')}</th>
                </tr>
              </thead>
              <tbody>
                {job.headers.map((header) => (
                  <tr key={header} className="border-b last:border-0">
                    <td className="px-4 py-2 font-medium sm:pl-5">{header}</td>
                    <td className="max-w-56 truncate px-3 py-2 text-fg-muted">
                      {job.sample.find((r) => r[header])?.[header] ?? '—'}
                    </td>
                    <td className="px-4 py-2 sm:pr-5">
                      <Select
                        aria-label={t('imports.importAsFor', { column: header })}
                        className="h-8 min-w-44"
                        value={mapping[header] ?? ''}
                        invalid={Boolean(mappingErrors[header])}
                        onChange={(e) => setMapping((m) => ({ ...m, [header]: e.target.value }))}
                      >
                        <option value="">{t('imports.ignore')}</option>
                        {targets.map((target) => (
                          <option
                            key={target}
                            value={target}
                            disabled={used.has(target) && mapping[header] !== target}
                          >
                            {targetLabel(target)}
                          </option>
                        ))}
                      </Select>
                      {mappingErrors[header] && (
                        <p className="mt-1 text-xs text-danger">{mappingErrors[header]}</p>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="space-y-3 border-t px-4 py-3 sm:px-5">
            {mappingErrors.mapping && <Alert tone="danger">{mappingErrors.mapping}</Alert>}
            {saveMapping.isError && !Object.keys(mappingErrors).length && (
              <Alert tone="danger">{getErrorMessage(saveMapping.error)}</Alert>
            )}
            <p className="text-[13px] text-fg-muted">{t('imports.mapHint')}</p>
            <div className="flex justify-between gap-2">
              <Button variant="secondary" onClick={() => setStep('upload')}>
                {t('imports.otherFile')}
              </Button>
              <Button loading={saveMapping.isPending} onClick={() => void toPreview()}>
                {t('imports.toPreview')} <ArrowRight className="size-4" aria-hidden />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {step === 'preview' && job && (
        <div className="space-y-4">
          {preview.isPending ? (
            <Skeleton className="h-40 w-full" />
          ) : preview.isError ? (
            <Alert tone="danger">{getErrorMessage(preview.error)}</Alert>
          ) : (
            preview.data && (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {(
                    [
                      ['valid', preview.data.summary.valid, 'text-success'],
                      ['invalid', preview.data.summary.invalid, 'text-danger'],
                      ['existing', preview.data.summary.existing_contacts, 'text-accent'],
                      ['duplicates', preview.data.summary.duplicates_in_file, 'text-warning'],
                    ] as const
                  ).map(([key, value, tone]) => (
                    <Card key={key} className="p-4">
                      <p className={cn('text-2xl font-semibold tabular-nums', tone)}>{value}</p>
                      <p className="text-[13px] text-fg-muted">{t(`imports.summary.${key}`)}</p>
                    </Card>
                  ))}
                </div>
                <Card>
                  <div className="border-b px-4 py-3 sm:px-5">
                    <p className="font-medium">{t('imports.previewTitle')}</p>
                    <p className="text-[13px] text-fg-muted">{t('imports.previewHint')}</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[13px]">
                      <thead>
                        <tr className="border-b text-xs text-fg-muted">
                          <th className="px-4 py-2 font-medium sm:pl-5">#</th>
                          {Object.entries(mapping)
                            .filter(([, target]) => target)
                            .map(([header, target]) => (
                              <th key={header} className="px-3 py-2 font-medium whitespace-nowrap">
                                {targetLabel(target)}
                              </th>
                            ))}
                          <th className="px-4 py-2 font-medium sm:pr-5">{t('imports.problems')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.data.rows.map((row) => (
                          <tr
                            key={row.row_number}
                            className={cn(
                              'border-b last:border-0',
                              row.errors.length && 'bg-danger-soft/50',
                            )}
                          >
                            <td className="px-4 py-2 text-fg-muted tabular-nums sm:pl-5">
                              {row.row_number}
                            </td>
                            {Object.entries(mapping)
                              .filter(([, target]) => target)
                              .map(([header, target]) => (
                                <td key={header} className="max-w-48 truncate px-3 py-2">
                                  {row.values[target] || '—'}
                                </td>
                              ))}
                            <td className="px-4 py-2 text-xs text-danger sm:pr-5">
                              {row.errors.join(' · ')}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
                <Alert tone="info">
                  {preview.data.mode === 'live'
                    ? t('imports.liveHint', { count: preview.data.summary.total })
                    : t('imports.backgroundHint', { count: preview.data.summary.total })}
                </Alert>
                {run.isError && <Alert tone="danger">{getErrorMessage(run.error)}</Alert>}
                <div className="flex justify-between gap-2">
                  <Button variant="secondary" onClick={() => setStep('map')}>
                    <ArrowLeft className="size-4" aria-hidden /> {t('imports.backToMapping')}
                  </Button>
                  <Button
                    loading={run.isPending}
                    onClick={() => void start()}
                    disabled={!preview.data.summary.valid}
                  >
                    {t('imports.run', { count: preview.data.summary.valid })}
                  </Button>
                </div>
              </>
            )
          )}
        </div>
      )}
    </div>
  );
}
