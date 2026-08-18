import React, { useState } from 'react';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Loader2, CheckCircle2 } from 'lucide-react';

import { CalendarPicker } from './CalendarPicker';
import { useAvailableSlots } from './useAvailableSlots';
import { configService } from '@/services/config';

/*
 * /meet — unlisted direct-scheduling page for recruiters, HR, and personal
 * contacts. No intake chat, no offering fork, no payment: one 30-minute call
 * booked straight against real calendar availability via the same
 * POST /api/booking/free path as /consult's free call. The page is shared by
 * link only: it is deliberately absent from the nav, the prerender route list,
 * and the sitemap, and carries a noindex meta. Same locked visual system as
 * /consult: charcoal / bone / single vermilion accent.
 */

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const MeetPage: React.FC = () => {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [company, setCompany] = useState('');
    const [reason, setReason] = useState('');

    const [selectedDate, setSelectedDate] = useState<string | null>(null);
    const [selectedTime, setSelectedTime] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [confirmed, setConfirmed] = useState<{
        slot: string; meetLink?: string | null; emailSent?: boolean;
    } | null>(null);

    const { slots, loading: slotsLoading, error: slotsError, bookable } = useAvailableSlots(
        selectedDate,
        '30'
    );

    const emailValid = EMAIL_RE.test(email.trim());
    const contextValid = !!(name.trim() && emailValid && company.trim() && reason.trim());
    // The chosen time must still be in the *current* successful response —
    // a leftover pick from another date would submit against availability
    // nobody has verified.
    const timeStillOffered = !!selectedTime && slots.some((s) => s.start === selectedTime);
    const canSubmit = !!(
        contextValid && timeStillOffered &&
        bookable && !slotsLoading && !slotsError
    );

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

    const buildNotes = () =>
        [
            'Booked via /meet (direct scheduling page)',
            `Company: ${company.trim()}`,
            '',
            `What they want to discuss:\n${reason.trim()}`,
        ].join('\n').slice(0, 1990);

    const handleBook = async () => {
        if (!canSubmit || !selectedTime) return;
        setIsSubmitting(true);
        setError(null);
        try {
            const backendUrl = configService.getBackendUrl().replace(/\/$/, '');
            const res = await fetch(`${backendUrl}/api/booking/free`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    slot_start: selectedTime,
                    name: name.trim(),
                    email: email.trim(),
                    notes: buildNotes(),
                }),
            });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data.detail || `Booking failed (${res.status})`);
            }
            const data = await res.json();
            setConfirmed({
                slot: selectedTime,
                meetLink: data.meet_link,
                // Older responses have no notification_status; absent means
                // "unknown", which we treat as sent rather than alarming.
                emailSent: data.notification_status?.requestor_email !== 'failed',
            });
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Booking failed. Please try again.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const inputClass =
        'w-full bg-[#12110F] border border-[#37332E] rounded-[4px] p-4 min-h-[48px] outline-none focus:border-[#F04A32] transition-colors text-[#F1EADF] placeholder-[#A8A096]';

    return (
        <div className="min-h-[100dvh] bg-[#12110F] text-[#F1EADF] antialiased" style={{ colorScheme: 'dark' }}>
            <Helmet>
                <title>Book Time with Yanqing Jiang</title>
                <meta name="description" content="Pick a time that works and get a Google Meet invite — synced with Yanqing's real calendar." />
                {/* Unlisted: shared by link only, never crawled. */}
                <meta name="robots" content="noindex, nofollow" />
            </Helmet>

            {/* Minimal nav back to landing */}
            <header className="sticky top-0 z-50 border-b border-[#37332E] bg-[#12110F]/90 backdrop-blur-md">
                <nav className="mx-auto flex h-16 max-w-[1080px] items-center justify-between px-6">
                    <Link to="/" className="text-[15px] font-bold tracking-tight text-[#F1EADF]">Yanqing Jiang</Link>
                    <Link to="/" className="text-[14px] text-[#A8A096] hover:text-[#F1EADF]">← Back to site</Link>
                </nav>
            </header>

            {!confirmed && (
                <>
                    {/* Hero */}
                    <section className="mx-auto max-w-[1080px] px-6 pt-16 pb-10 sm:pt-24">
                        <h1 className="font-black tracking-[-0.045em] text-[#F1EADF]" style={{ fontSize: 'clamp(40px, 8vw, 84px)' }}>
                            Grab 30 minutes with Yanqing<span className="text-[#F04A32]">.</span>
                        </h1>
                        <p className="mt-6 max-w-[54ch] text-[18px] leading-[1.5] text-[#A8A096]">
                            Pick any open slot — it's synced with my real calendar. You'll get a
                            confirmation email with a Google Meet link and a calendar invite right away.
                        </p>
                    </section>

                    {/* Contact form + scheduling */}
                    <section className="mx-auto max-w-[1080px] px-6 py-4 pb-16">
                        <div className="grid gap-12 lg:grid-cols-2">
                            <div className="space-y-4">
                                <div>
                                    <h2 className="text-[22px] font-bold text-[#F1EADF]">Who's calling?</h2>
                                    <p className="mt-2 text-[13px] text-[#A8A096]">
                                        A line of context helps me show up prepared.
                                    </p>
                                </div>
                                <div className="grid gap-4 sm:grid-cols-2">
                                    <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                                        maxLength={100} className={inputClass} placeholder="Name *" aria-label="Name (required)" />
                                    <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                                        className={inputClass} placeholder="Email *" aria-label="Email (required)" />
                                </div>
                                <input type="text" value={company} onChange={(e) => setCompany(e.target.value)}
                                    maxLength={120} className={inputClass} placeholder="Company / organization *" aria-label="Company (required)" />
                                <label className="block">
                                    <span className="mb-2 block text-[13px] font-medium text-[#F1EADF]">
                                        What would you like to discuss?<span className="ml-1 text-[#F04A32]" aria-hidden="true">*</span>
                                    </span>
                                    <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)}
                                        maxLength={1500} className={inputClass + ' resize-none'}
                                        placeholder="A role, an intro, a project — a sentence or two is plenty" />
                                </label>
                            </div>

                            {/* Scheduling */}
                            <div className="space-y-6">
                                <div>
                                    <h2 className="text-[22px] font-bold text-[#F1EADF]">Pick a time</h2>
                                </div>
                                <div>
                                    {!contextValid && (
                                        <p className="text-[13px] text-[#A8A096]">
                                            Fill in your details — then choose a date and time.
                                        </p>
                                    )}
                                    <div className={!contextValid ? 'mt-3 opacity-60' : undefined}>
                                        <CalendarPicker
                                            selectedDate={selectedDate}
                                            onSelectDate={(d) => { setSelectedDate(d); setSelectedTime(null); }}
                                            disabled={!contextValid}
                                        />
                                    </div>
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
                                            ) : !bookable ? (
                                                /* Not a missing calendar — the bookings table is down or
                                                   unreadable, so no pick can be honoured. Ask for an email. */
                                                <p className="py-3 text-[14px] leading-relaxed text-[#A8A096]">
                                                    Online scheduling is temporarily unavailable. Email{' '}
                                                    <a
                                                        href="mailto:jiangyanqing91@gmail.com?subject=Booking%20a%2030-minute%20call"
                                                        className="font-semibold text-[#F04A32] underline decoration-[#F04A32]/40 hover:decoration-[#F04A32]"
                                                    >
                                                        jiangyanqing91@gmail.com
                                                    </a>{' '}
                                                    with a couple of times that work and Yanqing will send an invite directly.
                                                </p>
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
                                            <Loader2 className="h-5 w-5 animate-spin" /> Booking…
                                        </span>
                                    ) : (
                                        'Book the call'
                                    )}
                                </button>
                            </div>
                        </div>
                    </section>
                </>
            )}

            {/* Confirmation */}
            <AnimatePresence>
                {confirmed && (
                    <motion.section
                        initial={{ opacity: 0, y: 24 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mx-auto max-w-[720px] px-6 py-24 text-center"
                    >
                        <CheckCircle2 className="mx-auto h-12 w-12 text-[#F04A32]" />
                        <h2 className="mt-6 text-[28px] font-black tracking-[-0.02em] text-[#F1EADF]">You're booked.</h2>
                        <p className="mt-4 text-[16px] text-[#A8A096]">
                            Your 30-minute call is confirmed for {formatSlotDateTime(confirmed.slot)}.
                            {confirmed.emailSent === false
                                ? ' We could not send the confirmation email, so save these details — Yanqing will follow up to confirm.'
                                : ` A confirmation email with the calendar invite${confirmed.meetLink ? ' and Google Meet link' : ''} is on its way.`}
                        </p>
                        {confirmed.meetLink ? (
                            <a href={confirmed.meetLink} target="_blank" rel="noopener noreferrer"
                                className="mt-6 inline-block font-semibold text-[#F04A32] hover:underline">
                                {confirmed.meetLink}
                            </a>
                        ) : (
                            /* No Meet link means the room never provisioned. Nothing
                               retries it, so promise a person, not a mechanism —
                               Yanqing is alerted and sends the link by hand. */
                            <p className="mt-6 text-[14px] text-[#A8A096]">
                                The video link didn't generate — Yanqing will email it to you before the call.
                            </p>
                        )}
                        <div className="mt-8">
                            <Link to="/" className="text-[14px] text-[#A8A096] hover:text-[#F1EADF]">← Back to site</Link>
                        </div>
                    </motion.section>
                )}
            </AnimatePresence>
        </div>
    );
};
