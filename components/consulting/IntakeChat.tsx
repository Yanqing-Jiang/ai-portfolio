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

// Defensive client-side validation of a turn response before it hits state.
const coerceTurn = (data: unknown): TurnResult => {
    const d = (data ?? {}) as Record<string, unknown>;
    const rawBrief = (d.brief && typeof d.brief === 'object') ? d.brief as Record<string, unknown> : {};
    const brief: Brief = {};
    for (const f of STR_FIELDS) {
        const v = rawBrief[f.key as string];
        if (typeof v === 'string' && v.trim()) (brief as Record<string, unknown>)[f.key] = v;
    }
    if (Array.isArray(rawBrief.open_questions)) {
        const oq = (rawBrief.open_questions as unknown[]).filter((q): q is string => typeof q === 'string');
        if (oq.length) brief.open_questions = oq;
    }
    return {
        reply: typeof d.reply === 'string' ? d.reply : 'Could you tell me a bit more?',
        brief,
        quick_replies: Array.isArray(d.quick_replies) ? (d.quick_replies as unknown[]).filter((q): q is string => typeof q === 'string').slice(0, 3) : [],
        complete: d.complete === true,
        recommended_next_step: typeof d.recommended_next_step === 'string' ? d.recommended_next_step : '',
        session: typeof d.session === 'string' ? d.session : undefined,
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

    const backendUrl = useMemo(() => configService.getBackendUrl().replace(/\/$/, ''), []);

    const mergeServerBrief = (server: Brief) => {
        setBrief((prev) => {
            const next: Brief = { ...prev };
            const flash = new Set<string>();
            for (const f of STR_FIELDS) {
                if (touched.has(f.key as string)) continue; // never clobber user edits
                const b = (server[f.key] as string | undefined) || '';
                const a = (prev[f.key] as string | undefined) || '';
                if (b && a !== b) { (next as Record<string, unknown>)[f.key] = b; flash.add(f.key as string); }
            }
            if (!touched.has('open_questions') && server.open_questions && server.open_questions.length) {
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
