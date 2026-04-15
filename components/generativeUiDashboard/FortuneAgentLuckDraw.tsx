/**
 * FortuneAgentLuckDraw — Bespoke mobile flow for the "Luck Draw" purpose.
 *
 * Progressive section reveal: one section at a time. As the user completes
 * a step, the next animates in and smooth-scrolls into view. Completed
 * sections remain above as compact summary rows with an Edit affordance.
 *
 * Visual motif: concentric rings (moon cycle / year cycle / chosen horizon)
 * + ember-like pulsing CTA. No literal fire graphics — restrained.
 *
 * Self-contained; no backend. Fires `onComplete(payload)` on draw.
 */

import {
    useState,
    useEffect,
    useRef,
    useMemo,
    useCallback,
    type CSSProperties,
    type ReactNode,
} from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BirthdayScrollPicker } from './BirthdayScrollPicker';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type HorizonValue =
    | 'this-month'
    | 'this-year'
    | { year: number; month?: number };

interface LuckDrawPayload {
    horizon: HorizonValue;
    focus: string[];
    profile: {
        birthDate: string;
        birthTime: string | null;
        timeUnknown: boolean;
        gender: string;
    };
}

export interface FortuneAgentLuckDrawProps {
    onBack?: () => void;
    onComplete?: (payload: LuckDrawPayload) => void;
}

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

const FOCUS_OPTIONS = [
    { id: 'career', label: 'Career', glyph: '事' },
    { id: 'wealth', label: 'Wealth', glyph: '財' },
    { id: 'love', label: 'Love', glyph: '情' },
    { id: 'health', label: 'Health', glyph: '體' },
    { id: 'family', label: 'Family', glyph: '家' },
    { id: 'study', label: 'Study', glyph: '學' },
    { id: 'general', label: 'General', glyph: '運' },
] as const;

const GENDER_OPTIONS = [
    { id: 'male', label: 'Male', icon: '♂' },
    { id: 'female', label: 'Female', icon: '♀' },
    { id: 'unknown', label: '—', icon: '' },
] as const;

const MONTH_SHORT = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

const MAX_FOCUS = 2;

const NOW = new Date();
const CURRENT_YEAR = NOW.getFullYear();

// ---------------------------------------------------------------------------
// Concentric rings motif — reusable inline SVG
// ---------------------------------------------------------------------------

interface RingsProps {
    active?: 0 | 1 | 2 | 3; // which ring is "lit"
    size?: number;
    spin?: boolean;
}

function ConcentricRings({ active = 0, size = 120, spin = true }: RingsProps) {
    const rings = [
        { r: 52, stroke: 1, opacity: 0.22, dash: '2 6' },
        { r: 38, stroke: 1, opacity: 0.3, dash: '3 4' },
        { r: 24, stroke: 1.25, opacity: 0.45, dash: '1 3' },
    ];
    return (
        <div style={{ width: size, height: size, position: 'relative' }}>
            {rings.map((r, i) => {
                const isActive = active > 0 && i === active - 1;
                return (
                    <motion.svg
                        key={i}
                        width={size}
                        height={size}
                        viewBox="0 0 120 120"
                        style={{ position: 'absolute', inset: 0 }}
                        animate={
                            spin
                                ? { rotate: i % 2 === 0 ? 360 : -360 }
                                : { rotate: 0 }
                        }
                        transition={{
                            duration: 40 + i * 20,
                            ease: 'linear',
                            repeat: Infinity,
                        }}
                    >
                        <circle
                            cx="60"
                            cy="60"
                            r={r.r}
                            fill="none"
                            stroke={
                                isActive
                                    ? 'var(--ming-gold, #d4af37)'
                                    : 'rgba(212, 175, 55, 0.55)'
                            }
                            strokeWidth={isActive ? r.stroke + 0.5 : r.stroke}
                            strokeDasharray={r.dash}
                            opacity={isActive ? 0.95 : r.opacity}
                            style={
                                isActive
                                    ? {
                                          filter:
                                              'drop-shadow(0 0 6px rgba(212,175,55,0.55))',
                                      }
                                    : undefined
                            }
                        />
                    </motion.svg>
                );
            })}
            {/* Center dot */}
            <div
                style={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: 'var(--ming-gold, #d4af37)',
                    transform: 'translate(-50%, -50%)',
                    boxShadow: '0 0 10px rgba(212,175,55,0.6)',
                }}
            />
        </div>
    );
}

// ---------------------------------------------------------------------------
// Mini Rings — for summary rows (static, tiny)
// ---------------------------------------------------------------------------

function MiniRings({ active = 1 }: { active?: 1 | 2 | 3 }) {
    return (
        <svg width={28} height={28} viewBox="0 0 28 28" aria-hidden>
            {[10, 7, 4].map((r, i) => (
                <circle
                    key={i}
                    cx="14"
                    cy="14"
                    r={r}
                    fill="none"
                    stroke="var(--ming-gold, #d4af37)"
                    strokeWidth={0.8}
                    opacity={i === active - 1 ? 0.95 : 0.25}
                />
            ))}
        </svg>
    );
}

// ---------------------------------------------------------------------------
// Section wrapper — unified animation in / out
// ---------------------------------------------------------------------------

interface SectionProps {
    children: ReactNode;
    id: string;
}

const SectionCard = ({ children, id }: SectionProps) => (
    <motion.section
        id={id}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        style={{
            padding: '20px 18px 24px',
            borderRadius: 18,
            background:
                'linear-gradient(180deg, rgba(148,163,184,0.05) 0%, rgba(148,163,184,0.02) 100%)',
            border: '1px solid rgba(212,175,55,0.12)',
            marginBottom: 16,
        }}
    >
        {children}
    </motion.section>
);

// ---------------------------------------------------------------------------
// Summary row — collapsed completed section
// ---------------------------------------------------------------------------

interface SummaryRowProps {
    step: number;
    label: string;
    value: string;
    onEdit: () => void;
}

function SummaryRow({ step, label, value, onEdit }: SummaryRowProps) {
    return (
        <motion.button
            layout
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            onClick={onEdit}
            style={{
                width: '100%',
                minHeight: 52,
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '10px 14px',
                marginBottom: 8,
                borderRadius: 12,
                background: 'rgba(148,163,184,0.04)',
                border: '1px solid rgba(148,163,184,0.1)',
                textAlign: 'left',
                cursor: 'pointer',
            }}
        >
            <MiniRings active={((step % 3) + 1) as 1 | 2 | 3} />
            <div style={{ flex: 1, minWidth: 0 }}>
                <div
                    style={{
                        fontSize: 11,
                        letterSpacing: 0.4,
                        textTransform: 'uppercase',
                        color: 'rgba(148,163,184,0.7)',
                    }}
                >
                    {label}
                </div>
                <div
                    style={{
                        fontSize: 14,
                        color: '#e2e8f0',
                        marginTop: 2,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                    }}
                >
                    {value}
                </div>
            </div>
            <span
                style={{
                    fontSize: 12,
                    color: 'var(--ming-gold, #d4af37)',
                    opacity: 0.85,
                }}
            >
                Edit
            </span>
        </motion.button>
    );
}

// ---------------------------------------------------------------------------
// Horizon option card (Section 1)
// ---------------------------------------------------------------------------

interface HorizonOptionProps {
    active: boolean;
    ringIndex: 1 | 2 | 3;
    title: string;
    subtitle: string;
    onClick: () => void;
    children?: ReactNode;
}

function HorizonOption({
    active,
    ringIndex,
    title,
    subtitle,
    onClick,
    children,
}: HorizonOptionProps) {
    return (
        <button
            onClick={onClick}
            style={{
                width: '100%',
                minHeight: 72,
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '14px 16px',
                marginBottom: 10,
                borderRadius: 14,
                background: active
                    ? 'rgba(212,175,55,0.08)'
                    : 'rgba(148,163,184,0.04)',
                border: active
                    ? '1px solid rgba(212,175,55,0.55)'
                    : '1px solid rgba(148,163,184,0.12)',
                textAlign: 'left',
                color: '#e2e8f0',
                cursor: 'pointer',
                transition: 'background 200ms, border-color 200ms',
            }}
        >
            <div style={{ flexShrink: 0 }}>
                <MiniRings active={ringIndex} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 500 }}>{title}</div>
                <div
                    style={{
                        fontSize: 12,
                        color: 'rgba(148,163,184,0.85)',
                        marginTop: 2,
                    }}
                >
                    {subtitle}
                </div>
                {children}
            </div>
        </button>
    );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function FortuneAgentLuckDraw({
    onBack,
    onComplete,
}: FortuneAgentLuckDrawProps) {
    // Progression. `step` = the current "open" section (1..4). Completed
    // sections are rendered as summary rows; `editingStep` lets a user
    // jump back to edit a completed section without losing later input.
    const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
    const [editingStep, setEditingStep] = useState<1 | 2 | 3 | 4 | null>(null);
    const activeStep = editingStep ?? step;

    // Section 1 — horizon
    const [horizonKind, setHorizonKind] = useState<
        'this-month' | 'this-year' | 'pick' | null
    >(null);
    const [pickYear, setPickYear] = useState<number>(CURRENT_YEAR);
    const [pickMonth, setPickMonth] = useState<number | undefined>(undefined);

    // Section 2 — focus
    const [focus, setFocus] = useState<string[]>([]);

    // Section 3 — profile
    const [birthDate, setBirthDate] = useState<string>('');
    const [birthTime, setBirthTime] = useState<string | null>(null);
    const [timeUnknown, setTimeUnknown] = useState<boolean>(false);
    const [gender, setGender] = useState<string>('unknown');

    // Section 4 — draw
    const [drawing, setDrawing] = useState(false);

    // Refs for smooth-scroll on reveal
    const sectionRefs = {
        1: useRef<HTMLDivElement>(null!),
        2: useRef<HTMLDivElement>(null!),
        3: useRef<HTMLDivElement>(null!),
        4: useRef<HTMLDivElement>(null!),
    } as const;

    // Manually scroll so the active section's top lands just below the
    // sticky header with a bit of breathing room. `scroll-padding-top` +
    // `scrollIntoView` proved unreliable (browsers silently clamped to
    // the top of the document for section 1, which left the heading
    // clipped under the sticky header). Doing the math explicitly —
    // rect.top + scrollY - (header + breathing) — is predictable on both
    // desktop and mobile, regardless of viewport height.
    useEffect(() => {
        const ref = sectionRefs[activeStep as 1 | 2 | 3 | 4]?.current;
        if (!ref) return;
        const isInitial = activeStep === 1 && !editingStep;
        const t = setTimeout(() => {
            const rect = ref.getBoundingClientRect();
            const HEADER_OFFSET = 96; // ~72px sticky header + 24px breathing
            const target = Math.max(0, rect.top + window.scrollY - HEADER_OFFSET);
            window.scrollTo({
                top: target,
                behavior: isInitial ? 'auto' : 'smooth',
            });
        }, isInitial ? 0 : 120);
        return () => clearTimeout(t);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeStep]);

    // Advance helper — only move `step` forward, never backward via "next"
    const advance = useCallback(
        (from: 1 | 2 | 3) => {
            if (editingStep !== null) {
                // Finishing an edit — collapse back to the furthest step reached
                setEditingStep(null);
                return;
            }
            setStep((prev) => (prev > from ? prev : ((from + 1) as 2 | 3 | 4)));
        },
        [editingStep]
    );

    const editStep = (s: 1 | 2 | 3) => setEditingStep(s);

    // ---- Derived summaries -------------------------------------------------

    const horizonSummary = useMemo(() => {
        if (horizonKind === 'this-month') {
            return `Right now · ${MONTH_SHORT[NOW.getMonth()]} ${CURRENT_YEAR}`;
        }
        if (horizonKind === 'this-year') return `This year · ${CURRENT_YEAR}`;
        if (horizonKind === 'pick') {
            return pickMonth
                ? `${MONTH_SHORT[pickMonth - 1]} ${pickYear}`
                : `${pickYear}`;
        }
        return '';
    }, [horizonKind, pickYear, pickMonth]);

    const focusSummary = useMemo(() => {
        if (focus.length === 0) return '';
        return focus
            .map((id) => FOCUS_OPTIONS.find((f) => f.id === id)?.label ?? id)
            .join(' · ');
    }, [focus]);

    const profileSummary = useMemo(() => {
        if (!birthDate) return '';
        const g =
            GENDER_OPTIONS.find((o) => o.id === gender)?.label ?? gender;
        const t = timeUnknown
            ? 'time unknown'
            : birthTime
              ? birthTime
              : '—';
        return `${birthDate} · ${t} · ${g}`;
    }, [birthDate, birthTime, timeUnknown, gender]);

    // ---- Validation --------------------------------------------------------

    const horizonDone =
        horizonKind === 'this-month' ||
        horizonKind === 'this-year' ||
        (horizonKind === 'pick' && !!pickYear);

    const focusDone = focus.length >= 1;

    const profileDone =
        !!birthDate && (timeUnknown || !!birthTime) && !!gender;

    const canDraw = horizonDone && focusDone && profileDone && !drawing;

    // ---- Handlers ----------------------------------------------------------

    const toggleFocus = (id: string) => {
        setFocus((prev) => {
            if (prev.includes(id)) return prev.filter((x) => x !== id);
            if (prev.length >= MAX_FOCUS) {
                // Replace the oldest selection — feels smoother than a hard block
                return [prev[1], id];
            }
            return [...prev, id];
        });
    };

    const buildHorizonValue = (): HorizonValue => {
        if (horizonKind === 'this-month') return 'this-month';
        if (horizonKind === 'this-year') return 'this-year';
        return pickMonth
            ? { year: pickYear, month: pickMonth }
            : { year: pickYear };
    };

    const handleDraw = () => {
        if (!canDraw) return;
        setDrawing(true);
        // Brief ceremonial pause — ring-close + ember flare
        setTimeout(() => {
            onComplete?.({
                horizon: buildHorizonValue(),
                focus,
                profile: {
                    birthDate,
                    birthTime: timeUnknown ? null : birthTime,
                    timeUnknown,
                    gender,
                },
            });
            setDrawing(false);
        }, 950);
    };

    // -----------------------------------------------------------------------
    // Render
    // -----------------------------------------------------------------------

    const progressDots = [1, 2, 3, 4] as const;

    return (
        <div
            style={{
                minHeight: '100vh',
                background:
                    'linear-gradient(180deg, #200a06 0%, #4a1608 55%, #0c0a14 100%)',
                color: '#e2e8f0',
                fontFamily:
                    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                paddingBottom: 48,
            }}
        >
            {onBack ? (
                <button
                    type="button"
                    onClick={onBack}
                    aria-label="Back"
                    style={{
                        position: 'fixed',
                        top: 'calc(env(safe-area-inset-top, 0px) + 16px)',
                        right: 16,
                        zIndex: 60,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        minHeight: 44,
                        padding: '8px 14px',
                        borderRadius: 999,
                        border: '1px solid rgba(255,255,255,0.1)',
                        background: 'rgba(15,23,42,0.7)',
                        backdropFilter: 'blur(8px)',
                        WebkitBackdropFilter: 'blur(8px)',
                        color: '#cbd5e1',
                        fontSize: 14,
                        cursor: 'pointer',
                    }}
                >
                    <span aria-hidden>←</span>
                    <span>Back</span>
                </button>
            ) : null}

            {/* Sticky mini-header ------------------------------------------ */}
            <div
                style={{
                    position: 'sticky',
                    top: 0,
                    zIndex: 10,
                    background:
                        'linear-gradient(180deg, rgba(32,10,6,0.94) 0%, rgba(32,10,6,0.72) 100%)',
                    backdropFilter: 'blur(10px)',
                    WebkitBackdropFilter: 'blur(10px)',
                    borderBottom: '1px solid rgba(249, 115, 22, 0.14)',
                }}
            >
                <div
                    style={{
                        maxWidth: 390,
                        margin: '0 auto',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '12px 16px',
                    }}
                >
                    <div style={{ flex: 1 }}>
                        <div
                            style={{
                                fontSize: 13,
                                letterSpacing: 0.6,
                                color: 'rgba(148,163,184,0.7)',
                                textTransform: 'uppercase',
                            }}
                        >
                            Luck Draw
                        </div>
                        <div
                            style={{
                                fontSize: 14,
                                color: 'var(--ming-gold, #d4af37)',
                                fontFamily:
                                    'var(--ming-font-chinese), serif',
                            }}
                        >
                            抽運 · Draw the cycle
                        </div>
                    </div>
                    {/* 4-dot progress */}
                    <div style={{ display: 'flex', gap: 6 }}>
                        {progressDots.map((d) => {
                            const reached = d <= step;
                            const current = d === activeStep;
                            return (
                                <div
                                    key={d}
                                    style={{
                                        width: current ? 18 : 6,
                                        height: 6,
                                        borderRadius: 999,
                                        background: reached
                                            ? 'var(--ming-gold, #d4af37)'
                                            : 'rgba(148,163,184,0.25)',
                                        opacity: reached ? 0.95 : 1,
                                        transition:
                                            'width 250ms, background 250ms',
                                    }}
                                />
                            );
                        })}
                    </div>
                </div>
            </div>

            {/* Body -------------------------------------------------------- */}
            <div
                style={{
                    maxWidth: 390,
                    margin: '0 auto',
                    // Generous bottom padding gives scrollIntoView({block:'center'})
                    // enough runway to center any section, including the last one.
                    padding: '20px 16px 45vh',
                }}
            >
                <AnimatePresence initial={false}>
                    {/* ---- Section 1 ---- */}
                    {activeStep === 1 ? (
                        <div ref={sectionRefs[1]} key="s1-open">
                            <SectionCard id="section-1">
                                <SectionOneHorizon
                                    horizonKind={horizonKind}
                                    setHorizonKind={setHorizonKind}
                                    pickYear={pickYear}
                                    setPickYear={setPickYear}
                                    pickMonth={pickMonth}
                                    setPickMonth={setPickMonth}
                                    onNext={() => advance(1)}
                                    canNext={horizonDone}
                                />
                            </SectionCard>
                        </div>
                    ) : step >= 1 ? (
                        <SummaryRow
                            key="s1-summary"
                            step={1}
                            label="Horizon"
                            value={horizonSummary || '—'}
                            onEdit={() => editStep(1)}
                        />
                    ) : null}

                    {/* ---- Section 2 ---- */}
                    {step >= 2 && activeStep === 2 ? (
                        <div ref={sectionRefs[2]} key="s2-open">
                            <SectionCard id="section-2">
                                <SectionTwoFocus
                                    focus={focus}
                                    toggleFocus={toggleFocus}
                                    onNext={() => advance(2)}
                                    canNext={focusDone}
                                />
                            </SectionCard>
                        </div>
                    ) : step >= 2 ? (
                        <SummaryRow
                            key="s2-summary"
                            step={2}
                            label="Focus"
                            value={focusSummary || '—'}
                            onEdit={() => editStep(2)}
                        />
                    ) : null}

                    {/* ---- Section 3 ---- */}
                    {step >= 3 && activeStep === 3 ? (
                        <div ref={sectionRefs[3]} key="s3-open">
                            <SectionCard id="section-3">
                                <SectionThreeProfile
                                    birthDate={birthDate}
                                    setBirthDate={setBirthDate}
                                    birthTime={birthTime}
                                    setBirthTime={setBirthTime}
                                    timeUnknown={timeUnknown}
                                    setTimeUnknown={setTimeUnknown}
                                    gender={gender}
                                    setGender={setGender}
                                    onNext={() => advance(3)}
                                    canNext={profileDone}
                                />
                            </SectionCard>
                        </div>
                    ) : step >= 3 ? (
                        <SummaryRow
                            key="s3-summary"
                            step={3}
                            label="Profile"
                            value={profileSummary || '—'}
                            onEdit={() => editStep(3)}
                        />
                    ) : null}

                    {/* ---- Section 4 ---- */}
                    {step >= 4 && activeStep === 4 ? (
                        <div ref={sectionRefs[4]} key="s4-open">
                            <SectionCard id="section-4">
                                <SectionFourDraw
                                    horizonSummary={horizonSummary}
                                    focusSummary={focusSummary}
                                    profileSummary={profileSummary}
                                    canDraw={canDraw}
                                    drawing={drawing}
                                    onDraw={handleDraw}
                                />
                            </SectionCard>
                        </div>
                    ) : null}
                </AnimatePresence>
            </div>
        </div>
    );
}

export default FortuneAgentLuckDraw;

// ---------------------------------------------------------------------------
// Section 1 — Horizon
// ---------------------------------------------------------------------------

interface SectionOneProps {
    horizonKind: 'this-month' | 'this-year' | 'pick' | null;
    setHorizonKind: (k: 'this-month' | 'this-year' | 'pick') => void;
    pickYear: number;
    setPickYear: (y: number) => void;
    pickMonth: number | undefined;
    setPickMonth: (m: number | undefined) => void;
    onNext: () => void;
    canNext: boolean;
}

function SectionOneHorizon({
    horizonKind,
    setHorizonKind,
    pickYear,
    setPickYear,
    pickMonth,
    setPickMonth,
    onNext,
    canNext,
}: SectionOneProps) {
    const activeRing: 0 | 1 | 2 | 3 =
        horizonKind === 'this-month'
            ? 3
            : horizonKind === 'this-year'
              ? 2
              : horizonKind === 'pick'
                ? 1
                : 0;

    // Years: current - 5 .. current + 10 (covers retrospective + near-future)
    const years = useMemo(
        () =>
            Array.from({ length: 16 }, (_, i) => CURRENT_YEAR - 5 + i),
        []
    );

    return (
        <div>
            <SectionHeading
                step={1}
                chinese="何時"
                title="How far do you want to look?"
                subtitle="Pick a horizon. The cycle narrows from there."
            />

            <div
                style={{
                    display: 'flex',
                    justifyContent: 'center',
                    margin: '8px 0 18px',
                }}
            >
                <ConcentricRings active={activeRing} size={128} />
            </div>

            <HorizonOption
                active={horizonKind === 'this-month'}
                ringIndex={3}
                title="Right now"
                subtitle={`The present cycle · ${MONTH_SHORT[NOW.getMonth()]} ${CURRENT_YEAR}`}
                onClick={() => setHorizonKind('this-month')}
            />
            <HorizonOption
                active={horizonKind === 'this-year'}
                ringIndex={2}
                title="This year"
                subtitle={`The full arc of ${CURRENT_YEAR}`}
                onClick={() => setHorizonKind('this-year')}
            />
            <HorizonOption
                active={horizonKind === 'pick'}
                ringIndex={1}
                title="Pick a year or month"
                subtitle="A specific moment in time"
                onClick={() => setHorizonKind('pick')}
            >
                <AnimatePresence>
                    {horizonKind === 'pick' ? (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.3 }}
                            style={{ overflow: 'hidden', marginTop: 12 }}
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div
                                style={{
                                    fontSize: 11,
                                    color: 'rgba(148,163,184,0.7)',
                                    textTransform: 'uppercase',
                                    letterSpacing: 0.4,
                                    marginBottom: 6,
                                }}
                            >
                                Year
                            </div>
                            <div
                                style={{
                                    display: 'flex',
                                    gap: 6,
                                    overflowX: 'auto',
                                    paddingBottom: 6,
                                    scrollbarWidth: 'none',
                                }}
                            >
                                {years.map((y) => (
                                    <button
                                        key={y}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setPickYear(y);
                                        }}
                                        style={{
                                            minWidth: 56,
                                            height: 44,
                                            borderRadius: 10,
                                            padding: '0 10px',
                                            flexShrink: 0,
                                            background:
                                                pickYear === y
                                                    ? 'rgba(212,175,55,0.18)'
                                                    : 'rgba(148,163,184,0.06)',
                                            border:
                                                pickYear === y
                                                    ? '1px solid rgba(212,175,55,0.6)'
                                                    : '1px solid rgba(148,163,184,0.12)',
                                            color:
                                                pickYear === y
                                                    ? 'var(--ming-gold, #d4af37)'
                                                    : '#cbd5e1',
                                            fontSize: 14,
                                            cursor: 'pointer',
                                        }}
                                    >
                                        {y}
                                    </button>
                                ))}
                            </div>

                            <div
                                style={{
                                    fontSize: 11,
                                    color: 'rgba(148,163,184,0.7)',
                                    textTransform: 'uppercase',
                                    letterSpacing: 0.4,
                                    marginTop: 14,
                                    marginBottom: 6,
                                }}
                            >
                                Month{' '}
                                <span
                                    style={{
                                        textTransform: 'none',
                                        opacity: 0.7,
                                    }}
                                >
                                    (optional)
                                </span>
                            </div>
                            <div
                                style={{
                                    display: 'grid',
                                    gridTemplateColumns:
                                        'repeat(6, minmax(0,1fr))',
                                    gap: 6,
                                }}
                            >
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setPickMonth(undefined);
                                    }}
                                    style={monthPillStyle(pickMonth === undefined)}
                                >
                                    Any
                                </button>
                                {MONTH_SHORT.slice(0, 11).map((m, i) => (
                                    <button
                                        key={m}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setPickMonth(i + 1);
                                        }}
                                        style={monthPillStyle(
                                            pickMonth === i + 1
                                        )}
                                    >
                                        {m}
                                    </button>
                                ))}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setPickMonth(12);
                                    }}
                                    style={monthPillStyle(pickMonth === 12)}
                                >
                                    Dec
                                </button>
                            </div>
                        </motion.div>
                    ) : null}
                </AnimatePresence>
            </HorizonOption>

            <PrimaryButton disabled={!canNext} onClick={onNext}>
                Next →
            </PrimaryButton>
        </div>
    );
}

function monthPillStyle(active: boolean): CSSProperties {
    return {
        minHeight: 44,
        borderRadius: 10,
        background: active
            ? 'rgba(212,175,55,0.18)'
            : 'rgba(148,163,184,0.06)',
        border: active
            ? '1px solid rgba(212,175,55,0.6)'
            : '1px solid rgba(148,163,184,0.12)',
        color: active ? 'var(--ming-gold, #d4af37)' : '#cbd5e1',
        fontSize: 13,
        cursor: 'pointer',
    };
}

// ---------------------------------------------------------------------------
// Section 2 — Focus
// ---------------------------------------------------------------------------

interface SectionTwoProps {
    focus: string[];
    toggleFocus: (id: string) => void;
    onNext: () => void;
    canNext: boolean;
}

function SectionTwoFocus({
    focus,
    toggleFocus,
    onNext,
    canNext,
}: SectionTwoProps) {
    return (
        <div>
            <SectionHeading
                step={2}
                chinese="何事"
                title="Which parts of life?"
                subtitle={`Pick up to ${MAX_FOCUS}. A tight lens reads clearer.`}
            />

            <div
                style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 8,
                    marginTop: 12,
                    marginBottom: 4,
                }}
            >
                {FOCUS_OPTIONS.map((opt) => {
                    const active = focus.includes(opt.id);
                    return (
                        <button
                            key={opt.id}
                            onClick={() => toggleFocus(opt.id)}
                            style={{
                                minHeight: 44,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                padding: '0 14px',
                                borderRadius: 999,
                                background: active
                                    ? 'rgba(212,175,55,0.14)'
                                    : 'rgba(148,163,184,0.05)',
                                border: active
                                    ? '1px solid rgba(212,175,55,0.55)'
                                    : '1px solid rgba(148,163,184,0.14)',
                                color: active
                                    ? 'var(--ming-gold, #d4af37)'
                                    : '#cbd5e1',
                                cursor: 'pointer',
                                transition: 'all 180ms',
                            }}
                        >
                            <span
                                style={{
                                    fontFamily:
                                        'var(--ming-font-chinese), serif',
                                    fontSize: 16,
                                    lineHeight: 1,
                                    opacity: active ? 1 : 0.75,
                                }}
                            >
                                {opt.glyph}
                            </span>
                            <span style={{ fontSize: 13.5 }}>{opt.label}</span>
                        </button>
                    );
                })}
            </div>

            <div
                style={{
                    marginTop: 10,
                    fontSize: 11,
                    color: 'rgba(148,163,184,0.7)',
                }}
            >
                {focus.length} / {MAX_FOCUS} selected
                {focus.length === MAX_FOCUS
                    ? ' · choosing another replaces the first'
                    : ''}
            </div>

            <PrimaryButton disabled={!canNext} onClick={onNext}>
                Next →
            </PrimaryButton>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Section 3 — Profile
// ---------------------------------------------------------------------------

interface SectionThreeProps {
    birthDate: string;
    setBirthDate: (d: string) => void;
    birthTime: string | null;
    setBirthTime: (t: string | null) => void;
    timeUnknown: boolean;
    setTimeUnknown: (b: boolean) => void;
    gender: string;
    setGender: (g: string) => void;
    onNext: () => void;
    canNext: boolean;
}

function SectionThreeProfile({
    birthDate,
    setBirthDate,
    birthTime,
    setBirthTime,
    timeUnknown,
    setTimeUnknown,
    gender,
    setGender,
    onNext,
    canNext,
}: SectionThreeProps) {
    return (
        <div>
            <SectionHeading
                step={3}
                chinese="何人"
                title="Who's drawing?"
                subtitle="The cycle needs an anchor — your arrival into it."
            />

            {/* Birthday */}
            <div style={{ marginTop: 14 }}>
                <FieldLabel>Birthday</FieldLabel>
                <BirthdayScrollPicker value={birthDate} onChange={setBirthDate} />
            </div>

            {/* Birth time — 12 Earthly Branch pills */}
            <div style={{ marginTop: 18 }}>
                <FieldLabel>
                    Birth time{' '}
                    <span
                        style={{
                            color: 'rgba(148,163,184,0.6)',
                            fontWeight: 400,
                        }}
                    >
                        (double-hour)
                    </span>
                </FieldLabel>
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                        gap: 6,
                    }}
                >
                    {EARTHLY_BRANCHES.map((eb) => {
                        const selected =
                            birthTime === eb.hour && !timeUnknown;
                        return (
                            <button
                                key={eb.branch}
                                onClick={() => {
                                    setBirthTime(eb.hour);
                                    setTimeUnknown(false);
                                }}
                                style={{
                                    minHeight: 44,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    borderRadius: 10,
                                    padding: '6px 2px',
                                    background: selected
                                        ? 'var(--ming-accent, #b91c1c)'
                                        : 'rgba(148,163,184,0.06)',
                                    border: selected
                                        ? '1px solid var(--ming-accent, #b91c1c)'
                                        : '1px solid rgba(148,163,184,0.14)',
                                    color: selected ? '#fff' : '#cbd5e1',
                                    cursor: 'pointer',
                                }}
                            >
                                <span
                                    style={{
                                        fontFamily:
                                            'var(--ming-font-chinese), serif',
                                        fontSize: 16,
                                        lineHeight: 1,
                                    }}
                                >
                                    {eb.branch}
                                </span>
                                <span
                                    style={{
                                        fontSize: 10,
                                        opacity: 0.65,
                                        marginTop: 2,
                                    }}
                                >
                                    {eb.time}
                                </span>
                            </button>
                        );
                    })}
                </div>
                <button
                    onClick={() => {
                        setTimeUnknown(!timeUnknown);
                        if (!timeUnknown) setBirthTime(null);
                    }}
                    style={{
                        marginTop: 8,
                        width: '100%',
                        minHeight: 44,
                        borderRadius: 10,
                        background: timeUnknown
                            ? 'rgba(148,163,184,0.18)'
                            : 'rgba(148,163,184,0.05)',
                        border: timeUnknown
                            ? '1px solid rgba(148,163,184,0.4)'
                            : '1px solid rgba(148,163,184,0.12)',
                        color: '#94a3b8',
                        fontSize: 13,
                        cursor: 'pointer',
                    }}
                >
                    I don't know my birth time
                </button>
            </div>

            {/* Gender */}
            <div style={{ marginTop: 18 }}>
                <FieldLabel>
                    Gender{' '}
                    <span
                        style={{
                            color: 'rgba(148,163,184,0.6)',
                            fontWeight: 400,
                        }}
                    >
                        (for luck pillar direction)
                    </span>
                </FieldLabel>
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(3, minmax(0,1fr))',
                        gap: 8,
                    }}
                >
                    {GENDER_OPTIONS.map((opt) => {
                        const active = gender === opt.id;
                        return (
                            <button
                                key={opt.id}
                                onClick={() => setGender(opt.id)}
                                style={{
                                    minHeight: 44,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: 6,
                                    borderRadius: 10,
                                    background: active
                                        ? 'rgba(148,163,184,0.16)'
                                        : 'rgba(148,163,184,0.05)',
                                    border: active
                                        ? '1.5px solid rgba(148,163,184,0.42)'
                                        : '1px solid rgba(148,163,184,0.12)',
                                    color: active ? '#e2e8f0' : '#94a3b8',
                                    fontSize: 13.5,
                                    cursor: 'pointer',
                                }}
                            >
                                {opt.icon ? <span>{opt.icon}</span> : null}
                                <span>{opt.label}</span>
                            </button>
                        );
                    })}
                </div>
            </div>

            <PrimaryButton disabled={!canNext} onClick={onNext}>
                Next →
            </PrimaryButton>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Section 4 — The Draw
// ---------------------------------------------------------------------------

interface SectionFourProps {
    horizonSummary: string;
    focusSummary: string;
    profileSummary: string;
    canDraw: boolean;
    drawing: boolean;
    onDraw: () => void;
}

function SectionFourDraw({
    horizonSummary,
    focusSummary,
    profileSummary,
    canDraw,
    drawing,
    onDraw,
}: SectionFourProps) {
    return (
        <div>
            <SectionHeading
                step={4}
                chinese="抽運"
                title="Pull the cycle"
                subtitle="One breath, one draw. The rings will close."
            />

            {/* Recap card */}
            <div
                style={{
                    marginTop: 14,
                    marginBottom: 24,
                    padding: '14px 16px',
                    borderRadius: 14,
                    background: 'rgba(148,163,184,0.04)',
                    border: '1px solid rgba(212,175,55,0.14)',
                }}
            >
                <RecapRow label="Horizon" value={horizonSummary} />
                <RecapRow label="Focus" value={focusSummary} />
                <RecapRow label="You" value={profileSummary} last />
            </div>

            {/* Ember-like CTA */}
            <div
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    marginTop: 8,
                }}
            >
                <EmberButton
                    disabled={!canDraw}
                    drawing={drawing}
                    onClick={onDraw}
                />
                <div
                    style={{
                        marginTop: 14,
                        fontSize: 12,
                        color: 'rgba(148,163,184,0.6)',
                    }}
                >
                    {drawing
                        ? 'The cycle is closing…'
                        : 'Tap once. The draw is singular.'}
                </div>
            </div>
        </div>
    );
}

function RecapRow({
    label,
    value,
    last,
}: {
    label: string;
    value: string;
    last?: boolean;
}) {
    return (
        <div
            style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                padding: '8px 0',
                borderBottom: last
                    ? 'none'
                    : '1px dashed rgba(148,163,184,0.12)',
                gap: 12,
            }}
        >
            <span
                style={{
                    fontSize: 11,
                    color: 'rgba(148,163,184,0.7)',
                    textTransform: 'uppercase',
                    letterSpacing: 0.4,
                    flexShrink: 0,
                }}
            >
                {label}
            </span>
            <span
                style={{
                    fontSize: 13,
                    color: '#e2e8f0',
                    textAlign: 'right',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                }}
            >
                {value || '—'}
            </span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Ember Button — pre-animated breathing loop + draw flare
// ---------------------------------------------------------------------------

function EmberButton({
    disabled,
    drawing,
    onClick,
}: {
    disabled: boolean;
    drawing: boolean;
    onClick: () => void;
}) {
    return (
        <div
            style={{
                position: 'relative',
                width: 220,
                height: 220,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
            }}
        >
            {/* Outer ring — closes in when drawing */}
            <motion.svg
                width={220}
                height={220}
                viewBox="0 0 220 220"
                style={{ position: 'absolute', inset: 0 }}
                animate={
                    drawing
                        ? { rotate: 360, scale: 0.78 }
                        : { rotate: 360, scale: 1 }
                }
                transition={{
                    rotate: {
                        duration: 24,
                        ease: 'linear',
                        repeat: Infinity,
                    },
                    scale: { duration: 0.7, ease: [0.22, 1, 0.36, 1] },
                }}
            >
                <circle
                    cx="110"
                    cy="110"
                    r="96"
                    fill="none"
                    stroke="rgba(212,175,55,0.4)"
                    strokeWidth="1"
                    strokeDasharray="3 7"
                />
            </motion.svg>

            {/* Mid ring */}
            <motion.svg
                width={220}
                height={220}
                viewBox="0 0 220 220"
                style={{ position: 'absolute', inset: 0 }}
                animate={
                    drawing
                        ? { rotate: -360, scale: 0.82 }
                        : { rotate: -360, scale: 1 }
                }
                transition={{
                    rotate: {
                        duration: 34,
                        ease: 'linear',
                        repeat: Infinity,
                    },
                    scale: { duration: 0.75 },
                }}
            >
                <circle
                    cx="110"
                    cy="110"
                    r="76"
                    fill="none"
                    stroke="rgba(212,175,55,0.55)"
                    strokeWidth="1"
                    strokeDasharray="1 4"
                />
            </motion.svg>

            {/* Breathing glow halo */}
            <motion.div
                animate={{
                    opacity: drawing ? [0.35, 0.95, 0.6] : [0.35, 0.6, 0.35],
                    scale: drawing ? [1, 1.25, 1.1] : [1, 1.08, 1],
                }}
                transition={{
                    duration: drawing ? 0.9 : 3.2,
                    repeat: drawing ? 0 : Infinity,
                    ease: 'easeInOut',
                }}
                style={{
                    position: 'absolute',
                    width: 150,
                    height: 150,
                    borderRadius: '50%',
                    background:
                        'radial-gradient(circle, rgba(212,175,55,0.35) 0%, rgba(185,28,28,0.18) 45%, rgba(0,0,0,0) 70%)',
                    filter: 'blur(6px)',
                    pointerEvents: 'none',
                }}
            />

            {/* The button itself */}
            <motion.button
                onClick={onClick}
                disabled={disabled}
                whileTap={disabled ? undefined : { scale: 0.96 }}
                animate={{
                    boxShadow: disabled
                        ? '0 0 0 rgba(0,0,0,0)'
                        : drawing
                          ? '0 0 40px rgba(212,175,55,0.75), 0 0 80px rgba(185,28,28,0.4)'
                          : [
                                '0 0 18px rgba(212,175,55,0.45)',
                                '0 0 28px rgba(212,175,55,0.65)',
                                '0 0 18px rgba(212,175,55,0.45)',
                            ],
                }}
                transition={{
                    duration: drawing ? 0.6 : 3.2,
                    repeat: drawing ? 0 : Infinity,
                    ease: 'easeInOut',
                }}
                style={{
                    position: 'relative',
                    width: 128,
                    height: 128,
                    borderRadius: '50%',
                    border: '1px solid rgba(212,175,55,0.7)',
                    background:
                        'radial-gradient(circle at 35% 30%, rgba(250,204,140,0.95) 0%, var(--ming-gold, #d4af37) 30%, var(--ming-accent, #b91c1c) 78%, #5b0e0e 100%)',
                    color: '#fff9ec',
                    fontSize: 13,
                    fontWeight: 600,
                    letterSpacing: 0.4,
                    cursor: disabled ? 'not-allowed' : 'pointer',
                    opacity: disabled ? 0.4 : 1,
                    filter: disabled
                        ? 'grayscale(0.5)'
                        : 'drop-shadow(0 2px 10px rgba(185,28,28,0.35))',
                    transition: 'opacity 200ms, filter 200ms',
                }}
            >
                <span
                    style={{
                        fontFamily: 'var(--ming-font-chinese), serif',
                        fontSize: 22,
                        display: 'block',
                        marginBottom: 4,
                    }}
                >
                    抽
                </span>
                <span>Draw my luck →</span>
            </motion.button>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Small shared pieces
// ---------------------------------------------------------------------------

function SectionHeading({
    step,
    chinese,
    title,
    subtitle,
}: {
    step: number;
    chinese: string;
    title: string;
    subtitle: string;
}) {
    return (
        <div style={{ marginBottom: 4 }}>
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    fontSize: 11,
                    color: 'rgba(148,163,184,0.6)',
                    textTransform: 'uppercase',
                    letterSpacing: 0.8,
                }}
            >
                <span>Step {step} / 4</span>
                <span
                    style={{
                        flex: 1,
                        height: 1,
                        background:
                            'linear-gradient(to right, rgba(212,175,55,0.25), rgba(0,0,0,0))',
                    }}
                />
                <span
                    style={{
                        fontFamily: 'var(--ming-font-chinese), serif',
                        fontSize: 14,
                        color: 'var(--ming-gold, #d4af37)',
                        letterSpacing: 2,
                    }}
                >
                    {chinese}
                </span>
            </div>
            <h2
                style={{
                    fontSize: 20,
                    fontWeight: 500,
                    color: '#f1f5f9',
                    margin: '6px 0 4px',
                    lineHeight: 1.25,
                }}
            >
                {title}
            </h2>
            <p
                style={{
                    margin: 0,
                    fontSize: 13,
                    color: 'rgba(148,163,184,0.8)',
                }}
            >
                {subtitle}
            </p>
        </div>
    );
}

function FieldLabel({ children }: { children: ReactNode }) {
    return (
        <label
            style={{
                display: 'block',
                fontSize: 12.5,
                fontWeight: 500,
                color: '#cbd5e1',
                marginBottom: 6,
            }}
        >
            {children}
        </label>
    );
}

function PrimaryButton({
    disabled,
    onClick,
    children,
}: {
    disabled?: boolean;
    onClick?: () => void;
    children: ReactNode;
}) {
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            style={{
                marginTop: 20,
                width: '100%',
                minHeight: 48,
                borderRadius: 12,
                background: disabled
                    ? 'rgba(148,163,184,0.08)'
                    : 'linear-gradient(135deg, var(--ming-accent, #b91c1c), #7f1d1d)',
                border: disabled
                    ? '1px solid rgba(148,163,184,0.12)'
                    : '1px solid rgba(212,175,55,0.3)',
                color: disabled ? 'rgba(148,163,184,0.5)' : '#fef3c7',
                fontSize: 15,
                fontWeight: 500,
                letterSpacing: 0.3,
                cursor: disabled ? 'not-allowed' : 'pointer',
                transition: 'opacity 200ms',
            }}
        >
            {children}
        </button>
    );
}
