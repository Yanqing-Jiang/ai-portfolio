import React, { useEffect, useRef, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { HOMER_THEME } from '../theme';

// AudioClip — a small play/pause bar with a static waveform and progress.
// Used for live TTS responses (data: URL) and pre-recorded lines (static mp3).

const BARS = 48;

export const AudioClip: React.FC<{ src: string; label?: string; autoPlay?: boolean; durationMs?: number | null }> = ({
  src,
  label,
  autoPlay = false,
  durationMs,
}) => {
  const ref = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [dur, setDur] = useState<number | null>(durationMs ? durationMs / 1000 : null);

  useEffect(() => {
    const a = ref.current;
    if (!a) return;
    const onTime = () => a.duration && setProgress(a.currentTime / a.duration);
    const onMeta = () => Number.isFinite(a.duration) && setDur(a.duration);
    const onEnd = () => {
      setPlaying(false);
      setProgress(0);
    };
    a.addEventListener('timeupdate', onTime);
    a.addEventListener('loadedmetadata', onMeta);
    a.addEventListener('ended', onEnd);
    a.addEventListener('pause', () => setPlaying(false));
    a.addEventListener('play', () => setPlaying(true));
    if (autoPlay) a.play().catch(() => undefined);
    return () => {
      a.removeEventListener('timeupdate', onTime);
      a.removeEventListener('loadedmetadata', onMeta);
      a.removeEventListener('ended', onEnd);
    };
  }, [autoPlay, src]);

  const toggle = () => {
    const a = ref.current;
    if (!a) return;
    if (a.paused) a.play().catch(() => undefined);
    else a.pause();
  };

  return (
    <div className="flex items-center gap-3">
      <audio ref={ref} src={src} preload="metadata" />
      <button
        type="button"
        onClick={toggle}
        aria-label={playing ? 'Pause' : 'Play'}
        className="w-9 h-9 rounded-full grid place-items-center shrink-0"
        style={{ background: HOMER_THEME.accent, color: '#1a1611' }}
      >
        {playing ? <Pause size={14} /> : <Play size={14} className="ml-0.5" />}
      </button>
      <div className="flex-1 min-w-0">
        <div className="flex items-end gap-[2px] h-6" aria-hidden>
          {Array.from({ length: BARS }, (_, i) => {
            const h = 4 + Math.abs(Math.sin(i * 0.6) * Math.cos(i * 0.21)) * 18;
            const lit = i / BARS <= progress;
            return <i key={i} className="block w-[3px] rounded-sm" style={{ height: h, background: HOMER_THEME.accent, opacity: lit ? 0.95 : 0.35 }} />;
          })}
        </div>
        {label && (
          <div className="text-[11px] mt-1 truncate" style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}>
            “{label}”
          </div>
        )}
      </div>
      <span className="text-[11px] tabular-nums shrink-0" style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}>
        {dur ? `${dur.toFixed(1)} s` : ''}
      </span>
    </div>
  );
};

export default AudioClip;
