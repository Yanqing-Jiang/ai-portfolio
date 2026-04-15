/**
 * FortuneAgentCustomWishResult — 問 Custom Wish reading.
 *
 * Theme continuity: blue accent (#60a5fa) carries through from hub's
 * ink-pool section into input into result. Gold reserved for classical
 * citation cards (shared brand anchor).
 *
 * Tabs: Verdict · Anchor (which pillars matter for this question) ·
 *       Why (mechanism + classical citations) · Ask (oracle scroll).
 *
 * Copy shape follows psychology research: anchor → conditional lean →
 * mitigation → one-thing-this-week closure.
 *
 * Research anchors:
 * - ~/homer/output/gemini/fortune-mobile-tabs-ux-2026-04-15-1400.md
 * - ~/homer/output/gemini/fortune-bazi-result-design-2026-04-15-1400.md
 * - ~/homer/output/gemini/fortune-psychology-doubt-resolution-2026-04-15-1400.md
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    ChevronDown,
    CheckCircle2,
    AlertTriangle,
    XCircle,
    Sparkles,
    Zap,
    Star,
    ShieldCheck,
    Info,
} from 'lucide-react';
import {
    FortuneAgentResultShell,
    type FortuneTab,
} from './FortuneAgentResultShell';
import {
    FortuneAgentAskTab,
    type AskTurn,
} from './FortuneAgentAskTab';
import {
    FORTUNE_THEMES,
    FORTUNE_GOLD,
    FORTUNE_GOLD_SOFT,
    FORTUNE_CHINESE_FONT,
} from './fortuneAgentTheme';

interface FortuneAgentCustomWishResultProps {
    onBack?: () => void;
    initialQuestion?: string;
}

const THEME = FORTUNE_THEMES['custom-wish']; // blue / glyph 問

// --- Types ------------------------------------------------------------

interface Condition {
    id: string;
    type: 'check' | 'warn' | 'cross';
    text: string;
}

interface AnchorPillar {
    id: string;
    label: string;
    symbol: string;
    relevance: number;
    bullets: string[];
}

interface Mechanism {
    id: string;
    name: string;
    bullets: string[];
    icon: React.FC<{ className?: string; style?: React.CSSProperties }>;
    citation: { source: string; text: string; translation: string };
}

// --- Mock data --------------------------------------------------------

const MOCK_CONDITIONS: Condition[] = [
    { id: 'c1', type: 'check', text: 'Earth-Metal flow supports the career pivot.' },
    { id: 'c2', type: 'warn', text: 'First 90 days: friction with your Hour Pillar.' },
    {
        id: 'c3',
        type: 'cross',
        text: "Don't sign if start date lands in July (Fire–Fire clash).",
    },
];

const MOCK_ANCHORS: AnchorPillar[] = [
    {
        id: 'p1',
        label: 'Day Master',
        symbol: '丙 Fire',
        relevance: 95,
        bullets: [
            'Your fire nature seeks challenge.',
            "Shanghai's pace matches your rhythm.",
            'Dynamic environment feeds your Qi.',
        ],
    },
    {
        id: 'p2',
        label: 'Wealth Star',
        symbol: 'Earth',
        relevance: 72,
        bullets: [
            'Stable financial growth expected.',
            'Requires consistent daily output.',
            'Secondary gains from Q4 onwards.',
        ],
    },
    {
        id: 'p3',
        label: 'Fame Star',
        symbol: 'Wood',
        relevance: 68,
        bullets: [
            'Industry reputation will expand.',
            'Mentors appear in early 2027.',
            'Visibility increases significantly.',
        ],
    },
    {
        id: 'p4',
        label: 'Hour Pillar',
        symbol: '癸巳',
        relevance: 45,
        bullets: [
            'Water–Fire friction at daily cycles.',
            'Late-night decision fatigue likely.',
            'Physical stress needs management.',
        ],
    },
];

const MOCK_MECHANISMS: Mechanism[] = [
    {
        id: 'm1',
        name: 'Fire nature matches city of ambition',
        icon: Zap,
        bullets: [
            'Bing Fire thrives in active hubs.',
            'The Wood–Fire axis is dominant.',
            'Success through visible action.',
        ],
        citation: {
            source: '滴天髓 · 丙火',
            text: '丙火猛烈，欺霜侮雪。能煅庚金，逢辛反怯。',
            translation:
                'Bing Fire is fierce; it defies frost and insults snow. It can forge Geng metal, but fears Xin metal.',
        },
    },
    {
        id: 'm2',
        name: 'Earth–Metal flow supports the pivot',
        icon: ShieldCheck,
        bullets: [
            'Smooth transition between roles.',
            'Wealth creation through logic.',
            'Structural stability in contracts.',
        ],
        citation: {
            source: '淵海子平 · 財星',
            text: '何知其人富，財氣通門戶。',
            translation:
                'How do we know a person is wealthy? When the wealth energy flows through the gates.',
        },
    },
    {
        id: 'm3',
        name: 'Fame Star active in 2026',
        icon: Star,
        bullets: [
            '2026 Fire Horse fuels recognition.',
            'Year Pillar resonance is high.',
            'Social capital yields dividends.',
        ],
        citation: {
            source: '子平真詮 · 名利',
            text: '官以印為資，官星有氣。',
            translation:
                'Authority relies on the Seal for support; when the Authority star has Qi, reputation flourishes.',
        },
    },
    {
        id: 'm4',
        name: 'Hour Pillar friction: late-night stress',
        icon: AlertTriangle,
        bullets: [
            'Daily grind may tax the spirit.',
            'Incompatibility with nocturnal work.',
            'Need for grounding rituals.',
        ],
        citation: {
            source: '命理約言 · 時柱',
            text: '凡時柱受冲，主晚景及日用。',
            translation:
                'When the Hour Pillar is clashed, it affects the later years and daily routines.',
        },
    },
];

const SUGGESTED_CHIPS = [
    'What if I take the other offer?',
    'How about next quarter?',
    'Is my partner supportive?',
    "Any red flags I'm missing?",
];

const TABS: FortuneTab[] = [
    { id: 'Verdict', label: 'Verdict' },
    { id: 'Anchor', label: 'Anchor' },
    { id: 'Why', label: 'Why' },
    { id: 'Ask', label: 'Ask' },
];

// --- Component --------------------------------------------------------

export const FortuneAgentCustomWishResult: React.FC<FortuneAgentCustomWishResultProps> = ({
    onBack,
    initialQuestion = 'Should I take the new job in Shanghai?',
}) => {
    const [activeTab, setActiveTab] = useState<string>('Verdict');
    const [expandedAnchor, setExpandedAnchor] = useState<string | null>('p1');
    const [isReasoningOpen, setIsReasoningOpen] = useState(false);
    const [askInput, setAskInput] = useState('');
    const [askHistory, setAskHistory] = useState<AskTurn[]>([
        {
            id: 'a1',
            role: 'agent',
            content:
                'The real question under your question: is this city a match for your Fire, or a stage for your ambition? The chart says both — but the ambition peaks in Q3.',
        },
    ]);

    const handleSend = () => {
        if (!askInput.trim()) return;
        const msg = askInput.trim();
        setAskHistory((h) => [
            ...h,
            { id: String(Date.now()), role: 'user', content: msg },
        ]);
        setAskInput('');
        setTimeout(() => {
            setAskHistory((h) => [
                ...h,
                {
                    id: String(Date.now() + 1),
                    role: 'agent',
                    content:
                        "The other offer's Month Pillar is quieter — lower visibility but gentler friction. If you want the spotlight, Shanghai. If you want the runway, the other.",
                },
            ]);
        }, 900);
    };

    return (
        <FortuneAgentResultShell
            purpose="custom-wish"
            eyebrow="Custom Wish"
            subtitle={initialQuestion}
            tabs={TABS}
            activeTabId={activeTab}
            onTabChange={setActiveTab}
            onBack={onBack}
        >
            <AnimatePresence mode="wait">
                {activeTab === 'Verdict' && (
                    <motion.div
                        key="verdict"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                        className="space-y-6"
                    >
                        {/* Question quote */}
                        <div
                            className="relative rounded-r-2xl border-l-2 py-4 pl-6 pr-4"
                            style={{
                                borderColor: THEME.accentSoft,
                                background: THEME.accentWash,
                            }}
                        >
                            <span
                                aria-hidden
                                className="absolute -left-1 -top-2 text-4xl italic"
                                style={{
                                    color: `${THEME.accent}33`,
                                    fontFamily: FORTUNE_CHINESE_FONT,
                                }}
                            >
                                “
                            </span>
                            <p
                                className="text-base italic leading-relaxed text-white/90"
                                style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                            >
                                {initialQuestion}
                            </p>
                            <span
                                aria-hidden
                                className="absolute bottom-0 right-4 text-4xl italic"
                                style={{
                                    color: `${THEME.accent}33`,
                                    fontFamily: FORTUNE_CHINESE_FONT,
                                }}
                            >
                                ”
                            </span>
                        </div>

                        {/* Hero verdict */}
                        <div
                            className="relative overflow-hidden rounded-2xl border p-6 backdrop-blur-sm"
                            style={{
                                borderColor: THEME.accentSoft,
                                background: 'rgba(12,10,20,0.55)',
                            }}
                        >
                            <div
                                className="pointer-events-none absolute right-0 top-0 h-48 w-48 -translate-y-1/2 translate-x-1/2 rounded-full border-[16px]"
                                style={{ borderColor: `${THEME.accent}0d` }}
                            />
                            <div className="relative z-10 space-y-6">
                                <div>
                                    <h2
                                        className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em]"
                                        style={{ color: THEME.accent }}
                                    >
                                        Final Verdict
                                    </h2>
                                    <p
                                        className="text-2xl font-bold leading-tight text-white"
                                        style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                    >
                                        Yes, but wait until{' '}
                                        <span style={{ color: THEME.accent }}>
                                            Q3 2026
                                        </span>{' '}
                                        for the most harmonious transition.
                                    </p>
                                </div>

                                <div className="space-y-2.5">
                                    {MOCK_CONDITIONS.map((c) => (
                                        <div
                                            key={c.id}
                                            className="flex items-center gap-3 rounded-xl border p-3"
                                            style={{
                                                borderColor: 'rgba(248,250,252,0.08)',
                                                background: 'rgba(248,250,252,0.03)',
                                            }}
                                        >
                                            {c.type === 'check' && (
                                                <CheckCircle2 className="h-5 w-5 flex-none text-emerald-500" />
                                            )}
                                            {c.type === 'warn' && (
                                                <AlertTriangle className="h-5 w-5 flex-none text-amber-500" />
                                            )}
                                            {c.type === 'cross' && (
                                                <XCircle className="h-5 w-5 flex-none text-red-500" />
                                            )}
                                            <span className="text-sm leading-snug text-white/85">
                                                {c.text}
                                            </span>
                                        </div>
                                    ))}
                                </div>

                                <div
                                    className="border-t pt-4"
                                    style={{ borderColor: 'rgba(248,250,252,0.08)' }}
                                >
                                    <p
                                        className="text-sm italic leading-relaxed text-white/65"
                                        style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                    >
                                        The Metal–Water axis of Shanghai provides stable
                                        ground for your Bing Fire nature — provided
                                        you don't ignite too early in the summer heat.
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Reasoning trace */}
                        <div
                            className="overflow-hidden rounded-2xl border"
                            style={{
                                borderColor: 'rgba(248,250,252,0.08)',
                                background: 'rgba(248,250,252,0.03)',
                            }}
                        >
                            <button
                                onClick={() => setIsReasoningOpen(!isReasoningOpen)}
                                className="group flex w-full items-center justify-between p-4"
                            >
                                <div className="flex items-center gap-2">
                                    <Info
                                        className="h-4 w-4"
                                        style={{ color: `${THEME.accent}aa` }}
                                    />
                                    <span className="text-[10px] uppercase tracking-widest text-white/50 group-hover:text-white/75">
                                        Reasoning trace
                                    </span>
                                </div>
                                <ChevronDown
                                    className={`h-4 w-4 transition-transform ${isReasoningOpen ? 'rotate-180' : ''}`}
                                    style={{ color: `${THEME.accent}88` }}
                                />
                            </button>
                            <AnimatePresence initial={false}>
                                {isReasoningOpen && (
                                    <motion.div
                                        initial={{ height: 0 }}
                                        animate={{ height: 'auto' }}
                                        exit={{ height: 0 }}
                                        className="overflow-hidden border-t"
                                        style={{
                                            borderColor: 'rgba(248,250,252,0.06)',
                                            background: 'rgba(12,10,20,0.4)',
                                        }}
                                    >
                                        <div className="space-y-4 p-6">
                                            {[
                                                {
                                                    step: 1,
                                                    label: 'Chart Extraction',
                                                    desc: 'Sync with user birth pillars.',
                                                },
                                                {
                                                    step: 2,
                                                    label: 'Elemental Balance',
                                                    desc: 'Detect Wood/Fire axis dominance.',
                                                },
                                                {
                                                    step: 3,
                                                    label: 'Temporal Mapping',
                                                    desc: 'Correlate with 2026 Fire Horse energy.',
                                                },
                                            ].map((s) => (
                                                <div
                                                    key={s.step}
                                                    className="flex items-start gap-4"
                                                >
                                                    <div
                                                        className="flex h-6 w-6 flex-none items-center justify-center rounded-full border font-mono text-[10px]"
                                                        style={{
                                                            borderColor: THEME.accentSoft,
                                                            background: THEME.accentWash,
                                                            color: THEME.accent,
                                                        }}
                                                    >
                                                        {s.step}
                                                    </div>
                                                    <div>
                                                        <h4 className="text-xs font-bold uppercase tracking-wide text-white/80">
                                                            {s.label}
                                                        </h4>
                                                        <p className="mt-1 text-xs text-white/45">
                                                            {s.desc}
                                                        </p>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>

                        {/* Closure — one thing this week */}
                        <div
                            className="rounded-2xl border p-4"
                            style={{
                                borderColor: THEME.accentSoft,
                                background: 'rgba(12,10,20,0.5)',
                            }}
                        >
                            <p
                                className="mb-1 text-[10px] font-bold uppercase tracking-[0.22em]"
                                style={{ color: THEME.accent }}
                            >
                                One thing this week
                            </p>
                            <p className="text-sm leading-relaxed text-white/85">
                                Before deciding, block one quiet Wu 午 hour (11–13h)
                                to write: what would "the right choice" feel like in 12
                                months? The answer usually arrives in that hour.
                            </p>
                        </div>
                    </motion.div>
                )}

                {activeTab === 'Anchor' && (
                    <motion.div
                        key="anchor"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                        className="space-y-4"
                    >
                        <div className="flex items-center gap-2">
                            <span
                                aria-hidden
                                className="h-px w-6"
                                style={{ background: `${THEME.accent}4d` }}
                            />
                            <p
                                className="text-[10px] uppercase tracking-[0.22em]"
                                style={{ color: THEME.accent }}
                            >
                                Chart Anchors
                            </p>
                        </div>

                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                            {MOCK_ANCHORS.map((a) => {
                                const open = expandedAnchor === a.id;
                                return (
                                    <motion.div
                                        key={a.id}
                                        layout
                                        onClick={() =>
                                            setExpandedAnchor(open ? null : a.id)
                                        }
                                        className="cursor-pointer rounded-2xl border p-4 transition-all"
                                        style={{
                                            borderColor: open
                                                ? THEME.accent
                                                : THEME.accentSoft,
                                            background: open
                                                ? THEME.accentWash
                                                : 'rgba(12,10,20,0.55)',
                                            boxShadow: open
                                                ? `0 0 22px -8px ${THEME.accentGlow}`
                                                : 'none',
                                        }}
                                    >
                                        <div className="mb-2 flex items-start justify-between">
                                            <div>
                                                <h3
                                                    className="text-[10px] font-bold uppercase tracking-widest"
                                                    style={{ color: THEME.accent }}
                                                >
                                                    {a.label}
                                                </h3>
                                                <p
                                                    className="text-lg font-bold text-white/90"
                                                    style={{
                                                        fontFamily: FORTUNE_CHINESE_FONT,
                                                    }}
                                                >
                                                    {a.symbol}
                                                </p>
                                            </div>
                                            <div
                                                className="rounded-full border px-2 py-0.5 text-[9px] font-bold"
                                                style={{
                                                    borderColor: THEME.accentSoft,
                                                    background: THEME.accentWash,
                                                    color: THEME.accent,
                                                }}
                                            >
                                                {a.relevance}%
                                            </div>
                                        </div>

                                        <AnimatePresence initial={false}>
                                            {open && (
                                                <motion.div
                                                    initial={{ opacity: 0, height: 0 }}
                                                    animate={{ opacity: 1, height: 'auto' }}
                                                    exit={{ opacity: 0, height: 0 }}
                                                    className="space-y-2 border-t pt-4"
                                                    style={{
                                                        borderColor: THEME.accentSoft,
                                                    }}
                                                >
                                                    {a.bullets.map((b, i) => (
                                                        <div
                                                            key={i}
                                                            className="flex gap-2 text-xs leading-relaxed text-white/70"
                                                        >
                                                            <span
                                                                className="mt-1"
                                                                style={{ color: THEME.accent }}
                                                            >
                                                                ◈
                                                            </span>
                                                            {b}
                                                        </div>
                                                    ))}
                                                </motion.div>
                                            )}
                                        </AnimatePresence>
                                    </motion.div>
                                );
                            })}
                        </div>

                        <p className="px-8 text-center text-[10px] italic text-white/35">
                            Tap each pillar to see how it anchors the question's answer.
                        </p>
                    </motion.div>
                )}

                {activeTab === 'Why' && (
                    <motion.div
                        key="why"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                        className="space-y-4"
                    >
                        <div className="flex items-center gap-2">
                            <span
                                aria-hidden
                                className="h-px w-6"
                                style={{ background: `${THEME.accent}4d` }}
                            />
                            <p
                                className="text-[10px] uppercase tracking-[0.22em]"
                                style={{ color: THEME.accent }}
                            >
                                Classical Mechanisms
                            </p>
                        </div>

                        {MOCK_MECHANISMS.map((mech) => {
                            const Icon = mech.icon;
                            return (
                                <div
                                    key={mech.id}
                                    className="overflow-hidden rounded-2xl border backdrop-blur-sm"
                                    style={{
                                        borderColor: THEME.accentSoft,
                                        background: 'rgba(12,10,20,0.55)',
                                    }}
                                >
                                    <div className="space-y-4 p-5">
                                        <div className="flex items-center gap-3">
                                            <div
                                                className="rounded-lg border p-2"
                                                style={{
                                                    borderColor: THEME.accentSoft,
                                                    background: THEME.accentWash,
                                                }}
                                            >
                                                <Icon
                                                    className="h-4 w-4"
                                                    style={{ color: THEME.accent }}
                                                />
                                            </div>
                                            <h3
                                                className="font-bold text-white/90"
                                                style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                            >
                                                {mech.name}
                                            </h3>
                                        </div>

                                        <ul className="space-y-2.5">
                                            {mech.bullets.map((b, i) => (
                                                <li
                                                    key={i}
                                                    className="flex gap-3 text-xs leading-relaxed text-white/75"
                                                >
                                                    <span
                                                        className="mt-0.5"
                                                        style={{ color: THEME.accent }}
                                                    >
                                                        ◈
                                                    </span>
                                                    {b}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>

                                    {/* Classical citation — gold anchor */}
                                    <div
                                        className="border-t p-4"
                                        style={{
                                            borderColor: FORTUNE_GOLD_SOFT,
                                            background: 'rgba(234,179,8,0.04)',
                                        }}
                                    >
                                        <p
                                            className="mb-1 text-[10px] font-bold uppercase tracking-widest"
                                            style={{ color: FORTUNE_GOLD }}
                                        >
                                            {mech.citation.source}
                                        </p>
                                        <p
                                            className="mb-1 text-sm leading-relaxed text-white/85"
                                            style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                        >
                                            {mech.citation.text}
                                        </p>
                                        <p className="text-[11px] italic text-white/45">
                                            {mech.citation.translation}
                                        </p>
                                    </div>
                                </div>
                            );
                        })}
                    </motion.div>
                )}

                {activeTab === 'Ask' && (
                    <motion.div
                        key="ask"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                    >
                        {/* Little synthesis card above the thread */}
                        <motion.div
                            initial={{ opacity: 0, scale: 0.98 }}
                            animate={{ opacity: 1, scale: 1 }}
                            className="mb-6 rounded-2xl border p-5"
                            style={{
                                borderColor: THEME.accent,
                                background: `linear-gradient(135deg, ${THEME.accent}1a, transparent 70%)`,
                                boxShadow: `0 0 40px -10px ${THEME.accentGlow}`,
                            }}
                        >
                            <h4
                                className="mb-3 flex items-center gap-2 font-bold"
                                style={{
                                    color: THEME.accent,
                                    fontFamily: FORTUNE_CHINESE_FONT,
                                }}
                            >
                                <Sparkles className="h-4 w-4" /> Synthesis
                            </h4>
                            <p
                                className="text-sm leading-relaxed text-white/90"
                                style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                            >
                                Go — and let Q3 2026 be the moment. Resource Star
                                supports the pivot; your task is to not perform
                                ambition in July, when Fire stacks on Fire.
                            </p>
                        </motion.div>

                        <FortuneAgentAskTab
                            purpose="custom-wish"
                            history={askHistory}
                            suggestedChips={SUGGESTED_CHIPS}
                            input={askInput}
                            onInputChange={setAskInput}
                            onSend={handleSend}
                            heading="Ask deeper"
                            placeholder="Refine the question…"
                        />
                    </motion.div>
                )}
            </AnimatePresence>
        </FortuneAgentResultShell>
    );
};

export default FortuneAgentCustomWishResult;
