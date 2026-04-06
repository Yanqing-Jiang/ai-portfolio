/**
 * FortuneReadingPanel — Streaming sectioned narrative display.
 *
 * Renders the fortune reading sections with typewriter effect during
 * streaming and staggered reveal on completion.
 *
 * Called from: ComponentRenderer.tsx via Registry
 * Data path: /data/narrative (emitted by stream_bridge.emit_narrative_delta / emit_narrative_complete)
 */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import type { A2UIRendererProps } from '../Registry';
import type { BoundValue } from '../../a2ui/types';
import { resolveBoundValue } from '../../a2ui/DataBinder';
import { useStreamingText } from '../../hooks/useStreamingText';

const SECTION_ICONS: Record<string, string> = {
    overview: '🔮',
    career: '📐',
    relationship: '🤝',
    health: '🌿',
    wealth: '💰',
    timing: '🕐',
    advice: '✨',
    year: '📅',
};

interface NarrativeSection {
    id: string;
    heading: string;
    content: string;
    type: string;
    citations: string[];
}

interface NarrativeData {
    sections: NarrativeSection[];
    isComplete: boolean;
}

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.1 } },
};

const sectionVariants = {
    hidden: { opacity: 0, y: 12 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { type: 'spring', stiffness: 200, damping: 25, mass: 0.8 },
    },
};

/**
 * Live section with streaming text effect.
 */
function LiveSection({ section }: { section: NarrativeSection }) {
    const { displayText, isStreaming } = useStreamingText(section.content, {
        speed: 15,
        resetKey: section.content,
    });

    const icon = SECTION_ICONS[section.type] || '📖';

    return (
        <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
                <span className="text-base">{icon}</span>
                <h3 className="text-lg font-semibold text-slate-200">
                    {section.heading}
                </h3>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
                {displayText}
                {isStreaming && (
                    <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-slate-400" />
                )}
            </p>
        </div>
    );
}

/**
 * Completed section (no streaming effect).
 */
function CompletedSection({ section }: { section: NarrativeSection }) {
    const icon = SECTION_ICONS[section.type] || '📖';

    return (
        <motion.div variants={sectionVariants} className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
                <span className="text-base">{icon}</span>
                <h3 className="text-lg font-semibold text-slate-200">
                    {section.heading}
                </h3>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
                {section.content}
            </p>
            {section.citations?.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                    {section.citations.map((cite, i) => (
                        <span
                            key={i}
                            className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-500"
                        >
                            {cite}
                        </span>
                    ))}
                </div>
            )}
        </motion.div>
    );
}

export function FortuneReadingPanel({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const data = resolveBoundValue(
        props.sectionsPath as BoundValue | undefined,
        dataModel
    ) as NarrativeData | undefined;

    const sections = useMemo(() => data?.sections || [], [data?.sections]);
    const isComplete = data?.isComplete ?? false;

    if (!sections.length) {
        return <div data-component-id={componentId} />;
    }

    // During streaming: show last section with typewriter, rest as static
    if (!isComplete) {
        const liveSectionIndex = sections.length - 1;
        return (
            <div
                data-component-id={componentId}
                className="flex w-full flex-col gap-4"
            >
                {sections.map((section, idx) =>
                    idx === liveSectionIndex ? (
                        <LiveSection key={section.id} section={section} />
                    ) : (
                        <CompletedSection
                            key={section.id}
                            section={section}
                        />
                    )
                )}

                {/* Shimmer skeleton for upcoming content */}
                <div className="space-y-2">
                    <div
                        className="h-3 w-3/4 rounded"
                        style={{
                            background:
                                'linear-gradient(90deg, rgba(148,163,184,0.08) 0%, rgba(148,163,184,0.15) 50%, rgba(148,163,184,0.08) 100%)',
                            backgroundSize: '200% 100%',
                            animation: 'shimmer 1.6s ease-in-out infinite',
                        }}
                    />
                    <div
                        className="h-3 w-1/2 rounded"
                        style={{
                            background:
                                'linear-gradient(90deg, rgba(148,163,184,0.08) 0%, rgba(148,163,184,0.15) 50%, rgba(148,163,184,0.08) 100%)',
                            backgroundSize: '200% 100%',
                            animation: 'shimmer 1.6s ease-in-out infinite 0.2s',
                        }}
                    />
                </div>
                <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
            </div>
        );
    }

    // Completed: all sections with stagger
    return (
        <motion.div
            data-component-id={componentId}
            className="flex w-full flex-col gap-4"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
        >
            {sections.map((section) => (
                <CompletedSection key={section.id} section={section} />
            ))}
        </motion.div>
    );
}
