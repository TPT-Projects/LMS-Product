import { Mic, Square, Trash2 } from 'lucide-react';
import { forwardRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, Button, Textarea } from '@/components/ui';
import { useVoiceRecorder } from '@/hooks/useVoiceRecorder';
import { getErrorMessage } from '@/lib/api/errors';
import { cn } from '@/lib/cn';

import { useAddNote } from '../../api';
import { formatDuration } from '../../format';

interface Props {
  enquiryId: number;
  onDone?: () => void;
  autoFocus?: boolean;
}

/** Text note, voice note, or both. Ctrl/Cmd + Enter saves. */
export const NoteForm = forwardRef<HTMLTextAreaElement, Props>(function NoteForm(
  { enquiryId, onDone, autoFocus },
  ref,
) {
  const { t } = useTranslation();
  const add = useAddNote(enquiryId);
  const voice = useVoiceRecorder();
  const [body, setBody] = useState('');
  const canSave = Boolean(body.trim()) || voice.state === 'recorded';

  const submit = async () => {
    if (!canSave || voice.state === 'recording') return;
    await add.mutateAsync({
      body: body.trim(),
      audio: voice.state === 'recorded' ? voice.blob : null,
      audioDurationSeconds: voice.seconds,
    });
    setBody('');
    voice.reset();
    onDone?.();
  };

  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <Textarea
        ref={ref}
        rows={3}
        value={body}
        maxLength={5000}
        autoFocus={autoFocus}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void submit();
        }}
        placeholder={t('notes.placeholder')}
        aria-label={t('notes.add')}
      />

      {/* Voice note */}
      {voice.state === 'recording' && (
        <div className="flex items-center gap-3 rounded-lg border border-danger/40 bg-danger-soft px-3 py-2">
          <span className="relative flex size-2.5" aria-hidden>
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-danger opacity-60" />
            <span className="relative inline-flex size-2.5 rounded-full bg-danger" />
          </span>
          <span className="text-[13px] font-medium text-danger tabular-nums" role="status">
            {t('voice.recording', { time: formatDuration(voice.seconds) })}
          </span>
          <Button size="sm" variant="secondary" className="ml-auto" onClick={voice.stop}>
            <Square className="size-3 fill-current" aria-hidden /> {t('voice.stop')}
          </Button>
        </div>
      )}
      {voice.state === 'recorded' && voice.url && (
        <div className="flex items-center gap-2 rounded-lg border bg-subtle p-2">
          <audio src={voice.url} controls className="h-9 min-w-0 flex-1" />
          <span className="text-xs text-fg-muted tabular-nums">
            {formatDuration(voice.seconds)}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label={t('voice.discard')}
            onClick={voice.reset}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      )}
      {voice.error && <Alert tone="danger">{t(`voice.errors.${voice.error}`)}</Alert>}
      {add.isError && <Alert tone="danger">{getErrorMessage(add.error)}</Alert>}

      <div className="flex items-center justify-between gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={voice.start}
          disabled={voice.state === 'recording' || voice.state === 'recorded'}
          className={cn(voice.state === 'recording' && 'border-danger text-danger')}
        >
          <Mic className="size-3.5" aria-hidden /> {t('voice.record')}
        </Button>
        <span className="hidden flex-1 text-xs text-fg-subtle sm:inline">
          {t('notes.shortcut')}
        </span>
        <Button
          type="submit"
          size="sm"
          loading={add.isPending}
          disabled={!canSave || voice.state === 'recording'}
        >
          {t('notes.add')}
        </Button>
      </div>
    </form>
  );
});
