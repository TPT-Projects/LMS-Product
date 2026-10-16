import { Download, FileText, Paperclip, Upload } from 'lucide-react';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Button, EmptyState, Skeleton } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';
import { getErrorMessage } from '@/lib/api/errors';

import { downloadAttachment, useAttachments, useUploadAttachment } from '../api';
import { formatBytes } from '../format';

const ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp,.txt,.csv,.doc,.docx,.xls,.xlsx';
const MAX_BYTES = 10 * 1024 * 1024;

export function AttachmentsPanel({ enquiryId, canEdit }: { enquiryId: number; canEdit: boolean }) {
  const { t } = useTranslation();
  const format = useDateFormat();
  const input = useRef<HTMLInputElement>(null);
  const attachments = useAttachments(enquiryId);
  const upload = useUploadAttachment(enquiryId);
  const [error, setError] = useState<string | null>(null);

  const onFiles = async (files: FileList | null) => {
    setError(null);
    for (const file of Array.from(files ?? [])) {
      if (file.size > MAX_BYTES) {
        setError(t('attachments.tooBig', { name: file.name }));
        continue;
      }
      try {
        await upload.mutateAsync(file);
      } catch (err) {
        setError(getErrorMessage(err));
      }
    }
    if (input.current) input.current.value = '';
  };

  return (
    <div className="space-y-4">
      {canEdit && (
        <div
          className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-5 text-center"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            void onFiles(e.dataTransfer.files);
          }}
        >
          <Upload className="size-5 text-fg-subtle" aria-hidden />
          <p className="text-[13px] text-fg-muted">{t('attachments.drop')}</p>
          <input
            ref={input}
            type="file"
            multiple
            accept={ACCEPT}
            className="sr-only"
            id={`upload-${enquiryId}`}
            onChange={(e) => void onFiles(e.target.files)}
          />
          <Button
            variant="secondary"
            size="sm"
            loading={upload.isPending}
            onClick={() => input.current?.click()}
          >
            <Paperclip className="size-3.5" aria-hidden /> {t('attachments.choose')}
          </Button>
          <p className="text-xs text-fg-subtle">{t('attachments.limits')}</p>
        </div>
      )}
      {error && <Alert tone="danger">{error}</Alert>}
      {attachments.isPending ? (
        <Skeleton className="h-12 w-full" />
      ) : !attachments.data?.length ? (
        <EmptyState icon={Paperclip} title={t('attachments.empty')} className="py-8" />
      ) : (
        <ul className="divide-y rounded-lg border">
          {attachments.data.map((a) => (
            <li key={a.id} className="flex items-center gap-3 p-3">
              <FileText className="size-5 shrink-0 text-fg-subtle" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium">{a.file_name}</p>
                <p className="text-xs text-fg-muted">
                  {formatBytes(a.size)} · {a.uploaded_by?.full_name} · {format.date(a.created_at)}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t('attachments.download', { name: a.file_name })}
                onClick={() =>
                  void downloadAttachment(enquiryId, a).catch((e) => setError(getErrorMessage(e)))
                }
              >
                <Download className="size-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
