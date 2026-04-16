/**
 * FortuneAgentCompatibilityResult — 緣 Compatibility reading.
 *
 * Theme continuity: rose accent (#f43f5e) carries through from hub → input
 * → result tabs. Gold (#eab308) is reserved for classical citations only,
 * acting as the shared "classical anchor" across all 4 result pages.
 *
 * Tabs: Overview (match + dynamics) · Pillars (side-by-side chart) ·
 *       Why (mechanism cards w/ classical citations) · Ask (oracle scroll).
 *
 * Mobile-first: <= 375px. Anchors in Flash research:
 * - ~/homer/output/gemini/fortune-mobile-tabs-ux-2026-04-15-1400.md
 * - ~/homer/output/gemini/fortune-bazi-result-design-2026-04-15-1400.md
 * - ~/homer/output/gemini/fortune-psychology-doubt-resolution-2026-04-15-1400.md
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Flame, Zap, ChevronDown, Sparkles, Layers, Heart } from 'lucide-react';
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

interface FortuneAgentCompatibilityResultProps {
    onBack?: () => void;
    inputPayload?: {
        relationship: string;
        personA: { name: string; birthDate: string; birthTime: string | null; gender: string };
        personB: { name: string; birthDate: string; birthTime: string | null; gender: string };
    } | null;
}

const THEME = FORTUNE_THEMES.compatibility;

// --- Mock Data ---------------------------------------------------------

const PARTNER_A = {
    name: 'You',
    birth: '1991-09-05 07:20',
    dayMaster: '丙 Bing Fire',
    dominant: 'Fire',
    weakest: 'Water',
    elements: { Wood: 15, Fire: 45, Earth: 20, Metal: 10, Water: 10 },
    pillars: [
        { label: 'Year', stem: 'Xin 辛', branch: 'Wei 未', note: 'Metal-Earth' },
        { label: 'Month', stem: 'Bing 丙', branch: 'Shen 申', note: 'Fire-Metal' },
        { label: 'Day', stem: 'Bing 丙', branch: 'Wu 午', note: 'Fire-Fire' },
        { label: 'Hour', stem: 'Ren 壬', branch: 'Chen 辰', note: 'Water-Earth' },
    ],
};

const PARTNER_B = {
    name: 'Her',
    birth: '1993-06-12 14:30',
    dayMaster: '己 Ji Earth',
    dominant: 'Earth',
    weakest: 'Wood',
    elements: { Wood: 10, Fire: 20, Earth: 50, Metal: 15, Water: 5 },
    pillars: [
        { label: 'Year', stem: 'Gui 癸', branch: 'You 酉', note: 'Water-Metal' },
        { label: 'Month', stem: 'Wu 戊', branch: 'Wu 午', note: 'Earth-Fire' },
        { label: 'Day', stem: 'Ji 己', branch: 'Mao 卯', note: 'Earth-Wood' },
        { label: 'Hour', stem: 'Xin 辛', branch: 'Wei 未', note: 'Metal-Earth' },
    ],
};

const DYNAMICS = [
    { label: 'Supportive', chinese: '支持', text: 'Earth tames Fire', tone: 'positive' as const },
    { label: 'Warming', chinese: '温暖', text: 'Fire warms Earth', tone: 'positive' as const },
    { label: 'Friction', chinese: '摩擦', text: 'Hour-pillar clash', tone: 'negative' as const },
];

const MECHANISMS = [
    {
        icon: Flame,
        title: 'Bing 丙 Fire warmed by Ji 己 Earth',
        points: [
            'Your intense Fire is safely absorbed by her soft Earth.',
            'Creates a cycle of production rather than exhaustion.',
            'Ensures mutual emotional stability during high stress.',
        ],
        citation: {
            source: '滴天髓 · 丙火',
            text: '丙火猛烈, 欺霜侮雪. 能煅庚金, 逢辛反怯. 土众成慈, 水猖显节.',
            translation:
                'Bing fire is fierce — with abundant Earth it becomes compassionate; with rampant Water it shows integrity.',
        },
    },
    {
        icon: Sparkles,
        title: 'Year-Pillar Harmonize (Wood-Earth)',
        points: [
            'Foundational values align through elemental balance.',
            'Family backgrounds provide a stable root for growth.',
            'Shared long-term vision for security and heritage.',
        ],
        citation: {
            source: '渊海子平 · 月令',
            text: '木能生火, 火多木焚; 強金得水, 方挫其鋒.',
            translation:
                'Wood produces Fire, but too much Fire burns the Wood. Strong Metal needs Water to blunt its edge.',
        },
    },
    {
        icon: Heart,
        title: 'Day-Master Support',
        points: [
            'Natural affinity between your Day Stems.',
            "Intrinsic understanding of each other's core needs.",
            'Supportive dynamic in daily decision-making.',
        ],
        citation: {
            source: '滴天髓 · 天干论',
            text: '五陽皆陽丙為最, 五陰皆陰癸為至.',
            translation:
                'Of the five Yang, Bing Fire is most Yang; of the five Yin, Gui Water is most Yin.',
        },
    },
    {
        icon: Zap,
        title: 'Hour-Pillar Clash (Hai 亥 vs Si 巳)',
        points: [
            'Minor friction around late-night habits or long-horizon goals.',
            'Tension arises when discussing 10-year plans.',
            'Requires conscious compromise on non-urgent matters.',
        ],
        citation: {
            source: '子平真诠 · 冲合',
            text: '刑冲會合, 為命理之關鍵.',
            translation:
                'Punishment, Clash, Union, and Combination are the keys of destiny.',
        },
    },
    {
        icon: Layers,
        title: '10-God Dynamic: Wealth meets Resource',
        points: [
            'Your drive for results (Wealth) is guided by her wisdom (Resource).',
            'She provides strategy; you provide execution.',
            'A structural fit for long-term accumulation.',
        ],
        citation: {
            source: '命理约言',
            text: '財官印綬, 各有所宜.',
            translation: 'Wealth, Officer, and Resource — each has its proper place.',
        },
    },
];

const SUGGESTED_CHIPS = [
    'What about moving in together?',
    'How to handle his Fire temper?',
    'Best month to propose?',
    'Does 2027 help or hurt us?',
];

const TABS: FortuneTab[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'pillars', label: 'Pillars' },
    { id: 'why', label: 'Why' },
    { id: 'ask', label: 'Ask' },
];

// --- Sub-components ----------------------------------------------------

const ScoreRing: React.FC<{ score: number }> = ({ score }) => (
    <div className="relative mx-auto mb-3 flex h-24 w-24 items-center justify-center">
        <svg className="h-full w-full -rotate-90 transform" viewBox="0 0 96 96">
            <circle
                cx="48"
                cy="48"
                r="42"
                stroke={`${THEME.accent}1a`}
                strokeWidth="4"
                fill="transparent"
            />
            <motion.circle
                cx="48"
                cy="48"
                r="42"
                stroke={THEME.accent}
                strokeWidth="4"
                fill="transparent"
                strokeLinecap="round"
                strokeDasharray="263.89"
                initial={{ strokeDashoffset: 263.89 }}
                animate={{ strokeDashoffset: 263.89 - (score / 100) * 263.89 }}
                transition={{ duration: 1.4, ease: [0.22, 0.61, 0.36, 1] }}
            />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold text-[#f8fafc]">{score}</span>
            <span
                className="text-[9px] uppercase tracking-[0.25em]"
                style={{ color: THEME.accent }}
            >
                match
            </span>
        </div>
    </div>
);

const MechanismCard: React.FC<{
    item: (typeof MECHANISMS)[0];
    open: boolean;
    onToggle: () => void;
}> = ({ item, open, onToggle }) => {
    const Icon = item.icon;
    return (
        <div
            className="overflow-hidden rounded-2xl border backdrop-blur-sm"
            style={{
                borderColor: open ? THEME.accentSoft : 'rgba(248,250,252,0.08)',
                background: 'rgba(12,10,20,0.55)',
            }}
        >
            <button
                onClick={onToggle}
                className="flex w-full items-center justify-between gap-3 p-4 text-left"
            >
                <div className="flex min-w-0 items-center gap-3">
                    <div
                        className="flex h-8 w-8 flex-none items-center justify-center rounded-full border"
                        style={{
                            borderColor: THEME.accentSoft,
                            background: THEME.accentWash,
                        }}
                    >
                        <Icon className="h-4 w-4" style={{ color: THEME.accent }} />
                    </div>
                    <span
                        className="truncate text-sm font-bold text-[#f8fafc]"
                        style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                    >
                        {item.title}
                    </span>
                </div>
                <ChevronDown
                    className={`h-4 w-4 flex-none transition-transform ${open ? 'rotate-180' : ''}`}
                    style={{ color: THEME.accent }}
                />
            </button>
            <AnimatePresence initial={false}>
                {open && (
                    <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: 'auto' }}
                        exit={{ height: 0 }}
                        className="overflow-hidden"
                    >
                        <div className="space-y-3 px-4 pb-4">
                            <ul className="space-y-2">
                                {item.points.map((p, i) => (
                                    <li
                                        key={i}
                                        className="flex gap-2 text-xs leading-relaxed text-white/70"
                                    >
                                        <span style={{ color: THEME.accent }}>·</span>
                                        {p}
                                    </li>
                                ))}
                            </ul>
                            {/* Classical citation — gold, shared brand anchor */}
                            <div
                                className="rounded-lg border p-3"
                                style={{
                                    borderColor: FORTUNE_GOLD_SOFT,
                                    background: 'rgba(234,179,8,0.04)',
                                }}
                            >
                                <p
                                    className="mb-1 text-[10px] font-bold uppercase tracking-widest"
                                    style={{ color: FORTUNE_GOLD }}
                                >
                                    {item.citation.source}
                                </p>
                                <p
                                    className="mb-1 text-sm leading-relaxed text-[#f8fafc]"
                                    style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                >
                                    {item.citation.text}
                                </p>
                                <p className="text-[11px] italic text-white/45">
                                    {item.citation.translation}
                                </p>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

// --- Main component ----------------------------------------------------

export const FortuneAgentCompatibilityResult: React.FC<FortuneAgentCompatibilityResultProps> = ({
    onBack,
    inputPayload,
}) => {
    const partnerA = inputPayload
        ? { ...PARTNER_A, name: inputPayload.personA.name || 'You', birth: `${inputPayload.personA.birthDate} ${inputPayload.personA.birthTime || ''}`.trim() }
        : PARTNER_A;
    const partnerB = inputPayload
        ? { ...PARTNER_B, name: inputPayload.personB.name || 'Partner', birth: `${inputPayload.personB.birthDate} ${inputPayload.personB.birthTime || ''}`.trim() }
        : PARTNER_B;
    const [activeTab, setActiveTab] = useState<string>('overview');
    const [openMechanism, setOpenMechanism] = useState<number | null>(0);
    const [expandedPillar, setExpandedPillar] = useState<number | null>(null);
    const [askInput, setAskInput] = useState('');
    const [askHistory, setAskHistory] = useState<AskTurn[]>([
        {
            id: 'a1',
            role: 'agent',
            content:
                'Her Earth tames your Fire — a soft harbor for your intensity. The real question under your question: will daily life nurture or drain you together?',
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
        // Mock response — the backend will replace this
        setTimeout(() => {
            setAskHistory((h) => [
                ...h,
                {
                    id: String(Date.now() + 1),
                    role: 'agent',
                    content:
                        'In 2027 (Ding Wei year), your Bing Fire receives a subtle boost while her Earth core grounds it. The season favors moving forward — provided you communicate openly in the summer months.',
                },
            ]);
        }, 900);
    };

    return (
        <FortuneAgentResultShell
            purpose="compatibility"
            eyebrow="Compatibility"
            subtitle="兩命 · Two Charts"
            tabs={TABS}
            activeTabId={activeTab}
            onTabChange={setActiveTab}
            onBack={onBack}
        >
            <AnimatePresence mode="wait">
                {activeTab === 'overview' && (
                    <motion.div
                        key="overview"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                        className="space-y-7"
                    >
                        {/* Hero — match score + verdict quote */}
                        <section className="text-center">
                            <ScoreRing score={78} />
                            <h2
                                className="mx-auto max-w-[320px] text-lg italic leading-relaxed text-white/90"
                                style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                            >
                                "Her Earth tames your Fire, providing a soft harbor
                                for your intensity."
                            </h2>
                            <p className="mt-2 text-[11px] uppercase tracking-[0.22em] text-white/40">
                                丙 Bing Fire · 己 Ji Earth
                            </p>
                        </section>

                        {/* Dynamics chips */}
                        <section className="flex flex-wrap justify-center gap-2">
                            {DYNAMICS.map((d) => {
                                const good = d.tone === 'positive';
                                const color = good ? THEME.accent : '#dc2626';
                                return (
                                    <div
                                        key={d.label}
                                        className="flex items-center gap-2 rounded-full border px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest"
                                        style={{
                                            borderColor: `${color}55`,
                                            background: `${color}10`,
                                            color,
                                        }}
                                    >
                                        <span
                                            className="opacity-60"
                                            style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                        >
                                            {d.chinese}
                                        </span>
                                        <span>{d.text}</span>
                                    </div>
                                );
                            })}
                        </section>

                        {/* Elemental dualism bars */}
                        <section className="space-y-3">
                            <div className="flex items-end justify-between">
                                <h3
                                    className="text-[10px] font-bold uppercase tracking-[0.22em]"
                                    style={{ color: THEME.accent }}
                                >
                                    Elemental Dualism
                                </h3>
                                <span className="text-[10px] uppercase tracking-wide text-white/35">
                                    Fire vs Earth
                                </span>
                            </div>
                            <div className="space-y-2.5">
                                {(['Wood', 'Fire', 'Earth', 'Metal', 'Water'] as const).map(
                                    (el) => (
                                        <div
                                            key={el}
                                            className="relative flex h-4 w-full overflow-hidden rounded-full"
                                            style={{ background: 'rgba(248,250,252,0.05)' }}
                                        >
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: `${partnerA.elements[el]}%` }}
                                                transition={{ duration: 0.9 }}
                                                className="h-full"
                                                style={{ background: `${THEME.accent}55` }}
                                            />
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: `${partnerB.elements[el]}%` }}
                                                transition={{ duration: 0.9, delay: 0.1 }}
                                                className="h-full"
                                                style={{ background: 'rgba(248,250,252,0.12)' }}
                                            />
                                            <div className="absolute inset-0 flex items-center justify-between px-3">
                                                <span className="text-[9px] font-bold uppercase text-white/55">
                                                    {el}
                                                </span>
                                                <div className="flex gap-1.5 font-mono text-[9px]">
                                                    <span style={{ color: THEME.accent }}>
                                                        {partnerA.elements[el]}%
                                                    </span>
                                                    <span className="text-white/25">/</span>
                                                    <span className="text-white/45">
                                                        {partnerB.elements[el]}%
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    ),
                                )}
                            </div>
                        </section>

                        {/* One-thing-to-do closure (psychology research §5) */}
                        <section
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
                                Plan a shared slow evening in the Wu 午 hour (11–13h).
                                Fire meets Earth best when neither is performing.
                            </p>
                        </section>
                    </motion.div>
                )}

                {activeTab === 'pillars' && (
                    <motion.div
                        key="pillars"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                        className="space-y-4"
                    >
                        <div className="mb-2 grid grid-cols-2 gap-4">
                            <div
                                className="text-center text-[10px] uppercase tracking-widest"
                                style={{ color: THEME.accent }}
                            >
                                You
                            </div>
                            <div className="text-center text-[10px] uppercase tracking-widest text-white/45">
                                Her
                            </div>
                        </div>

                        {partnerA.pillars.map((p, i) => {
                            const clash = i === 3; // Hour-pillar clash
                            return (
                                <div key={i} className="space-y-2">
                                    <div
                                        onClick={() =>
                                            setExpandedPillar(expandedPillar === i ? null : i)
                                        }
                                        className="flex cursor-pointer items-center gap-3"
                                    >
                                        <div
                                            className="flex flex-1 flex-col items-center rounded-xl border p-3"
                                            style={{
                                                borderColor: THEME.accentSoft,
                                                background: THEME.accentWash,
                                            }}
                                        >
                                            <span className="mb-1 text-[9px] uppercase tracking-widest text-white/35">
                                                {p.label}
                                            </span>
                                            <span
                                                className="text-lg text-[#f8fafc]"
                                                style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                            >
                                                {p.stem}
                                            </span>
                                            <span
                                                className="text-lg text-[#f8fafc]"
                                                style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                            >
                                                {p.branch}
                                            </span>
                                        </div>

                                        <div
                                            className="h-2 w-2 flex-none rounded-full"
                                            style={{
                                                background: clash ? '#dc2626' : THEME.accent,
                                                boxShadow: `0 0 10px ${
                                                    clash ? '#dc2626aa' : THEME.accentGlow
                                                }`,
                                            }}
                                        />

                                        <div
                                            className="flex flex-1 flex-col items-center rounded-xl border p-3"
                                            style={{
                                                borderColor: 'rgba(248,250,252,0.1)',
                                                background: 'rgba(248,250,252,0.03)',
                                            }}
                                        >
                                            <span className="mb-1 text-[9px] uppercase tracking-widest text-white/35">
                                                {partnerB.pillars[i].label}
                                            </span>
                                            <span
                                                className="text-lg text-[#f8fafc]"
                                                style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                            >
                                                {partnerB.pillars[i].stem}
                                            </span>
                                            <span
                                                className="text-lg text-[#f8fafc]"
                                                style={{ fontFamily: FORTUNE_CHINESE_FONT }}
                                            >
                                                {partnerB.pillars[i].branch}
                                            </span>
                                        </div>
                                    </div>

                                    <AnimatePresence initial={false}>
                                        {expandedPillar === i && (
                                            <motion.div
                                                initial={{ height: 0, opacity: 0 }}
                                                animate={{ height: 'auto', opacity: 1 }}
                                                exit={{ height: 0, opacity: 0 }}
                                                className="overflow-hidden"
                                            >
                                                <div
                                                    className="rounded-lg border p-3 text-center text-[11px] italic leading-relaxed text-white/75"
                                                    style={{
                                                        borderColor: clash
                                                            ? 'rgba(220,38,38,0.3)'
                                                            : THEME.accentSoft,
                                                        background: clash
                                                            ? 'rgba(220,38,38,0.05)'
                                                            : THEME.accentWash,
                                                    }}
                                                >
                                                    {clash
                                                        ? `${p.label} branches clash — expect occasional late-night tension; ride it, don't fight it.`
                                                        : `${p.label} stems harmonize — baseline agreement on ${
                                                              i === 0
                                                                  ? 'family values'
                                                                  : i === 1
                                                                  ? 'career rhythm'
                                                                  : 'daily life'
                                                          }.`}
                                                </div>
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </div>
                            );
                        })}
                    </motion.div>
                )}

                {activeTab === 'why' && (
                    <motion.div
                        key="why"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                        className="space-y-3"
                    >
                        {MECHANISMS.map((item, i) => (
                            <MechanismCard
                                key={i}
                                item={item}
                                open={openMechanism === i}
                                onToggle={() =>
                                    setOpenMechanism(openMechanism === i ? null : i)
                                }
                            />
                        ))}
                    </motion.div>
                )}

                {activeTab === 'ask' && (
                    <motion.div
                        key="ask"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                    >
                        <FortuneAgentAskTab
                            purpose="compatibility"
                            history={askHistory}
                            suggestedChips={SUGGESTED_CHIPS}
                            input={askInput}
                            onInputChange={setAskInput}
                            onSend={handleSend}
                            heading="Ask the pair"
                            placeholder="Ask about the two of you…"
                        />
                    </motion.div>
                )}
            </AnimatePresence>
        </FortuneAgentResultShell>
    );
};
