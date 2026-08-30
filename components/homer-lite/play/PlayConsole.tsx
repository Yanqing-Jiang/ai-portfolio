import React, { useEffect, useRef, useState } from 'react';
import { Loader2, Send } from 'lucide-react';
import { HOMER_THEME } from '../theme';
import { configService } from '../../../services/config';
import type { PlayEnvelope, PlayError, PlayRequest, PlayTab, VoiceRecording } from './types';
import { AudioClip } from './AudioClip';

// PlayConsole — the shared "try it" chatbox embedded in every Architecture tab.
//
// One-turn interactions (Yanqing, 2026-08-29): each Send is independent, the
// transcript just stacks. No history is sent to the server and nothing is
// persisted client-side beyond component state.
//
// Visual rule: the box must NOT blend into the dark theme — cream surface,
// gold border, dark Send button — so a visitor sees "you can type here" at a
// glance without reading the copy.

export interface PlayTurn<T = unknown> {
  id: string;
  message: string;
  action: string;
  state: 'loading' | 'ok' | 'error';
  response?: PlayEnvelope<T>;
  error?: { code: string; message: string; retryAfter?: number };
}

export interface PlayConsoleProps<T = unknown> {
  tab: PlayTab;
  /** Eyebrow under the tab headline, e.g. "Search it, or feed it a sentence". */
  label: string;
  placeholder: string;
  suggestions: readonly string[];
  /** Pick the action (and optional input) for a given message. */
  route: (message: string) => { action: string; input?: Record<string, unknown> };
  /** Render the `data` of a successful envelope. */
  render: (envelope: PlayEnvelope<T>) => React.ReactNode;
  maxLength?: number;
  /** URL of a static manifest of pre-recorded lines; rendered as click-to-play chips (no API call). */
  recordingsManifest?: string;
}

const CREAM = '#f3ecdd';
const INK = '#1a1611';
const INK_MUTED = '#6b6357';

const getApiBase = () => {
  if (typeof window === 'undefined') return configService.getBackendUrl();
  const host = window.location.hostname;
  const bffHosted = host === 'yanqing.app' || host.endsWith('.yanqing.app') || host.endsWith('.pages.dev');
  return bffHosted ? '' : configService.getBackendUrl();
};

const newId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `t_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

const formatRetry = (seconds?: number) => {
  if (!seconds || seconds < 1) return 'in a moment';
  const minutes = Math.ceil(seconds / 60);
  return minutes <= 1 ? 'in about a minute' : `in about ${minutes} minutes`;
};

export function PlayConsole<T = unknown>({
  tab,
  label,
  placeholder,
  suggestions,
  route,
  render,
  maxLength = 500,
  recordingsManifest,
}: PlayConsoleProps<T>) {
  const [value, setValue] = useState('');
  const [turns, setTurns] = useState<PlayTurn<T>[]>([]);
  const [remaining, setRemaining] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const busy = turns.some((t) => t.state === 'loading');
  const [recordings, setRecordings] = useState<VoiceRecording[]>([]);
  const [activeRecording, setActiveRecording] = useState<VoiceRecording | null>(null);

  useEffect(() => {
    if (!recordingsManifest) return;
    let cancelled = false;
    fetch(recordingsManifest)
      .then((r) => (r.ok ? r.json() : []))
      .then((list: VoiceRecording[]) => {
        if (!cancelled && Array.isArray(list)) setRecordings(list);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [recordingsManifest]);

  const send = async (raw: string) => {
    const message = raw.trim().slice(0, maxLength);
    if (!message || busy) return;
    const { action, input } = route(message);
    const id = newId();
    setTurns((prev) => [{ id, message, action, state: 'loading' }, ...prev]);
    setValue('');

    const body: PlayRequest = { version: '1', tab, action, message, input, client_turn_id: id };
    try {
      const res = await fetch(`${getApiBase()}/api/homer/play`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const json = (await res.json().catch(() => null)) as PlayEnvelope<T> | PlayError | null;
      if (!res.ok || !json || json.ok === false) {
        const err = json && json.ok === false ? json.error : null;
        const retryAfter = Number(res.headers.get('retry-after')) || undefined;
        setTurns((prev) =>
          prev.map((t) =>
            t.id === id
              ? {
                  ...t,
                  state: 'error',
                  error: {
                    code: err?.code ?? (res.status === 429 ? 'rate_limited' : `http_${res.status}`),
                    message:
                      res.status === 429
                        ? `You've used this hour's tries. Come back ${formatRetry(retryAfter)}.`
                        : err?.message ?? `Homer didn't answer (HTTP ${res.status}).`,
                    retryAfter,
                  },
                }
              : t,
          ),
        );
        if (res.status === 429) setRemaining(0);
        return;
      }
      if (json.limits) setRemaining(json.limits.remaining_this_hour);
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, state: 'ok', response: json } : t)));
    } catch (e) {
      setTurns((prev) =>
        prev.map((t) =>
          t.id === id
            ? { ...t, state: 'error', error: { code: 'network', message: e instanceof DOMException && e.name === 'AbortError' ? 'Cancelled.' : "Homer didn't answer — the Mac mini may be unreachable. Try again in a minute." } }
            : t,
        ),
      );
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div>
        <div
          className="text-[10px] tracking-[0.22em] uppercase"
          style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
        >
          Try it · {label}
        </div>
        <div className="text-[11px] mt-1" style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}>
          {remaining === null ? (
            <>10 tries an hour · read-only · nothing you type is stored</>
          ) : (
            <>
              <span style={{ color: HOMER_THEME.text }}>{remaining}</span> of 10 tries left this hour · read-only · nothing you type is stored
            </>
          )}
        </div>
      </div>

      {recordings.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="text-[10px] tracking-[0.18em] uppercase" style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.textMuted }}>
            Listen first — recorded lines, no try spent
          </div>
          <div className="flex flex-wrap gap-2">
            {recordings.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setActiveRecording(r)}
                className="px-2.5 py-1.5 rounded-md text-[12px] text-left transition-colors hover:bg-white/[0.04]"
                style={{
                  fontFamily: HOMER_THEME.fontMono,
                  color: activeRecording?.id === r.id ? HOMER_THEME.text : HOMER_THEME.accent,
                  border: `1px solid ${activeRecording?.id === r.id ? HOMER_THEME.accent : 'rgba(212, 160, 86, 0.45)'}`,
                  background: activeRecording?.id === r.id ? HOMER_THEME.accentSoft : 'transparent',
                }}
              >
                ▶ {r.text.length > 48 ? `${r.text.slice(0, 46)}…` : r.text}
              </button>
            ))}
          </div>
          {activeRecording && (
            <div className="rounded-lg px-3.5 py-3" style={{ background: HOMER_THEME.bg, border: `1px solid ${HOMER_THEME.divider}` }}>
              <AudioClip key={activeRecording.id} src={activeRecording.file} label={activeRecording.text} autoPlay durationMs={activeRecording.duration_ms} />
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => send(s)}
            disabled={busy}
            className="px-2.5 py-1.5 rounded-md text-[12px] text-left transition-colors hover:bg-white/[0.04] disabled:opacity-50"
            style={{
              fontFamily: HOMER_THEME.fontMono,
              color: HOMER_THEME.accent,
              border: '1px dashed rgba(212, 160, 86, 0.45)',
            }}
          >
            {s}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(value);
        }}
        className="flex items-center gap-2.5 rounded-[10px] pl-4 pr-2 py-2"
        style={{
          background: CREAM,
          border: `2px solid ${HOMER_THEME.accent}`,
          boxShadow: `0 0 0 4px rgba(212,160,86,0.12), 0 8px 30px rgba(0,0,0,0.45)`,
        }}
      >
        <span style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent, fontWeight: 500 }}>›</span>
        <input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          maxLength={maxLength}
          autoComplete="off"
          aria-label={`Ask Homer (${tab})`}
          className="flex-1 min-w-0 bg-transparent outline-none text-[15px]"
          style={{ color: INK, caretColor: HOMER_THEME.accent }}
        />
        <button
          type="submit"
          disabled={busy || !value.trim()}
          className="inline-flex items-center gap-1.5 rounded-[7px] px-3.5 py-2.5 text-[12px] uppercase tracking-[0.08em] disabled:opacity-60"
          style={{ background: INK, color: CREAM, fontFamily: HOMER_THEME.fontMono }}
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
          Send
        </button>
        <style>{`input::placeholder{color:${INK_MUTED}}`}</style>
      </form>

      {turns.length > 0 && (
        <div className="flex flex-col gap-2.5 mt-1">
          {turns.map((t) => (
            <div key={t.id} className="flex flex-col gap-2">
              <Turn who="you">
                <div
                  className="rounded-lg px-3.5 py-2.5 text-sm"
                  style={{ border: `1px dashed ${HOMER_THEME.divider}`, color: HOMER_THEME.text }}
                >
                  {t.message}
                </div>
              </Turn>
              <Turn who="homer">
                <div
                  className="rounded-lg px-3.5 py-3 text-sm"
                  style={{ background: HOMER_THEME.bg, border: `1px solid ${HOMER_THEME.divider}`, color: HOMER_THEME.text }}
                >
                  {t.state === 'loading' && (
                    <span className="inline-flex items-center gap-2" style={{ color: HOMER_THEME.textMuted }}>
                      <Loader2 size={13} className="animate-spin" /> thinking…
                    </span>
                  )}
                  {t.state === 'error' && <span style={{ color: '#f5cf94' }}>{t.error?.message}</span>}
                  {t.state === 'ok' && t.response && (
                    <>
                      {t.response.degraded?.active && (
                        <div
                          className="inline-block mb-2 px-2 py-0.5 rounded text-[10px] uppercase tracking-[0.14em]"
                          style={{
                            fontFamily: HOMER_THEME.fontMono,
                            color: '#c4b5fd',
                            border: '1px solid rgba(196,181,253,0.4)',
                          }}
                        >
                          replay · {t.response.degraded.reason.replace(/_/g, ' ')}
                        </div>
                      )}
                      {render(t.response)}
                    </>
                  )}
                </div>
              </Turn>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const Turn: React.FC<{ who: 'you' | 'homer'; children: React.ReactNode }> = ({ who, children }) => (
  <div className="grid gap-3" style={{ gridTemplateColumns: '56px 1fr' }}>
    <span
      className="text-[10px] tracking-[0.18em] uppercase pt-2"
      style={{ fontFamily: HOMER_THEME.fontMono, color: who === 'homer' ? HOMER_THEME.accent : HOMER_THEME.textMuted }}
    >
      {who}
    </span>
    <div className="min-w-0">{children}</div>
  </div>
);

export default PlayConsole;
