/**
 * FortuneAgentResultShell — shared mobile-first layout for all 4 result pages
 * (Compatibility / Occasion / Cycle / Custom Wish).
 *
 * Design intent:
 * - Each result page inherits its function's accent + gradient from
 *   fortuneAgentTheme.ts, so the visual story from hub → input → result
 *   stays continuous.
 * - Top-sticky floating glass pill for tabs (ceremonial, not SaaS-y).
 * - Label-only tabs in Noto Serif SC; the active tab glows with the
 *   function's accent color (layoutId spring animation).
 * - The 4th tab is always "Ask" — conversational follow-up.
 * - Safe-area aware so iOS home indicator doesn't clip the bottom chrome.
 *
 * References:
 * - ~/homer/output/gemini/fortune-mobile-tabs-ux-2026-04-15-1400.md
 * - fortuneAgentTheme.ts
 */

import React from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import {
    FORTUNE_THEMES,
    FORTUNE_GOLD,
    FORTUNE_CHINESE_FONT,
    type FortunePurposeId,
} from './fortuneAgentTheme';

export interface FortuneTab {
    id: string;
    label: string;
}

interface FortuneAgentResultShellProps {
    purpose: FortunePurposeId;
    /** Short label shown next to the glyph badge (e.g. "Compatibility Reading"). */
    eyebrow: string;
    /** Optional subtitle below the eyebrow (truncates on mobile). */
    subtitle?: string;
    tabs: FortuneTab[];
    activeTabId: string;
    onTabChange: (id: string) => void;
    onBack?: () => void;
    children: React.ReactNode;
}

export const FortuneAgentResultShell: React.FC<FortuneAgentResultShellProps> = ({
    purpose,
    eyebrow,
    subtitle,
    tabs,
    activeTabId,
    onTabChange,
    onBack,
    children,
}) => {
    const theme = FORTUNE_THEMES[purpose];
    const gradient = `linear-gradient(180deg, ${theme.gradient[0]} 0%, ${theme.gradient[1]} 55%, #0c0a14 100%)`;

    return (
        <div
            className="min-h-screen text-[#f8fafc] selection:bg-[#eab308]/30"
            style={{ background: gradient }}
        >
            {/* ----- Top bar: glyph badge + back button ----- */}
            <div
                className="sticky top-0 z-40 backdrop-blur-md"
                style={{
                    background: 'rgba(12, 10, 20, 0.72)',
                    borderBottom: `1px solid ${theme.accentSoft}`,
                    paddingTop: 'env(safe-area-inset-top, 0px)',
                }}
            >
                <div className="mx-auto flex w-full max-w-[560px] items-center justify-between px-4 py-2.5">
                    <div className="flex items-center gap-2.5 min-w-0">
                        <div
                            className="flex h-8 w-8 flex-none items-center justify-center rounded-lg border"
                            style={{
                                borderColor: theme.accentSoft,
                                background: theme.accentWash,
                            }}
                        >
                            <span
                                style={{
                                    fontFamily: FORTUNE_CHINESE_FONT,
                                    color: theme.accent,
                                    fontSize: 18,
                                    lineHeight: 1,
                                }}
                            >
                                {theme.glyph}
                            </span>
                        </div>
                        <div className="min-w-0">
                            <h1
                                className="text-[11px] font-bold uppercase tracking-[0.2em] truncate"
                                style={{ color: theme.accent }}
                            >
                                {eyebrow}
                            </h1>
                            {subtitle && (
                                <p className="text-[10px] uppercase tracking-[0.18em] text-white/45 truncate">
                                    {subtitle}
                                </p>
                            )}
                        </div>
                    </div>

                    {onBack && (
                        <button
                            type="button"
                            onClick={onBack}
                            aria-label="Back"
                            className="inline-flex h-9 items-center gap-1.5 rounded-full border px-3 text-[10px] font-bold uppercase tracking-[0.18em] transition-colors"
                            style={{
                                minHeight: 36,
                                borderColor: theme.accentSoft,
                                color: theme.accent,
                                background: 'rgba(12,10,20,0.4)',
                            }}
                        >
                            <ArrowLeft className="w-3.5 h-3.5" />
                            Back
                        </button>
                    )}
                </div>

                {/* ----- Floating glass pill tab bar ----- */}
                <div className="px-4 pb-3 pt-1">
                    <nav
                        role="tablist"
                        aria-label={`${eyebrow} sections`}
                        className="mx-auto flex w-full max-w-[420px] items-center justify-between gap-1 rounded-full border px-1.5 py-1 backdrop-blur-xl"
                        style={{
                            borderColor: theme.accentSoft,
                            background: 'rgba(12, 10, 20, 0.55)',
                            boxShadow: `0 10px 30px -20px ${theme.accentGlow}`,
                        }}
                    >
                        {tabs.map((t) => {
                            const active = activeTabId === t.id;
                            return (
                                <button
                                    key={t.id}
                                    type="button"
                                    role="tab"
                                    aria-selected={active}
                                    onClick={() => onTabChange(t.id)}
                                    className="relative flex-1 py-2 text-[11px] font-medium tracking-[0.16em] transition-colors"
                                    style={{
                                        fontFamily: FORTUNE_CHINESE_FONT,
                                        color: active ? '#fff' : 'rgba(248,250,252,0.5)',
                                        minHeight: 36,
                                    }}
                                >
                                    {active && (
                                        <motion.span
                                            layoutId={`fortune-tab-${purpose}`}
                                            className="absolute inset-0 rounded-full"
                                            style={{
                                                background: `linear-gradient(180deg, ${theme.accent}33, ${theme.accent}11)`,
                                                boxShadow: `0 0 18px -4px ${theme.accentGlow}`,
                                                border: `1px solid ${theme.accentSoft}`,
                                            }}
                                            transition={{
                                                type: 'spring',
                                                bounce: 0.2,
                                                duration: 0.55,
                                            }}
                                        />
                                    )}
                                    <span className="relative z-10">{t.label}</span>
                                </button>
                            );
                        })}
                    </nav>
                </div>
            </div>

            {/* ----- Main content ----- */}
            <main
                className="mx-auto w-full max-w-[560px] px-4"
                style={{
                    paddingTop: 16,
                    paddingBottom:
                        'max(env(safe-area-inset-bottom, 0px) + 32px, 40px)',
                }}
            >
                {children}
            </main>

            {/* ----- Ambient gold glyph watermark ----- */}
            <div
                aria-hidden
                className="pointer-events-none fixed bottom-4 left-0 right-0 flex justify-center"
                style={{ opacity: 0.06 }}
            >
                <span
                    style={{
                        fontFamily: FORTUNE_CHINESE_FONT,
                        color: FORTUNE_GOLD,
                        fontSize: 56,
                        lineHeight: 1,
                    }}
                >
                    {theme.glyph}
                </span>
            </div>
        </div>
    );
};
