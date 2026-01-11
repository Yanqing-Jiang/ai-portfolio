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
    /** Key to force reset - when this changes, streaming restarts even if text is same */
    resetKey?: string | number;
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
    const { speed = 30, enabled = true, onComplete, resetKey } = options;

    const [displayText, setDisplayText] = useState('');
    const [isComplete, setIsComplete] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const indexRef = useRef(0);
    const previousTextRef = useRef('');
    const previousResetKeyRef = useRef<string | number | undefined>(resetKey);

    // Cleanup interval on unmount
    useEffect(() => {
        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, []);

    // Handle text changes or resetKey changes
    useEffect(() => {
        if (!enabled) {
            setDisplayText(fullText);
            setIsComplete(true);
            setIsStreaming(false);
            return;
        }

        // Check if resetKey changed (forces restart even if text is same)
        const resetKeyChanged = resetKey !== previousResetKeyRef.current;
        const textChanged = fullText !== previousTextRef.current;

        // If text changed OR resetKey changed, restart streaming
        if (textChanged || resetKeyChanged) {
            // Update refs BEFORE starting interval to prevent race conditions
            previousTextRef.current = fullText;
            if (resetKeyChanged) {
                previousResetKeyRef.current = resetKey;
            }

            // Reset state
            indexRef.current = 0;
            setDisplayText('');
            setIsComplete(false);
            setIsStreaming(true);

            // Clear existing interval before creating new one
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }

            // Don't start streaming if text is empty
            if (fullText.length === 0) {
                setIsComplete(true);
                setIsStreaming(false);
                return;
            }

            // Start streaming with local copy of fullText to avoid closure issues
            const targetText = fullText;
            intervalRef.current = setInterval(() => {
                if (indexRef.current < targetText.length) {
                    indexRef.current += 1;
                    setDisplayText(targetText.slice(0, indexRef.current));
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
    }, [fullText, speed, enabled, onComplete, resetKey]);

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
