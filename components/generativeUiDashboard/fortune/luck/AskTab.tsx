import React from 'react';
import { motion } from 'framer-motion';
import { useFortuneAsk } from '../../hooks/useFortuneAsk';
import { OracleChat } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { tabContentVariants } from '../animations';

const ACCENT = FLOW_ACCENTS['luck-cycle'];

const SUGGESTIONS = [
  'Which decade is my financial peak?',
  'Should I be cautious in 2028?',
  'How does the Wood element affect me?',
  'Best years for career transition?',
];

export const AskTab: React.FC = () => {
  const { input, setInput, history, loading, memoryDegraded, send, fortuneId } = useFortuneAsk();

  return (
    <motion.div
      key="ask"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="pb-20"
    >
      <div className="px-1 mb-4">
        <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
          Cycle Inquiry
        </h3>
        <p className="text-[11px] text-slate-500 leading-tight mt-1">
          Deep dive into specific timing or life domains.
        </p>
      </div>

      <OracleChat
        messages={history.map((h) => ({ id: h.id, role: h.role, content: h.content }))}
        input={input}
        onInputChange={setInput}
        onSend={send}
        suggestions={SUGGESTIONS}
        accentColor={ACCENT.primary}
        isLoading={loading}
        memoryDegraded={memoryDegraded}
        disabled={!fortuneId}
      />
    </motion.div>
  );
};
