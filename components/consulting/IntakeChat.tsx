import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, Send } from 'lucide-react';
import { configService } from '@/services/config';

/*
 * AI Brief Agent — the /consult intake chat (Phase 2).
 * A guided interviewer that builds a LIVE, editable structured brief while it
 * asks, then routes into the booking flow. Same charcoal/bone/vermilion system
 * as the rest of the site — it should read as the site, not a widget.
 *
 * Progressive enhancement: if the backend intake endpoint is unavailable or
 * errors, it calls onFallback() so ConsultingPage renders the guided form.
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
}

interface Msg { role: 'user' | 'assistant'; content: string }

const BRIEF_FIELDS: Array<{ key: keyof Brief; label: string }> = [
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

const briefToNotes = (path: Path, brief: Brief): string => {
    const lines: string[] = [
        `Path: ${path === 'business' ? 'Business workflow' : 'Personal system'}`,
        '',
        'AI intake brief:',
    ];
    for (const f of BRIEF_FIELDS) {
        const v = (brief[f.key] as string | undefined)?.trim();
        if (v) lines.push(`- ${f.label}: ${v}`);
    }
    if (brief.open_questions && brief.open_questions.length) {
        lines.push('- Open questions: ' + brief.open_questions.join('; '));
    }
    return lines.join('\n').slice(0, 1990);
};

const briefCount = (brief: Brief): number =>
    BRIEF_FIELDS.filter((f) => (brief[f.key] as string | undefined)?.trim()).length +
    ((brief.open_questions && brief.open_questions.length) ? 1 : 0);

interface IntakeChatProps {
    path: Path;
    onComplete: (notes: string, recommendedNextStep: string, brief: Brief) => void;
    onFallback: () => void;
}

export const IntakeChat: React.FC<IntakeChatProps> = ({ path, onComplete, onFallback }) => {
    const [transcript, setTranscript] = useState<Msg[]>([]); // full transcript incl. hidden seed
    const [display, setDisplay] = useState<Msg[]>([]); // what the user sees (assistant + their replies)
    const [brief, setBrief] = useState<Brief>({});
    const [changed, setChanged] = useState<Set<string>>(new Set());
    const [quickReplies, setQuickReplies] = useState<string[]>([]);
    const [complete, setComplete] = useState(false);
    const [nextStep, setNextStep] = useState('');
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);
    const [briefOpen, setBriefOpen] = useState(false); // mobile bottom-sheet
    const scrollRef = useRef<HTMLDivElement>(null);
    const startedRef = useRef(false);

    const backendUrl = useMemo(() => configService.getBackendUrl().replace(/\/$/, ''), []);

    const applyResult = (r: TurnResult) => {
        setDisplay((d) => [...d, { role: 'assistant', content: r.reply }]);
        setTranscript((t) => [...t, { role: 'assistant', content: r.reply }]);
        // Flash fields that gained/changed content.
        setBrief((prev) => {
            const next = { ...prev, ...r.brief };
            const flash = new Set<string>();
            for (const f of BRIEF_FIELDS) {
                const a = (prev[f.key] as string | undefined) || '';
                const b = (next[f.key] as string | undefined) || '';
                if (a !== b && b.trim()) flash.add(f.key as string);
            }
            if (flash.size) {
                setChanged(flash);
                setTimeout(() => setChanged(new Set()), 600);
            }
            return next;
        });
        setQuickReplies(r.quick_replies || []);
        setNextStep(r.recommended_next_step || '');
        setComplete(!!r.complete);
    };

    const callTurn = async (msgs: Msg[]) => {
        setLoading(true);
        setError(false);
        try {
            const res = await fetch(`${backendUrl}/api/intake/message`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path, messages: msgs }),
            });
            if (!res.ok) throw new Error(String(res.status));
            const data: TurnResult = await res.json();
            applyResult(data);
        } catch {
            setError(true);
        } finally {
            setLoading(false);
        }
    };

    // Kick off with a hidden seed message so the agent asks the first question.
    useEffect(() => {
        if (startedRef.current) return;
        startedRef.current = true;
        const seeded: Msg[] = [{ role: 'user', content: seedFor(path) }];
        setTranscript(seeded);
        callTurn(seeded);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [path]);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }, [display, loading]);

    const send = (text: string) => {
        const t = text.trim();
        if (!t || loading) return;
        const nextTranscript: Msg[] = [...transcript, { role: 'user', content: t }];
        setTranscript(nextTranscript);
        setDisplay((d) => [...d, { role: 'user', content: t }]);
        setInput('');
        setQuickReplies([]);
        callTurn(nextTranscript);
    };

    const count = briefCount(brief);

    const BriefPane = (
        <div className="space-y-4">
            <div className="flex items-baseline justify-between">
                <h3 className="text-[13px] font-semibold uppercase tracking-[0.18em] text-[#A8A096]">Your project brief</h3>
                <span className="text-[12px] text-[#A8A096]">{count} {count === 1 ? 'item' : 'items'}</span>
            </div>
            <div className="space-y-3">
                {BRIEF_FIELDS.map((f) => {
                    const v = (brief[f.key] as string | undefined)?.trim();
                    const isChanged = changed.has(f.key as string);
                    return (
                        <div key={f.key as string} className={`border-l-2 pl-3 transition-colors duration-500 ${isChanged ? 'border-[#F04A32]' : 'border-[#37332E]'}`}>
                            <p className="text-[11px] uppercase tracking-[0.14em] text-[#A8A096]">{f.label}</p>
                            <p className={`mt-0.5 text-[14px] leading-[1.45] ${v ? 'text-[#F1EADF]' : 'text-[#565049]'}`}>{v || '—'}</p>
                        </div>
                    );
                })}
                {brief.open_questions && brief.open_questions.length > 0 && (
                    <div className="border-l-2 border-[#37332E] pl-3">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-[#A8A096]">Open questions</p>
                        <ul className="mt-0.5 space-y-0.5">
                            {brief.open_questions.map((q, i) => (
                                <li key={i} className="text-[14px] leading-[1.45] text-[#F1EADF]">— {q}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
            <p className="pt-2 text-[12px] text-[#A8A096]">Yanqing receives the approved brief — not the raw chat.</p>
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
                            The intake agent is unavailable right now.{' '}
                            <button onClick={onFallback} className="font-semibold underline decoration-[#F04A32] decoration-2 underline-offset-4">
                                Continue with the guided form instead →
                            </button>
                        </div>
                    )}
                </div>

                {/* Completion / composer */}
                {complete ? (
                    <div className="border-t border-[#37332E] p-5">
                        <p className="text-[14px] text-[#A8A096]">Your project brief is ready. Correct anything I misread on the right, then book.</p>
                        <button
                            onClick={() => onComplete(briefToNotes(path, brief), nextStep, brief)}
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
                        <form
                            onSubmit={(e) => { e.preventDefault(); send(input); }}
                            className="flex items-end gap-2"
                        >
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
                        <button onClick={onFallback} className="mt-3 text-[13px] text-[#A8A096] hover:text-[#F1EADF]">
                            Rather not chat? Use the quick form →
                        </button>
                    </div>
                )}
            </div>

            {/* Live brief pane — sticky on desktop */}
            <div className="hidden lg:block">
                <div className="sticky top-24 rounded-[6px] border border-[#37332E] bg-[#191816]/40 p-5">{BriefPane}</div>
            </div>

            {/* Mobile: brief bottom-sheet pill */}
            <button
                onClick={() => setBriefOpen(true)}
                className="fixed bottom-4 left-1/2 z-40 -translate-x-1/2 rounded-full border border-[#37332E] bg-[#191816] px-5 py-3 text-[14px] font-semibold text-[#F1EADF] shadow-lg lg:hidden"
            >
                View brief · {count} {count === 1 ? 'item' : 'items'}
            </button>
            {briefOpen && (
                <div className="fixed inset-0 z-50 flex items-end bg-black/50 lg:hidden" onClick={() => setBriefOpen(false)}>
                    <div className="max-h-[80vh] w-full overflow-y-auto rounded-t-[12px] border-t border-[#37332E] bg-[#12110F] p-6" onClick={(e) => e.stopPropagation()}>
                        <div className="mb-4 flex justify-end">
                            <button onClick={() => setBriefOpen(false)} className="text-[14px] font-semibold text-[#A8A096]">Close</button>
                        </div>
                        {BriefPane}
                    </div>
                </div>
            )}
        </div>
    );
};

export default IntakeChat;
