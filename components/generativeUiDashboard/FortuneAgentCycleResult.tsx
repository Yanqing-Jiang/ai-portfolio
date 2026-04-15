/**
 * FortuneAgentCycleResult — 運 Cycle Reading (year/month luck timeline).
 *
 * Theme continuity: orange accent (#f97316) carries through from hub's
 * ember-ring section into input into result. Gold is reserved for
 * classical citation cards (shared brand anchor).
 *
 * Tabs: Now (current month snapshot) · Year (10-year sparklines) ·
 *       Why (luck-pillar mechanism cards) · Ask (oracle scroll).
 * Mobile-first with safe-area aware layout.
 *
 * Research anchors:
 * - ~/homer/output/gemini/fortune-mobile-tabs-ux-2026-04-15-1400.md
 * - ~/homer/output/gemini/fortune-bazi-result-design-2026-04-15-1400.md
 * - ~/homer/output/gemini/fortune-psychology-doubt-resolution-2026-04-15-1400.md
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
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

interface FortuneAgentCycleResultProps {
    onBack?: () => void;
}

const THEME = FORTUNE_THEMES['luck-draw']; // orange / glyph 運

// --- Mock data --------------------------------------------------------

const MOCK_CURRENT = {
    month: 'April 2026',
    pillar: '癸巳月',
    score: 68,
    bullets: [
        'Mood: internal restlessness meeting strategic clarity.',
        'Opportunity: harmonious Wood supports your Fire Day Master.',
        'Warning: Metal of the year brings pressure to consolidate.',
    ],
    citation: { text: '水火既濟，君子以思患而豫防之。', source: '《易經》' },
    horizonPosition: 0.2,
};

const MOCK_DECADES = [
    { name: '己丑', range: '2012 — 2021', status: 'past' as const },
    {
        name: '庚寅',
        range: '2022 — 2031',
        status: 'current' as const,
        analysis:
            'Metal shapes your Fire — a decade of material achievement through discipline.',
    },
    { name: '辛卯', range: '2032 — 2041', status: 'future' as const },
];

const MOCK_YEARS = [
    { year: 2025, label: '2025 · 33 sui', pillar: '乙巳', score: 52, scores: [45, 38, 50, 55, 60, 58, 52, 48, 45, 50, 55, 62], summary: ['Consolidation phase.', 'Watch health in early Q1.', 'Family harmony improves.'], citation: { text: '乙木生火，氣勢和平。', source: '《淵海子平》' } },
    { year: 2026, label: '2026 · 34 sui', pillar: '丙午', score: 78, scores: [60, 65, 68, 70, 75, 82, 85, 80, 78, 88, 92, 85], summary: ['Peak energy year.', 'Career breakthrough in Oct / Nov.', 'Yang-blade intensity — focus required.'], citation: { text: '丙午之火，得地而強。', source: '《子平真詮》' } },
    { year: 2027, label: '2027 · 35 sui', pillar: '丁未', score: 54, scores: [65, 60, 55, 52, 50, 48, 45, 42, 50, 55, 60, 62], summary: ['Steady consolidation.', 'Avoid high-risk pivots.', 'Focus on internal growth.'], citation: { text: '丁未土中，火氣收斂。', source: '《命理約言》' } },
    { year: 2028, label: '2028 · 36 sui', pillar: '戊申', score: 82, scores: [70, 75, 85, 88, 90, 85, 80, 78, 82, 85, 88, 85], summary: ['Surge in wealth affinity.', 'Strategic investments favored.', 'Travel brings opportunity.'], citation: { text: '戊申之土，生金化火。', source: '《滴天髓》' } },
    { year: 2029, label: '2029 · 37 sui', pillar: '己酉', score: 62, scores: [60, 58, 55, 52, 58, 62, 65, 68, 70, 65, 62, 60], summary: ['Balanced flow.', 'Partnership development.', 'Creative output peaks.'], citation: { text: '己酉金地，火入長生。', source: '《淵海子平》' } },
];

const MOCK_WHY_CARDS = [
    {
        name: 'Decade Pillar 庚寅 (2022—2031)',
        bullets: [
            'Metal shapes your Fire — discipline yields results.',
            'Growth in wood energy supports vitality.',
            'Resource accumulation through persistence.',
        ],
        citation: '滴天髓 · 庚金',
    },
    {
        name: 'Current Year 丙午 — 羊刃',
        bullets: [
            'Yang-blade intensity: high risk, high reward.',
            'Direct support to Day Master Bing Fire.',
            'Need for emotional grounding in summer.',
        ],
        citation: '淵海子平 · 羊刃',
    },
    {
        name: 'Luck Window: Late 2026',
        bullets: [
            'Triple Fire alignment in autumn months.',
            'Breakthrough period for career pivots.',
            'Social capital peaks in November.',
        ],
        citation: '子平真詮 · 運限',
    },
    {
        name: '2027 Strategy: Consolidation',
        bullets: [
            'Earth energy absorbs excess heat.',
            'Shift from expansion to stabilization.',
            'Ideal for property or family foundations.',
        ],
        citation: '命理約言',
    },
];

const SUGGESTED_CHIPS = [
    'What about 2027?',
    'When will money flow?',
    'Best career window?',
    'Pivot or hold?',
];

const TABS: FortuneTab[] = [
    { id: 'Now', label: 'Now' },
    { id: 'Year', label: 'Year' },
    { id: 'Why', label: 'Why' },
    { id: 'Ask', label: 'Ask' },
];

// --- Sub-components ---------------------------------------------------

const SparklineDots: React.FC<{ scores: number[]; activeMonth?: number }> = ({
    scores,
    activeMonth,
}) => (
    <div className="flex items-center gap-1">
        {scores.map((s, i) => {
            const color = s > 75 ? THEME.accent : s < 50 ? '#dc2626' : '#f8fafc';
            const opacity = s > 75 ? 1 : s < 50 ? 0.8 : 0.4;
            const isActive = activeMonth === i + 1;
            return (
                <div
                    key={i}
                    className="relative"
                    style={{
                        width: 6,
                        height: 6,
                        borderRadius: 9999,
                        backgroundColor: color,
                        opacity,
                    }}
                >
                    {isActive && (
                        <motion.div
                            className="absolute inset-[-4px] rounded-full border"
                            style={{ borderColor: THEME.accent }}
                            animate={{ scale: [1, 1.5, 1], opacity: [1, 0, 1] }}
                            transition={{ duration: 2, repeat: Infinity }}
                        />
                    )}
                </div>
            );
        })}
    </div>
);

const ElementRingSmall: React.FC<{ position: number }> = ({ position }) => (
    <div className="relative flex h-12 w-12 items-center justify-center">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
            <circle
                cx="50"
                cy="50"
                r="45"
                fill="transparent"
                stroke={THEME.accent}
                strokeWidth="2"
                strokeDasharray="2 4"
                opacity="0.4"
            />
            <motion.circle
                cx="50"
                cy="50"
                r="45"
                fill="transparent"
                stroke={THEME.accent}
                strokeWidth="6"
                strokeDasharray="282.7"
                strokeDashoffset={282.7 * (1 - position)}
                strokeLinecap="round"
            />
        </svg>
        <div
            className="absolute text-[8px] font-bold"
            style={{ color: THEME.accent }}
        >
            NOW
        </div>
    </div>
);

// --- Main component ---------------------------------------------------

export const FortuneAgentCycleResult: React.FC<FortuneAgentCycleResultProps> = ({
    onBack,
}) => {
    const [activeTab, setActiveTab] = useState<string>('Now');
    const [expandedYear, setExpandedYear] = useState<number | null>(2026);
    const [askInput, setAskInput] = useState('');
    const [askHistory, setAskHistory] = useState<AskTurn[]>([
        {
            id: 'a1',
            role: 'agent',
            content:
                'Your Fire is at full tide in 2026. The pressure you feel is not a sign to stop — it is the ember burning hottest. One thing to watch: don\'t confuse intensity for direction.',
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
                        '2027 (Ding Wei) tempers your Fire with moist Earth — a season to stabilize, not pivot. Master your current domain; the expansion returns in 2028.',
                },
            ]);
        }, 900);
    };

    return (
        <FortuneAgentResultShell
            purpose="luck-draw"
            eyebrow="Cycle Reading"
            subtitle="運勢 · Year & Month · Bing Fire"
            tabs={TABS}
            activeTabId={activeTab}
            onTabChange={setActiveTab}
            onBack={onBack}
        >
            {/* Decade strip — visible on Now / Year / Why tabs */}
            {activeTab !== 'Ask' && (
                <section
                    className="mb-6 rounded-2xl border p-3 backdrop-blur-sm"
                    style={{
                        borderColor: THEME.accentSoft,
                        background: 'rgba(12,10,20,0.55)',
                    }}
                >
                    <div className="space-y-1.5">
                        {MOCK_DECADES.map((d) => {
                            const current = d.status === 'current';
                            return (
                                <div
                                    key={d.name}
                                    className="flex items-center justify-between rounded-lg px-2 py-1"
                                    style={{
                                        background: current
                                            ? `${THEME.accent}12`
                                            : 'transparent',
                                        border: current
                                            ? `1px solid ${THEME.accentSoft}`
                                            : '1px solid transparent',
                                        opacity: current ? 1 : 0.4,
                                    }}
                                >
                                    <div className="flex items-center gap-3">
                                        <span
                                            className="text-sm font-bold"
                                            style={{
                                                fontFamily: FORTUNE_CHINESE_FONT,
                                                color: current
                                                    ? THEME.accent
                                                    : '#f8fafc',
                                            }}
                                        >
                                            {d.name}
                                        </span>
                                        <span className="text-[10px] uppercase tracking-wider text-white/60">
                                            {d.range}
                                        </span>
                                    </div>
                                    <span
                                        className="rounded px-1.5 text-[8px] font-bold uppercase"
                                        style={{
                                            color: current
                                                ? THEME.accent
                                                : 'rgba(248,250,252,0.5)',
                                            border: current
                                                ? `1px solid ${THEME.accentSoft}`
                                                : 'none',
                                        }}
                                    >
                                        {d.status}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </section>
            )}

            <AnimatePresence mode="wait">
                {activeTab === 'Now' && (
                    <motion.div
                        key="now"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                        className="space-y-6"
                    >
                        <div
                            className="relative overflow-hidden rounded-2xl border p-6 backdrop-blur-sm"
                            style={{
                                borderColor: THEME.accentSoft,
                                background: 'rgba(12,10,20,0.55)',
                            }}
                        >
                            <div className="absolute right-4 top-4">
                                <ElementRingSmall
                                    position={MOCK_CURRENT.horizonPosition}
                                />
                            </div>
                            <h2 className="mb-1 text-2xl font-bold text-[#f8fafc]">
                                {MOCK_CURRENT.month}
                            </h2>
                            <div className="mb-5 flex items-center gap-3">
                                <span
                                    className="text-lg font-bold"
                                    style={{
                                        color: THEME.accent,
                                        fontFamily: FORTUNE_CHINESE_FONT,
                                    }}
                                >
                                    {MOCK_CURRENT.pillar}
                                </span>
                                <div
                                    className="h-4 w-px"
                                    style={{ background: THEME.accentSoft }}
                                />
                                <div className="flex items-baseline gap-1.5">
                                    <span className="text-2xl font-bold text-[#f8fafc]">
                                        {MOCK_CURRENT.score}
                                    </span>
                                    <span className="text-[10px] uppercase tracking-widest text-white/45">
                                        luck
                                    </span>
                                </div>
                            </div>

                            <ul className="mb-6 space-y-2.5">
                                {MOCK_CURRENT.bullets.map((b, i) => (
                                    <li
                                        key={i}
                                        className="flex gap-3 text-sm leading-relaxed text-white/80"
                                    >
                                        <span style={{ color: THEME.accent }}>✦</span>
                                        {b}
                                    </li>
                                ))}
                            </ul>

                            {/* Classical citation — gold anchor */}
                            <div
                                className="flex items-end justify-between gap-3 border-t pt-4"
                                style={{ borderColor: FORTUNE_GOLD_SOFT }}
                            >
                                <p
                                    className="max-w-[70%] text-xs italic leading-relaxed text-white/50"
                                    style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                >
                                    "{MOCK_CURRENT.citation.text}"
                                </p>
                                <p
                                    className="text-[10px] font-bold uppercase tracking-widest"
                                    style={{ color: FORTUNE_GOLD }}
                                >
                                    {MOCK_CURRENT.citation.source}
                                </p>
                            </div>
                        </div>

                        {/* One-thing-this-week closure */}
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
                                Pick one consolidation task you've been avoiding
                                (renegotiate a rate, finalize a filing, close a
                                loop). Ship it before the new month enters.
                            </p>
                        </div>
                    </motion.div>
                )}

                {activeTab === 'Year' && (
                    <motion.div
                        key="year"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                        className="space-y-3"
                    >
                        {MOCK_YEARS.map((y) => {
                            const open = expandedYear === y.year;
                            return (
                                <div key={y.year} className="flex flex-col">
                                    <button
                                        onClick={() =>
                                            setExpandedYear(open ? null : y.year)
                                        }
                                        className="flex items-center justify-between rounded-xl border p-4 transition-all"
                                        style={{
                                            borderColor: open
                                                ? THEME.accent
                                                : THEME.accentSoft,
                                            background: open
                                                ? THEME.accentWash
                                                : 'rgba(12,10,20,0.3)',
                                        }}
                                    >
                                        <div className="flex flex-col items-start gap-1">
                                            <span className="text-sm font-bold text-[#f8fafc]">
                                                {y.label}
                                            </span>
                                            <div className="flex items-center gap-2">
                                                <span
                                                    className="text-[10px] font-bold uppercase tracking-widest"
                                                    style={{ color: THEME.accent }}
                                                >
                                                    {y.pillar}
                                                </span>
                                                <div
                                                    className="h-1 w-1 rounded-full"
                                                    style={{
                                                        background: THEME.accentSoft,
                                                    }}
                                                />
                                                <span className="text-[10px] font-bold text-white/60">
                                                    SCORE {y.score}
                                                </span>
                                            </div>
                                        </div>
                                        <SparklineDots
                                            scores={y.scores}
                                            activeMonth={y.year === 2026 ? 4 : undefined}
                                        />
                                    </button>

                                    <AnimatePresence initial={false}>
                                        {open && (
                                            <motion.div
                                                initial={{ height: 0, opacity: 0 }}
                                                animate={{ height: 'auto', opacity: 1 }}
                                                exit={{ height: 0, opacity: 0 }}
                                                className="-mt-2 mb-2 overflow-hidden rounded-b-xl border-x border-b"
                                                style={{
                                                    borderColor: THEME.accentSoft,
                                                    background: THEME.accentWash,
                                                }}
                                            >
                                                <div className="space-y-4 p-4 pt-6">
                                                    <div className="grid grid-cols-2 gap-4">
                                                        <div>
                                                            <span
                                                                className="text-[9px] uppercase tracking-widest"
                                                                style={{
                                                                    color: THEME.accent,
                                                                }}
                                                            >
                                                                Peak months
                                                            </span>
                                                            <div className="mt-1 text-xs font-bold text-white/80">
                                                                Aug · Oct · Nov
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <span className="text-[9px] uppercase tracking-widest text-[#dc2626]">
                                                                Trough months
                                                            </span>
                                                            <div className="mt-1 text-xs font-bold text-white/80">
                                                                Feb · May
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div className="space-y-1.5">
                                                        {y.summary.map((s, i) => (
                                                            <p
                                                                key={i}
                                                                className="text-xs leading-relaxed text-white/70"
                                                            >
                                                                · {s}
                                                            </p>
                                                        ))}
                                                    </div>
                                                    <div
                                                        className="border-t pt-3 text-right text-[10px] italic"
                                                        style={{
                                                            borderColor: FORTUNE_GOLD_SOFT,
                                                            color: FORTUNE_GOLD,
                                                        }}
                                                    >
                                                        "{y.citation.text}" — {y.citation.source}
                                                    </div>
                                                </div>
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </div>
                            );
                        })}
                    </motion.div>
                )}

                {activeTab === 'Why' && (
                    <motion.div
                        key="why"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                        className="space-y-3"
                    >
                        {MOCK_WHY_CARDS.map((card, i) => (
                            <div
                                key={i}
                                className="rounded-2xl border p-4 backdrop-blur-sm"
                                style={{
                                    borderColor: THEME.accentSoft,
                                    background: 'rgba(12,10,20,0.55)',
                                }}
                            >
                                <div className="mb-3 flex items-center gap-3">
                                    <div
                                        className="flex h-8 w-8 items-center justify-center rounded-full border"
                                        style={{
                                            borderColor: THEME.accentSoft,
                                            background: THEME.accentWash,
                                        }}
                                    >
                                        <span style={{ color: THEME.accent }}>✦</span>
                                    </div>
                                    <h3
                                        className="text-sm font-bold uppercase tracking-widest"
                                        style={{ color: THEME.accent }}
                                    >
                                        {card.name}
                                    </h3>
                                </div>
                                <ul className="mb-4 space-y-2 pl-11">
                                    {card.bullets.map((b, bi) => (
                                        <li
                                            key={bi}
                                            className="text-xs leading-relaxed text-white/80"
                                        >
                                            {b}
                                        </li>
                                    ))}
                                </ul>
                                <div
                                    className="rounded border p-2 text-right"
                                    style={{
                                        borderColor: FORTUNE_GOLD_SOFT,
                                        background: 'rgba(234,179,8,0.04)',
                                    }}
                                >
                                    <span
                                        className="text-[10px] font-bold italic uppercase tracking-wide"
                                        style={{ color: FORTUNE_GOLD }}
                                    >
                                        {card.citation}
                                    </span>
                                </div>
                            </div>
                        ))}
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
                        <FortuneAgentAskTab
                            purpose="luck-draw"
                            history={askHistory}
                            suggestedChips={SUGGESTED_CHIPS}
                            input={askInput}
                            onInputChange={setAskInput}
                            onSend={handleSend}
                            heading="Ask the cycles"
                            placeholder="Ask about a year, a month, a pivot…"
                        />
                    </motion.div>
                )}
            </AnimatePresence>
        </FortuneAgentResultShell>
    );
};

export default FortuneAgentCycleResult;
