import { ArrowLeft, Download, FileSpreadsheet } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { Alert, Button, Card, EmptyState, Skeleton } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';
import { paths } from '@/routes/paths';

import { downloadFile, RUNNING, useImport } from '../api';
import { ImportStatusBadge } from '../components/ImportStatusBadge';

/** Import log for one file: progress, counts and the failed rows. */
export default function ImportDetailPage() {
  const { t } = useTranslation();
  const format = useDateFormat();
  const id = Number(useParams().id);
  const job = useImport(id);

  if (job.isPending) return <Skeleton className="mx-auto h-64 max-w-4xl" />;
  if (job.isError || !job.data) {
    return (
      <EmptyState
        icon={FileSpreadsheet}
        title={t('imports.notFound')}
        description={getErrorMessage(job.error)}
        className="py-24"
      />
    );
  }

  const j = job.data;
  const running = RUNNING.includes(j.status);
  const percent = j.row_count ? Math.round((j.processed_count / j.row_count) * 100) : 0;

  return (
    <div className="mx-auto max-w-4xl">
      <Link
        to={paths.imports}
        className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="size-4" aria-hidden /> {t('imports.back')}
      </Link>
      <PageHeader
        title={j.original_name}
        description={t('imports.detailMeta', {
          rows: j.row_count,
          by: j.created_by ?? '—',
          date: format.dateTime(j.created_at),
        })}
        actions={<ImportStatusBadge status={j.status} />}
      />

      {running && (
        <Card className="mb-4 p-4">
          <div className="mb-2 flex justify-between text-[13px]">
            <span>{j.status === 'queued' ? t('imports.queued') : t('imports.running')}</span>
            <span className="text-fg-muted tabular-nums">
              {j.processed_count} / {j.row_count}
            </span>
          </div>
          <div
            className="h-2 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full rounded-full bg-accent transition-all"
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-fg-muted">{t('imports.keepWorking')}</p>
        </Card>
      )}
      {j.status === 'failed' && (
        <Alert tone="danger" className="mb-4">
          {j.error || t('imports.failedHint')}
        </Alert>
      )}

      <div className="mb-4 grid grid-cols-3 gap-3">
        {(
          [
            ['created', j.created_count, 'text-success'],
            ['linked', j.linked_count, 'text-accent'],
            ['failed', j.failed_count, 'text-danger'],
          ] as const
        ).map(([key, value, tone]) => (
          <Card key={key} className="p-4">
            <p className={cn('text-2xl font-semibold tabular-nums', tone)}>{value}</p>
            <p className="text-[13px] text-fg-muted">{t(`imports.counts.${key}`)}</p>
          </Card>
        ))}
      </div>

      {j.failed_count > 0 && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3 sm:px-5">
            <div>
              <p className="font-medium">{t('imports.failedRows')}</p>
              <p className="text-[13px] text-fg-muted">{t('imports.failedRowsHint')}</p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() =>
                void downloadFile(
                  `/imports/${j.id}/failed-report`,
                  `import-${j.id}-failed-rows.csv`,
                )
              }
            >
              <Download className="size-3.5" aria-hidden /> {t('imports.downloadFailed')}
            </Button>
          </div>
          <ul className="divide-y">
            {j.failed_rows.map((row) => (
              <li key={row.row_number} className="px-4 py-2.5 text-[13px] sm:px-5">
                <span className="mr-2 text-fg-muted tabular-nums">
                  {t('imports.rowNumber', { n: row.row_number })}
                </span>
                <span className="text-danger">{row.errors.join(' · ')}</span>
              </li>
            ))}
          </ul>
          {j.failed_count > j.failed_rows.length && (
            <p className="border-t px-4 py-2.5 text-xs text-fg-muted sm:px-5">
              {t('imports.moreFailed', { count: j.failed_count - j.failed_rows.length })}
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
