/**
 * Tab 4: Oracle Chat
 * Result-aware suggestions and context-aware context panel.
 */
import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { TrendingUp } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import { useFortuneAsk } from '../../hooks/useFortuneAsk';
import { OracleChat, type OracleChatMessage } from '../shared/OracleChat';
import { FLOW_ACCENTS, GLASS } from '../designTokens';
import { tabContentVariants } from '../animations';
import type { OccasionPick } from '../../lib/fortuneTypes';

export const AskTab: React.FC = () => {
  const { dataModel } = useFortuneStore(useShallow((s) => ({
    dataModel: s.dataModel,
  })));

  const accent = FLOW_ACCENTS['lucky-day'];
  const topPicks = (dataModel?.occasion?.topPicks || []) as OccasionPick[];

  const { input, setInput, history, loading, memoryDegraded, send, fortuneId } = useFortuneAsk();

  // Result-aware suggestions
  const suggestions = useMemo(() => {
    if (topPicks.length > 0) {
      const bestDate = new Date(topPicks[0].date).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
      return [
        `Why is ${bestDate} ranked #1?`,
        `Compare #1 vs #2 picks`,
        `Best hours on ${bestDate}`,
        'What if I can only do weekends?',
      ];
    }
    return [
      "What defines a 'Lucky Day'?",
      'How is my birth chart used?',
      'What if there are no good days?',
      'Explain the scoring logic',
    ];
  }, [topPicks]);

  return (
    <motion.div
      key="ask"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="flex flex-col gap-4 pb-24"
    >
      {/* Context Micro-card */}
      {topPicks.length > 0 && (
        <div>
          <div
            className={`${GLASS} p-3 bg-amber-500/[0.03] border-amber-500/20 flex items-center justify-between gap-3`}
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-full bg-amber-500/10 flex items-center justify-center border border-amber-500/20 shrink-0">
                <TrendingUp size={14} className="text-amber-500" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-[10px] text-white/40 uppercase font-bold tracking-tighter">
                  Current Recommendation
                </span>
                <span className="text-xs text-white font-medium truncate">
                  {new Date(topPicks[0].date).toLocaleDateString('en-US', {
                    month: 'long',
                    day: 'numeric',
                  })}{' '}
                  (Score {topPicks[0].score})
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() =>
                setInput(
                  `Tell me more about the ${new Date(topPicks[0].date).toLocaleDateString(
                    'en-US',
                    { month: 'short', day: 'numeric' },
                  )} pick`,
                )
              }
              className="shrink-0 text-[10px] font-bold text-amber-500 hover:text-amber-400"
            >
              Ask Detail
            </button>
          </div>
        </div>
      )}

      {/* Main Chat */}
      <div className="flex-1 min-h-[400px]">
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
          suggestions={suggestions}
          accentColor={accent.primary}
          isLoading={loading}
          memoryDegraded={memoryDegraded}
          disabled={!fortuneId}
          flowFocus="occasion"
        />
      </div>
    </motion.div>
  );
};
