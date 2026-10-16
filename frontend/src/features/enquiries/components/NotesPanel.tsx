import { StickyNote } from 'lucide-react';
import { forwardRef } from 'react';
import { useTranslation } from 'react-i18next';

import { Avatar, EmptyState, Skeleton } from '@/components/ui';
import { useDateFormat } from '@/features/auth/useAuth';

import { useNotes } from '../api';
import { NoteForm } from './forms/NoteForm';
import { VoiceNotePlayer } from './VoiceNotePlayer';

interface Props {
  enquiryId: number;
  canEdit: boolean;
}

export const NotesPanel = forwardRef<HTMLTextAreaElement, Props>(function NotesPanel(
  { enquiryId, canEdit },
  ref,
) {
  const { t } = useTranslation();
  const format = useDateFormat();
  const notes = useNotes(enquiryId);

  return (
    <div className="space-y-4">
      {canEdit && <NoteForm ref={ref} enquiryId={enquiryId} />}
      {notes.isPending ? (
        <Skeleton className="h-16 w-full" />
      ) : !notes.data?.length ? (
        <EmptyState icon={StickyNote} title={t('notes.empty')} className="py-8" />
      ) : (
        <ul className="space-y-3">
          {notes.data.map((note) => (
            <li key={note.id} className="space-y-2 rounded-lg border p-3">
              <div className="flex items-center gap-2 text-xs text-fg-muted">
                <Avatar name={note.author?.full_name ?? '?'} className="size-5 text-[9px]" />
                <span className="font-medium text-fg">
                  {note.author?.full_name ?? t('timeline.system')}
                </span>
                <span className="tabular-nums">{format.dateTime(note.created_at)}</span>
              </div>
              {note.has_audio && (
                <VoiceNotePlayer
                  enquiryId={enquiryId}
                  noteId={note.id}
                  duration={note.audio_duration_seconds}
                />
              )}
              {note.body && (
                <p className="text-[13px] break-words whitespace-pre-line">{note.body}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
});
