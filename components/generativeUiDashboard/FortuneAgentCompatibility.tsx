/**
 * FortuneAgentCompatibility — Progressive-reveal mobile flow for "Compatibility Check".
 *
 * Sections unfold one at a time (Hinge-style). Previously completed sections collapse
 * into a compact summary row with an Edit affordance; the active section occupies the
 * user's attention. After advancing, the newly revealed section smoothly scrolls into view.
 *
 * Flow:
 *   1. Relationship context (chips)
 *   2. Person A (birthday + earthly-branch time + unknown toggle + gender)
 *   3. Person B (mirrors A, visually distinct accent)
 *   4. Synastry preview + CTA → onComplete(payload)
 *
 * Uses shared ProfileStep / ConfirmStep from fortune/intake.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    ProfileStep,
    ConfirmStep,
    EMPTY_INTAKE_PROFILE,
    type IntakeProfile,
} from './fortune/intake';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------


const RELATIONSHIPS = [
    { id: 'romantic', label: 'Romantic', glyph: '緣' },
    { id: 'cofounder', label: 'Co-founder', glyph: '業' },
    { id: 'family', label: 'Family', glyph: '親' },
    { id: 'friend', label: 'Friend', glyph: '友' },
] as const;


// Mock heavenly-stem glyphs for the synastry preview (purely decorative)
const PREVIEW_STEMS_A = ['甲', '丙', '戊', '庚'];
const PREVIEW_STEMS_B = ['乙', '丁', '己', '辛'];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PersonData = IntakeProfile;

interface Props {
    onBack?: () => void;
    onComplete?: (payload: {
        relationship: string;
        personA: PersonData;
        personB: PersonData;
    }) => void;
}

type StepIndex = 0 | 1 | 2 | 3;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
    if (!iso) return '—';
    const [y, m, d] = iso.split('-').map(Number);
    if (!y || !m || !d) return iso;
    const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${MONTHS[m - 1]} ${d}, ${y}`;
}

function personSummary(p: PersonData): string {
    if (!p.birthDate) return 'Incomplete';
    const date = formatDate(p.birthDate);
    const time = p.timeUnknown ? 'time unknown' : p.birthTime || '—';
    return `${date} · ${time}`;
}

function personValid(p: PersonData): boolean {
    return Boolean(p.birthDate) && (p.timeUnknown || Boolean(p.birthTime));
}

// ---------------------------------------------------------------------------
// Sub-component: Person form (reused for A and B with visual variance)
// ---------------------------------------------------------------------------

interface PersonFormProps {
    value: PersonData;
    onChange: (next: PersonData) => void;
    accent: 'rose' | 'teal';
}

function PersonForm({ value, onChange, accent }: PersonFormProps) {
    const accentColor = accent === 'rose'
        ? 'var(--ming-accent, #e11d48)'
        : 'var(--ming-gold, #0d9488)';
    const accentBg = accent === 'rose'
        ? 'rgba(225, 29, 72, 0.14)'
        : 'rgba(13, 148, 136, 0.14)';
    const accentBorder = accent === 'rose'
        ? 'rgba(225, 29, 72, 0.55)'
        : 'rgba(13, 148, 136, 0.55)';

    return (
        <ProfileStep
            value={value}
            onChange={onChange}
            accentColor={accentColor}
            accentBg={accentBg}
            accentBorder={accentBorder}
            genderHint="(for luck cycle)"
        />
    );
}

// ---------------------------------------------------------------------------
// Sub-component: Compact summary row for completed sections
// ---------------------------------------------------------------------------

interface SummaryRowProps {
    label: string;
    value: string;
    onEdit: () => void;
    accent?: 'accent' | 'gold' | 'rose' | 'teal';
}

function SummaryRow({ label, value, onEdit, accent = 'accent' }: SummaryRowProps) {
    const dotColor =
        accent === 'gold'
            ? 'var(--ming-gold, #eab308)'
            : accent === 'rose'
            ? 'var(--ming-accent, #e11d48)'
            : accent === 'teal'
            ? '#0d9488'
            : 'var(--ming-accent, #e11d48)';

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center justify-between rounded-xl px-3 py-2.5"
            style={{
                background: 'rgba(148, 163, 184, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.1)',
            }}
        >
            <div className="flex min-w-0 items-center gap-2.5">
                <span
                    aria-hidden
                    className="h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: dotColor }}
                />
                <div className="min-w-0">
                    <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        {label}
                    </div>
                    <div className="truncate text-sm text-slate-200">{value}</div>
                </div>
            </div>
            <button
                type="button"
                onClick={onEdit}
                aria-label={`Edit ${label}`}
                className="ml-2 min-h-[36px] shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-400 transition-colors hover:bg-slate-700/40 hover:text-slate-200"
            >
                Edit
            </button>
        </motion.div>
    );
}

// ---------------------------------------------------------------------------
// Sub-component: Synastry pillar preview (decorative animation)
// ---------------------------------------------------------------------------

function SynastryPreview() {
    return (
        <div className="relative flex items-center justify-center py-6">
            {/* Person A pillars — lean right */}
            <motion.div
                initial={{ x: -8, rotate: -4, opacity: 0 }}
                animate={{ x: 0, rotate: -3, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 120, damping: 14, delay: 0.1 }}
                className="flex gap-1.5"
            >
                {PREVIEW_STEMS_A.map((g, i) => (
                    <motion.div
                        key={i}
                        initial={{ y: 20, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        transition={{ delay: 0.2 + i * 0.05 }}
                        className="flex h-14 w-8 flex-col items-center justify-center rounded-md"
                        style={{
                            background: 'rgba(225, 29, 72, 0.14)',
                            border: '1px solid rgba(225, 29, 72, 0.45)',
                            color: 'var(--ming-accent, #e11d48)',
                            fontFamily: 'var(--ming-font-chinese)',
                        }}
                    >
                        <span className="text-lg leading-none">{g}</span>
                    </motion.div>
                ))}
            </motion.div>

            {/* Spark glyph between them */}
            <motion.div
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.55, type: 'spring', stiffness: 200 }}
                className="mx-3 text-2xl"
                style={{
                    fontFamily: 'var(--ming-font-chinese)',
                    color: 'var(--ming-gold, #eab308)',
                }}
                aria-hidden
            >
                合
            </motion.div>

            {/* Person B pillars — lean left */}
            <motion.div
                initial={{ x: 8, rotate: 4, opacity: 0 }}
                animate={{ x: 0, rotate: 3, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 120, damping: 14, delay: 0.15 }}
                className="flex gap-1.5"
            >
                {PREVIEW_STEMS_B.map((g, i) => (
                    <motion.div
                        key={i}
                        initial={{ y: 20, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        transition={{ delay: 0.3 + i * 0.05 }}
                        className="flex h-14 w-8 flex-col items-center justify-center rounded-md"
                        style={{
                            background: 'rgba(13, 148, 136, 0.14)',
                            border: '1px solid rgba(13, 148, 136, 0.45)',
                            color: '#0d9488',
                            fontFamily: 'var(--ming-font-chinese)',
                        }}
                    >
                        <span className="text-lg leading-none">{g}</span>
                    </motion.div>
                ))}
            </motion.div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Sub-component: Progressive section wrapper
// ---------------------------------------------------------------------------

interface SectionProps {
    step: StepIndex;
    currentStep: StepIndex;
    title: string;
    subtitle?: string;
    children: React.ReactNode;
    sectionRef: React.RefObject<HTMLDivElement>;
}

function Section({ step, currentStep, title, subtitle, children, sectionRef }: SectionProps) {
    const visible = step <= currentStep;
    if (!visible) return null;

    return (
        <motion.section
            ref={sectionRef}
            layout
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 160, damping: 20 }}
            className="rounded-2xl p-4"
            style={{
                background: 'rgba(15, 23, 42, 0.55)',
                border: '1px solid rgba(148, 163, 184, 0.12)',
            }}
            aria-current={step === currentStep ? 'step' : undefined}
        >
            <header className="mb-4">
                <h2
                    className="text-lg font-semibold text-slate-100"
                    style={{ fontFamily: 'var(--ming-font-chinese)' }}
                >
                    {title}
                </h2>
                {subtitle && (
                    <p className="mt-0.5 text-sm text-slate-400">{subtitle}</p>
                )}
            </header>
            {children}
        </motion.section>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function FortuneAgentCompatibility({ onBack, onComplete }: Props) {
    const [currentStep, setCurrentStep] = useState<StepIndex>(0);
    const [relationship, setRelationship] = useState<string | null>(null);
    const [personA, setPersonA] = useState<PersonData>({ ...EMPTY_INTAKE_PROFILE });
    const [personB, setPersonB] = useState<PersonData>({ ...EMPTY_INTAKE_PROFILE });

    // Refs for smooth scroll-into-view on step change
    const sec1Ref = useRef<HTMLDivElement>(null!);
    const sec2Ref = useRef<HTMLDivElement>(null!);
    const sec3Ref = useRef<HTMLDivElement>(null!);
    const sec4Ref = useRef<HTMLDivElement>(null!);

    // Scroll the active section to a predictable position just below
    // the sticky header. Manual math avoids browsers clamping to
    // document top and tucking section 1 under the sticky header.
    const HEADER_OFFSET = 96;
    const scrollTo = useCallback((ref: React.RefObject<HTMLDivElement>, behavior: ScrollBehavior = 'smooth') => {
        requestAnimationFrame(() => {
            const el = ref.current;
            if (!el) return;
            const rect = el.getBoundingClientRect();
            const target = Math.max(0, rect.top + window.scrollY - HEADER_OFFSET);
            window.scrollTo({ top: target, behavior });
        });
    }, []);

    const advance = useCallback(
        (to: StepIndex) => {
            setCurrentStep((prev) => (to > prev ? to : prev));
            const ref = to === 1 ? sec2Ref : to === 2 ? sec3Ref : to === 3 ? sec4Ref : sec1Ref;
            scrollTo(ref);
        },
        [scrollTo],
    );

    const editStep = useCallback((to: StepIndex) => {
        setCurrentStep(to);
        const ref = to === 0 ? sec1Ref : to === 1 ? sec2Ref : to === 2 ? sec3Ref : sec4Ref;
        scrollTo(ref);
    }, [scrollTo]);

    const handleComplete = useCallback(() => {
        if (!relationship || !personValid(personA) || !personValid(personB)) return;
        onComplete?.({ relationship, personA, personB });
    }, [relationship, personA, personB, onComplete]);

    const aValid = useMemo(() => personValid(personA), [personA]);
    const bValid = useMemo(() => personValid(personB), [personB]);

    // Initial mount — place section 1 at its resting position just below
    // the sticky header. `behavior: 'auto'` avoids a visible scroll jump.
    useEffect(() => {
        scrollTo(sec1Ref, 'auto');
    }, [scrollTo]);

    const relationshipLabel = useMemo(
        () => RELATIONSHIPS.find((r) => r.id === relationship)?.label ?? '—',
        [relationship],
    );

    return (
        <div
            className="min-h-screen w-full text-slate-100"
            style={{
                background:
                    'linear-gradient(180deg, #1a0a10 0%, #3a0f14 55%, #0c0a14 100%)',
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
                className="sticky top-0 z-20 flex items-center justify-center px-3 py-2.5 backdrop-blur"
                style={{
                    background: 'rgba(26, 10, 16, 0.85)',
                    borderBottom: '1px solid rgba(244, 63, 94, 0.14)',
                }}
            >
                {/* 4-dot progress indicator */}
                <div
                    className="flex items-center gap-1.5"
                    role="progressbar"
                    aria-valuemin={1}
                    aria-valuemax={4}
                    aria-valuenow={currentStep + 1}
                    aria-label={`Step ${currentStep + 1} of 4`}
                >
                    {[0, 1, 2, 3].map((i) => {
                        const done = i < currentStep;
                        const active = i === currentStep;
                        return (
                            <motion.span
                                key={i}
                                animate={{
                                    width: active ? 20 : 6,
                                    opacity: done || active ? 1 : 0.35,
                                }}
                                transition={{ type: 'spring', stiffness: 260, damping: 24 }}
                                className="h-1.5 rounded-full"
                                style={{
                                    background: active
                                        ? 'var(--ming-gold, #eab308)'
                                        : done
                                        ? 'var(--ming-accent, #e11d48)'
                                        : 'rgba(148, 163, 184, 0.4)',
                                }}
                            />
                        );
                    })}
                </div>

            </header>

            <main className="mx-auto flex w-full max-w-[420px] flex-col gap-3 px-4 pt-5 pb-[45vh]">
                {/* Top motif — only prominent when on step 0 */}
                <AnimatePresence mode="wait">
                    {currentStep === 0 && (
                        <motion.div
                            key="hero-motif"
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            transition={{ type: 'spring', stiffness: 140, damping: 18 }}
                            className="flex flex-col items-center pb-1 pt-2"
                        >
                            <div
                                className="text-6xl"
                                style={{
                                    fontFamily: 'var(--ming-font-chinese)',
                                    color: 'var(--ming-gold, #eab308)',
                                }}
                                aria-hidden
                            >
                                緣
                            </div>
                            <p className="mt-2 text-center text-sm text-slate-400">
                                Compatibility Check — two charts, one story.
                            </p>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Section 1: Relationship context */}
                {currentStep > 0 ? (
                    <SummaryRow
                        label="Relationship"
                        value={relationshipLabel}
                        onEdit={() => editStep(0)}
                        accent="gold"
                    />
                ) : (
                    <Section
                        step={0}
                        currentStep={currentStep}
                        sectionRef={sec1Ref}
                        title="What are you reading?"
                        subtitle="Pick the relationship — the lens changes the reading."
                    >
                        <div className="grid grid-cols-2 gap-2">
                            {RELATIONSHIPS.map((r) => {
                                const active = relationship === r.id;
                                return (
                                    <button
                                        key={r.id}
                                        type="button"
                                        aria-pressed={active}
                                        onClick={() => setRelationship(r.id)}
                                        className="flex min-h-[72px] items-center gap-3 rounded-xl px-4 py-3 text-left transition-colors"
                                        style={{
                                            background: active
                                                ? 'rgba(234, 179, 8, 0.12)'
                                                : 'rgba(148, 163, 184, 0.06)',
                                            border: active
                                                ? '1.5px solid var(--ming-gold, #eab308)'
                                                : '1px solid rgba(148, 163, 184, 0.12)',
                                            color: active ? 'var(--ming-gold, #eab308)' : '#cbd5e1',
                                        }}
                                    >
                                        <span
                                            className="text-2xl leading-none"
                                            style={{ fontFamily: 'var(--ming-font-chinese)' }}
                                            aria-hidden
                                        >
                                            {r.glyph}
                                        </span>
                                        <span className="text-sm font-medium">{r.label}</span>
                                    </button>
                                );
                            })}
                        </div>

                        <button
                            type="button"
                            disabled={!relationship}
                            onClick={() => advance(1)}
                            className="mt-5 w-full min-h-[48px] rounded-xl px-4 py-3 text-sm font-semibold transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
                            style={{
                                background: 'var(--ming-gold, #eab308)',
                                color: '#0b1120',
                            }}
                        >
                            Continue →
                        </button>
                    </Section>
                )}

                {/* Section 2: Person A */}
                {currentStep > 1 ? (
                    <SummaryRow
                        label="You (Person A)"
                        value={personSummary(personA)}
                        onEdit={() => editStep(1)}
                        accent="rose"
                    />
                ) : currentStep >= 1 ? (
                    <Section
                        step={1}
                        currentStep={currentStep}
                        sectionRef={sec2Ref}
                        title="You, first."
                        subtitle="Person A — your four pillars anchor the chart."
                    >
                        <PersonForm
                            value={personA}
                            onChange={setPersonA}
                            accent="rose"
                        />
                        <button
                            type="button"
                            disabled={!aValid}
                            onClick={() => advance(2)}
                            className="mt-5 w-full min-h-[48px] rounded-xl px-4 py-3 text-sm font-semibold transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
                            style={{
                                background: 'var(--ming-accent, #e11d48)',
                                color: '#fff',
                            }}
                        >
                            Next →
                        </button>
                    </Section>
                ) : null}

                {/* Section 3: Person B */}
                {currentStep > 2 ? (
                    <SummaryRow
                        label="Person B"
                        value={personSummary(personB)}
                        onEdit={() => editStep(2)}
                        accent="teal"
                    />
                ) : currentStep >= 2 ? (
                    <Section
                        step={2}
                        currentStep={currentStep}
                        sectionRef={sec3Ref}
                        title="Now, them."
                        subtitle="Person B — the other half of the pairing."
                    >
                        {/* Mirrored motif — subtle teal flourish to signal pairing */}
                        <div className="mb-3 flex items-center gap-2">
                            <span
                                className="text-xl"
                                style={{
                                    fontFamily: 'var(--ming-font-chinese)',
                                    color: '#0d9488',
                                }}
                                aria-hidden
                            >
                                對
                            </span>
                            <span className="text-xs text-slate-500">
                                Mirroring Person A's pillars
                            </span>
                        </div>

                        <PersonForm
                            value={personB}
                            onChange={setPersonB}
                            accent="teal"
                        />
                        <button
                            type="button"
                            disabled={!bValid}
                            onClick={() => advance(3)}
                            className="mt-5 w-full min-h-[48px] rounded-xl px-4 py-3 text-sm font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
                            style={{
                                background: '#0d9488',
                            }}
                        >
                            Next →
                        </button>
                    </Section>
                ) : null}

                {/* Section 4: Synastry preview */}
                {currentStep >= 3 && (
                    <Section
                        step={3}
                        currentStep={currentStep}
                        sectionRef={sec4Ref}
                        title="The reading is ready."
                        subtitle="Four pillars vs four pillars — we'll read the harmony and the sparks."
                    >
                        <ConfirmStep hideDefaultCta accentRgb="225, 29, 72">
                            <SynastryPreview />
                            <motion.button
                                type="button"
                                onClick={handleComplete}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.6 }}
                                whileTap={{ scale: 0.98 }}
                                className="mt-2 w-full min-h-[52px] rounded-xl px-4 py-3.5 text-base font-semibold transition-opacity"
                                style={{
                                    background:
                                        'linear-gradient(135deg, var(--ming-accent, #e11d48) 0%, var(--ming-gold, #eab308) 100%)',
                                    color: '#fff',
                                }}
                            >
                                Reveal our reading →
                            </motion.button>
                        </ConfirmStep>
                    </Section>
                )}
            </main>
        </div>
    );
}

export default FortuneAgentCompatibility;
