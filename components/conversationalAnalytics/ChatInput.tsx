/**
 * Function: ChatInput â€” Modern chat input with suggestions, animations, and auth/quota status
 * Called from: ConversationalAnalyticsPage
 * Invokes: Supabase auth (authService) + /api/rate-limit/usage to show the signed-in widget; AuthModal for sign-in
 * Purpose: Provides the conversational input experience while mirroring the sign-in/quota pill used in other project chats
 */

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { theme } from './styles';
import { authService, type AuthState } from '../../services/auth';
import { apiService, type UsageStats } from '../../services/apiService';
import { AuthModal } from '../AuthModal';

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
  { label: 'Project showcase', prompt: 'Project showcase walkthrough of the Next Gen Analytics agent', icon: '🗂️' },
];

// Use shared chat scope so credits align across projects
const RATE_LIMIT_SCOPE = 'chat';

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
  const [authState, setAuthState] = useState<AuthState>({ user: null, loading: true, error: null });
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  const [isUsageLoading, setIsUsageLoading] = useState(true);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const suggestions = suggestionsOverride && suggestionsOverride.length > 0 ? suggestionsOverride : baseSuggestions;

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 150) + 'px';
    }
  }, [value]);

  useEffect(() => {
    const unsubscribe = authService.subscribe(setAuthState);
    return unsubscribe;
  }, []);

  useEffect(() => {
    let isMounted = true;
    const fetchUsage = async () => {
      setIsUsageLoading(true);
      const result = await apiService.getUsageStats(RATE_LIMIT_SCOPE);
      if (!isMounted) return;
      if (result.success && result.data) {
        setUsageStats(result.data);
      } else {
        setUsageStats(null);
      }
      setIsUsageLoading(false);
    };

    if (!authState.loading) {
      fetchUsage();
    }

    return () => {
      isMounted = false;
    };
  }, [authState.loading, authState.user?.id]);

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
    <>
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
            <p className="text-xs mb-2" style={{ color: theme.colors.text.muted }}>
              Quick Suggestions
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

        {/* Auth + quota status */}
        <div
          className="mt-3 flex items-center gap-3 text-xs"
          style={{ color: theme.colors.text.muted }}
        >
          <div className="flex items-center gap-1.5">
            <span
              className="w-2 h-2 rounded-full"
              style={{
                backgroundColor: authState.loading
                  ? theme.colors.status.warning
                  : authState.user
                  ? theme.colors.status.success
                  : theme.colors.status.warning,
              }}
            />
            <span>
              {authState.loading
                ? 'Checking...'
                : authState.user
                ? (authState.user.email ?? 'Member')
                : 'Guest'}
            </span>
            <span style={{ opacity: 0.5 }}>•</span>
            <span>
              {usageStats ? `${usageStats.current_usage}/${usageStats.limit}` : isUsageLoading ? '—' : '—'} requests/day
            </span>
          </div>
          {authState.user ? (
            <button
              onClick={async () => {
                await authService.signOut();
                setUsageStats(null);
                setIsUsageLoading(true);
              }}
              style={{ color: theme.colors.accent.primary }}
            >
              Sign out
            </button>
          ) : (
            <button
              onClick={() => setShowAuthModal(true)}
              style={{ color: theme.colors.accent.primary }}
            >
              Sign in for more
            </button>
          )}
        </div>
      </div>
      </div>

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={() => setShowAuthModal(false)}
      />
    </>
  );
};

export default ChatInput;
