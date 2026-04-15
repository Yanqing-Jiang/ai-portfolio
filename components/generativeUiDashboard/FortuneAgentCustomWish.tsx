import React, { useState, useRef } from 'react';
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion';
import { BirthdayScrollPicker } from './BirthdayScrollPicker';

// ---------------------------------------------------------------------------
// Types & Constants
// ---------------------------------------------------------------------------

interface Props {
  onBack?: () => void;
  onComplete?: (payload: {
    question: string;
    profile: {
      birthDate: string;
      birthTime: string | null;
      timeUnknown: boolean;
      gender: string;
    };
  }) => void;
}

const EARTHLY_BRANCHES = [
  { branch: '子', time: '23-01', hour: '23:00' },
  { branch: '丑', time: '01-03', hour: '01:00' },
  { branch: '寅', time: '03-05', hour: '03:00' },
  { branch: '卯', time: '05-07', hour: '05:00' },
  { branch: '辰', time: '07-09', hour: '07:00' },
  { branch: '巳', time: '09-11', hour: '09:00' },
  { branch: '午', time: '11-13', hour: '11:00' },
  { branch: '未', time: '13-15', hour: '13:00' },
  { branch: '申', time: '15-17', hour: '15:00' },
  { branch: '酉', time: '17-19', hour: '17:00' },
  { branch: '戌', time: '19-21', hour: '19:00' },
  { branch: '亥', time: '21-23', hour: '21:00' },
] as const;

const GENDER_OPTIONS = [
  { id: 'male', label: 'Male', icon: '♂' },
  { id: 'female', label: 'Female', icon: '♀' },
  { id: 'unknown', label: 'Other', icon: '—' },
] as const;

const QUESTION_SUGGESTIONS = [
  "Should I leave my job?",
  "Is this relationship worth fighting for?",
  "Will I be okay this year?",
  "Am I about to meet someone?",
];

// ---------------------------------------------------------------------------
// Atoms
// ---------------------------------------------------------------------------

function SectionHeader({ 
  title, 
  subtitle, 
  isCompleted, 
  onEdit 
}: { 
  title: string; 
  subtitle?: string; 
  isCompleted?: boolean; 
  onEdit?: () => void 
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h2 className="text-lg font-medium text-slate-100" style={{ fontFamily: 'var(--ming-font-chinese)' }}>{title}</h2>
        {subtitle && !isCompleted && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
      {isCompleted && (
        <button 
          onClick={onEdit}
          className="text-xs font-medium px-3 py-1.5 rounded-full border border-slate-700 text-slate-400 active:bg-slate-800 transition-colors"
        >
          Edit
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function FortuneAgentCustomWish({ onBack, onComplete }: Props) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [question, setQuestion] = useState('');
  const [birthDate, setBirthDate] = useState('');
  const [selectedTime, setSelectedTime] = useState<string | null>(null);
  const [timeUnknown, setTimeUnknown] = useState(false);
  const [gender, setGender] = useState('unknown');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const section1Ref = useRef<HTMLDivElement>(null!);
  const section2Ref = useRef<HTMLDivElement>(null!);
  const section3Ref = useRef<HTMLDivElement>(null!);

  const scrollTo = (ref: React.RefObject<HTMLDivElement>) => {
    setTimeout(() => {
      ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  const handleStep1Complete = () => {
    if (question.length >= 5) {
      setStep(2);
      scrollTo(section2Ref);
    }
  };

  const handleStep2Complete = () => {
    if (birthDate && (selectedTime || timeUnknown)) {
      setStep(3);
      scrollTo(section3Ref);
    }
  };

  const handleAsk = () => {
    setIsSubmitting(true);
    // Simulate ink ripple then complete
    setTimeout(() => {
      onComplete?.({
        question,
        profile: {
          birthDate,
          birthTime: selectedTime,
          timeUnknown,
          gender
        }
      });
    }, 800);
  };

  return (
    <div className="min-h-screen pb-20 select-none" style={{ background: 'var(--ming-bg, #0c0a14)', color: '#f5efe6' }}>
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          aria-label="Back"
          className="fixed right-4 z-[60] flex items-center gap-2 rounded-full border border-white/10 bg-slate-900/70 px-3.5 py-2 text-sm text-slate-300 backdrop-blur transition-colors hover:text-white"
          style={{ top: 'calc(env(safe-area-inset-top, 0px) + 16px)', minHeight: 44 }}
        >
          <span aria-hidden>←</span>
          <span>Back</span>
        </button>
      ) : null}

      {/* Sticky Mini-Header */}
      <header className="sticky top-0 z-40 w-full backdrop-blur-md bg-[#0c0a14]/80 border-b border-white/5 px-4 h-14 flex items-center justify-center">
        <div className="flex gap-1.5">
          {[1, 2, 3].map((s) => (
            <div 
              key={s} 
              className="h-1.5 w-1.5 rounded-full transition-all duration-300" 
              style={{ 
                background: step === s ? 'var(--ming-gold)' : 'rgba(255,255,255,0.1)',
                transform: step === s ? 'scale(1.2)' : 'scale(1)'
              }}
            />
          ))}
        </div>
      </header>

      <main className="max-w-[390px] mx-auto px-5 pt-6 flex flex-col gap-10">
        <LayoutGroup>
          {/* Section 1: The Question */}
          <motion.section 
            ref={section1Ref}
            layout
            className="relative"
          >
            <SectionHeader 
              title="一 · The Question" 
              isCompleted={step > 1} 
              onEdit={() => setStep(1)} 
            />
            
            <AnimatePresence mode="wait">
              {step === 1 ? (
                <motion.div
                  key="step1-active"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                >
                  {/* Suggestions Chips - Safe Area Aware */}
                  <div className="flex flex-wrap gap-2 mb-4">
                    {QUESTION_SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        onClick={() => setQuestion(s)}
                        className="text-[12px] px-3 py-2 rounded-full border border-white/10 bg-white/5 text-slate-400 active:bg-white/10 transition-colors whitespace-nowrap"
                      >
                        {s}
                      </button>
                    ))}
                  </div>

                  {/* Ink Well Textarea */}
                  <div className="relative group">
                    <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/5 to-transparent rounded-2xl pointer-events-none" />
                    <textarea
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      placeholder="Ask the old heaven anything…"
                      rows={6}
                      className="w-full bg-[#0f0d1a] border border-white/10 rounded-2xl px-5 py-6 text-lg leading-relaxed text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/30 transition-all resize-none shadow-2xl"
                      style={{ 
                        fontFamily: 'serif',
                        backgroundImage: 'radial-gradient(circle at 50% 50%, rgba(255,255,255,0.01) 0%, transparent 100%)'
                      }}
                    />
                    <div className="absolute bottom-4 right-5 text-[10px] tracking-widest text-slate-600 font-mono">
                      {question.length} CHR
                    </div>
                  </div>

                  <motion.button
                    disabled={question.length < 5}
                    onClick={handleStep1Complete}
                    className="mt-6 w-full h-[52px] rounded-xl font-medium tracking-widest uppercase text-xs transition-all disabled:opacity-30 flex items-center justify-center gap-2"
                    style={{ 
                      background: 'rgba(255,255,255,0.05)', 
                      border: '1px solid rgba(255,255,255,0.1)',
                      color: 'var(--ming-gold)'
                    }}
                    whileTap={{ scale: 0.98 }}
                  >
                    Ready
                  </motion.button>
                </motion.div>
              ) : (
                <motion.div 
                  key="step1-summary"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="bg-white/5 border border-white/5 rounded-xl p-4 italic text-slate-400 text-sm line-clamp-2"
                >
                  "{question}"
                </motion.div>
              )}
            </AnimatePresence>
          </motion.section>

          {/* Section 2: Your Profile */}
          <motion.section 
            ref={section2Ref}
            layout
            className={`relative transition-opacity duration-500 ${step < 2 ? 'opacity-20 pointer-events-none' : 'opacity-100'}`}
          >
            <SectionHeader 
              title="二 · Who's asking?" 
              isCompleted={step > 2} 
              onEdit={() => setStep(2)} 
            />

            <AnimatePresence mode="wait">
              {step === 2 ? (
                <motion.div
                  key="step2-active"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="flex flex-col gap-8"
                >
                  {/* Birthday Picker */}
                  <div className="space-y-2">
                    <label className="text-[11px] uppercase tracking-[0.2em] text-slate-500 ml-1">Birth Date</label>
                    <BirthdayScrollPicker value={birthDate} onChange={setBirthDate} />
                  </div>

                  {/* Birth Time - Earthly Branches */}
                  <div className="space-y-3">
                    <label className="text-[11px] uppercase tracking-[0.2em] text-slate-500 ml-1">Birth Time</label>
                    <div className="grid grid-cols-4 gap-2">
                      {EARTHLY_BRANCHES.map((eb) => (
                        <button
                          key={eb.branch}
                          disabled={timeUnknown}
                          onClick={() => setSelectedTime(eb.hour)}
                          className="h-[44px] rounded-lg flex flex-col items-center justify-center transition-all border"
                          style={{
                            background: selectedTime === eb.hour && !timeUnknown ? 'var(--ming-accent)' : 'rgba(255,255,255,0.03)',
                            borderColor: selectedTime === eb.hour && !timeUnknown ? 'var(--ming-accent)' : 'rgba(255,255,255,0.08)',
                            color: selectedTime === eb.hour && !timeUnknown ? '#fff' : '#94a3b8'
                          }}
                        >
                          <span className="text-base leading-none" style={{ fontFamily: 'var(--ming-font-chinese)' }}>{eb.branch}</span>
                          <span className="text-[9px] opacity-50 mt-0.5">{eb.time}</span>
                        </button>
                      ))}
                    </div>
                    
                    <button
                      onClick={() => {
                        setTimeUnknown(!timeUnknown);
                        if (!timeUnknown) setSelectedTime(null);
                      }}
                      className="w-full h-11 rounded-lg border flex items-center justify-center gap-2 text-xs transition-colors"
                      style={{
                        background: timeUnknown ? 'rgba(255,255,255,0.1)' : 'transparent',
                        borderColor: 'rgba(255,255,255,0.1)',
                        color: timeUnknown ? '#fff' : '#64748b'
                      }}
                    >
                      <div className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center transition-colors ${timeUnknown ? 'bg-indigo-500 border-indigo-500' : 'border-slate-700'}`}>
                        {timeUnknown && <div className="w-1.5 h-1.5 bg-white rounded-full" />}
                      </div>
                      I don't know my birth time
                    </button>
                  </div>

                  {/* Gender Pills */}
                  <div className="space-y-2">
                    <label className="text-[11px] uppercase tracking-[0.2em] text-slate-500 ml-1">Gender</label>
                    <div className="grid grid-cols-3 gap-2">
                      {GENDER_OPTIONS.map((opt) => (
                        <button
                          key={opt.id}
                          onClick={() => setGender(opt.id)}
                          className="h-[44px] rounded-lg flex items-center justify-center gap-2 transition-all border text-xs font-medium"
                          style={{
                            background: gender === opt.id ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.03)',
                            borderColor: gender === opt.id ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)',
                            color: gender === opt.id ? '#fff' : '#64748b'
                          }}
                        >
                          <span className="text-sm">{opt.icon}</span>
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <motion.button
                    disabled={!birthDate || (!selectedTime && !timeUnknown)}
                    onClick={handleStep2Complete}
                    className="mt-2 w-full h-[52px] rounded-xl font-medium tracking-widest uppercase text-xs transition-all disabled:opacity-30"
                    style={{ 
                      background: 'rgba(255,255,255,0.05)', 
                      border: '1px solid rgba(255,255,255,0.1)',
                      color: 'var(--ming-gold)'
                    }}
                    whileTap={{ scale: 0.98 }}
                  >
                    Confirm Profile
                  </motion.button>
                </motion.div>
              ) : step > 2 ? (
                <motion.div 
                  key="step2-summary"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="bg-white/5 border border-white/5 rounded-xl p-4 text-slate-400 text-xs flex justify-between items-center"
                >
                  <div className="flex gap-4">
                    <span>{birthDate}</span>
                    <span>{timeUnknown ? 'Time unknown' : selectedTime}</span>
                    <span className="capitalize">{gender}</span>
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </motion.section>

          {/* Section 3: Ask */}
          <motion.section 
            ref={section3Ref}
            layout
            className={`relative transition-opacity duration-500 pb-10 ${step < 3 ? 'opacity-20 pointer-events-none' : 'opacity-100'}`}
          >
            <SectionHeader title="三 · The Oracle Awaits" />

            <AnimatePresence>
              {step === 3 && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-center text-center"
                >
                  {/* Recap Card */}
                  <div className="w-full bg-[#0f0d1a] border border-white/10 rounded-3xl px-8 py-12 mb-8 shadow-2xl relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-indigo-500/20 to-transparent" />
                    
                    <span className="block text-[10px] uppercase tracking-[0.4em] text-slate-500 mb-6">Your Query</span>
                    
                    <h3 className="text-2xl leading-relaxed text-slate-100 italic" style={{ fontFamily: 'serif' }}>
                      “{question}”
                    </h3>
                    
                    <div className="mt-8 pt-8 border-t border-white/5 flex flex-col items-center gap-1">
                       <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600">Offered by</span>
                       <span className="text-xs text-slate-400">
                         {gender === 'male' ? 'A Son' : gender === 'female' ? 'A Daughter' : 'A Soul'} 
                         {' '}born on {birthDate}
                       </span>
                    </div>
                  </div>

                  {/* Submit Button with Ink Ripple Simulation */}
                  <button
                    disabled={isSubmitting}
                    onClick={handleAsk}
                    className="group relative w-full h-[64px] rounded-full overflow-hidden transition-all active:scale-95"
                    style={{ 
                      background: 'var(--ming-gold)',
                      boxShadow: '0 20px 40px -12px rgba(234, 179, 8, 0.3)'
                    }}
                  >
                    <span className={`relative z-10 flex items-center justify-center gap-3 text-black font-bold uppercase tracking-[0.2em] text-sm transition-opacity ${isSubmitting ? 'opacity-0' : 'opacity-100'}`}>
                      Ask the oracle →
                    </span>
                    
                    {/* Ripple / Loading State */}
                    {isSubmitting && (
                      <div className="absolute inset-0 flex items-center justify-center bg-black">
                        <motion.div 
                          initial={{ scale: 0, opacity: 0.8 }}
                          animate={{ scale: 4, opacity: 0 }}
                          transition={{ duration: 0.8, ease: "easeOut" }}
                          className="w-20 h-20 rounded-full bg-white/20"
                        />
                        <span className="absolute text-[10px] font-bold text-white tracking-[0.3em] uppercase">Consulting...</span>
                      </div>
                    )}
                  </button>
                  
                  <p className="mt-6 text-[10px] text-slate-500 uppercase tracking-widest leading-relaxed max-w-[200px]">
                    The answer is already written; we simply unfold it.
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.section>
        </LayoutGroup>
      </main>

      {/* Fade gradients to focus on center */}
      <div className="pointer-events-none fixed inset-0 z-0 bg-gradient-to-b from-transparent via-transparent to-black/40" />
    </div>
  );
}

export default FortuneAgentCustomWish;
