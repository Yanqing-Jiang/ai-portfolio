import React, { useState, useEffect } from 'react';
// @ts-ignore
import { Helmet } from 'react-helmet-async';
import { motion, AnimatePresence } from 'framer-motion';
import { Calendar as CalendarIcon, Clock, ShieldCheck, HelpCircle, Loader2, LogIn } from 'lucide-react';

import { SessionTypeCard } from './SessionTypeCard';
import { CalendarPicker } from './CalendarPicker';
import { BookingConfirmation } from './BookingConfirmation';
import { useAvailableSlots } from './useAvailableSlots';
import { MyBookingsSection } from './MyBookingsSection';
import { configService } from '@/services/config';
import { authService, type AuthState } from '@/services/auth';
import { AuthModal } from '@/components/AuthModal';

type SessionType = '30' | '60';

const SESSIONS = [
  {
    title: 'Discovery Call',
    duration: '30' as SessionType,
    price: 50,
    features: ['Technical Q&A', 'Career Roadmap', 'Quick Architecture Review'],
  },
  {
    title: 'Strategic Deep Dive',
    duration: '60' as SessionType,
    price: 90,
    features: ['Full Product Roadmap', 'Code & Architecture Review', 'Agent Implementation Strategy'],
  },
];

const FAQ = [
  {
    q: 'What happens after I book?',
    a: 'You\'ll receive an instant confirmation email with a Google Meet link and a calendar invitation.',
  },
  {
    q: 'Can I reschedule or cancel?',
    a: 'Sign in to manage your bookings. You can reschedule up to 2 hours before your session. Cancellations more than 24 hours before receive a full refund.',
  },
  {
    q: 'What topics can we cover?',
    a: 'AI agent architecture, Claude/OpenAI API integration, career in AI engineering, building AI products, team training, or custom implementation reviews.',
  },
];

export const ConsultingPage: React.FC = () => {
  const [selectedSession, setSelectedSession] = useState<SessionType | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedTime, setSelectedTime] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authState, setAuthState] = useState<AuthState>({ user: null, loading: true, error: null });
  const [showAuthModal, setShowAuthModal] = useState(false);

  // Subscribe to auth state
  useEffect(() => {
    const unsubscribe = authService.subscribe(setAuthState);
    return unsubscribe;
  }, []);

  // Auto-fill name/email from auth user
  useEffect(() => {
    if (authState.user) {
      const meta = authState.user.user_metadata;
      if (meta?.full_name && !name) setName(meta.full_name as string);
      if (authState.user.email && !email) setEmail(authState.user.email);
    }
  }, [authState.user]);

  // Check URL for Stripe redirect confirmation
  const [confirmationSessionId, setConfirmationSessionId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status');
    const sessionId = params.get('session_id');
    if (status === 'success' && sessionId) {
      setConfirmationSessionId(sessionId);
    }
  }, []);

  const { slots, loading: slotsLoading } = useAvailableSlots(
    selectedDate,
    selectedSession || '30'
  );

  const selectedPrice = SESSIONS.find((s) => s.duration === selectedSession)?.price || 0;

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

  const handleBooking = async () => {
    if (!selectedSession || !selectedDate || !selectedTime || !name || !email) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const backendUrl = configService.getBackendUrl().replace(/\/$/, '');
      const res = await fetch(`${backendUrl}/api/booking/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_type: selectedSession,
          slot_start: selectedTime,
          name,
          email,
          notes: notes || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Booking failed (${res.status})`);
      }

      const { url } = await res.json();
      if (url) {
        window.location.href = url;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Booking failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const canSubmit = selectedSession && selectedDate && selectedTime && name.trim() && email.trim();

  // Show confirmation page if returning from Stripe
  if (confirmationSessionId) {
    return (
      <div className="min-h-[100dvh] bg-[#010208] text-white px-6">
        <Helmet>
          <title>Booking Confirmed | Yanqing Jiang</title>
        </Helmet>
        <BookingConfirmation
          stripeSessionId={confirmationSessionId}
          onBack={() => {
            setConfirmationSessionId(null);
            if (typeof window !== 'undefined') {
              window.history.replaceState({}, '', '/consult');
            }
          }}
        />
      </div>
    );
  }

  return (
    <div className="min-h-[100dvh] bg-[#010208] text-white overflow-x-hidden selection:bg-blue-500/30">
      <Helmet>
        <title>AI Consulting | Yanqing Jiang</title>
        <meta
          name="description"
          content="Book a 1:1 AI consulting session with Yanqing Jiang. Discuss agent architecture, AI engineering careers, or custom implementation. $50/30min or $90/1hr."
        />
        <meta property="og:title" content="AI Consulting | Yanqing Jiang" />
        <meta
          property="og:description"
          content="Expert 1:1 AI strategy and consulting sessions. Agent architecture, AI careers, and implementation reviews."
        />
        <meta property="og:url" content="https://yanqing.app/consult" />
        <link rel="canonical" href="https://yanqing.app/consult" />
      </Helmet>

      {/* Hero */}
      <section className="relative px-6 pt-24 sm:pt-32 pb-16 sm:pb-20">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/3 w-[400px] h-[400px] bg-blue-500/5 blur-[120px] rounded-full" />
          <div className="absolute bottom-1/4 right-1/4 w-[300px] h-[300px] bg-purple-500/5 blur-[100px] rounded-full" />
        </div>
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-3xl sm:text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-b from-white to-white/60 bg-clip-text text-transparent"
          >
            Expert AI Strategy & Consulting
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-base sm:text-lg text-slate-400 mb-8 max-w-2xl mx-auto leading-relaxed"
          >
            Accelerate your AI journey. Book a 1:1 strategy session to discuss agent architecture,
            AI engineering careers, or custom implementation.
          </motion.p>
        </div>
      </section>

      {/* My Bookings / Sign-in prompt */}
      {authState.user ? (
        <MyBookingsSection user={authState.user} />
      ) : (
        <section className="px-6 pb-8 max-w-5xl mx-auto">
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-5 sm:p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-slate-400 text-sm text-center sm:text-left">
              Sign in to view and manage your bookings
            </p>
            <button
              onClick={() => setShowAuthModal(true)}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 rounded-xl
                         text-white text-sm font-medium transition-colors whitespace-nowrap"
            >
              <LogIn className="w-4 h-4" />
              Sign In
            </button>
          </div>
        </section>
      )}

      {/* Session Cards */}
      <section className="px-6 pb-12 max-w-5xl mx-auto">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          {SESSIONS.map((s) => (
            <SessionTypeCard
              key={s.duration}
              title={s.title}
              duration={s.duration}
              price={s.price}
              features={s.features}
              active={selectedSession === s.duration}
              onSelect={() => {
                setSelectedSession(s.duration);
                setSelectedTime(null);
              }}
            />
          ))}
        </div>
      </section>

      {/* Calendar & Booking Form */}
      <AnimatePresence>
        {selectedSession && (
          <motion.section
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="px-6 py-12 sm:py-16 bg-white/[0.01] border-t border-white/[0.05]"
          >
            <div className="max-w-6xl mx-auto">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16">
                {/* Calendar */}
                <div className="space-y-6">
                  <h3 className="text-xl sm:text-2xl font-bold flex items-center gap-3">
                    <CalendarIcon className="w-6 h-6 text-blue-400" /> Select a Date
                  </h3>
                  <p className="text-sm text-slate-400">
                    Sessions available Monday-Friday in Pacific Time
                  </p>
                  <CalendarPicker
                    selectedDate={selectedDate}
                    onSelectDate={(d) => {
                      setSelectedDate(d);
                      setSelectedTime(null);
                    }}
                  />
                </div>

                {/* Time Slots & Form */}
                <div className="space-y-8">
                  {/* Time slots */}
                  {selectedDate && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="space-y-4"
                    >
                      <h3 className="text-xl sm:text-2xl font-bold flex items-center gap-3">
                        <Clock className="w-6 h-6 text-purple-400" /> Available Times
                      </h3>
                      {slotsLoading ? (
                        <div className="flex items-center gap-2 text-slate-400 py-4">
                          <Loader2 className="w-4 h-4 animate-spin" /> Loading times...
                        </div>
                      ) : slots.length === 0 ? (
                        <p className="text-slate-400 py-4">No available times for this date.</p>
                      ) : (
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                          {slots.map((slot) => (
                            <motion.button
                              key={slot.start}
                              whileTap={{ scale: 0.95 }}
                              onClick={() => setSelectedTime(slot.start)}
                              className={`py-3 px-4 rounded-xl border text-sm font-medium transition-all min-h-[44px] ${
                                selectedTime === slot.start
                                  ? 'bg-blue-600 border-blue-500 text-white'
                                  : 'border-white/10 bg-white/5 hover:border-blue-500/50 text-slate-300'
                              }`}
                            >
                              {formatSlotTime(slot.start)}
                            </motion.button>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  )}

                  {/* Booking form */}
                  {selectedTime && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="space-y-4 pt-6 border-t border-white/10"
                    >
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-xl p-4 min-h-[48px] outline-none focus:ring-2 ring-blue-500/50 transition-all text-white placeholder-slate-500"
                        placeholder="Name"
                        maxLength={100}
                      />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-xl p-4 min-h-[48px] outline-none focus:ring-2 ring-blue-500/50 transition-all text-white placeholder-slate-500"
                        placeholder="Email address"
                      />
                      <textarea
                        rows={3}
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        maxLength={500}
                        className="w-full bg-white/5 border border-white/10 rounded-xl p-4 outline-none focus:ring-2 ring-blue-500/50 transition-all text-white placeholder-slate-500 resize-none"
                        placeholder="What would you like to discuss? (optional)"
                      />

                      {error && (
                        <p className="text-red-400 text-sm">{error}</p>
                      )}

                      <button
                        onClick={handleBooking}
                        disabled={!canSubmit || isSubmitting}
                        className="w-full py-4 bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl font-bold text-lg shadow-xl shadow-blue-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                      >
                        {isSubmitting ? (
                          <span className="flex items-center justify-center gap-2">
                            <Loader2 className="w-5 h-5 animate-spin" /> Processing...
                          </span>
                        ) : (
                          `Confirm & Pay $${selectedPrice}`
                        )}
                      </button>
                      <p className="text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                        <ShieldCheck className="w-4 h-4" /> Secured by Stripe Payments
                      </p>
                    </motion.div>
                  )}
                </div>
              </div>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      {/* FAQ */}
      <section className="px-6 py-20 sm:py-24 max-w-4xl mx-auto">
        <h2 className="text-2xl sm:text-3xl font-bold mb-12 text-center flex items-center justify-center gap-3">
          <HelpCircle className="w-7 h-7 text-blue-400" /> Frequently Asked Questions
        </h2>
        <div className="space-y-4">
          {FAQ.map((item) => (
            <div
              key={item.q}
              className="p-6 sm:p-8 rounded-2xl bg-white/[0.03] border border-white/10"
            >
              <h4 className="text-lg font-bold mb-2">{item.q}</h4>
              <p className="text-slate-400 leading-relaxed text-sm sm:text-base">{item.a}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Auth Modal */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
      />
    </div>
  );
};

export default ConsultingPage;
