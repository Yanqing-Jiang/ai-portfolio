import React, { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Loader2, AlertCircle } from 'lucide-react';
import { GLASS } from '../designTokens';
import { staggerItem } from '../animations';

interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  content: string;
}

interface OracleChatProps {
  messages: ChatMessage[];
  input: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  suggestions?: string[];
  accentColor?: string;
  isLoading?: boolean;
  memoryDegraded?: boolean;
  disabled?: boolean;
}

const FORTUNE_CHINESE_FONT = "'Noto Serif SC', 'Songti SC', 'Songti TC', Georgia, serif";

export const OracleChat: React.FC<OracleChatProps> = ({
  messages,
  input,
  onInputChange,
  onSend,
  suggestions = [],
  accentColor = '#14b8a6',
  isLoading = false,
  memoryDegraded = false,
  disabled = false,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages.length]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="flex flex-col h-[60vh] max-h-[500px]">
      {/* Degraded memory banner */}
      {memoryDegraded && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 p-2 mb-3 text-[11px] text-amber-400">
          <AlertCircle className="w-3.5 h-3.5 flex-none" />
          Memory is limited — the oracle may not recall earlier context.
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 mb-3 pr-1 scrollbar-hide">
        <AnimatePresence>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              variants={staggerItem}
              initial="hidden"
              animate="visible"
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-white/10 text-slate-200'
                    : `${GLASS} text-slate-200`
                }`}
                style={msg.role === 'agent' ? {
                  borderLeft: `2px solid ${accentColor}66`,
                  fontFamily: FORTUNE_CHINESE_FONT,
                } : undefined}
              >
                {msg.content}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {isLoading && (
          <div className="flex justify-start">
            <div className={`${GLASS} px-4 py-3 flex items-center gap-2 text-xs text-slate-400`}>
              <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: accentColor }} />
              Consulting the pillars...
            </div>
          </div>
        )}
      </div>

      {/* Suggestion chips */}
      {suggestions.length > 0 && messages.length <= 1 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => { onInputChange(s); }}
              className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[11px] text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex items-end gap-2">
        <textarea
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask the oracle..."
          disabled={disabled || isLoading}
          rows={1}
          className="flex-1 resize-none rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-white/20"
          style={{ maxHeight: 100, minHeight: 38 }}
        />
        <button
          type="button"
          onClick={onSend}
          disabled={disabled || isLoading || !input.trim()}
          className="flex h-[38px] w-[38px] flex-none items-center justify-center rounded-xl border transition-colors"
          style={{
            borderColor: `${accentColor}33`,
            background: input.trim() ? `${accentColor}1A` : 'transparent',
            color: input.trim() ? accentColor : '#64748b',
          }}
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
