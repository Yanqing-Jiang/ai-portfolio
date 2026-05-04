import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { useFortuneAsk } from '../../hooks/useFortuneAsk';
import { OracleChat } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { tabContentVariants } from '../animations';

const ACCENT = FLOW_ACCENTS.wish;

const DEFAULT_SUGGESTIONS = [
  "What's the best timing?",
  "What should I avoid?",
  "Who can help me?",
  "What would change the verdict?",
];

export const AskTab: React.FC<{ question?: string }> = ({ question }) => {
  const { input, setInput, history, loading, memoryDegraded, send, fortuneId } = useFortuneAsk();

  // Derive suggestions from the original question if possible
  const suggestions = useMemo(() => {
    if (!question) return DEFAULT_SUGGESTIONS;
    
    const lowerQ = question.toLowerCase();
    
    if (lowerQ.includes('job') || lowerQ.includes('career') || lowerQ.includes('work')) {
      return [
        "What about salary prospects?",
        "Is my boss supportive?",
        "Should I wait for next month?",
        "Will I face competition?"
      ];
    }
    
    if (lowerQ.includes('love') || lowerQ.includes('relationship') || lowerQ.includes('marry')) {
      return [
        "Is the timing right for marriage?",
        "Are there hidden conflicts?",
        "How can I improve our harmony?",
        "What about our parents' influence?"
      ];
    }

    if (lowerQ.includes('money') || lowerQ.includes('wealth') || lowerQ.includes('investment')) {
      return [
        "When is my peak wealth luck?",
        "Which element brings me money?",
        "Is this a high-risk period?",
        "Should I partner with others?"
      ];
    }

    return DEFAULT_SUGGESTIONS;
  }, [question]);

  return (
    <motion.div
      key="ask"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="pb-8"
    >
      <div className="mb-4 px-1">
        <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
          Refine your inquiry
        </h3>
      </div>

      <OracleChat
        messages={history.map((h) => ({ id: h.id, role: h.role, content: h.content }))}
        input={input}
        onInputChange={setInput}
        onSend={send}
        suggestions={suggestions}
        accentColor={ACCENT.primary}
        isLoading={loading}
        memoryDegraded={memoryDegraded}
        disabled={!fortuneId}
      />
    </motion.div>
  );
};
