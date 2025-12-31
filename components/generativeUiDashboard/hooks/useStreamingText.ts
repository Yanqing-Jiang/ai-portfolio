/**
 * useStreamingText Hook
 * 
 * Provides word-by-word text reveal animation for A2UI narrative components.
 * 
 * Function: useStreamingText
 * Called from: ExplainMovePanel.tsx
 * Why: Creates engaging typewriter effect for AI-generated explanations.
 */

import { useState, useEffect, useRef } from 'react';

export interface UseStreamingTextOptions {
    /** Speed in milliseconds per character (default: 30) */
    speed?: number;
    /** Whether streaming is enabled (default: true) */
    enabled?: boolean;
    /** Callback when streaming completes */
    onComplete?: () => void;
}

export interface UseStreamingTextResult {
    /** Currently displayed text (partially revealed) */
    displayText: string;
    /** Whether streaming is complete */
    isComplete: boolean;
    /** Whether currently streaming */
    isStreaming: boolean;
    /** Reset and re-stream from beginning */
    reset: () => void;
    /** Skip to full text immediately */
    skipToEnd: () => void;
}

export function useStreamingText(
    fullText: string,
    options: UseStreamingTextOptions = {}
): UseStreamingTextResult {
    const { speed = 30, enabled = true, onComplete } = options;

    const [displayText, setDisplayText] = useState('');
    const [isComplete, setIsComplete] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const indexRef = useRef(0);
    const previousTextRef = useRef('');

    // Cleanup interval on unmount
    useEffect(() => {
        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, []);

    // Handle text changes
    useEffect(() => {
        if (!enabled) {
            setDisplayText(fullText);
            setIsComplete(true);
            setIsStreaming(false);
            return;
        }

        // If text changed, restart streaming
        if (fullText !== previousTextRef.current) {
            previousTextRef.current = fullText;
            indexRef.current = 0;
            setDisplayText('');
            setIsComplete(false);
            setIsStreaming(true);

            // Clear existing interval
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }

            // Start streaming
            intervalRef.current = setInterval(() => {
                if (indexRef.current < fullText.length) {
                    indexRef.current += 1;
                    setDisplayText(fullText.slice(0, indexRef.current));
                } else {
                    // Streaming complete
                    if (intervalRef.current) {
                        clearInterval(intervalRef.current);
                        intervalRef.current = null;
                    }
                    setIsComplete(true);
                    setIsStreaming(false);
                    onComplete?.();
                }
            }, speed);
        }
    }, [fullText, speed, enabled, onComplete]);

    const reset = () => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
        indexRef.current = 0;
        setDisplayText('');
        setIsComplete(false);
        setIsStreaming(false);
        previousTextRef.current = '';
    };

    const skipToEnd = () => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
        setDisplayText(fullText);
        setIsComplete(true);
        setIsStreaming(false);
        indexRef.current = fullText.length;
    };

    return {
        displayText,
        isComplete,
        isStreaming,
        reset,
        skipToEnd,
    };
}
