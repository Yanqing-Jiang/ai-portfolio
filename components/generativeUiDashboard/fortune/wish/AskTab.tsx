import React from 'react';
import { motion } from 'framer-motion';
import { useFortuneAsk } from '../../hooks/useFortuneAsk';
import { OracleChat } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { tabContentVariants } from '../animations';

const ACCENT = FLOW_ACCENTS.wish;

const SUGGESTIONS = [
  'What if I take the other offer?',
  'How about next quarter?',
  'Is my partner supportive?',
  "Any red flags I'm missing?",
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
    >
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
