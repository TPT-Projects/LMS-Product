import { Loader2, Play } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getErrorMessage } from '@/lib/api/errors';

import { fetchNoteAudio } from '../api';
import { formatDuration } from '../format';

/** Loads a private voice note only when the user presses play. */
export function VoiceNotePlayer({
  enquiryId,
  noteId,
  duration,
}: {
  enquiryId: number;
  noteId: number;
  duration: number | null;
}) {
  const { t } = useTranslation();
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => () => void (url && URL.revokeObjectURL(url)), [url]);

  if (url) {
    return <audio src={url} controls autoPlay className="h-9 w-full max-w-sm" />;
  }
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={async () => {
          setLoading(true);
          setError(null);
          try {
            setUrl(await fetchNoteAudio(enquiryId, noteId));
          } catch (err) {
            setError(getErrorMessage(err));
          } finally {
            setLoading(false);
          }
        }}
        className="inline-flex items-center gap-2 rounded-full border bg-subtle px-3 py-1.5 text-[13px] font-medium hover:bg-muted"
        aria-label={t('voice.play')}
      >
        {loading ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : (
          <Play className="size-3.5 fill-current" aria-hidden />
        )}
        {t('voice.note')}
        {duration ? (
          <span className="text-fg-muted tabular-nums">{formatDuration(duration)}</span>
        ) : null}
      </button>
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}
