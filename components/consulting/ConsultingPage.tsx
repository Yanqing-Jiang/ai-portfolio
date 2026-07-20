import React, { useState, useEffect, useMemo } from 'react';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Loader2, CheckCircle2 } from 'lucide-react';

import { CalendarPicker } from './CalendarPicker';
import { BookingConfirmation } from './BookingConfirmation';
import { useAvailableSlots } from './useAvailableSlots';
import { configService } from '@/services/config';

/*
 * /consult — Phase 1 "Prices on the door" booking.
 * De-walled: no sign-in required. Visible pricing ($50/$90, kept exactly).
 * Enterprise fit call is FREE. A short REQUIRED context form runs before the
 * calendar; its answers ride in `notes` and are copied to both intake
 * recipients server-side (D5). Locked visual system: charcoal / bone /
 * single vermilion accent — no blue, purple, or amber.
 */

// 'fit' = free enterprise fit call (30 min). '30'/'60' = paid working sessions.
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
        label: 'Enterprise fit call',
        duration: '30 min',
        priceLabel: 'Free',
        free: true,
        blurb: 'A qualification call for teams. We confirm the problem is a fit, and what a scoped build would look like.',
        features: ['Is this a fit?', 'Rough shape of a build', 'What scoping would cost'],
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
        a: "You'll receive a confirmation email with a Google Meet link and a calendar invitation. The enterprise fit call is free; working sessions are paid at booking.",
    },
    {
        q: 'Can I reschedule or cancel?',
        a: 'Just reply to your confirmation email. You can reschedule up to 2 hours before your session. Cancellations more than 24 hours before receive a full refund.',
    },
    {
        q: 'What about a full build?',
        a: 'Builds receive a fixed proposal after scoping — no hourly meter. Start with a fit call or a working session and we size it from the actual problem.',
    },
];

const slotSessionType = (offering: Offering): '30' | '60' => (offering === '60' ? '60' : '30');

// Buyer intent carried from the landing offer CTAs (?offer=...).
const OFFER_LABELS: Record<string, string> = {
    pipeline: 'Enterprise agentic pipelines',
    'delivery-team': 'Embedded AI delivery team',
    'personal-agent': 'Personal agent OS',
    website: 'Zero-maintenance personal website',
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const ConsultingPage: React.FC = () => {
    const [selected, setSelected] = useState<Offering | null>(null);

    // Required context form
    const [improve, setImprove] = useState('');
    const [today, setToday] = useState('');
    const [useful, setUseful] = useState('');
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [company, setCompany] = useState('');

    // Buyer intent from landing (?path=&offer=), preserved into notes/preselect.
    const [pathIntent, setPathIntent] = useState<string | null>(null);
    const [offerIntent, setOfferIntent] = useState<string | null>(null);

    // Scheduling
    const [selectedDate, setSelectedDate] = useState<string | null>(null);
    const [selectedTime, setSelectedTime] = useState<string | null>(null);

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [freeConfirmed, setFreeConfirmed] = useState<{ slot: string; meetLink?: string | null } | null>(null);
    const [confirmationSessionId, setConfirmationSessionId] = useState<string | null>(null);

    // Preselect path from landing (?path=enterprise|individual&offer=...)
    useEffect(() => {
        if (typeof window === 'undefined') return;
        const params = new URLSearchParams(window.location.search);
        const path = params.get('path');
        const offer = params.get('offer');
        if (path) setPathIntent(path);
        if (offer) setOfferIntent(offer);
        // Preselect the offering. Offer intent is finer-grained than path:
        // pipeline/delivery-team are enterprise (free fit call); personal-agent
        // and website are individual (working session).
        if (offer === 'personal-agent' || offer === 'website' || path === 'individual') setSelected('30');
        else if (offer === 'pipeline' || offer === 'delivery-team' || path === 'enterprise') setSelected('fit');
        const context = params.get('context');
        if (context === 'invoice-reconciliation') {
            setImprove('An invoice reconciliation / AP workflow similar to the case study.');
        }
        // Stripe redirect confirmation
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
    const contextValid = !!(improve.trim() && today.trim() && useful.trim() && name.trim() && emailValid);
    const canSubmit = !!(selected && contextValid && selectedTime);

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

    const buildNotes = () => {
        const lines = [
            `Call: ${activeOffering?.label ?? selected}`,
            pathIntent ? `Buyer path: ${pathIntent}` : null,
            offerLabel ? `Interested in: ${offerLabel}` : (offerIntent ? `Interested in: ${offerIntent}` : null),
            company.trim() ? `Company: ${company.trim()}` : null,
            '',
            `What are you trying to improve?\n${improve.trim()}`,
            '',
            `What happens today?\n${today.trim()}`,
            '',
            `What would make the conversation useful?\n${useful.trim()}`,
        ].filter((l) => l !== null);
        return lines.join('\n').slice(0, 1990);
    };

    const handleBook = async () => {
        if (!canSubmit || !selected || !selectedTime) return;
        setIsSubmitting(true);
        setError(null);
        try {
            const backendUrl = configService.getBackendUrl().replace(/\/$/, '');
            const notes = buildNotes();

            if (selected === 'fit') {
                // Free enterprise fit call — direct booking, no payment.
                const res = await fetch(`${backendUrl}/api/booking/free`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ slot_start: selectedTime, name, email, notes }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.detail || `Booking failed (${res.status})`);
                }
                const data = await res.json();
                setFreeConfirmed({ slot: selectedTime, meetLink: data.meet_link });
            } else {
                // Paid working session — Stripe checkout (guest, no sign-in).
                const res = await fetch(`${backendUrl}/api/booking/checkout`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_type: selected, slot_start: selectedTime, name, email, notes }),
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

    const seo = useMemo(() => ({
        title: 'Start an AI System Project | Yanqing Jiang',
        description:
            'Book the right conversation with Yanqing Jiang: a free enterprise fit call or a paid working session. Prices and availability are visible — no sign-in required.',
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
                <meta property="og:title" content={seo.title} />
                <meta property="og:description" content={seo.description} />
                <meta property="og:url" content="https://yanqing.app/consult" />
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
                    Choose a call, add the context first, and the time starts with your problem — not introductions.
                </p>
                <p className="mt-4 text-[13px] text-[#A8A096]">No sign-in. Prices and availability are visible.</p>
            </section>

            {/* Offering cards */}
            <section className="mx-auto max-w-[1080px] px-6 pb-4">
                {offerLabel && (
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

            {/* Context form + scheduling */}
            <AnimatePresence>
                {activeOffering && !freeConfirmed && (
                    <motion.section
                        initial={{ opacity: 0, y: 24 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="mx-auto max-w-[1080px] px-6 py-12"
                    >
                        <div className="grid gap-12 lg:grid-cols-2">
                            {/* Required context */}
                            <div className="space-y-4">
                                <div>
                                    <h2 className="text-[22px] font-bold text-[#F1EADF]">Add the context</h2>
                                    <p className="mt-2 text-[13px] text-[#A8A096]">
                                        Keep details high level. Do not include confidential data or credentials.
                                    </p>
                                </div>
                                <FormField label="What are you trying to improve?">
                                    <textarea rows={2} value={improve} onChange={(e) => setImprove(e.target.value)}
                                        maxLength={600} className={inputClass + ' resize-none'}
                                        placeholder="The process, system, or outcome you want to change" />
                                </FormField>
                                <FormField label="What happens today?">
                                    <textarea rows={2} value={today} onChange={(e) => setToday(e.target.value)}
                                        maxLength={600} className={inputClass + ' resize-none'}
                                        placeholder="How it works now, who does it, roughly how long it takes" />
                                </FormField>
                                <FormField label="What would make the conversation useful?">
                                    <textarea rows={2} value={useful} onChange={(e) => setUseful(e.target.value)}
                                        maxLength={600} className={inputClass + ' resize-none'}
                                        placeholder="What you'd want to walk away with" />
                                </FormField>
                                <div className="grid gap-4 sm:grid-cols-2">
                                    <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                                        maxLength={100} className={inputClass} placeholder="Name" />
                                    <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                                        className={inputClass} placeholder="Email" />
                                </div>
                                <input type="text" value={company} onChange={(e) => setCompany(e.target.value)}
                                    maxLength={120} className={inputClass} placeholder="Company (optional)" />
                            </div>

                            {/* Scheduling */}
                            <div className="space-y-6">
                                <div>
                                    <h2 className="text-[22px] font-bold text-[#F1EADF]">Pick a time</h2>
                                    <p className="mt-2 text-[13px] text-[#A8A096]">Mon–Fri 1–5pm PT · Sat–Sun 1–4:30pm PT</p>
                                </div>
                                {!contextValid && (
                                    <p className="text-[13px] text-[#A8A096]">Fill in the context on the left to unlock scheduling.</p>
                                )}
                                <div className={contextValid ? '' : 'pointer-events-none opacity-40'}>
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
                                        'Book the free fit call'
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
                        Your free enterprise fit call is confirmed for {formatSlotTime(freeConfirmed.slot)}. A
                        confirmation email with the calendar invite{freeConfirmed.meetLink ? ' and Google Meet link' : ''} is on its way.
                    </p>
                    {freeConfirmed.meetLink && (
                        <a href={freeConfirmed.meetLink} target="_blank" rel="noopener noreferrer"
                            className="mt-6 inline-block font-semibold text-[#F04A32] hover:underline">
                            {freeConfirmed.meetLink}
                        </a>
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

const FormField: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
    <label className="block">
        <span className="mb-2 block text-[13px] font-medium text-[#F1EADF]">{label}</span>
        {children}
    </label>
);

export default ConsultingPage;
