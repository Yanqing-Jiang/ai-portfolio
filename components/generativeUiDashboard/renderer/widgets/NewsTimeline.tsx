/**
 * NewsTimeline Widget
 *
 * Vertical timeline of news events with sentiment indicators.
 */

import React from 'react';
import type { A2UIRendererProps } from '../Registry';
import { resolveArray } from '../../a2ui/DataBinder';
import type { NewsTimelineProps } from '../../a2ui/types';

interface NewsEvent {
    date: string;
    title: string;
    summary?: string;
    sentiment?: 'positive' | 'negative' | 'neutral';
    source?: string;
    url?: string;
}

export function NewsTimeline({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const timelineProps = props as unknown as NewsTimelineProps;
    const events = resolveArray<NewsEvent>(timelineProps.events, dataModel, []);

    // Sentiment colors
    const sentimentColors: Record<string, { bg: string; border: string; text: string }> = {
        positive: { bg: 'rgba(34, 197, 94, 0.1)', border: '#22c55e', text: '#22c55e' },
        negative: { bg: 'rgba(239, 68, 68, 0.1)', border: '#ef4444', text: '#ef4444' },
        neutral: { bg: 'rgba(148, 163, 184, 0.1)', border: '#94a3b8', text: '#94a3b8' },
    };

    // Format date
    const formatDate = (dateStr: string): string => {
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
            });
        } catch {
            return dateStr;
        }
    };

    return (
        <div
            className="a2ui-news-timeline"
            data-component-id={componentId}
            style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem',
            }}
        >
            {events.length === 0 && (
                <div
                    style={{
                        padding: '2rem',
                        textAlign: 'center',
                        color: '#64748b',
                        backgroundColor: 'rgba(30, 41, 59, 0.3)',
                        borderRadius: '8px',
                    }}
                >
                    No news events to display
                </div>
            )}

            {events.map((event, index) => {
                const sentiment = event.sentiment || 'neutral';
                const colors = sentimentColors[sentiment];

                return (
                    <div
                        key={index}
                        className="a2ui-news-timeline__event"
                        style={{
                            display: 'flex',
                            gap: '1rem',
                        }}
                    >
                        {/* Timeline connector */}
                        <div
                            style={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                width: '20px',
                            }}
                        >
                            <div
                                style={{
                                    width: '12px',
                                    height: '12px',
                                    borderRadius: '50%',
                                    backgroundColor: colors.border,
                                    flexShrink: 0,
                                }}
                            />
                            {index < events.length - 1 && (
                                <div
                                    style={{
                                        width: '2px',
                                        flex: 1,
                                        backgroundColor: 'rgba(99, 102, 241, 0.2)',
                                        marginTop: '4px',
                                    }}
                                />
                            )}
                        </div>

                        {/* Event content */}
                        <div
                            style={{
                                flex: 1,
                                padding: '1rem',
                                backgroundColor: colors.bg,
                                borderLeft: `3px solid ${colors.border}`,
                                borderRadius: '0 8px 8px 0',
                            }}
                        >
                            {/* Date and source */}
                            <div
                                style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    marginBottom: '0.5rem',
                                }}
                            >
                                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                                    {formatDate(event.date)}
                                </span>
                                {event.source && (
                                    <span style={{ fontSize: '0.75rem', color: colors.text }}>
                                        {event.source}
                                    </span>
                                )}
                            </div>

                            {/* Title */}
                            <h4
                                style={{
                                    margin: '0 0 0.5rem 0',
                                    fontSize: '0.875rem',
                                    fontWeight: 600,
                                    color: '#f8fafc',
                                }}
                            >
                                {event.url ? (
                                    <a
                                        href={event.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{ color: 'inherit', textDecoration: 'none' }}
                                    >
                                        {event.title}
                                    </a>
                                ) : (
                                    event.title
                                )}
                            </h4>

                            {/* Summary */}
                            {event.summary && (
                                <p
                                    style={{
                                        margin: 0,
                                        fontSize: '0.8125rem',
                                        color: '#94a3b8',
                                        lineHeight: 1.5,
                                    }}
                                >
                                    {event.summary}
                                </p>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
