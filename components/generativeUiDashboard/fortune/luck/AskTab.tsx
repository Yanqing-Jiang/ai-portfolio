import React from 'react';
import { motion } from 'framer-motion';
import { useFortuneAsk } from '../../hooks/useFortuneAsk';
import { OracleChat } from '../shared';
import { FLOW_ACCENTS } from '../designTokens';
import { tabContentVariants } from '../animations';

const ACCENT = FLOW_ACCENTS['luck-cycle'];

const SUGGESTIONS = [
  'When is the best time to change jobs?',
  'What should I watch out for in 2027?',
  'How does this decade affect my health?',
  'Career or wealth — what peaks first?',
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
