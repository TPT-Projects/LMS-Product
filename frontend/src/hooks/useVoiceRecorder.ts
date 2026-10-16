import { useCallback, useEffect, useRef, useState } from 'react';

export type RecorderState = 'idle' | 'recording' | 'recorded' | 'error';
export type RecorderError = 'unsupported' | 'denied' | 'failed';

const MAX_SECONDS = 10 * 60; // the API accepts up to 10 minutes

/** First audio format this browser can record (Safari: mp4, others: webm/opus). */
function pickMimeType(): string | undefined {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
  if (typeof MediaRecorder === 'undefined') return undefined;
  return candidates.find((type) => MediaRecorder.isTypeSupported(type));
}

/** Record a voice note with the microphone. Stops on its own after 10 minutes. */
export function useVoiceRecorder() {
  const [state, setState] = useState<RecorderState>('idle');
  const [error, setError] = useState<RecorderError | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [url, setUrl] = useState<string | null>(null);

  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number | null>(null);
  const startedAt = useRef(0);

  const stopTracks = () => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    if (timer.current) window.clearInterval(timer.current);
    timer.current = null;
  };

  const stop = useCallback(() => {
    if (recorder.current?.state === 'recording') recorder.current.stop();
  }, []);

  const start = useCallback(async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('unsupported');
      setState('error');
      return;
    }
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError('denied');
      setState('error');
      return;
    }
    const mimeType = pickMimeType();
    const rec = new MediaRecorder(stream.current, mimeType ? { mimeType } : undefined);
    chunks.current = [];
    rec.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.current.push(event.data);
    };
    rec.onerror = () => {
      stopTracks();
      setError('failed');
      setState('error');
    };
    rec.onstop = () => {
      stopTracks();
      const recorded = new Blob(chunks.current, { type: rec.mimeType || mimeType || 'audio/webm' });
      setSeconds(Math.max(1, Math.round((Date.now() - startedAt.current) / 1000)));
      setBlob(recorded);
      setUrl(URL.createObjectURL(recorded));
      setState('recorded');
    };
    recorder.current = rec;
    startedAt.current = Date.now();
    setSeconds(0);
    rec.start(1000);
    setState('recording');
    timer.current = window.setInterval(() => {
      const elapsed = Math.round((Date.now() - startedAt.current) / 1000);
      setSeconds(elapsed);
      if (elapsed >= MAX_SECONDS) rec.stop();
    }, 500);
  }, []);

  const reset = useCallback(() => {
    if (recorder.current?.state === 'recording') {
      recorder.current.onstop = null;
      recorder.current.stop();
    }
    stopTracks();
    setUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return null;
    });
    setBlob(null);
    setSeconds(0);
    setError(null);
    setState('idle');
  }, []);

  // Release the microphone and the preview URL when the component goes away.
  useEffect(
    () => () => {
      if (recorder.current?.state === 'recording') {
        recorder.current.onstop = null;
        recorder.current.stop();
      }
      stream.current?.getTracks().forEach((track) => track.stop());
      if (timer.current) window.clearInterval(timer.current);
    },
    [],
  );
  useEffect(() => () => void (url && URL.revokeObjectURL(url)), [url]);

  return { state, error, seconds, blob, url, start, stop, reset, maxSeconds: MAX_SECONDS };
}
