'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { BirthdayScrollPicker } from './BirthdayScrollPicker';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

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
    { id: 'unknown', label: 'Prefer not to say', icon: '—' },
] as const;

type OccasionId =
    | 'business'
    | 'wedding'
    | 'engagement'
    | 'moving'
    | 'contract'
    | 'travel';

interface OccasionDef {
    id: OccasionId;
    glyph: string;
    label: string;
    tag: string;
    accent: string; // rgb triple for accent color
    accentName: string;
}

const OCCASIONS: OccasionDef[] = [
    {
        id: 'business',
        glyph: '開',
        label: 'Business Opening',
        tag: 'launch day',
        accent: '220, 38, 38', // crimson
        accentName: 'crimson',
    },
    {
        id: 'wedding',
        glyph: '婚',
        label: 'Wedding',
        tag: 'the vows',
        accent: '212, 175, 55', // gold
        accentName: 'gold',
    },
    {
        id: 'engagement',
        glyph: '訂',
        label: 'Engagement',
        tag: 'the ring',
        accent: '225, 140, 160', // rose
        accentName: 'rose',
    },
    {
        id: 'moving',
        glyph: '搬',
        label: 'Moving',
        tag: '搬家 · new home',
        accent: '56, 72, 104', // ink
        accentName: 'ink',
    },
    {
        id: 'contract',
        glyph: '印',
        label: 'Contract Signing',
        tag: 'the seal',
        accent: '176, 127, 66', // bronze
        accentName: 'bronze',
    },
    {
        id: 'travel',
        glyph: '行',
        label: 'Travel',
        tag: 'the journey',
        accent: '88, 140, 126', // jade
        accentName: 'jade',
    },
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Profile {
    birthDate: string;
    birthTime: string | null;
    timeUnknown: boolean;
    gender: string;
}

export interface FortuneAgentLuckyDayProps {
    onBack?: () => void;
    onComplete?: (payload: {
        occasion: string;
        profile: Profile;
        windowStart: string;
        windowEnd: string;
        partner?: Profile;
    }) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MONTH_NAMES_SHORT = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

const MONTH_NAMES_LONG = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
];

function buildMonthStrip(from: Date, count: number): { key: string; year: number; month: number }[] {
    const out: { key: string; year: number; month: number }[] = [];
    const start = new Date(from.getFullYear(), from.getMonth(), 1);
    for (let i = 0; i < count; i += 1) {
        const d = new Date(start.getFullYear(), start.getMonth() + i, 1);
        out.push({
            key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`,
            year: d.getFullYear(),
            month: d.getMonth() + 1,
        });
    }
    return out;
}

function firstOfMonthISO(year: number, month: number): string {
    return `${year}-${String(month).padStart(2, '0')}-01`;
}

function lastOfMonthISO(year: number, month: number): string {
    const last = new Date(year, month, 0).getDate();
    return `${year}-${String(month).padStart(2, '0')}-${String(last).padStart(2, '0')}`;
}

function monthKeyCompare(a: string, b: string): number {
    return a < b ? -1 : a > b ? 1 : 0;
}

function summarizeWindow(startKey: string | null, endKey: string | null): string {
    if (!startKey) return 'Pick when you need the date';
    const [sy, sm] = startKey.split('-').map(Number);
    if (!endKey || endKey === startKey) {
        return `Looking in ${MONTH_NAMES_LONG[sm - 1]} ${sy}`;
    }
    const [ey, em] = endKey.split('-').map(Number);
    if (sy === ey) {
        return `Looking in ${MONTH_NAMES_LONG[sm - 1]}–${MONTH_NAMES_LONG[em - 1]} ${sy}`;
    }
    return `Looking in ${MONTH_NAMES_SHORT[sm - 1]} ${sy} – ${MONTH_NAMES_SHORT[em - 1]} ${ey}`;
}

function formatProfileSummary(p: Profile | null): string {
    if (!p || !p.birthDate) return '—';
    const t = p.timeUnknown ? 'time unknown' : p.birthTime ?? '—';
    return `${p.birthDate} · ${t} · ${p.gender}`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface SectionShellProps {
    index: number;
    title: string;
    subtitle?: string;
    isActive: boolean;
    isCompleted: boolean;
    summary?: string;
    onEdit?: () => void;
    children: React.ReactNode;
    innerRef?: React.RefObject<HTMLDivElement>;
}

function SectionShell({
    index,
    title,
    subtitle,
    isActive,
    isCompleted,
    summary,
    onEdit,
    children,
    innerRef,
}: SectionShellProps) {
    return (
        <motion.section
            ref={innerRef}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 220, damping: 24 }}
            className="mb-4 rounded-2xl border"
            style={{
                borderColor: isActive
                    ? 'rgba(212, 175, 55, 0.35)'
                    : 'rgba(148, 163, 184, 0.12)',
                background: isActive
                    ? 'rgba(20, 16, 30, 0.85)'
                    : 'rgba(16, 14, 24, 0.6)',
                boxShadow: isActive
                    ? '0 10px 40px -20px rgba(212, 175, 55, 0.25)'
                    : 'none',
            }}
        >
            <header className="flex items-start justify-between px-4 pt-4">
                <div className="flex items-baseline gap-2">
                    <span
                        className="flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold"
                        style={{
                            background: isCompleted
                                ? 'var(--ming-gold, #d4af37)'
                                : isActive
                                ? 'var(--ming-accent, #dc2626)'
                                : 'rgba(148, 163, 184, 0.15)',
                            color: isCompleted || isActive ? '#0c0a14' : '#94a3b8',
                        }}
                    >
                        {isCompleted ? '✓' : index}
                    </span>
                    <div>
                        <h2 className="text-base font-semibold text-slate-100">
                            {title}
                        </h2>
                        {subtitle && (
                            <p className="text-xs text-slate-400">{subtitle}</p>
                        )}
                    </div>
                </div>
                {isCompleted && onEdit && (
                    <button
                        onClick={onEdit}
                        className="min-h-[32px] rounded-md px-2 py-1 text-xs text-slate-300 transition-colors hover:text-[var(--ming-gold,#d4af37)]"
                        style={{ border: '1px solid rgba(148, 163, 184, 0.2)' }}
                    >
                        Edit
                    </button>
                )}
            </header>

            {isCompleted && summary && !isActive && (
                <div className="px-4 pb-3 pt-1">
                    <p className="text-sm text-slate-300">{summary}</p>
                </div>
            )}

            {isActive && <div className="px-4 pb-4 pt-3">{children}</div>}
        </motion.section>
    );
}

// Profile editor used by Section 2 and Section 4 (partner)
interface ProfileEditorProps {
    value: Profile;
    onChange: (p: Profile) => void;
    accent?: string; // rgb triple
}

function ProfileEditor({ value, onChange, accent = '212, 175, 55' }: ProfileEditorProps) {
    return (
        <div className="space-y-4">
            <div>
                <label className="mb-1 block text-sm font-medium text-slate-300">
                    Birthday
                </label>
                <BirthdayScrollPicker
                    value={value.birthDate}
                    onChange={(d) => onChange({ ...value, birthDate: d })}
                />
            </div>

            <div>
                <label className="mb-1 block text-sm font-medium text-slate-300">
                    Birth Time
                </label>
                <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-6">
                    {EARTHLY_BRANCHES.map((eb) => {
                        const selected = value.birthTime === eb.hour && !value.timeUnknown;
                        return (
                            <button
                                key={eb.branch}
                                className="flex min-h-[44px] flex-col items-center justify-center rounded-lg px-1 py-1.5 transition-colors"
                                style={{
                                    background: selected
                                        ? `rgba(${accent}, 0.9)`
                                        : 'rgba(148, 163, 184, 0.08)',
                                    border: selected
                                        ? `1px solid rgba(${accent}, 1)`
                                        : '1px solid rgba(148, 163, 184, 0.15)',
                                    color: selected ? '#fff' : '#cbd5e1',
                                }}
                                onClick={() =>
                                    onChange({
                                        ...value,
                                        birthTime: eb.hour,
                                        timeUnknown: false,
                                    })
                                }
                            >
                                <span
                                    className="text-base leading-none"
                                    style={{ fontFamily: 'var(--ming-font-chinese)' }}
                                >
                                    {eb.branch}
                                </span>
                                <span className="mt-0.5 text-[10px] opacity-60">
                                    {eb.time}
                                </span>
                            </button>
                        );
                    })}
                </div>
                <button
                    className="mt-1.5 min-h-[44px] w-full rounded-lg px-3 py-2 text-sm transition-colors"
                    style={{
                        background: value.timeUnknown
                            ? 'rgba(148, 163, 184, 0.2)'
                            : 'rgba(148, 163, 184, 0.06)',
                        border: value.timeUnknown
                            ? '1px solid rgba(148, 163, 184, 0.4)'
                            : '1px solid rgba(148, 163, 184, 0.1)',
                        color: '#94a3b8',
                    }}
                    onClick={() =>
                        onChange({
                            ...value,
                            timeUnknown: !value.timeUnknown,
                            birthTime: value.timeUnknown ? value.birthTime : null,
                        })
                    }
                >
                    {value.timeUnknown ? '✓ Time unknown' : "I don't know the time"}
                </button>
            </div>

            <div>
                <label className="mb-1 block text-sm font-medium text-slate-300">
                    Gender
                </label>
                <div className="grid grid-cols-3 gap-1.5">
                    {GENDER_OPTIONS.map((g) => {
                        const selected = value.gender === g.id;
                        return (
                            <button
                                key={g.id}
                                className="flex min-h-[44px] items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-sm transition-colors"
                                style={{
                                    background: selected
                                        ? `rgba(${accent}, 0.9)`
                                        : 'rgba(148, 163, 184, 0.08)',
                                    border: selected
                                        ? `1px solid rgba(${accent}, 1)`
                                        : '1px solid rgba(148, 163, 184, 0.15)',
                                    color: selected ? '#fff' : '#cbd5e1',
                                }}
                                onClick={() => onChange({ ...value, gender: g.id })}
                            >
                                <span className="text-base leading-none">{g.icon}</span>
                                <span className="text-xs">{g.label}</span>
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const EMPTY_PROFILE: Profile = {
    birthDate: '',
    birthTime: null,
    timeUnknown: false,
    gender: 'unknown',
};

export function FortuneAgentLuckyDay({ onBack, onComplete }: FortuneAgentLuckyDayProps) {
    // Section index: 1..5. `activeStep` is the section currently being edited.
    // `maxStep` is the furthest section ever reached (controls what's rendered).
    const [activeStep, setActiveStep] = useState(1);
    const [maxStep, setMaxStep] = useState(1);

    // Section 1
    const [occasion, setOccasion] = useState<OccasionId | null>(null);

    // Section 2
    const [profile, setProfile] = useState<Profile>(EMPTY_PROFILE);

    // Section 3
    const [windowStart, setWindowStart] = useState<string | null>(null);
    const [windowEnd, setWindowEnd] = useState<string | null>(null);

    // Section 4
    const [includePartner, setIncludePartner] = useState<null | boolean>(null);
    const [partner, setPartner] = useState<Profile>(EMPTY_PROFILE);

    // Refs for smooth scroll
    const sectionRefs = [
        useRef<HTMLDivElement>(null!),
        useRef<HTMLDivElement>(null!),
        useRef<HTMLDivElement>(null!),
        useRef<HTMLDivElement>(null!),
        useRef<HTMLDivElement>(null!),
    ];

    const currentOccasion = useMemo(
        () => OCCASIONS.find((o) => o.id === occasion) ?? null,
        [occasion],
    );

    const activeAccent = currentOccasion?.accent ?? '212, 175, 55';

    // Advance helper
    const advanceTo = (n: number) => {
        setActiveStep(n);
        setMaxStep((m) => Math.max(m, n));
        // Smooth-scroll after render
        setTimeout(() => {
            const ref = sectionRefs[n - 1]?.current;
            if (ref) {
                ref.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 80);
    };

    // Auto-advance from Section 1 on occasion tap (tiny delay for visual feedback)
    useEffect(() => {
        if (occasion && activeStep === 1) {
            const t = setTimeout(() => advanceTo(2), 220);
            return () => clearTimeout(t);
        }
        return undefined;
    }, [occasion]); // eslint-disable-line react-hooks/exhaustive-deps

    // Section 2 completeness
    const profileComplete =
        Boolean(profile.birthDate) &&
        (Boolean(profile.birthTime) || profile.timeUnknown);

    // Section 3 completeness
    const windowComplete = Boolean(windowStart);

    // Section 4 completeness
    const partnerComplete =
        includePartner === false ||
        (includePartner === true &&
            Boolean(partner.birthDate) &&
            (Boolean(partner.birthTime) || partner.timeUnknown));

    // ---- Section 3: Month stripe state ----
    const monthStrip = useMemo(() => {
        const today = new Date();
        return buildMonthStrip(today, 18); // next 18 months
    }, []);

    const handleMonthTap = (key: string) => {
        if (!windowStart) {
            setWindowStart(key);
            setWindowEnd(null);
            return;
        }
        if (windowStart && !windowEnd) {
            // Second tap: set end
            if (monthKeyCompare(key, windowStart) < 0) {
                // Tapped before start → new start
                setWindowStart(key);
                setWindowEnd(null);
            } else if (key === windowStart) {
                // Same month → keep as single-month pick
                setWindowEnd(key);
            } else {
                setWindowEnd(key);
            }
            return;
        }
        // Both set → restart range
        setWindowStart(key);
        setWindowEnd(null);
    };

    const isMonthInRange = (key: string) => {
        if (!windowStart) return false;
        if (!windowEnd) return key === windowStart;
        return monthKeyCompare(key, windowStart) >= 0 && monthKeyCompare(key, windowEnd) <= 0;
    };

    const applyQuickChip = (chip: 'next30' | 'summer' | 'eoy') => {
        const today = new Date();
        if (chip === 'next30') {
            const k = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
            setWindowStart(k);
            setWindowEnd(k);
            return;
        }
        if (chip === 'summer') {
            const yr = today.getFullYear();
            setWindowStart(`${yr}-06`);
            setWindowEnd(`${yr}-08`);
            return;
        }
        if (chip === 'eoy') {
            const yr = today.getFullYear();
            const sm = String(today.getMonth() + 1).padStart(2, '0');
            setWindowStart(`${yr}-${sm}`);
            setWindowEnd(`${yr}-12`);
        }
    };

    // Final submit
    const handleSubmit = () => {
        if (!occasion || !profileComplete || !windowComplete || !partnerComplete) return;
        if (!onComplete) return;
        const effectiveEndKey = windowEnd ?? windowStart!;
        const [sy, sm] = windowStart!.split('-').map(Number);
        const [ey, em] = effectiveEndKey.split('-').map(Number);
        onComplete({
            occasion,
            profile,
            windowStart: firstOfMonthISO(sy, sm),
            windowEnd: lastOfMonthISO(ey, em),
            partner: includePartner ? partner : undefined,
        });
    };

    const canSubmit =
        Boolean(occasion) && profileComplete && windowComplete && partnerComplete;

    // Progress dots
    const ProgressDots = () => (
        <div className="flex items-center gap-1.5">
            {[1, 2, 3, 4, 5].map((n) => (
                <span
                    key={n}
                    className="h-1.5 rounded-full transition-all"
                    style={{
                        width: n === activeStep ? 18 : 6,
                        background:
                            n < activeStep || n === activeStep
                                ? `rgba(${activeAccent}, 0.9)`
                                : 'rgba(148, 163, 184, 0.25)',
                    }}
                />
            ))}
        </div>
    );

    return (
        <div
            className="min-h-screen w-full"
            style={{
                background:
                    'linear-gradient(180deg, #1a1304 0%, #3a2a08 55%, #0c0a14 100%)',
                overscrollBehavior: 'none',
            }}
        >
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

            {/* Sticky mini-header */}
            <header
                className="sticky top-0 z-20 flex items-center justify-center px-4 py-3 backdrop-blur"
                style={{
                    background: 'rgba(26, 19, 4, 0.85)',
                    borderBottom: '1px solid rgba(234, 179, 8, 0.14)',
                }}
            >
                <div className="flex flex-col items-center">
                    <span
                        className="text-[11px] uppercase tracking-[0.2em] text-slate-500"
                        style={{ fontFamily: 'var(--ming-font-chinese)' }}
                    >
                        擇日 · Lucky Day
                    </span>
                    <ProgressDots />
                </div>
            </header>

            <div className="mx-auto w-full max-w-[420px] px-4 pb-24 pt-4">
                {/* -------- Section 1: The Occasion -------- */}
                <SectionShell
                    index={1}
                    title="The Occasion"
                    subtitle="What are we timing?"
                    isActive={activeStep === 1}
                    isCompleted={maxStep > 1 && activeStep !== 1 && Boolean(occasion)}
                    summary={
                        currentOccasion
                            ? `${currentOccasion.glyph}  ${currentOccasion.label}`
                            : undefined
                    }
                    onEdit={() => setActiveStep(1)}
                    innerRef={sectionRefs[0]}
                >
                    <div className="grid grid-cols-2 gap-2.5">
                        {OCCASIONS.map((o) => {
                            const selected = occasion === o.id;
                            return (
                                <motion.button
                                    key={o.id}
                                    whileTap={{ scale: 0.97 }}
                                    onClick={() => setOccasion(o.id)}
                                    className="relative flex min-h-[96px] flex-col items-start justify-between overflow-hidden rounded-xl p-3 text-left transition-all"
                                    style={{
                                        background: selected
                                            ? `linear-gradient(135deg, rgba(${o.accent}, 0.35), rgba(${o.accent}, 0.08))`
                                            : 'rgba(148, 163, 184, 0.06)',
                                        border: selected
                                            ? `1px solid rgba(${o.accent}, 0.85)`
                                            : '1px solid rgba(148, 163, 184, 0.12)',
                                        boxShadow: selected
                                            ? `0 8px 28px -14px rgba(${o.accent}, 0.7)`
                                            : 'none',
                                    }}
                                >
                                    <span
                                        aria-hidden
                                        className="absolute right-2 top-1 select-none text-5xl leading-none opacity-20"
                                        style={{
                                            fontFamily: 'var(--ming-font-chinese)',
                                            color: `rgb(${o.accent})`,
                                        }}
                                    >
                                        {o.glyph}
                                    </span>
                                    <div className="relative z-10">
                                        <div
                                            className="text-2xl leading-none"
                                            style={{
                                                fontFamily: 'var(--ming-font-chinese)',
                                                color: selected
                                                    ? `rgb(${o.accent})`
                                                    : '#e2e8f0',
                                            }}
                                        >
                                            {o.glyph}
                                        </div>
                                    </div>
                                    <div className="relative z-10">
                                        <div className="text-sm font-semibold text-slate-100">
                                            {o.label}
                                        </div>
                                        <div className="text-[11px] text-slate-400">
                                            {o.tag}
                                        </div>
                                    </div>
                                </motion.button>
                            );
                        })}
                    </div>
                    {occasion && (
                        <button
                            onClick={() => advanceTo(2)}
                            className="mt-4 min-h-[48px] w-full rounded-xl px-4 py-3 text-sm font-semibold text-white transition-transform active:scale-[0.98]"
                            style={{
                                background: `linear-gradient(135deg, rgba(${activeAccent}, 1), rgba(${activeAccent}, 0.75))`,
                            }}
                        >
                            Continue →
                        </button>
                    )}
                </SectionShell>

                {/* -------- Section 2: Your Profile -------- */}
                {maxStep >= 2 && (
                    <SectionShell
                        index={2}
                        title="Your Profile"
                        subtitle="So we can read your pillars"
                        isActive={activeStep === 2}
                        isCompleted={maxStep > 2 && profileComplete}
                        summary={formatProfileSummary(profile)}
                        onEdit={() => setActiveStep(2)}
                        innerRef={sectionRefs[1]}
                    >
                        <ProfileEditor
                            value={profile}
                            onChange={setProfile}
                            accent={activeAccent}
                        />
                        <button
                            disabled={!profileComplete}
                            onClick={() => advanceTo(3)}
                            className="mt-5 min-h-[48px] w-full rounded-xl px-4 py-3 text-sm font-semibold transition-all active:scale-[0.98]"
                            style={{
                                background: profileComplete
                                    ? `linear-gradient(135deg, rgba(${activeAccent}, 1), rgba(${activeAccent}, 0.75))`
                                    : 'rgba(148, 163, 184, 0.1)',
                                color: profileComplete ? '#fff' : '#64748b',
                                cursor: profileComplete ? 'pointer' : 'not-allowed',
                            }}
                        >
                            Continue →
                        </button>
                    </SectionShell>
                )}

                {/* -------- Section 3: The Window -------- */}
                {maxStep >= 3 && (
                    <SectionShell
                        index={3}
                        title="The Window"
                        subtitle="When do you need the date?"
                        isActive={activeStep === 3}
                        isCompleted={maxStep > 3 && windowComplete}
                        summary={summarizeWindow(windowStart, windowEnd)}
                        onEdit={() => setActiveStep(3)}
                        innerRef={sectionRefs[2]}
                    >
                        <p
                            className="mb-3 text-center text-sm font-medium"
                            style={{ color: `rgb(${activeAccent})` }}
                        >
                            {summarizeWindow(windowStart, windowEnd)}
                        </p>

                        {/* Quick chips */}
                        <div className="mb-3 flex flex-wrap gap-1.5">
                            {[
                                { id: 'next30' as const, label: 'Next 30 days' },
                                { id: 'summer' as const, label: 'This summer' },
                                { id: 'eoy' as const, label: 'Before year-end' },
                            ].map((chip) => (
                                <button
                                    key={chip.id}
                                    onClick={() => applyQuickChip(chip.id)}
                                    className="min-h-[32px] rounded-full px-3 py-1 text-xs transition-colors"
                                    style={{
                                        background: 'rgba(148, 163, 184, 0.08)',
                                        border: '1px solid rgba(148, 163, 184, 0.18)',
                                        color: '#cbd5e1',
                                    }}
                                >
                                    {chip.label}
                                </button>
                            ))}
                        </div>

                        {/* Horizontal month stripe */}
                        <div
                            className="relative -mx-4 overflow-x-auto px-4 pb-2"
                            style={{
                                scrollSnapType: 'x mandatory',
                                WebkitOverflowScrolling: 'touch',
                            }}
                        >
                            <div className="flex gap-2">
                                {monthStrip.map((m) => {
                                    const inRange = isMonthInRange(m.key);
                                    const isAnchor =
                                        m.key === windowStart || m.key === windowEnd;
                                    return (
                                        <button
                                            key={m.key}
                                            onClick={() => handleMonthTap(m.key)}
                                            className="flex min-h-[72px] w-[68px] flex-none flex-col items-center justify-center rounded-xl transition-all"
                                            style={{
                                                scrollSnapAlign: 'center',
                                                background: inRange
                                                    ? `rgba(${activeAccent}, 0.18)`
                                                    : 'rgba(148, 163, 184, 0.06)',
                                                border: isAnchor
                                                    ? `1.5px solid var(--ming-gold, #d4af37)`
                                                    : inRange
                                                    ? `1px solid rgba(${activeAccent}, 0.5)`
                                                    : '1px solid rgba(148, 163, 184, 0.14)',
                                                color: inRange ? '#fff' : '#cbd5e1',
                                            }}
                                        >
                                            <span className="text-[10px] uppercase tracking-wider opacity-70">
                                                {m.year}
                                            </span>
                                            <span className="text-base font-semibold">
                                                {MONTH_NAMES_SHORT[m.month - 1]}
                                            </span>
                                            {isAnchor && (
                                                <span
                                                    className="mt-0.5 h-1 w-1 rounded-full"
                                                    style={{
                                                        background:
                                                            'var(--ming-gold, #d4af37)',
                                                    }}
                                                />
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                        <p className="mt-2 text-center text-[11px] text-slate-500">
                            Tap once for a month, twice to set a range
                        </p>

                        <button
                            disabled={!windowComplete}
                            onClick={() => advanceTo(4)}
                            className="mt-4 min-h-[48px] w-full rounded-xl px-4 py-3 text-sm font-semibold transition-all active:scale-[0.98]"
                            style={{
                                background: windowComplete
                                    ? `linear-gradient(135deg, rgba(${activeAccent}, 1), rgba(${activeAccent}, 0.75))`
                                    : 'rgba(148, 163, 184, 0.1)',
                                color: windowComplete ? '#fff' : '#64748b',
                                cursor: windowComplete ? 'pointer' : 'not-allowed',
                            }}
                        >
                            Continue →
                        </button>
                    </SectionShell>
                )}

                {/* -------- Section 4: Partner (optional) -------- */}
                {maxStep >= 4 && (
                    <SectionShell
                        index={4}
                        title="Partner / Co-signer"
                        subtitle="Optional — a second person tied to this date"
                        isActive={activeStep === 4}
                        isCompleted={maxStep > 4 && partnerComplete}
                        summary={
                            includePartner === false
                                ? 'No partner'
                                : includePartner
                                ? formatProfileSummary(partner)
                                : undefined
                        }
                        onEdit={() => setActiveStep(4)}
                        innerRef={sectionRefs[3]}
                    >
                        <AnimatePresence mode="wait">
                            {includePartner === null && (
                                <motion.div
                                    key="choose"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                >
                                    <p className="mb-3 text-sm text-slate-300">
                                        Is there a second person whose chart should
                                        harmonize with this date? (e.g., spouse for a
                                        wedding, co-founder for a business opening)
                                    </p>
                                    <div className="grid grid-cols-2 gap-2">
                                        <button
                                            onClick={() => setIncludePartner(true)}
                                            className="min-h-[48px] rounded-xl px-3 py-2 text-sm font-medium text-white"
                                            style={{
                                                background: `linear-gradient(135deg, rgba(${activeAccent}, 1), rgba(${activeAccent}, 0.7))`,
                                            }}
                                        >
                                            Yes, add them
                                        </button>
                                        <button
                                            onClick={() => {
                                                setIncludePartner(false);
                                                setTimeout(() => advanceTo(5), 120);
                                            }}
                                            className="min-h-[48px] rounded-xl px-3 py-2 text-sm text-slate-200"
                                            style={{
                                                background: 'rgba(148, 163, 184, 0.08)',
                                                border: '1px solid rgba(148, 163, 184, 0.2)',
                                            }}
                                        >
                                            Skip
                                        </button>
                                    </div>
                                </motion.div>
                            )}
                            {includePartner === true && (
                                <motion.div
                                    key="editor"
                                    initial={{ opacity: 0, y: 8 }}
                                    animate={{ opacity: 1, y: 0 }}
                                >
                                    <ProfileEditor
                                        value={partner}
                                        onChange={setPartner}
                                        accent={activeAccent}
                                    />
                                    <div className="mt-4 flex gap-2">
                                        <button
                                            onClick={() => {
                                                setIncludePartner(false);
                                                setPartner(EMPTY_PROFILE);
                                                setTimeout(() => advanceTo(5), 120);
                                            }}
                                            className="min-h-[48px] flex-1 rounded-xl px-3 py-2 text-sm text-slate-300"
                                            style={{
                                                background: 'rgba(148, 163, 184, 0.06)',
                                                border: '1px solid rgba(148, 163, 184, 0.18)',
                                            }}
                                        >
                                            Actually, skip
                                        </button>
                                        <button
                                            disabled={!partnerComplete}
                                            onClick={() => advanceTo(5)}
                                            className="min-h-[48px] flex-1 rounded-xl px-3 py-2 text-sm font-semibold"
                                            style={{
                                                background: partnerComplete
                                                    ? `linear-gradient(135deg, rgba(${activeAccent}, 1), rgba(${activeAccent}, 0.75))`
                                                    : 'rgba(148, 163, 184, 0.1)',
                                                color: partnerComplete ? '#fff' : '#64748b',
                                            }}
                                        >
                                            Continue →
                                        </button>
                                    </div>
                                </motion.div>
                            )}
                            {includePartner === false && activeStep === 4 && (
                                <motion.div
                                    key="skipped"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                >
                                    <p className="mb-3 text-sm text-slate-300">
                                        Skipped — solo reading.
                                    </p>
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => setIncludePartner(null)}
                                            className="min-h-[48px] flex-1 rounded-xl px-3 py-2 text-sm text-slate-300"
                                            style={{
                                                background: 'rgba(148, 163, 184, 0.06)',
                                                border: '1px solid rgba(148, 163, 184, 0.18)',
                                            }}
                                        >
                                            Add a partner
                                        </button>
                                        <button
                                            onClick={() => advanceTo(5)}
                                            className="min-h-[48px] flex-1 rounded-xl px-3 py-2 text-sm font-semibold text-white"
                                            style={{
                                                background: `linear-gradient(135deg, rgba(${activeAccent}, 1), rgba(${activeAccent}, 0.75))`,
                                            }}
                                        >
                                            Continue →
                                        </button>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </SectionShell>
                )}

                {/* -------- Section 5: Confirm -------- */}
                {maxStep >= 5 && (
                    <SectionShell
                        index={5}
                        title="Confirm"
                        subtitle="Double-check and we'll scan the calendar"
                        isActive={activeStep === 5}
                        isCompleted={false}
                        innerRef={sectionRefs[4]}
                    >
                        <div
                            className="rounded-xl p-4"
                            style={{
                                background: 'rgba(148, 163, 184, 0.05)',
                                border: '1px solid rgba(148, 163, 184, 0.15)',
                            }}
                        >
                            <div className="flex items-center gap-3 pb-3">
                                <span
                                    className="flex h-12 w-12 items-center justify-center rounded-lg text-3xl"
                                    style={{
                                        fontFamily: 'var(--ming-font-chinese)',
                                        background: `linear-gradient(135deg, rgba(${activeAccent}, 0.28), rgba(${activeAccent}, 0.06))`,
                                        color: `rgb(${activeAccent})`,
                                        border: `1px solid rgba(${activeAccent}, 0.4)`,
                                    }}
                                >
                                    {currentOccasion?.glyph}
                                </span>
                                <div>
                                    <div className="text-xs uppercase tracking-wider text-slate-500">
                                        Occasion
                                    </div>
                                    <div className="text-base font-semibold text-slate-100">
                                        {currentOccasion?.label}
                                    </div>
                                </div>
                            </div>

                            <div
                                className="space-y-2 border-t pt-3"
                                style={{ borderColor: 'rgba(148, 163, 184, 0.1)' }}
                            >
                                <div className="flex justify-between text-sm">
                                    <span className="text-slate-500">You</span>
                                    <span className="text-slate-200">
                                        {formatProfileSummary(profile)}
                                    </span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-slate-500">Window</span>
                                    <span className="text-slate-200">
                                        {summarizeWindow(windowStart, windowEnd)}
                                    </span>
                                </div>
                                {includePartner && (
                                    <div className="flex justify-between text-sm">
                                        <span className="text-slate-500">Partner</span>
                                        <span className="text-slate-200">
                                            {formatProfileSummary(partner)}
                                        </span>
                                    </div>
                                )}
                            </div>
                        </div>

                        <button
                            disabled={!canSubmit}
                            onClick={handleSubmit}
                            className="mt-5 min-h-[52px] w-full rounded-xl px-4 py-3 text-base font-semibold text-white transition-transform active:scale-[0.98]"
                            style={{
                                background: canSubmit
                                    ? `linear-gradient(135deg, rgba(${activeAccent}, 1), var(--ming-gold, #d4af37))`
                                    : 'rgba(148, 163, 184, 0.12)',
                                color: canSubmit ? '#fff' : '#64748b',
                                boxShadow: canSubmit
                                    ? `0 10px 30px -12px rgba(${activeAccent}, 0.6)`
                                    : 'none',
                            }}
                        >
                            Find auspicious days →
                        </button>
                    </SectionShell>
                )}
            </div>
        </div>
    );
}

export default FortuneAgentLuckyDay;
