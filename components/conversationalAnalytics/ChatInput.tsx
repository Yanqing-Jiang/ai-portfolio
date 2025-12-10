/**
 * Function: ChatInput — Modern chat input with suggestions and animations
 * Called from: ConversationalAnalyticsPage
 * Purpose: Provides elegant input experience with quick suggestions
 */

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { theme } from './styles';

interface SuggestionItem {
  label: string;
  prompt: string;
  icon: string;
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onPause: () => void;
  onResume: () => void;
  isStreaming: boolean;
  isPaused: boolean;
  placeholder?: string;
  suggestionsOverride?: SuggestionItem[];
}

const baseSuggestions: SuggestionItem[] = [
  { label: 'Market share', prompt: 'Market share of NVDA vs peers over last 5 years', icon: '📊' },
  { label: 'Revenue compare', prompt: 'Compare revenue for NVDA, AMD, INTC by year (5y)', icon: '📈' },
  { label: 'Revenue growth', prompt: 'YoY revenue growth for NVDA and AMD by quarter', icon: '📉' },
  { label: 'Margins vs peers', prompt: 'Net margin vs peers for NVDA over last 5 years', icon: '💹' },
  { label: 'Margin growth', prompt: 'Operating margin growth vs peers for AMD by quarter', icon: '🔺' },
];

const ChatInput: React.FC<ChatInputProps> = ({
  value,
  onChange,
  onSubmit,
  onPause,
  onResume,
  isStreaming,
  isPaused,
  placeholder = 'Ask about semiconductor financials...',
  suggestionsOverride,
}) => {
  const [isFocused, setIsFocused] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const suggestions = suggestionsOverride && suggestionsOverride.length > 0 ? suggestionsOverride : baseSuggestions;

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 150) + 'px';
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && !isPaused && value.trim()) {
        onSubmit();
      }
    }
  };

  const handleSuggestionClick = (prompt: string) => {
    onChange(prompt);
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  return (
    <div
      className="relative"
      style={{
        backgroundColor: theme.colors.bg.secondary,
        borderTop: `1px solid ${theme.colors.border.subtle}`,
      }}
    >
      {/* Suggestions */}
      <AnimatePresence>
        {showSuggestions && !value && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="absolute bottom-full left-0 right-0 p-4 pb-6"
            style={{ backgroundColor: theme.colors.bg.secondary }}
          >
            <p className="text-xs mb-3" style={{ color: theme.colors.text.muted }}>
              Quick suggestions
            </p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((s, idx) => (
                <motion.button
                  key={idx}
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  onClick={() => handleSuggestionClick(s.prompt)}
                  className="px-3 py-2 rounded-xl text-sm flex items-center gap-2 transition-all"
                  style={{
                    backgroundColor: theme.colors.bg.tertiary,
                    border: `1px solid ${theme.colors.border.subtle}`,
                    color: theme.colors.text.secondary,
                  }}
                  whileHover={{
                    backgroundColor: theme.colors.bg.elevated,
                    borderColor: theme.colors.border.medium,
                  }}
                >
                  <span>{s.icon}</span>
                  <span>{s.label}</span>
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input area */}
      <div className="p-4">
        <div
          className="relative flex items-end gap-3 rounded-2xl transition-all duration-200"
          style={{
            backgroundColor: theme.colors.bg.tertiary,
            border: `1px solid ${isFocused ? theme.colors.accent.primary + '50' : theme.colors.border.medium}`,
            boxShadow: isFocused ? `0 0 0 3px ${theme.colors.accent.primary}15` : 'none',
          }}
        >
          {/* Textarea */}
          <textarea
            ref={inputRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              setIsFocused(true);
              setShowSuggestions(true);
            }}
            onBlur={() => {
              setIsFocused(false);
              // Delay hiding suggestions to allow click
              setTimeout(() => setShowSuggestions(false), 200);
            }}
            placeholder={placeholder}
            disabled={isStreaming && !isPaused}
            rows={1}
            className="flex-1 px-4 py-3 bg-transparent resize-none outline-none text-sm leading-relaxed"
            style={{
              color: theme.colors.text.primary,
              minHeight: '48px',
              maxHeight: '150px',
            }}
          />

          {/* Send button */}
          <div className="p-2">
            <motion.button
              onClick={() => {
                if (isStreaming && !isPaused) {
                  onPause();
                } else if (isPaused) {
                  onResume();
                } else {
                  onSubmit();
                }
              }}
              disabled={!isPaused && !isStreaming && !value.trim()}
              className="w-10 h-10 rounded-xl flex items-center justify-center transition-all"
              style={{
                background: (isStreaming && !isPaused) || isPaused || value.trim()
                  ? theme.colors.user.bg
                  : theme.colors.bg.elevated,
                color: (isStreaming && !isPaused) || isPaused || value.trim()
                  ? theme.colors.user.text
                  : theme.colors.text.muted,
                cursor: (!isPaused && !isStreaming && !value.trim()) ? 'not-allowed' : 'pointer',
              }}
              whileHover={(isStreaming || isPaused || value.trim()) ? { scale: 1.05 } : {}}
              whileTap={(isStreaming || isPaused || value.trim()) ? { scale: 0.95 } : {}}
            >
              {isStreaming && !isPaused ? (
                <span className="text-xs font-semibold">Pause</span>
              ) : isPaused ? (
                <span className="text-xs font-semibold">Resume</span>
              ) : (
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{
                    opacity: value.trim() ? 1 : 0.35,
                  }}
                >
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              )}
            </motion.button>
          </div>
        </div>

        {/* Helper text */}
        <p className="mt-2 text-center text-xs" style={{ color: theme.colors.text.muted }}>
          Press <kbd className="px-1.5 py-0.5 rounded" style={{ backgroundColor: theme.colors.bg.elevated }}>Enter</kbd> to send, <kbd className="px-1.5 py-0.5 rounded" style={{ backgroundColor: theme.colors.bg.elevated }}>Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  );
};

export default ChatInput;

