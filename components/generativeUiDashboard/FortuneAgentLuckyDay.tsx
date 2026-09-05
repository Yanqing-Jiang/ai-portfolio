'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
    ProfileStep,
    ConfirmStep,
    WindowStep,
    summarizeWindow as summarizeWindowShared,
    normalizeWindowBoundary,
    EMPTY_INTAKE_PROFILE,
    isProfileComplete,
    formatProfileSummary as formatProfileSummaryShared,
    type IntakeProfile,
} from './fortune/intake';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------



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

type Profile = IntakeProfile;

export interface FortuneAgentLuckyDayProps {
    onBack?: () => void;
    onComplete?: (payload: {
        occasion: string;
        profile: Profile;
        windowStart: string;
        windowEnd: string;
    }) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function summarizeWindow(startKey: string | null, endKey: string | null): string {
    return summarizeWindowShared(startKey, endKey);
}

function formatProfileSummary(p: Profile | null): string {
    if (!p) return 'Incomplete';
    return formatProfileSummaryShared(p);
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

// Profile editor used by the profile section.
interface ProfileEditorProps {
    value: Profile;
    onChange: (p: Profile) => void;
    accent?: string; // rgb triple
}

function ProfileEditor({ value, onChange, accent = '212, 175, 55' }: ProfileEditorProps) {
    return (
        <ProfileStep
            value={value}
            onChange={onChange}
            accentRgb={accent}
        />
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const EMPTY_PROFILE: Profile = { ...EMPTY_INTAKE_PROFILE };

export function FortuneAgentLuckyDay({ onBack, onComplete }: FortuneAgentLuckyDayProps) {
    // Section index: 1..4. `activeStep` is the section currently being edited.
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

    // Refs for smooth scroll
    const sectionRefs = [
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

    // Scroll the active section to a predictable position just below
    // the sticky header. Manual math (rect.top + scrollY - offset) is
    // more reliable than `scroll-padding-top` + scrollIntoView, which
    // browsers clamp when already at scroll top and silently leave the
    // first section partially tucked under the sticky header.
    const HEADER_OFFSET = 96;
    const scrollSectionIntoView = (
        ref: HTMLDivElement | null,
        behavior: ScrollBehavior = 'smooth',
    ) => {
        if (!ref) return;
        const rect = ref.getBoundingClientRect();
        const target = Math.max(0, rect.top + window.scrollY - HEADER_OFFSET);
        window.scrollTo({ top: target, behavior });
    };

    const advanceTo = (n: number) => {
        setActiveStep(n);
        setMaxStep((m) => Math.max(m, n));
        setTimeout(() => {
            scrollSectionIntoView(sectionRefs[n - 1]?.current);
        }, 80);
    };

    useEffect(() => {
        // Initial mount — place section 1 at its resting position.
        scrollSectionIntoView(sectionRefs[0]?.current, 'auto');
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Auto-advance from Section 1 on occasion tap (tiny delay for visual feedback)
    useEffect(() => {
        if (occasion && activeStep === 1) {
            const t = setTimeout(() => advanceTo(2), 220);
            return () => clearTimeout(t);
        }
        return undefined;
    }, [occasion]); // eslint-disable-line react-hooks/exhaustive-deps

    // Section 2 completeness
    const profileComplete = isProfileComplete(profile);

    // Section 3 completeness
    const windowComplete = Boolean(windowStart);

    const handleSubmit = () => {
        if (!occasion || !profileComplete || !windowComplete) return;
        if (!onComplete) return;
        const effectiveEndKey = windowEnd ?? windowStart!;
        onComplete({
            occasion,
            profile,
            windowStart: normalizeWindowBoundary(windowStart!, 'start'),
            windowEnd: normalizeWindowBoundary(effectiveEndKey, 'end'),
        });
    };

    const canSubmit =
        Boolean(occasion) && profileComplete && windowComplete;

    // Progress dots
    const ProgressDots = () => (
        <div className="flex items-center gap-1.5">
            {[1, 2, 3, 4].map((n) => (
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

            <div className="mx-auto w-full max-w-[420px] px-4 pt-4 pb-[35vh]">
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
                        <WindowStep
                            windowStart={windowStart}
                            windowEnd={windowEnd}
                            onChange={(s, e) => {
                                setWindowStart(s);
                                setWindowEnd(e);
                            }}
                            accentRgb={activeAccent}
                        />

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

                {/* -------- Section 4: Confirm -------- */}
                {maxStep >= 4 && (
                    <SectionShell
                        index={4}
                        title="Confirm"
                        subtitle="Double-check and we'll scan the calendar"
                        isActive={activeStep === 4}
                        isCompleted={false}
                        innerRef={sectionRefs[3]}
                    >
                        <ConfirmStep
                            accentRgb={activeAccent}
                            rows={[
                                { label: 'Occasion', value: currentOccasion?.label || '—' },
                                { label: 'You', value: formatProfileSummary(profile) },
                                { label: 'Window', value: summarizeWindow(windowStart, windowEnd) },
                            ]}
                            ctaLabel="Find my lucky days →"
                            onConfirm={handleSubmit}
                            disabled={!canSubmit}
                        />
                    </SectionShell>
                )}
            </div>
        </div>
    );
}

export default FortuneAgentLuckyDay;
