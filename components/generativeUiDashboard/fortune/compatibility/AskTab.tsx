import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Brain, MessageSquareQuote } from 'lucide-react';
import { useFortuneAsk } from '../../hooks/useFortuneAsk';
import { useFortuneStore } from '../../stores/fortuneStore';
import { OracleChat } from '../shared';
import type { OracleChatMessage } from '../shared/OracleChat';
import { FLOW_ACCENTS, GLASS } from '../designTokens';
import { tabContentVariants } from '../animations';

const ACCENT = FLOW_ACCENTS.compatibility;

export const AskTab: React.FC = () => {
  const { input, setInput, history, loading, memoryDegraded, send, fortuneId } = useFortuneAsk();
  const dataModel = useFortuneStore(s => s.dataModel);

  const overview = dataModel?.compatibility?.overview;
  const interactionsCount = dataModel?.compatibility?.pairInteractions?.length || 0;
  const mechanismsCount = dataModel?.compatibility?.mechanisms?.length || 0;

  const dynamicSuggestions = useMemo(() => {
    const base = [
      'What triggers conflict between us?',
      'Best way to handle our clashes?',
    ];
    if (overview?.score && overview.score < 60) {
      base.unshift(`Why is our harmony score only ${Math.round(overview.score)}?`);
    } else {
      base.unshift('What makes our bond so strong?');
    }
    if (interactionsCount > 5) {
      base.push('Which connection is most important?');
    }
    return base;
  }, [overview?.score, interactionsCount]);

  return (
    <motion.div
      key="ask"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-4"
    >
      {/* Thinking Summary Banner */}
      <div className={`${GLASS} p-4 flex items-center gap-4 overflow-hidden relative`}>
        <div className="absolute top-0 right-0 p-1 opacity-5">
            <Brain size={60} />
        </div>
        <div className="h-10 w-10 rounded-xl bg-rose-500/10 flex items-center justify-center flex-none">
          <MessageSquareQuote size={20} className="text-rose-400" />
        </div>
        <div className="min-w-0 flex-1">
          <h4 className="text-[11px] font-bold uppercase tracking-widest text-slate-300">Analysis Summary</h4>
          <p className="text-[10px] text-slate-500 mt-0.5 truncate">
            The agent analyzed {interactionsCount} interactions and {mechanismsCount} mechanisms to calculate your compatibility.
          </p>
        </div>
      </div>

      <OracleChat
        messages={history.map((h) => ({
          id: h.id,
          role: h.role,
          content: h.content,
          narrative: h.narrative as OracleChatMessage['narrative'],
          runId: h.runId,
          degradedMemory: h.degradedMemory,
        }))}
        input={input}
        onInputChange={setInput}
        onSend={send}
        suggestions={dynamicSuggestions}
        accentColor={ACCENT.primary}
        isLoading={loading}
        memoryDegraded={memoryDegraded}
        disabled={!fortuneId}
        flowFocus="compatibility:romance"
      />
    </motion.div>
  );
};
