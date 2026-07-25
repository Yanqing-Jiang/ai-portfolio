import React, { useState, useEffect, useMemo } from 'react';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Loader2, CheckCircle2 } from 'lucide-react';

import { CalendarPicker } from './CalendarPicker';
import { BookingConfirmation } from './BookingConfirmation';
import { useAvailableSlots } from './useAvailableSlots';
import { IntakeChat, type Brief } from './IntakeChat';
import { configService } from '@/services/config';
import { DEFAULT_OG_IMAGE } from '@/constants/seo';

/*
 * /consult — Phase 1 "Prices on the door" booking.
 * De-walled: no sign-in required. Visible pricing ($50/$90, kept exactly).
 * The first 30-minute call is FREE for every path. A short REQUIRED context
 * form runs before the calendar; its answers ride in `notes` and are copied
 * to both intake recipients server-side (D5). Locked visual system: charcoal /
 * bone / single vermilion accent — no blue, purple, or amber.
 */

// 'fit' = free first call (30 min). '30'/'60' = paid follow-up working sessions.
type Offering = 'fit' | '30' | '60';

interface OfferingDef {
    id: Offering;
    label: string;
    duration: string;
    priceLabel: string;
    free: boolean;
    blurb: string;
    features: string[];
}

const OFFERINGS: OfferingDef[] = [
    {
        id: 'fit',
        label: 'First call',
        duration: '30 min',
        priceLabel: 'Free',
        free: true,
        blurb: 'A focused first conversation for any path. We clarify the outcome, current setup, and the right next step.',
        features: ['Clarify the problem', 'Review the current setup', 'Choose the right next step'],
    },
    {
        id: '30',
        label: 'Working session',
        duration: '30 min',
        priceLabel: '$50',
        free: false,
        blurb: 'A focused 1:1 on a specific system — agent OS, memory, or a talk-to-your-data setup.',
        features: ['Agent OS consultation', 'Short & long-term memory', 'Talk-to-your-DB setup'],
    },
    {
        id: '60',
        label: 'Strategic deep dive',
        duration: '60 min',
        priceLabel: '$90',
        free: false,
        blurb: 'A longer session for architecture, roadmap, and a review of what you already have.',
        features: ['Full agent OS roadmap', '24/7 agent assistant build', 'Memory + code review'],
    },
];

const FAQ = [
    {
        q: 'What happens after I book?',
        a: "You'll receive a confirmation email with a Google Meet link and a calendar invitation. Your first 30-minute call is free; follow-up working sessions are paid at booking.",
    },
    {
        q: 'Can I reschedule or cancel?',
        a: 'Just reply to your confirmation email. You can reschedule up to 2 hours before your session. Cancellations more than 24 hours before receive a full refund.',
    },
    {
        q: 'What about a full build?',
        a: 'Builds receive a fixed proposal after scoping — no hourly meter. Start with the free 30-minute call and we size the next step from the actual problem.',
    },
];

const slotSessionType = (offering: Offering): '30' | '60' => (offering === '60' ? '60' : '30');

// Buyer intent carried from the landing offer CTAs (?offer=...).
const OFFER_LABELS: Record<string, string> = {
    pipeline: 'Enterprise agentic pipelines',
    'delivery-team': 'Embedded AI delivery team',
    'personal-agent': 'Personal Agent OS',
    website: 'Agent-managed personal website',
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Synchronously read landing intent from the live URL. SSR/prerender-safe:
// returns nulls when `window` is absent (the prerendered /consult has no query
// string, so it renders the fork). The app mounts with createRoot (see
// index.tsx) — NOT hydrateRoot — so the first client render can depend on the
// real URL without any hydration reconciliation/mismatch, and param'd entries
// render their preselect immediately with no chooser flash.
const readIntent = (): { path: string | null; offer: string | null; context: string | null } => {
    if (typeof window === 'undefined') return { path: null, offer: null, context: null };
    const p = new URLSearchParams(window.location.search);
    return { path: p.get('path'), offer: p.get('offer'), context: p.get('context') };
};

// Every recognized landing intent starts with the same free 30-minute call.
// Returns null when nothing was specified (generic entry).
const intentToOffering = (path: string | null, offer: string | null): Offering | null => {
    if (
        offer === 'personal-agent' || offer === 'website' ||
        offer === 'pipeline' || offer === 'delivery-team' ||
        path === 'individual' || path === 'personal' ||
        path === 'enterprise' || path === 'business' || path === 'training'
    ) return 'fit';
    return null;
};

export const ConsultingPage: React.FC = () => {
    const initialIntent = readIntent();
    const initialSelected = intentToOffering(initialIntent.path, initialIntent.offer);

    const [selected, setSelected] = useState<Offering | null>(initialSelected);

    // Required context form
    const [improve, setImprove] = useState(
        initialIntent.context === 'invoice-reconciliation'
            ? 'An invoice reconciliation / AP workflow similar to the case study.'
            : ''
    );
    const [today, setToday] = useState('');
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [company, setCompany] = useState('');

    // Buyer intent from landing (?path=&offer=), preserved into notes/preselect.
    // A param-less entry starts null and is filled by the chat's own path fork.
    const [pathIntent, setPathIntent] = useState<string | null>(initialIntent.path);
    const offerIntent = initialIntent.offer; // never changes after mount

    // Phase 2 — AI Brief Agent. Chat-first when a path is known; falls back to
    // the guided form on agent failure (progressive enhancement). `briefNotes`
    // holds the approved brief that rides into the booking notes.
    const [useChat, setUseChat] = useState(true);
    const [briefNotes, setBriefNotes] = useState<string | null>(null);
    const [briefObj, setBriefObj] = useState<Brief | null>(null);
    const [briefSession, setBriefSession] = useState<string | null>(null);
    const [fallbackNotice, setFallbackNotice] = useState(false);

    // Scheduling
    const [selectedDate, setSelectedDate] = useState<string | null>(null);
    const [selectedTime, setSelectedTime] = useState<string | null>(null);

    // Set by the chat handoff: book as soon as the lifted slot + contact validate.
    const [autoBook, setAutoBook] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [freeConfirmed, setFreeConfirmed] = useState<{
        slot: string; meetLink?: string | null; emailSent?: boolean;
    } | null>(null);
    const [confirmationSessionId, setConfirmationSessionId] = useState<string | null>(null);

    // Stripe redirect confirmation (post-mount is fine — it swaps the whole view).
    useEffect(() => {
        if (typeof window === 'undefined') return;
        const params = new URLSearchParams(window.location.search);
        const status = params.get('status');
        const sessionId = params.get('session_id');
        if (status === 'success' && sessionId) setConfirmationSessionId(sessionId);
    }, []);

    const activeOffering = OFFERINGS.find((o) => o.id === selected) ?? null;
    const offerLabel = offerIntent ? OFFER_LABELS[offerIntent] ?? null : null;
    const { slots, loading: slotsLoading, error: slotsError } = useAvailableSlots(
        selectedDate,
        selected ? slotSessionType(selected) : '30'
    );

    const emailValid = EMAIL_RE.test(email.trim());
    // In brief mode the rich context came from the chat, so only name + a valid
    // email are still required; in form mode the two core questions are too.
    // Company is always optional. Scheduling stays hidden until this holds.
    const contextValid = briefNotes
        ? !!(name.trim() && emailValid)
        : !!(improve.trim() && today.trim() && name.trim() && emailValid);
    const canSubmit = !!(selected && contextValid && selectedTime);

    // Map landing aliases to the three intake paths.
    const chatPath: 'business' | 'individual' | 'training' | null =
        pathIntent === 'business' || pathIntent === 'enterprise'
            ? 'business'
            : pathIntent === 'training'
                ? 'training'
                : pathIntent === 'individual' || pathIntent === 'personal'
                    ? 'individual'
                    : null;
    // Show the chat whenever it isn't disabled, no brief is captured yet, and
    // we're not on a confirmation screen. An unknown path is fine — the chat
    // asks for it first (`chatPath` is null until then).
    const showChat = !!(useChat && !briefNotes && !freeConfirmed && !confirmationSessionId);

    const formatSlotTime = (iso: string) => {
        try {
            return new Intl.DateTimeFormat('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                timeZoneName: 'short',
            }).format(new Date(iso));
        } catch {
            return iso;
        }
    };

    // The confirmation needs the day too — the grid buttons don't, they sit under
    // a date the visitor just clicked.
    const formatSlotDateTime = (iso: string) => {
        try {
            return new Intl.DateTimeFormat('en-US', {
                weekday: 'long', month: 'long', day: 'numeric',
                hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
            }).format(new Date(iso));
        } catch {
            return iso;
        }
    };

    const buildNotes = () => {
        // Brief mode: the AI intake brief is the context; append call + company.
        if (briefNotes) {
            const extra = [
                `Call: ${activeOffering?.label ?? selected}`,
                company.trim() ? `Company: ${company.trim()}` : null,
            ].filter(Boolean).join('\n');
            return `${extra}\n\n${briefNotes}`.slice(0, 1990);
        }
        const lines = [
            `Call: ${activeOffering?.label ?? selected}`,
            pathIntent ? `Buyer path: ${pathIntent}` : null,
            offerLabel ? `Interested in: ${offerLabel}` : (offerIntent ? `Interested in: ${offerIntent}` : null),
            company.trim() ? `Company: ${company.trim()}` : null,
            '',
            `What are you trying to improve?\n${improve.trim()}`,
            '',
            `What happens today?\n${today.trim()}`,
        ].filter((l) => l !== null);
        return lines.join('\n').slice(0, 1990);
    };

    // Chat completed: attach the reviewed brief + its signed session and preselect
    // the universal free first call. Persistence happens at book time (once
    // name/email exist) so the stored row can carry contact + booking id.
    const handleBriefReady = (notes: string, _recommendedNextStep: string, brief: Brief, session: string | null) => {
        setBriefNotes(notes);
        setBriefObj(brief);
        setBriefSession(session);
        setSelected('fit');
        setUseChat(false);
    };

    // A2UI calendar handoff: every intake path is a free 30-minute first call.
    // Attach the brief and flow the picked slot into the normal confirm step.
    const handleCalendarPick = ({ date, time, notes, brief, session }: {
        date: string; time: string; sessionType: 'fit' | '30' | '60';
        notes: string; brief: Brief; session: string | null;
    }) => {
        setBriefNotes(notes);
        setBriefObj(brief);
        setBriefSession(session);
        setSelected('fit');
        setSelectedDate(date);
        setSelectedTime(time);
        setUseChat(false);
        // The chat's CTA already reads "Book the free 30-min call", so the handoff
        // must complete the booking — not park the prospect on a second button.
        setAutoBook(true);
    };

    // A2UI contact handoff: the chat's contact block fills the page's own
    // name/email/company state (same fields the guided form owns).
    const handleContact = ({ name: n, email: e, company: c }: { name: string; email: string; company: string }) => {
        if (n) setName(n);
        if (e) setEmail(e);
        if (c) setCompany(c);
    };

    // Chat/endpoint failure: switch to the guided form and carry over whatever
    // the agent captured so the prospect doesn't retype it.
    const handleChatFallback = (partial?: Brief) => {
        if (partial) {
            if (partial.desired_outcome && !improve.trim()) setImprove(partial.desired_outcome);
            if (partial.current_workflow && !today.trim()) setToday(partial.current_workflow);
        }
        setFallbackNotice(true);
        setUseChat(false);
    };

    // Persist the reviewed brief (requires the signed session). Returns brief_id
    // to attach to the booking, or null. Best-effort — never blocks the funnel.
    const persistBrief = async (backendUrl: string, bookingId?: string): Promise<string | null> => {
        if (!briefSession || !briefObj) return null;
        try {
            const res = await fetch(`${backendUrl}/api/intake/brief`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session: briefSession,
                    brief: briefObj,
                    name: name.trim() || null,
                    email: email.trim() || null,
                    recommended_next_step: selected === 'fit' || selected === '30' || selected === '60' ? selected : null,
                    booking_id: bookingId || null,
                }),
            });
            if (!res.ok) return null;
            const data = await res.json();
            return data.brief_id ?? null;
        } catch {
            return null;
        }
    };

    const handleBook = async () => {
        if (!canSubmit || !selected || !selectedTime) return;
        setIsSubmitting(true);
        setError(null);
        try {
            const backendUrl = configService.getBackendUrl().replace(/\/$/, '');
            const notes = buildNotes();
            // Persist the reviewed brief first (chat path only) so the booking can
            // reference it and the stored row carries contact info.
            const intakeBriefId = await persistBrief(backendUrl);

            if (selected === 'fit') {
                // Free first call — direct booking, no payment.
                const res = await fetch(`${backendUrl}/api/booking/free`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ slot_start: selectedTime, name, email, notes, intake_brief_id: intakeBriefId }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.detail || `Booking failed (${res.status})`);
                }
                const data = await res.json();
                setFreeConfirmed({
                    slot: selectedTime,
                    meetLink: data.meet_link,
                    // Older responses have no notification_status; absent means
                    // "unknown", which we treat as sent rather than alarming.
                    emailSent: data.notification_status?.requestor_email !== 'failed',
                });
            } else {
                // Paid working session — Stripe checkout (guest, no sign-in).
                const res = await fetch(`${backendUrl}/api/booking/checkout`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_type: selected, slot_start: selectedTime, name, email, notes, intake_brief_id: intakeBriefId }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.detail || `Booking failed (${res.status})`);
                }
                const { url } = await res.json();
                if (url) window.location.href = url;
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Booking failed. Please try again.');
        } finally {
            setIsSubmitting(false);
        }
    };

    // One-tap booking from the chat: the slot and contact details arrive in the
    // same click, so wait for them to validate, then submit exactly once.
    useEffect(() => {
        if (!autoBook || isSubmitting || freeConfirmed || !canSubmit) return;
        setAutoBook(false);
        void handleBook();
    }, [autoBook, canSubmit, isSubmitting, freeConfirmed]);

    const seo = useMemo(() => ({
        title: 'Book an AI Agent System Call | Yanqing Jiang',
        description:
            'Book a free 30-minute call with Yanqing Jiang, AI agent system builder — enterprise agent workflows, a personal agent OS, or hands-on training on the agentic stack. No sign-in required.',
    }), []);

    // Stripe redirect confirmation view
    if (confirmationSessionId) {
        return (
            <div className="min-h-[100dvh] bg-[#12110F] text-[#F1EADF] px-6" style={{ colorScheme: 'dark' }}>
                <Helmet><title>Booking Confirmed | Yanqing Jiang</title></Helmet>
                <BookingConfirmation
                    stripeSessionId={confirmationSessionId}
                    onBack={() => {
                        setConfirmationSessionId(null);
                        if (typeof window !== 'undefined') window.history.replaceState({}, '', '/consult');
                    }}
                />
            </div>
        );
    }

    const inputClass =
        'w-full bg-[#12110F] border border-[#37332E] rounded-[4px] p-4 min-h-[48px] outline-none focus:border-[#F04A32] transition-colors text-[#F1EADF] placeholder-[#A8A096]';

    return (
        <div className="min-h-[100dvh] bg-[#12110F] text-[#F1EADF] antialiased" style={{ colorScheme: 'dark' }}>
            <Helmet>
                <title>{seo.title}</title>
                <meta name="description" content={seo.description} />
                <meta property="og:type" content="website" />
                <meta property="og:title" content="From Business Question to Action—Without a Dashboard" />
                <meta property="og:description" content="See how agent systems turn business questions into SQL, charts, insights, and action—with humans in the loop." />
                <meta property="og:url" content="https://yanqing.app/consult" />
                <meta property="og:image" content={DEFAULT_OG_IMAGE} />
                <meta property="og:image:width" content="1200" />
                <meta property="og:image:height" content="630" />
                <meta property="og:image:alt" content="AI agent system builder." />
                <meta name="twitter:card" content="summary_large_image" />
                <meta name="twitter:image" content={DEFAULT_OG_IMAGE} />
                <link rel="canonical" href="https://yanqing.app/consult" />
            </Helmet>

            {/* Minimal nav back to landing */}
            <header className="sticky top-0 z-50 border-b border-[#37332E] bg-[#12110F]/90 backdrop-blur-md">
                <nav className="mx-auto flex h-16 max-w-[1080px] items-center justify-between px-6">
                    <Link to="/" className="text-[15px] font-bold tracking-tight text-[#F1EADF]">Yanqing Jiang</Link>
                    <Link to="/" className="text-[14px] text-[#A8A096] hover:text-[#F1EADF]">← Back to site</Link>
                </nav>
            </header>

            {/* Hero */}
            <section className="mx-auto max-w-[1080px] px-6 pt-16 pb-10 sm:pt-24">
                <h1 className="font-black tracking-[-0.045em] text-[#F1EADF]" style={{ fontSize: 'clamp(40px, 8vw, 84px)' }}>
                    Book the right conversation<span className="text-[#F04A32]">.</span>
                </h1>
                <p className="mt-6 max-w-[54ch] text-[18px] leading-[1.5] text-[#A8A096]">
                    Answer 2 quick questions to book time with me — my intake agent handles the booking.
                </p>
            </section>

            {/* AI Brief Agent — chat-first intake (Phase 2). The path fork lives
                INSIDE the chat now: with no ?path= intent it opens by asking
                "What are you trying to improve?" as tappable choices. */}
            {showChat && (
                <section className="mx-auto max-w-[1080px] px-6 pb-8">
                    <IntakeChat
                        path={chatPath}
                        onComplete={handleBriefReady}
                        onFallback={handleChatFallback}
                        onPathSelect={(p) => { setPathIntent(p); setSelected('fit'); setSelectedTime(null); setFreeConfirmed(null); }}
                        onCalendarPick={handleCalendarPick}
                        onContact={handleContact}
                    />
                    <p className="mt-6 text-[14px] text-[#A8A096]">
                        <button onClick={() => { setSelected(selected ?? 'fit'); setUseChat(false); }} className="font-semibold text-[#F1EADF] underline decoration-[#F04A32] decoration-2 underline-offset-4">
                            Rather not chat? Use the quick form →
                        </button>
                    </p>
                </section>
            )}

            {/* Offering cards */}
            {!showChat && (
            <section className="mx-auto max-w-[1080px] px-6 pb-4">
                {fallbackNotice && (
                    <p className="mb-6 inline-block rounded-[4px] border border-[#37332E] bg-[#191816] px-4 py-2 text-[13px] text-[#A8A096]">
                        The intake agent is temporarily unavailable — use the quick form below. Anything you already told the agent is carried over.
                    </p>
                )}
                {briefNotes && (
                    <p className="mb-6 inline-block rounded-[4px] border border-[#F04A32]/40 bg-[#191816] px-4 py-2 text-[13px] text-[#F1EADF]">
                        ✓ Your brief is ready and will be attached to the booking. Choose a call and time below.
                    </p>
                )}
                {!briefNotes && offerLabel && (
                    <p className="mb-6 inline-block rounded-[4px] border border-[#37332E] bg-[#191816] px-4 py-2 text-[13px] text-[#A8A096]">
                        You're here about <span className="font-semibold text-[#F1EADF]">{offerLabel}</span>. Pick a call below — I'll have the context.
                    </p>
                )}
                <div className="grid gap-5 sm:grid-cols-3">
                    {OFFERINGS.map((o) => {
                        const active = selected === o.id;
                        return (
                            <button
                                key={o.id}
                                onClick={() => {
                                    setSelected(o.id);
                                    setSelectedTime(null);
                                    setFreeConfirmed(null);
                                }}
                                className={`text-left rounded-[6px] border p-6 transition-colors ${
                                    active
                                        ? 'border-[#F04A32] bg-[#191816]'
                                        : 'border-[#37332E] bg-[#191816]/40 hover:border-[#A8A096]/50'
                                }`}
                            >
                                <div className="flex items-baseline justify-between">
                                    <p className="text-[12px] uppercase tracking-[0.2em] text-[#A8A096]">{o.duration}</p>
                                    {active && <CheckCircle2 className="h-5 w-5 text-[#F04A32]" />}
                                </div>
                                <h3 className="mt-3 text-[20px] font-bold text-[#F1EADF]">{o.label}</h3>
                                <p className="mt-2 text-[28px] font-black tracking-[-0.02em] text-[#F1EADF]">
                                    {o.priceLabel}
                                    {!o.free && <span className="ml-1 text-[13px] font-normal text-[#A8A096]">USD</span>}
                                </p>
                                <p className="mt-3 text-[14px] leading-[1.5] text-[#A8A096]">{o.blurb}</p>
                                <ul className="mt-4 space-y-1.5">
                                    {o.features.map((f) => (
                                        <li key={f} className="text-[13px] text-[#A8A096]">— {f}</li>
                                    ))}
                                </ul>
                            </button>
                        );
                    })}
                </div>
                <p className="mt-5 text-[14px] text-[#A8A096]">Builds receive a fixed proposal after scoping.</p>
            </section>
            )}

            {/* Context form + scheduling */}
            <AnimatePresence>
                {activeOffering && !freeConfirmed && !showChat && (
                    <motion.section
                        initial={{ opacity: 0, y: 24 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="mx-auto max-w-[1080px] px-6 py-12"
                    >
                        <div className="grid gap-12 lg:grid-cols-2">
                            {/* Context — brief attached (from chat) OR the guided form */}
                            {briefNotes ? (
                                <div className="space-y-4">
                                    <div>
                                        <h2 className="text-[22px] font-bold text-[#F1EADF]">Your details</h2>
                                        <p className="mt-2 text-[13px] text-[#A8A096]">
                                            Your intake brief is attached. Just add your name and email so Yanqing can reach you.
                                        </p>
                                    </div>
                                    <div className="grid gap-4 sm:grid-cols-2">
                                        <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                                            maxLength={100} className={inputClass} placeholder="Name" />
                                        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                                            className={inputClass} placeholder="Email" />
                                    </div>
                                    <input type="text" value={company} onChange={(e) => setCompany(e.target.value)}
                                        maxLength={120} className={inputClass} placeholder="Company (optional)" />
                                    <details className="rounded-[6px] border border-[#37332E] bg-[#191816]/40 p-4">
                                        <summary className="cursor-pointer text-[13px] font-semibold text-[#A8A096]">Review the brief being sent</summary>
                                        <pre className="mt-3 whitespace-pre-wrap font-sans text-[13px] leading-[1.5] text-[#A8A096]">{briefNotes}</pre>
                                    </details>
                                    <button onClick={() => { setBriefNotes(null); setUseChat(true); }} className="text-[13px] text-[#A8A096] hover:text-[#F1EADF]">
                                        ← Reopen the intake chat
                                    </button>
                                </div>
                            ) : (
                            <div className="space-y-4">
                                <div>
                                    <h2 className="text-[22px] font-bold text-[#F1EADF]">Add the context</h2>
                                    <p className="mt-2 text-[13px] text-[#A8A096]">
                                        Keep details high level. Do not include confidential data or credentials.
                                    </p>
                                </div>
                                <FormField label="What are you trying to improve?" required>
                                    <textarea rows={2} value={improve} onChange={(e) => setImprove(e.target.value)}
                                        maxLength={600} className={inputClass + ' resize-none'}
                                        placeholder="The process, system, or outcome you want to change" />
                                </FormField>
                                <FormField label="What happens today?" required>
                                    <textarea rows={2} value={today} onChange={(e) => setToday(e.target.value)}
                                        maxLength={600} className={inputClass + ' resize-none'}
                                        placeholder="How it works now, who does it, roughly how long it takes" />
                                </FormField>
                                <div className="grid gap-4 sm:grid-cols-2">
                                    <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                                        maxLength={100} className={inputClass} placeholder="Name *" aria-label="Name (required)" />
                                    <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                                        className={inputClass} placeholder="Email *" aria-label="Email (required)" />
                                </div>
                                <input type="text" value={company} onChange={(e) => setCompany(e.target.value)}
                                    maxLength={120} className={inputClass} placeholder="Company (optional)" />
                            </div>
                            )}

                            {/* Scheduling */}
                            <div className="space-y-6">
                                <div>
                                    <h2 className="text-[22px] font-bold text-[#F1EADF]">Pick a time</h2>
                                    <p className="mt-2 text-[13px] text-[#A8A096]">Mon–Fri 8am–4pm PT (selected windows) · Sat–Sun 1–4pm PT</p>
                                </div>
                                {/* The calendar is not rendered at all until the
                                    required fields are in — a dimmed-but-visible
                                    picker invited clicks that silently did nothing. */}
                                {!contextValid ? (
                                    <div className="rounded-[6px] border border-dashed border-[#37332E] bg-[#191816]/30 p-6">
                                        <p className="text-[13px] text-[#A8A096]">
                                            {briefNotes
                                                ? 'Add your name and email, then the calendar opens here.'
                                                : 'Answer the two questions and add your name and email — the calendar opens here.'}
                                        </p>
                                    </div>
                                ) : (
                                <div>
                                    <CalendarPicker
                                        selectedDate={selectedDate}
                                        onSelectDate={(d) => { setSelectedDate(d); setSelectedTime(null); }}
                                    />
                                    {selectedDate && (
                                        <div className="mt-6 space-y-3">
                                            <h3 className="flex items-center gap-2 text-[15px] font-semibold text-[#F1EADF]">
                                                <Clock className="h-4 w-4 text-[#F04A32]" /> Available times
                                            </h3>
                                            {slotsLoading ? (
                                                <div className="flex items-center gap-2 py-3 text-[#A8A096]">
                                                    <Loader2 className="h-4 w-4 animate-spin" /> Loading times…
                                                </div>
                                            ) : slotsError ? (
                                                <p className="py-3 text-[#F04A32]">Couldn't load availability. Please try again in a moment.</p>
                                            ) : slots.length === 0 ? (
                                                <p className="py-3 text-[#A8A096]">No available times for this date.</p>
                                            ) : (
                                                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                                                    {slots.map((slot) => (
                                                        <button
                                                            key={slot.start}
                                                            onClick={() => setSelectedTime(slot.start)}
                                                            className={`min-h-[44px] rounded-[4px] border px-3 py-2.5 text-[14px] font-medium transition-colors ${
                                                                selectedTime === slot.start
                                                                    ? 'border-[#F04A32] bg-[#F04A32] text-[#12110F]'
                                                                    : 'border-[#37332E] text-[#F1EADF] hover:border-[#A8A096]/60'
                                                            }`}
                                                        >
                                                            {formatSlotTime(slot.start)}
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                                )}

                                {error && <p className="text-[14px] text-[#F04A32]">{error}</p>}

                                <button
                                    onClick={handleBook}
                                    disabled={!canSubmit || isSubmitting}
                                    className="w-full rounded-[4px] bg-[#F04A32] py-4 text-[16px] font-semibold text-[#12110F] transition-colors hover:bg-[#D63B27] disabled:cursor-not-allowed disabled:opacity-40"
                                >
                                    {isSubmitting ? (
                                        <span className="flex items-center justify-center gap-2">
                                            <Loader2 className="h-5 w-5 animate-spin" /> Processing…
                                        </span>
                                    ) : selected === 'fit' ? (
                                        'Book the free 30-min call'
                                    ) : (
                                        `Confirm & pay ${activeOffering?.priceLabel}`
                                    )}
                                </button>
                                <p className="text-center text-[12px] text-[#A8A096]">
                                    {selected === 'fit'
                                        ? 'Free — no payment required.'
                                        : 'Guest checkout · secured by Stripe. Reschedule up to 2h before; full refund >24h out.'}
                                </p>
                            </div>
                        </div>
                    </motion.section>
                )}
            </AnimatePresence>

            {/* Free fit-call confirmation */}
            {freeConfirmed && (
                <section className="mx-auto max-w-[720px] px-6 py-16 text-center">
                    <CheckCircle2 className="mx-auto h-12 w-12 text-[#F04A32]" />
                    <h2 className="mt-6 text-[28px] font-black tracking-[-0.02em] text-[#F1EADF]">You're booked.</h2>
                    <p className="mt-4 text-[16px] text-[#A8A096]">
                        Your free 30-minute call is confirmed for {formatSlotDateTime(freeConfirmed.slot)}.
                        {freeConfirmed.emailSent === false
                            ? ' The calendar invite is on your calendar, but we could not send the confirmation email — save the link below.'
                            : ` A confirmation email with the calendar invite${freeConfirmed.meetLink ? ' and Google Meet link' : ''} is on its way.`}
                    </p>
                    {freeConfirmed.meetLink ? (
                        <a href={freeConfirmed.meetLink} target="_blank" rel="noopener noreferrer"
                            className="mt-6 inline-block font-semibold text-[#F04A32] hover:underline">
                            {freeConfirmed.meetLink}
                        </a>
                    ) : (
                        /* No Meet link means the room never provisioned; don't let the
                           prospect leave thinking they have a joining link. */
                        <p className="mt-6 text-[14px] text-[#A8A096]">
                            The video link is still being created — it will appear on the calendar invite.
                        </p>
                    )}
                    <div className="mt-8">
                        <Link to="/" className="text-[14px] text-[#A8A096] hover:text-[#F1EADF]">← Back to site</Link>
                    </div>
                </section>
            )}

            {/* FAQ (trimmed) */}
            <section className="mx-auto max-w-[720px] px-6 py-20">
                <h2 className="text-[24px] font-bold text-[#F1EADF]">Questions</h2>
                <div className="mt-8 divide-y divide-[#37332E] border-y border-[#37332E]">
                    {FAQ.map((item) => (
                        <div key={item.q} className="py-6">
                            <h3 className="text-[16px] font-semibold text-[#F1EADF]">{item.q}</h3>
                            <p className="mt-2 text-[15px] leading-[1.6] text-[#A8A096]">{item.a}</p>
                        </div>
                    ))}
                </div>
            </section>
        </div>
    );
};

const FormField: React.FC<{ label: string; required?: boolean; children: React.ReactNode }> = ({ label, required, children }) => (
    <label className="block">
        <span className="mb-2 block text-[13px] font-medium text-[#F1EADF]">
            {label}{required && <span className="ml-1 text-[#F04A32]" aria-hidden="true">*</span>}
        </span>
        {children}
    </label>
);

export default ConsultingPage;
