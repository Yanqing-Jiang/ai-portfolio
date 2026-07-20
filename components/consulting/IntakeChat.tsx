import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, Send, X } from 'lucide-react';
import { configService } from '@/services/config';

/*
 * AI Brief Agent — the /consult intake chat (Phase 2).
 * A guided interviewer that builds a LIVE, EDITABLE structured brief while it
 * asks, then routes into the booking flow with the reviewed brief attached.
 *
 * Server-authoritative: the transcript/turn-count/running-brief live in a signed
 * `session` token the server returns each turn; the client sends only the next
 * user reply plus that token. On any endpoint failure it auto-falls-back to the
 * guided form (carrying the partial brief).
 */

type Path = 'business' | 'individual';

export interface Brief {
    desired_outcome?: string;
    current_workflow?: string;
    people_and_frequency?: string;
    systems_and_data?: string;
    success_metric?: string;
    constraints?: string;
    timing_and_stakeholders?: string;
    open_questions?: string[];
}

interface TurnResult {
    reply: string;
    brief: Brief;
    quick_replies: string[];
    complete: boolean;
    recommended_next_step: string; // 'fit' | '30' | '60' | ''
    session?: string;
    capped?: boolean;
}

interface Msg { role: 'user' | 'assistant'; content: string }

const STR_FIELDS: Array<{ key: keyof Brief; label: string }> = [
    { key: 'desired_outcome', label: 'Desired outcome' },
    { key: 'current_workflow', label: 'Current workflow' },
    { key: 'people_and_frequency', label: 'People & frequency' },
    { key: 'systems_and_data', label: 'Systems & data' },
    { key: 'success_metric', label: 'Success metric' },
    { key: 'constraints', label: 'Constraints' },
    { key: 'timing_and_stakeholders', label: 'Timing & stakeholders' },
];

const seedFor = (path: Path) =>
    path === 'business'
        ? 'I want to improve a business workflow.'
        : 'I want to build a personal system.';

export const briefToNotes = (path: Path, brief: Brief): string => {
    const lines: string[] = [
        `Path: ${path === 'business' ? 'Business workflow' : 'Personal system'}`,
        '',
        'AI intake brief:',
    ];
    for (const f of STR_FIELDS) {
        const v = (brief[f.key] as string | undefined)?.trim();
        if (v) lines.push(`- ${f.label}: ${v}`);
    }
    if (brief.open_questions && brief.open_questions.length) {
        lines.push('- Open questions: ' + brief.open_questions.filter(Boolean).join('; '));
    }
    return lines.join('\n').slice(0, 1990);
};

const cleanBrief = (b: Brief): Brief => {
    const out: Brief = {};
    for (const f of STR_FIELDS) {
        const v = (b[f.key] as string | undefined)?.trim();
        if (v) (out as Record<string, unknown>)[f.key] = v;
    }
    const oq = (b.open_questions || []).map((q) => q.trim()).filter(Boolean);
    if (oq.length) out.open_questions = oq;
    return out;
};

const briefCount = (b: Brief): number =>
    STR_FIELDS.filter((f) => (b[f.key] as string | undefined)?.trim()).length +
    ((b.open_questions && b.open_questions.filter(Boolean).length) ? 1 : 0);

// Strict client-side validation of a turn response — mirrors the server's
// _validate_output. THROWS on a malformed/type-violating turn (which callTurn
// catches and turns into the guided-form fallback) rather than silently
// defaulting bad values into React state.
const coerceTurn = (data: unknown): TurnResult => {
    if (!data || typeof data !== 'object') throw new Error('intake: turn not an object');
    const d = data as Record<string, unknown>;
    if (typeof d.reply !== 'string') throw new Error('intake: reply must be a string');
    if (typeof d.complete !== 'boolean') throw new Error('intake: complete must be a boolean');
    // Every real server turn returns a signed session; its absence means a broken
    // response we must not continue from.
    if (typeof d.session !== 'string' || !d.session) throw new Error('intake: missing session');
    if (d.brief !== undefined && (typeof d.brief !== 'object' || d.brief === null || Array.isArray(d.brief))) {
        throw new Error('intake: brief must be an object');
    }
    const rawBrief = (d.brief as Record<string, unknown>) ?? {};
    const brief: Brief = {};
    for (const f of STR_FIELDS) {
        const v = rawBrief[f.key as string];
        if (v === undefined || v === null || v === '') continue;
        if (typeof v !== 'string') throw new Error(`intake: brief.${String(f.key)} must be a string`);
        if (v.trim()) (brief as Record<string, unknown>)[f.key] = v;
    }
    if (rawBrief.open_questions !== undefined && rawBrief.open_questions !== null) {
        if (!Array.isArray(rawBrief.open_questions)) throw new Error('intake: open_questions must be an array');
        const oq = (rawBrief.open_questions as unknown[]).map((q) => {
            if (typeof q !== 'string') throw new Error('intake: open_questions items must be strings');
            return q;
        }).filter((q) => q.trim());
        if (oq.length) brief.open_questions = oq;
    }
    // quick_replies: strict — every item must be a string (no silent filtering).
    let quick: string[] = [];
    if (d.quick_replies !== undefined && d.quick_replies !== null) {
        if (!Array.isArray(d.quick_replies)) throw new Error('intake: quick_replies must be an array');
        quick = (d.quick_replies as unknown[]).map((q) => {
            if (typeof q !== 'string') throw new Error('intake: quick_replies items must be strings');
            return q;
        }).slice(0, 3);
    }
    // recommended_next_step: strict — server contract requires a string ('' when unsure).
    if (typeof d.recommended_next_step !== 'string') {
        throw new Error('intake: recommended_next_step must be a string');
    }
    return {
        reply: d.reply,
        brief,
        quick_replies: quick,
        complete: d.complete,
        recommended_next_step: d.recommended_next_step,
        session: d.session,
        capped: d.capped === true,
    };
};

interface IntakeChatProps {
    path: Path;
    onComplete: (notes: string, recommendedNextStep: string, brief: Brief, session: string | null) => void;
    onFallback: (partialBrief?: Brief) => void;
}

export const IntakeChat: React.FC<IntakeChatProps> = ({ path, onComplete, onFallback }) => {
    const [display, setDisplay] = useState<Msg[]>([]);
    const [session, setSession] = useState<string | null>(null);
    // `brief` is the editable source of truth (display + notes + persist).
    const [brief, setBrief] = useState<Brief>({});
    const [touched, setTouched] = useState<Set<string>>(new Set());
    const [changed, setChanged] = useState<Set<string>>(new Set());
    const [quickReplies, setQuickReplies] = useState<string[]>([]);
    const [complete, setComplete] = useState(false);
    const [nextStep, setNextStep] = useState('');
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);
    const [briefOpen, setBriefOpen] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const startedRef = useRef(false);
    const briefRef = useRef<Brief>({});
    briefRef.current = brief;
    // Mirror `touched` in a ref so an in-flight merge reads the CURRENT edit set,
    // not the stale closure captured when the request started (edit-clobber race).
    const touchedRef = useRef<Set<string>>(touched);
    touchedRef.current = touched;

    const backendUrl = useMemo(() => configService.getBackendUrl().replace(/\/$/, ''), []);

    const mergeServerBrief = (server: Brief) => {
        setBrief((prev) => {
            // Read the live edit set from the ref — a field the user touched while
            // this request was in flight must not be overwritten by the merge.
            const t = touchedRef.current;
            const next: Brief = { ...prev };
            const flash = new Set<string>();
            for (const f of STR_FIELDS) {
                if (t.has(f.key as string)) continue; // never clobber user edits
                const b = (server[f.key] as string | undefined) || '';
                const a = (prev[f.key] as string | undefined) || '';
                if (b && a !== b) { (next as Record<string, unknown>)[f.key] = b; flash.add(f.key as string); }
            }
            if (!t.has('open_questions') && server.open_questions && server.open_questions.length) {
                next.open_questions = server.open_questions;
                flash.add('open_questions');
            }
            if (flash.size) { setChanged(flash); setTimeout(() => setChanged(new Set()), 600); }
            return next;
        });
    };

    const callTurn = async (message: string, sess: string | null) => {
        setLoading(true);
        setError(false);
        try {
            const res = await fetch(`${backendUrl}/api/intake/message`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path, session: sess, message }),
            });
            if (!res.ok) throw new Error(String(res.status));
            const data = coerceTurn(await res.json());
            setDisplay((d) => [...d, { role: 'assistant', content: data.reply }]);
            setSession(data.session ?? null);
            mergeServerBrief(data.brief);
            setQuickReplies(data.quick_replies);
            setNextStep(data.recommended_next_step);
            setComplete(data.complete);
            // Turn cap reached but the brief is too thin to book on: hand off to the
            // guided form (carrying the partial brief) instead of a dead-end chat.
            if (data.capped && !data.complete) {
                onFallback(cleanBrief(briefRef.current));
            }
        } catch {
            setError(true);
            // Progressive enhancement: auto-fall-back to the form, carrying the
            // partial brief captured so far. A visible notice shows briefly.
            onFallback(cleanBrief(briefRef.current));
        } finally {
            setLoading(false);
        }
    };

    // Kick off with a hidden seed so the agent asks the first question.
    useEffect(() => {
        if (startedRef.current) return;
        startedRef.current = true;
        callTurn(seedFor(path), null);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [path]);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }, [display, loading]);

    // Escape closes the mobile sheet.
    useEffect(() => {
        if (!briefOpen) return;
        const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setBriefOpen(false); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [briefOpen]);

    const send = (text: string) => {
        const t = text.trim();
        if (!t || loading) return;
        setDisplay((d) => [...d, { role: 'user', content: t }]);
        setInput('');
        setQuickReplies([]);
        callTurn(t, session);
    };

    const editField = (key: keyof Brief, value: string) => {
        setTouched((s) => new Set(s).add(key as string));
        setBrief((b) => ({ ...b, [key]: value }));
    };
    const removeField = (key: keyof Brief) => {
        setTouched((s) => new Set(s).add(key as string));
        setBrief((b) => { const n = { ...b }; delete n[key]; return n; });
    };
    const editQuestions = (text: string) => {
        setTouched((s) => new Set(s).add('open_questions'));
        setBrief((b) => ({ ...b, open_questions: text.split('\n').map((l) => l.trim()).filter(Boolean) }));
    };

    const count = briefCount(brief);

    const BriefPane = (
        <div className="space-y-4">
            <div className="flex items-baseline justify-between">
                <h3 className="text-[13px] font-semibold uppercase tracking-[0.18em] text-[#A8A096]">Your project brief</h3>
                <span className="text-[12px] text-[#A8A096]">{count} {count === 1 ? 'item' : 'items'}</span>
            </div>
            <p className="text-[12px] text-[#A8A096]">Edit any field before booking. Yanqing receives the approved brief — not the raw chat.</p>
            <div className="space-y-3">
                {STR_FIELDS.map((f) => {
                    const v = (brief[f.key] as string | undefined) || '';
                    const suggested = !!v && !touched.has(f.key as string);
                    const isChanged = changed.has(f.key as string);
                    return (
                        <div key={f.key as string} className={`border-l-2 pl-3 transition-colors duration-500 ${isChanged ? 'border-[#F04A32]' : 'border-[#37332E]'}`}>
                            <div className="flex items-center justify-between">
                                <label className="text-[11px] uppercase tracking-[0.14em] text-[#A8A096]">{f.label}</label>
                                {v && (
                                    <button onClick={() => removeField(f.key)} aria-label={`Remove ${f.label}`} className="text-[#A8A096] hover:text-[#F04A32]">
                                        <X className="h-3.5 w-3.5" />
                                    </button>
                                )}
                            </div>
                            <textarea
                                value={v}
                                onChange={(e) => editField(f.key, e.target.value)}
                                rows={v.length > 60 ? 2 : 1}
                                placeholder="—"
                                className="mt-1 w-full resize-none rounded-[4px] border border-transparent bg-transparent text-[14px] leading-[1.45] text-[#F1EADF] outline-none placeholder-[#565049] focus:border-[#37332E] focus:bg-[#12110F] focus:px-2 focus:py-1"
                            />
                            {suggested && <p className="text-[10px] italic text-[#A8A096]">Suggested by the agent — edit to confirm.</p>}
                        </div>
                    );
                })}
                <div className="border-l-2 border-[#37332E] pl-3">
                    <label className="text-[11px] uppercase tracking-[0.14em] text-[#A8A096]">Open questions (one per line)</label>
                    <textarea
                        value={(brief.open_questions || []).join('\n')}
                        onChange={(e) => editQuestions(e.target.value)}
                        rows={2}
                        placeholder="—"
                        className="mt-1 w-full resize-none rounded-[4px] border border-transparent bg-transparent text-[14px] leading-[1.45] text-[#F1EADF] outline-none placeholder-[#565049] focus:border-[#37332E] focus:bg-[#12110F] focus:px-2 focus:py-1"
                    />
                </div>
            </div>
        </div>
    );

    return (
        <div className="grid gap-8 lg:grid-cols-[7fr_5fr]">
            {/* Conversation */}
            <div className="flex min-h-[520px] flex-col rounded-[6px] border border-[#37332E] bg-[#191816]/40">
                <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto p-5" style={{ maxHeight: 560 }}>
                    {display.map((m, i) => (
                        <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                            <div className={`max-w-[85%] rounded-[6px] px-4 py-3 text-[15px] leading-[1.5] ${
                                m.role === 'user'
                                    ? 'bg-[#F04A32] text-[#12110F]'
                                    : 'border border-[#37332E] bg-[#12110F] text-[#F1EADF]'
                            }`}>
                                {m.content}
                            </div>
                        </div>
                    ))}
                    {loading && (
                        <div className="flex items-center gap-2 text-[14px] text-[#A8A096]">
                            <Loader2 className="h-4 w-4 animate-spin" /> Thinking…
                        </div>
                    )}
                    {error && (
                        <div className="rounded-[6px] border border-[#F04A32]/50 bg-[#F04A32]/5 p-4 text-[14px] text-[#F1EADF]">
                            The intake agent is unavailable — switching you to the quick form (your answers are carried over).
                        </div>
                    )}
                </div>

                {complete ? (
                    <div className="border-t border-[#37332E] p-5">
                        <p className="text-[14px] text-[#A8A096]">Your project brief is ready. Correct anything I misread on the right, then book.</p>
                        <button
                            onClick={() => onComplete(briefToNotes(path, cleanBrief(brief)), nextStep, cleanBrief(brief), session)}
                            className="mt-3 inline-flex min-h-[48px] items-center gap-2 rounded-[4px] bg-[#F04A32] px-6 text-[15px] font-semibold text-[#12110F] transition-colors hover:bg-[#D63B27]"
                        >
                            Book with this brief →
                        </button>
                    </div>
                ) : (
                    <div className="border-t border-[#37332E] p-4">
                        {quickReplies.length > 0 && (
                            <div className="mb-3 flex flex-wrap gap-2">
                                {quickReplies.map((q) => (
                                    <button
                                        key={q}
                                        onClick={() => send(q)}
                                        disabled={loading}
                                        className="rounded-[4px] border border-[#37332E] px-3 py-1.5 text-[13px] text-[#F1EADF] transition-colors hover:border-[#F04A32] disabled:opacity-40"
                                    >
                                        {q}
                                    </button>
                                ))}
                            </div>
                        )}
                        <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-end gap-2">
                            <textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); } }}
                                rows={1}
                                placeholder="Type your answer…"
                                className="min-h-[48px] flex-1 resize-none rounded-[4px] border border-[#37332E] bg-[#12110F] p-3 text-[15px] text-[#F1EADF] placeholder-[#A8A096] outline-none focus:border-[#F04A32]"
                            />
                            <button
                                type="submit"
                                disabled={loading || !input.trim()}
                                aria-label="Send"
                                className="flex h-[48px] w-[48px] items-center justify-center rounded-[4px] bg-[#F04A32] text-[#12110F] transition-colors hover:bg-[#D63B27] disabled:opacity-40"
                            >
                                <Send className="h-5 w-5" />
                            </button>
                        </form>
                        <button onClick={() => onFallback(cleanBrief(brief))} className="mt-3 text-[13px] text-[#A8A096] hover:text-[#F1EADF]">
                            Rather not chat? Use the quick form →
                        </button>
                    </div>
                )}
            </div>

            {/* Live editable brief pane — sticky on desktop */}
            <div className="hidden lg:block">
                <div className="sticky top-24 rounded-[6px] border border-[#37332E] bg-[#191816]/40 p-5">{BriefPane}</div>
            </div>

            {/* Mobile brief bottom-sheet */}
            <button
                onClick={() => setBriefOpen(true)}
                className="fixed bottom-4 left-1/2 z-40 -translate-x-1/2 rounded-full border border-[#37332E] bg-[#191816] px-5 py-3 text-[14px] font-semibold text-[#F1EADF] shadow-lg lg:hidden"
            >
                View brief · {count} {count === 1 ? 'item' : 'items'}
            </button>
            {briefOpen && (
                <div
                    className="fixed inset-0 z-50 flex items-end bg-black/50 lg:hidden"
                    role="dialog"
                    aria-modal="true"
                    aria-label="Your project brief"
                    onClick={() => setBriefOpen(false)}
                >
                    <div className="max-h-[80vh] w-full overflow-y-auto rounded-t-[12px] border-t border-[#37332E] bg-[#12110F] p-6" onClick={(e) => e.stopPropagation()}>
                        <div className="mb-4 flex justify-end">
                            <button onClick={() => setBriefOpen(false)} autoFocus className="text-[14px] font-semibold text-[#A8A096]">Close</button>
                        </div>
                        {BriefPane}
                    </div>
                </div>
            )}
        </div>
    );
};

export default IntakeChat;
