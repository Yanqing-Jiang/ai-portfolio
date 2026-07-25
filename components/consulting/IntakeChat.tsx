import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Clock, Loader2, Send, X } from 'lucide-react';
import { configService } from '@/services/config';
import { CalendarPicker } from './CalendarPicker';
import { useAvailableSlots } from './useAvailableSlots';

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

type Path = 'business' | 'individual' | 'training';

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

// --- Generative UI (A2UI) component contract — mirrors the server whitelist ---
export type SessionType = 'fit' | '30' | '60';
export interface UIChoiceOption { value: string; label: string }
export type UIComponent =
    | { kind: 'choice'; id: string; label: string; options: UIChoiceOption[]; multi: boolean }
    | { kind: 'text'; id: string; label: string; placeholder: string; multiline: boolean }
    | { kind: 'calendar'; session_type: SessionType }
    | { kind: 'contact' };

interface TurnResult {
    reply: string;
    brief: Brief;
    quick_replies: string[];
    complete: boolean;
    recommended_next_step: string; // 'fit' | '30' | '60' | ''
    ui: UIComponent[];
    session?: string;
    capped?: boolean;
}

// Assistant turns may carry generated UI; `turnKey` scopes answer/answered state.
interface Msg { role: 'user' | 'assistant'; content: string; ui?: UIComponent[]; turnKey?: number }

const STR_FIELDS: Array<{ key: keyof Brief; label: string }> = [
    { key: 'desired_outcome', label: 'Desired outcome' },
    { key: 'current_workflow', label: 'Current workflow' },
    { key: 'people_and_frequency', label: 'People & frequency' },
    { key: 'systems_and_data', label: 'Systems & data' },
    { key: 'success_metric', label: 'Success metric' },
    { key: 'constraints', label: 'Constraints' },
    { key: 'timing_and_stakeholders', label: 'Timing & stakeholders' },
];

// --- Client-seeded opening turns ------------------------------------------
// The chat now owns BOTH the path fork (was a card grid above the chat) and the
// first real question, so every question renders as tappable choices attached to
// the question itself. Seeded turns are answered locally: the fork just switches
// path, and the Q1 answer becomes the first message the server ever sees (its
// script knows the UI already asked Q1 — see backend/intake_agent.py).
const PATH_TURN_KEY = 0;
const Q1_TURN_KEY = 1;
const PATH_COMPONENT_ID = 'consult_path';

const PATH_OPTIONS: Array<{ value: Path; label: string }> = [
    { value: 'business', label: 'Enterprise workflow' },
    { value: 'individual', label: 'Personal Agent OS' },
    { value: 'training', label: 'Hands on training' },
];

const isPath = (v: string): v is Path =>
    v === 'business' || v === 'individual' || v === 'training';

// Question 1 per path. Concrete options beat an open "what outcome do you want?"
// — the prospect sees exactly what is on offer. The composer stays available for
// anything that isn't listed.
const FIRST_TURN: Record<Path, { question: string; ui: UIComponent[] }> = {
    business: {
        question: 'Which process do you want to cut down? Pick the closest one — or type your own.',
        ui: [{
            kind: 'choice', id: 'desired_outcome', multi: false,
            label: 'The process',
            options: [
                { value: 'db-to-deliverable', label: 'Database → PowerPoint or dashboard' },
                { value: 'documents', label: 'Document / invoice processing' },
                { value: 'research', label: 'Research & analysis' },
                { value: 'support-ops', label: 'Customer or ops support' },
            ],
        }],
    },
    individual: {
        question: 'What do you want to build first? Pick the closest one — or type your own.',
        ui: [{
            kind: 'choice', id: 'desired_outcome', multi: false,
            label: 'What you want',
            options: [
                { value: 'agent-os', label: 'Build my personal agent OS' },
                { value: 'harness', label: 'Learn an agent harness — Claude Code, Codex' },
                { value: 'website', label: 'Let an AI agent build my personal website' },
            ],
        }],
    },
    training: {
        question: 'Who is the training for, and what should be different afterward?',
        ui: [
            {
                kind: 'choice', id: 'people_and_frequency', multi: false,
                label: 'Who it is for',
                options: [
                    { value: 'just-me', label: 'Just me' },
                    { value: 'small-team', label: 'My team (2–10)' },
                    { value: 'org', label: 'My org (10+)' },
                ],
            },
            {
                kind: 'text', id: 'desired_outcome', multiline: true,
                label: 'What should be different afterward',
                placeholder: 'e.g. the team ships with Claude Code without hand-holding',
            },
        ],
    },
};

const pathQuestionMsg = (): Msg => ({
    role: 'assistant',
    content: 'What are you trying to improve?',
    turnKey: PATH_TURN_KEY,
    ui: [{
        kind: 'choice', id: PATH_COMPONENT_ID, multi: false,
        label: 'Pick the closest one',
        options: PATH_OPTIONS.map((o) => ({ value: o.value, label: o.label })),
    }],
});

const firstQuestionMsg = (path: Path): Msg => ({
    role: 'assistant',
    content: FIRST_TURN[path].question,
    turnKey: Q1_TURN_KEY,
    ui: FIRST_TURN[path].ui,
});

export const briefToNotes = (path: Path, brief: Brief): string => {
    const pathLabel =
        path === 'business' ? 'Enterprise workflow' :
        path === 'training' ? 'Hands on training' :
        'Personal Agent OS';
    const lines: string[] = [
        `Path: ${pathLabel}`,
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

// Strict client-side validation of the generated `ui` array — mirrors the
// server whitelist and, like coerceTurn, THROWS on malformed kinds rather than
// silently rendering junk (same strictness philosophy as recommended_next_step).
const coerceUI = (raw: unknown): UIComponent[] => {
    if (raw === undefined || raw === null) return [];
    if (!Array.isArray(raw)) throw new Error('intake: ui must be an array');
    const out: UIComponent[] = [];
    for (const item of raw) {
        if (!item || typeof item !== 'object') throw new Error('intake: ui item must be an object');
        const c = item as Record<string, unknown>;
        const kind = c.kind;
        if (kind === 'choice') {
            if (typeof c.id !== 'string' || typeof c.label !== 'string' || !Array.isArray(c.options)) {
                throw new Error('intake: malformed choice component');
            }
            const options: UIChoiceOption[] = c.options.map((o) => {
                const oo = o as Record<string, unknown>;
                if (typeof oo?.value !== 'string' || typeof oo?.label !== 'string') {
                    throw new Error('intake: malformed choice option');
                }
                return { value: oo.value, label: oo.label };
            });
            out.push({ kind: 'choice', id: c.id, label: c.label, options, multi: c.multi === true });
        } else if (kind === 'text') {
            if (typeof c.id !== 'string' || typeof c.label !== 'string') {
                throw new Error('intake: malformed text component');
            }
            out.push({
                kind: 'text', id: c.id, label: c.label,
                placeholder: typeof c.placeholder === 'string' ? c.placeholder : '',
                multiline: c.multiline === true,
            });
        } else if (kind === 'calendar') {
            if (c.session_type !== 'fit' && c.session_type !== '30' && c.session_type !== '60') {
                throw new Error('intake: malformed calendar component');
            }
            out.push({ kind: 'calendar', session_type: c.session_type });
        } else if (kind === 'contact') {
            out.push({ kind: 'contact' });
        } else {
            throw new Error('intake: unknown ui component kind');
        }
    }
    return out;
};

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
        ui: coerceUI(d.ui),
        session: d.session,
        capped: d.capped === true,
    };
};

// JetBrains Mono for A2UI component labels/ids (design token).
const MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, monospace";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const fmtSlot = (iso: string): string => {
    try {
        return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }).format(new Date(iso));
    } catch {
        return iso;
    }
};

// Day + time, for confirming back the slot the prospect just picked.
const fmtSlotFull = (iso: string): string => {
    try {
        return new Intl.DateTimeFormat('en-US', {
            weekday: 'short', month: 'short', day: 'numeric',
            hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
        }).format(new Date(iso));
    } catch {
        return iso;
    }
};

// In-chat calendar: mounts the shared CalendarPicker + the SAME slots fetch the
// booking page uses, then hands the picked date+time back for the existing flow.
const InChatCalendar: React.FC<{
    sessionType: SessionType;
    disabled?: boolean;
    onPick: (date: string, time: string) => void;
}> = ({ sessionType, disabled, onPick }) => {
    const [date, setDate] = useState<string | null>(null);
    const [picked, setPicked] = useState<string | null>(null);
    const slotType: '30' | '60' = sessionType === '60' ? '60' : '30';
    const { slots, loading, error } = useAvailableSlots(date, slotType);

    return (
        <div className={disabled ? 'pointer-events-none opacity-60' : ''}>
            <CalendarPicker selectedDate={date} onSelectDate={(d) => { setDate(d); setPicked(null); }} />
            {date && (
                <div className="mt-4 space-y-2">
                    <h4 className="flex items-center gap-2 text-[13px] font-semibold text-[#F1EADF]">
                        <Clock className="h-3.5 w-3.5 text-[#F04A32]" /> Available times
                    </h4>
                    {loading ? (
                        <div className="flex items-center gap-2 py-2 text-[13px] text-[#A8A096]"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
                    ) : error ? (
                        <p className="py-2 text-[13px] text-[#F04A32]">Couldn't load availability.</p>
                    ) : slots.length === 0 ? (
                        <p className="py-2 text-[13px] text-[#A8A096]">No times for this date.</p>
                    ) : (
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                            {slots.map((slot) => (
                                <button
                                    key={slot.start}
                                    disabled={disabled}
                                    onClick={() => { setPicked(slot.start); onPick(date, slot.start); }}
                                    className={`min-h-[44px] rounded-[4px] border px-3 py-2 text-[13px] font-medium transition-colors ${
                                        picked === slot.start
                                            ? 'border-[#F04A32] bg-[#F04A32] text-[#12110F]'
                                            : 'border-[#37332E] text-[#F1EADF] hover:border-[#A8A096]/60'
                                    }`}
                                >
                                    {fmtSlot(slot.start)}
                                </button>
                            ))}
                        </div>
                    )}
                    {/* Confirm the pick back in words — a highlighted chip alone
                        left people unsure the time had been captured. */}
                    {picked && (
                        <p className="flex items-center gap-2 pt-1 text-[13px] text-[#F1EADF]">
                            <Check className="h-3.5 w-3.5 shrink-0 text-[#F04A32]" />
                            <span>Time saved — <strong className="font-semibold">{fmtSlotFull(picked)}</strong>. Tap another slot to change it.</span>
                        </p>
                    )}
                </div>
            )}
        </div>
    );
};

interface IntakeChatProps {
    // null = no landing intent: the chat opens with the path fork as its first
    // question instead of jumping straight to Q1.
    path: Path | null;
    onComplete: (notes: string, recommendedNextStep: string, brief: Brief, session: string | null) => void;
    onFallback: (partialBrief?: Brief) => void;
    // Fires when the in-chat fork resolves the path, so the page can mirror it
    // into its own buyer-intent state (notes, preselect).
    onPathSelect?: (path: Path) => void;
    // A2UI handoffs: the in-chat calendar hands a picked date+time into the
    // existing booking flow; the contact block lifts name/email/company to the page.
    onCalendarPick?: (args: {
        date: string; time: string; sessionType: SessionType;
        notes: string; brief: Brief; session: string | null;
    }) => void;
    onContact?: (contact: { name: string; email: string; company: string }) => void;
}

export const IntakeChat: React.FC<IntakeChatProps> = ({
    path: initialPath, onComplete, onFallback, onPathSelect, onCalendarPick, onContact,
}) => {
    // Resolved either from the landing intent (?path=) or by the in-chat fork.
    const [path, setPath] = useState<Path | null>(initialPath);
    const [display, setDisplay] = useState<Msg[]>(() =>
        initialPath ? [firstQuestionMsg(initialPath)] : [pathQuestionMsg()]
    );
    const [session, setSession] = useState<string | null>(null);
    // `brief` is the editable source of truth (display + notes + persist).
    const [brief, setBrief] = useState<Brief>({});
    const [touched, setTouched] = useState<Set<string>>(new Set());
    const [changed, setChanged] = useState<Set<string>>(new Set());
    // Server-suggested short replies. Seeded turns carry their own choice chips,
    // so this starts empty for every path.
    const [quickReplies, setQuickReplies] = useState<string[]>([]);
    const [complete, setComplete] = useState(false);
    const [nextStep, setNextStep] = useState('');
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(false);
    const [briefOpen, setBriefOpen] = useState(false);
    // A2UI: answers keyed by `${turnKey}:${componentId}`; answered turns go inert.
    const [answers, setAnswers] = useState<Record<string, string[]>>({});
    const [answeredTurns, setAnsweredTurns] = useState<Set<number>>(new Set());
    const [contactDraft, setContactDraft] = useState({ name: '', email: '', company: '' });
    const [pendingCalendarPick, setPendingCalendarPick] = useState<{
        turnKey: number;
        date: string;
        time: string;
        sessionType: SessionType;
    } | null>(null);
    // Seeded turns hold keys 0 (fork) and 1 (Q1); server turns start at 2.
    const turnKeyRef = useRef(Q1_TURN_KEY);
    const scrollRef = useRef<HTMLDivElement>(null);
    const briefRef = useRef<Brief>({});
    briefRef.current = brief;
    const sessionRef = useRef<string | null>(null);
    sessionRef.current = session;
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

    const callTurn = async (message: string, sess: string | null, forPath: Path) => {
        setLoading(true);
        setError(false);
        try {
            const res = await fetch(`${backendUrl}/api/intake/message`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: forPath, session: sess, message }),
            });
            if (!res.ok) throw new Error(String(res.status));
            const data = coerceTurn(await res.json());
            const tk = ++turnKeyRef.current;
            setDisplay((d) => [...d, { role: 'assistant', content: data.reply, ui: data.ui, turnKey: tk }]);
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

    // `shownAs` lets a structured answer read naturally in the transcript ("Build
    // my personal agent OS") while the model still receives the field-tagged form
    // ("desired_outcome: Build my personal agent OS").
    const send = (text: string, shownAs?: string) => {
        const t = text.trim();
        // Before the fork resolves there is no path to interview against — the
        // composer is disabled in that state, so this is a guard, not a UX path.
        if (!t || loading || !path) return;
        setDisplay((d) => [...d, { role: 'user', content: (shownAs || t).trim() }]);
        setInput('');
        setQuickReplies([]);
        callTurn(t, session, path);
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

    // --- A2UI component interaction -----------------------------------------
    const ansKey = (turnKey: number, id: string) => `${turnKey}:${id}`;

    // A turn whose only input is one single-select choice submits on tap — no
    // second "Send answers" click for what reads as a quick reply.
    const isOneTapTurn = (m: Msg): boolean =>
        !!m.ui && m.ui.length === 1 && m.ui[0].kind === 'choice' && !m.ui[0].multi;

    const toggleChoice = (m: Msg, c: Extract<UIComponent, { kind: 'choice' }>, value: string) => {
        const turnKey = m.turnKey!;
        const key = ansKey(turnKey, c.id);
        setAnswers((prev) => {
            const cur = prev[key] || [];
            if (c.multi) {
                const next = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value];
                return { ...prev, [key]: next };
            }
            return { ...prev, [key]: [value] };
        });
        // Submit from the tapped value directly — `answers` has not re-rendered yet.
        if (isOneTapTurn(m)) submitTurnAnswers(m, { [key]: [value] });
    };

    const setTextAnswer = (turnKey: number, id: string, value: string) =>
        setAnswers((prev) => ({ ...prev, [ansKey(turnKey, id)]: [value] }));

    // Does this turn have at least one non-empty choice/text answer yet?
    const turnHasAnswer = (m: Msg): boolean =>
        !!m.ui && m.turnKey != null && m.ui.some((c) => {
            if (c.kind === 'choice') return (answers[ansKey(m.turnKey!, c.id)] || []).length > 0;
            if (c.kind === 'text') return ((answers[ansKey(m.turnKey!, c.id)] || [])[0] || '').trim().length > 0;
            return false;
        });

    // Resolve the in-chat path fork locally: no server turn, just switch path and
    // seed question 1 for the chosen path.
    const submitPathChoice = (value: string) => {
        if (!isPath(value) || answeredTurns.has(PATH_TURN_KEY)) return;
        const label = PATH_OPTIONS.find((o) => o.value === value)?.label ?? value;
        setAnsweredTurns((s) => new Set(s).add(PATH_TURN_KEY));
        setPath(value);
        onPathSelect?.(value);
        setDisplay((d) => [...d, { role: 'user', content: label }, firstQuestionMsg(value)]);
    };

    // Serialize a turn's choice/text answers into a compact human-readable string
    // (e.g. "systems_and_data: SAP, Excel; urgency: this quarter") and send it as
    // the next user message — the model reads it as prose, no schema change needed.
    // `override` carries a just-tapped value that `answers` has not committed yet.
    const submitTurnAnswers = (m: Msg, override?: Record<string, string[]>) => {
        if (!m.ui || m.turnKey == null || loading) return;
        const picked = { ...answers, ...(override || {}) };
        if (m.turnKey === PATH_TURN_KEY) {
            submitPathChoice((picked[ansKey(PATH_TURN_KEY, PATH_COMPONENT_ID)] || [])[0] || '');
            return;
        }
        const parts: string[] = [];   // for the model: field-tagged
        const shown: string[] = [];   // for the transcript: plain answers
        for (const c of m.ui) {
            if (c.kind === 'choice') {
                const sel = picked[ansKey(m.turnKey, c.id)] || [];
                const labels = sel.map((v) => c.options.find((o) => o.value === v)?.label ?? v);
                if (labels.length) {
                    parts.push(`${c.id}: ${labels.join(', ')}`);
                    shown.push(labels.join(', '));
                }
            } else if (c.kind === 'text') {
                const val = ((picked[ansKey(m.turnKey, c.id)] || [])[0] || '').trim();
                if (val) {
                    parts.push(`${c.id}: ${val}`);
                    shown.push(val);
                }
            }
        }
        if (!parts.length) return;
        setAnsweredTurns((s) => new Set(s).add(m.turnKey!));
        send(parts.join('; '), shown.join(' · '));
    };

    // Same email shape the booking page enforces — a malformed address here would
    // only fail once the booking request was already in flight.
    const contactReady = !!contactDraft.name.trim() && EMAIL_RE.test(contactDraft.email.trim());

    const submitContact = (turnKey: number) => {
        const { name, email } = contactDraft;
        if (!contactReady || loading || !path) return;
        onContact?.({ name: name.trim(), email: email.trim(), company: contactDraft.company.trim() });
        setAnsweredTurns((s) => new Set(s).add(turnKey));
        if (pendingCalendarPick?.turnKey === turnKey) {
            const cleaned = cleanBrief(briefRef.current);
            onCalendarPick?.({
                date: pendingCalendarPick.date,
                time: pendingCalendarPick.time,
                sessionType: pendingCalendarPick.sessionType,
                notes: briefToNotes(path, cleaned),
                brief: cleaned,
                session: sessionRef.current,
            });
            return;
        }
        send('Shared my contact details.');
    };

    const handleCalendarPick = (
        turnKey: number,
        sessionType: SessionType,
        date: string,
        time: string,
    ) => setPendingCalendarPick({ turnKey, date, time, sessionType });

    const count = briefCount(brief);
    // The completing turn carries the calendar, so booking finishes inside the
    // chat; the full booking page becomes the secondary route, not the next step.
    const bookingInChat = !!display[display.length - 1]?.ui?.some((c) => c.kind === 'calendar');
    const finishWithBrief = () => {
        if (!path) return;
        onComplete(briefToNotes(path, cleanBrief(brief)), nextStep, cleanBrief(brief), session);
    };

    // Render one assistant turn's generated UI components under its bubble.
    const renderTurnUI = (m: Msg) => {
        if (!m.ui || !m.ui.length || m.turnKey == null) return null;
        const tk = m.turnKey;
        const answered = answeredTurns.has(tk);
        // One-tap turns submit from the chip itself, so they need no submit button.
        const hasInputs = m.ui.some((c) => c.kind === 'choice' || c.kind === 'text') && !isOneTapTurn(m);
        return (
            <div className="w-full max-w-[85%] space-y-4 rounded-[6px] border border-[#37332E] bg-[#191816]/50 p-4">
                {m.ui.map((c, ci) => {
                    if (c.kind === 'choice') {
                        const sel = answers[ansKey(tk, c.id)] || [];
                        return (
                            <div key={ci} className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <label style={{ fontFamily: MONO }} className="text-[11px] uppercase tracking-[0.12em] text-[#A8A096]">{c.label}</label>
                                    {c.multi && <span style={{ fontFamily: MONO }} className="text-[10px] text-[#565049]">multi-select</span>}
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    {c.options.map((o) => {
                                        const on = sel.includes(o.value);
                                        return (
                                            <button
                                                key={o.value}
                                                disabled={answered || loading}
                                                onClick={() => toggleChoice(m, c, o.value)}
                                                className={`min-h-[40px] rounded-[4px] border px-3 py-1.5 text-[13px] font-medium transition-colors disabled:cursor-default ${
                                                    on
                                                        ? 'border-[#F04A32] bg-[#F04A32] text-[#12110F]'
                                                        : 'border-[#37332E] text-[#F1EADF] hover:border-[#F04A32] disabled:opacity-40'
                                                }`}
                                            >
                                                {o.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    }
                    if (c.kind === 'text') {
                        const val = (answers[ansKey(tk, c.id)] || [])[0] || '';
                        return (
                            <div key={ci} className="space-y-2">
                                <label style={{ fontFamily: MONO }} className="text-[11px] uppercase tracking-[0.12em] text-[#A8A096]">{c.label}</label>
                                {c.multiline ? (
                                    <textarea
                                        value={val}
                                        disabled={answered || loading}
                                        onChange={(e) => setTextAnswer(tk, c.id, e.target.value)}
                                        rows={2}
                                        placeholder={c.placeholder || '…'}
                                        className="w-full resize-none rounded-[4px] border border-[#37332E] bg-[#12110F] p-2.5 text-[14px] text-[#F1EADF] placeholder-[#565049] outline-none focus:border-[#F04A32] disabled:opacity-50"
                                    />
                                ) : (
                                    <input
                                        type="text"
                                        value={val}
                                        disabled={answered || loading}
                                        onChange={(e) => setTextAnswer(tk, c.id, e.target.value)}
                                        placeholder={c.placeholder || '…'}
                                        className="w-full rounded-[4px] border border-[#37332E] bg-[#12110F] p-2.5 text-[14px] text-[#F1EADF] placeholder-[#565049] outline-none focus:border-[#F04A32] disabled:opacity-50"
                                    />
                                )}
                            </div>
                        );
                    }
                    if (c.kind === 'calendar') {
                        return (
                            <div key={ci} className="space-y-2">
                                <label style={{ fontFamily: MONO }} className="text-[11px] uppercase tracking-[0.12em] text-[#A8A096]">Pick a time</label>
                                <InChatCalendar
                                    sessionType={c.session_type}
                                    disabled={answered}
                                    onPick={(date, time) => handleCalendarPick(tk, c.session_type, date, time)}
                                />
                            </div>
                        );
                    }
                    // The deterministic contact step appears only after a slot is picked.
                    if (pendingCalendarPick?.turnKey !== tk) return null;
                    // contact
                    return (
                        <div key={ci} className="space-y-2">
                            <label style={{ fontFamily: MONO }} className="text-[11px] uppercase tracking-[0.12em] text-[#A8A096]">Your contact details</label>
                            <div className="grid gap-2 sm:grid-cols-2">
                                <input type="text" value={contactDraft.name} disabled={answered || loading} maxLength={100}
                                    onChange={(e) => setContactDraft((d) => ({ ...d, name: e.target.value }))}
                                    placeholder="Name"
                                    className="rounded-[4px] border border-[#37332E] bg-[#12110F] p-2.5 text-[14px] text-[#F1EADF] placeholder-[#565049] outline-none focus:border-[#F04A32] disabled:opacity-50" />
                                <input type="email" value={contactDraft.email} disabled={answered || loading}
                                    onChange={(e) => setContactDraft((d) => ({ ...d, email: e.target.value }))}
                                    placeholder="Email"
                                    className="rounded-[4px] border border-[#37332E] bg-[#12110F] p-2.5 text-[14px] text-[#F1EADF] placeholder-[#565049] outline-none focus:border-[#F04A32] disabled:opacity-50" />
                            </div>
                            <input type="text" value={contactDraft.company} disabled={answered || loading} maxLength={120}
                                onChange={(e) => setContactDraft((d) => ({ ...d, company: e.target.value }))}
                                placeholder="Company (optional)"
                                className="w-full rounded-[4px] border border-[#37332E] bg-[#12110F] p-2.5 text-[14px] text-[#F1EADF] placeholder-[#565049] outline-none focus:border-[#F04A32] disabled:opacity-50" />
                            {!answered && (
                                <button onClick={() => submitContact(tk)} disabled={loading || !contactReady}
                                    className="mt-1 inline-flex min-h-[40px] items-center rounded-[4px] bg-[#F04A32] px-4 text-[13px] font-semibold text-[#12110F] transition-colors hover:bg-[#D63B27] disabled:opacity-40">
                                    {/* This click books — the page confirms it on
                                        handoff, so the label must say so. */}
                                    {pendingCalendarPick.sessionType === 'fit'
                                        ? 'Book the free 30-min call'
                                        : 'Continue to booking'}
                                </button>
                            )}
                        </div>
                    );
                })}
                {hasInputs && !answered && (
                    <button
                        onClick={() => submitTurnAnswers(m)}
                        disabled={loading || !turnHasAnswer(m)}
                        style={{ fontFamily: MONO }}
                        className="inline-flex min-h-[40px] items-center gap-2 rounded-[4px] bg-[#F04A32] px-4 text-[13px] font-semibold text-[#12110F] transition-colors hover:bg-[#D63B27] disabled:opacity-40"
                    >
                        Send answers →
                    </button>
                )}
                {answered && <p style={{ fontFamily: MONO }} className="text-[11px] text-[#565049]">Answered.</p>}
            </div>
        );
    };

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
                        m.role === 'user' ? (
                            <div key={i} className="flex justify-end">
                                <div className="max-w-[85%] rounded-[6px] bg-[#F04A32] px-4 py-3 text-[15px] leading-[1.5] text-[#12110F]">
                                    {m.content}
                                </div>
                            </div>
                        ) : (
                            <div key={i} className="flex flex-col items-start gap-3">
                                <div className="max-w-[85%] rounded-[6px] border border-[#37332E] bg-[#12110F] px-4 py-3 text-[15px] leading-[1.5] text-[#F1EADF]">
                                    {m.content}
                                </div>
                                {renderTurnUI(m)}
                                {/* Server quick replies belong to the question that
                                    asked them, not to the composer. At the booking
                                    step the calendar is the only next action. */}
                                {i === display.length - 1 && quickReplies.length > 0 && !bookingInChat && (
                                    <div className="flex flex-wrap gap-2">
                                        {quickReplies.map((q) => (
                                            <button
                                                key={q}
                                                onClick={() => send(q)}
                                                disabled={loading}
                                                className="min-h-[40px] rounded-[4px] border border-[#37332E] px-3 py-1.5 text-[13px] text-[#F1EADF] transition-colors hover:border-[#F04A32] disabled:opacity-40"
                                            >
                                                {q}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )
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
                        {bookingInChat ? (
                            <>
                                <p className="text-[14px] text-[#A8A096]">
                                    Last step — pick a date and time above, then add your details to confirm.
                                </p>
                                <button onClick={finishWithBrief} className="mt-3 text-[13px] text-[#A8A096] underline decoration-[#37332E] underline-offset-4 hover:text-[#F1EADF]">
                                    Rather book from the full page? →
                                </button>
                            </>
                        ) : (
                            <>
                                <p className="text-[14px] text-[#A8A096]">Your project brief is ready. Correct anything I misread on the right, then book.</p>
                                <button
                                    onClick={finishWithBrief}
                                    className="mt-3 inline-flex min-h-[48px] items-center gap-2 rounded-[4px] bg-[#F04A32] px-6 text-[15px] font-semibold text-[#12110F] transition-colors hover:bg-[#D63B27]"
                                >
                                    Book with this brief →
                                </button>
                            </>
                        )}
                    </div>
                ) : (
                    <div className="border-t border-[#37332E] p-4">
                        <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-end gap-2">
                            <textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); } }}
                                rows={1}
                                disabled={!path}
                                placeholder={path ? 'Type your answer…' : 'Pick one above to start…'}
                                className="min-h-[48px] flex-1 resize-none rounded-[4px] border border-[#37332E] bg-[#12110F] p-3 text-[15px] text-[#F1EADF] placeholder-[#A8A096] outline-none focus:border-[#F04A32] disabled:opacity-50"
                            />
                            <button
                                type="submit"
                                disabled={loading || !input.trim() || !path}
                                aria-label="Send"
                                className="flex h-[48px] w-[48px] items-center justify-center rounded-[4px] bg-[#F04A32] text-[#12110F] transition-colors hover:bg-[#D63B27] disabled:opacity-40"
                            >
                                <Send className="h-5 w-5" />
                            </button>
                        </form>
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
