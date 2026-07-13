/**
 * Unified Ask tab — parametrized per fortune function.
 * Preserves each mode's suggestions, headers, context banners, and flowFocus.
 */
import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { Brain, MessageSquareQuote, TrendingUp } from 'lucide-react';
import { useFortuneAsk } from '../../hooks/useFortuneAsk';
import { MemoryPanel } from './MemoryPanel';
import { useFortuneStore } from '../../stores/fortuneStore';
import { OracleChat, type OracleChatMessage } from './OracleChat';
import { FLOW_ACCENTS, OBSERVATORY_MONO, accentAlpha } from '../designTokens';
import { tabContentVariants } from '../animations';
import type { AskContext, FortuneFunctionId, OccasionPick } from '../../lib/fortuneTypes';
import type { CanonicalFortuneFunction } from '../../../../lib/fortuneRoutes';

/** Map canonical ids → legacy FLOW_ACCENTS / ask keys (API unchanged). */
const SESSION_ID: Record<CanonicalFortuneFunction, FortuneFunctionId> = {
  wish: 'wish',
  cycle: 'luck-cycle',
  compatibility: 'compatibility',
  occasion: 'lucky-day',
};

const FLOW_FOCUS: Record<CanonicalFortuneFunction, string> = {
  wish: 'wish',
  cycle: 'luck_cycle',
  compatibility: 'compatibility:romance',
  occasion: 'occasion',
};

const DEFAULT_SUGGESTIONS: Record<CanonicalFortuneFunction, string[]> = {
  wish: [
    "What's the best timing?",
    'What should I avoid?',
    'Who can help me?',
    'What would change the verdict?',
  ],
  cycle: [
    'Which decade is my financial peak?',
    'Should I be cautious in 2028?',
    'How does the Wood element affect me?',
    'Best years for career transition?',
  ],
  compatibility: [
    'What makes our bond so strong?',
    'What triggers conflict between us?',
    'Best way to handle our clashes?',
  ],
  occasion: [
    "What defines a 'Lucky Day'?",
    'How is my birth chart used?',
    'What if there are no good days?',
    'Explain the scoring logic',
  ],
};

const HEADERS: Record<
  CanonicalFortuneFunction,
  { title: string; subtitle?: string }
> = {
  wish: { title: 'Refine your inquiry' },
  cycle: {
    title: 'Cycle Inquiry',
    subtitle: 'Deep dive into specific timing or life domains.',
  },
  compatibility: { title: '' },
  occasion: { title: '' },
};

function wishSuggestions(question?: string): string[] {
  if (!question) return DEFAULT_SUGGESTIONS.wish;
  const lowerQ = question.toLowerCase();
  if (lowerQ.includes('job') || lowerQ.includes('career') || lowerQ.includes('work')) {
    return [
      'What about salary prospects?',
      'Is my boss supportive?',
      'Should I wait for next month?',
      'Will I face competition?',
    ];
  }
  if (lowerQ.includes('love') || lowerQ.includes('relationship') || lowerQ.includes('marry')) {
    return [
      'Is the timing right for marriage?',
      'Are there hidden conflicts?',
      'How can I improve our harmony?',
      "What about our parents' influence?",
    ];
  }
  if (lowerQ.includes('money') || lowerQ.includes('wealth') || lowerQ.includes('investment')) {
    return [
      'When is my peak wealth luck?',
      'Which element brings me money?',
      'Is this a high-risk period?',
      'Should I partner with others?',
    ];
  }
  return DEFAULT_SUGGESTIONS.wish;
}

export interface AskTabProps {
  functionId: CanonicalFortuneFunction;
  /** Wish-only: original question for suggestion derivation. */
  question?: string;
  context?: AskContext;
  ready?: boolean;
}

export const AskTab: React.FC<AskTabProps> = ({ functionId, question, context, ready = false }) => {
  const sessionId = SESSION_ID[functionId];
  const accent = FLOW_ACCENTS[sessionId];
  const header = HEADERS[functionId];
  const { input, setInput, history, loading, memoryDegraded, send, retry, fortuneId } =
    useFortuneAsk(context);

  const dataModel = useFortuneStore(useShallow((s) => s.dataModel));

  const suggestions = useMemo(() => {
    if (functionId === 'wish') return wishSuggestions(question);

    if (functionId === 'compatibility') {
      const overview = dataModel?.compatibility?.overview;
      const interactionsCount = dataModel?.compatibility?.pairInteractions?.length || 0;
      const base = [
        'What triggers conflict between us?',
        'Best way to handle our clashes?',
      ];
      if (overview?.score && overview.score < 60) {
        base.unshift(`Why is our harmony score only ${Math.round(overview.score)}?`);
      } else {
        base.unshift('What makes our bond so strong?');
      }
      if (interactionsCount > 5) base.push('Which connection is most important?');
      return base;
    }

    if (functionId === 'occasion') {
      const topPicks = (dataModel?.occasion?.topPicks || []) as OccasionPick[];
      if (topPicks.length > 0) {
        const bestDate = new Date(topPicks[0].date).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
        });
        return [
          `Why is ${bestDate} ranked #1?`,
          'Compare #1 vs #2 picks',
          `Best hours on ${bestDate}`,
          'What if I can only do weekends?',
        ];
      }
    }

    return DEFAULT_SUGGESTIONS[functionId];
  }, [functionId, question, dataModel]);

  const messages = history.map((h) => ({
    id: h.id,
    role: h.role,
    content: h.content,
    narrative: h.narrative as OracleChatMessage['narrative'],
    runId: h.runId,
    degradedMemory: h.degradedMemory,
    error: h.error,
    retryable: h.retryable,
    retryQuestion: h.retryQuestion,
    clientRequestId: h.clientRequestId,
    askContext: h.askContext,
  }));

  const chat = (
    <div className="flex flex-col gap-3">
      <MemoryPanel />
      <OracleChat
        messages={messages}
        input={input}
        onInputChange={setInput}
        onSend={send}
        onRetry={retry}
        suggestions={suggestions}
        accentColor={accent.primary}
        isLoading={loading}
        memoryDegraded={memoryDegraded}
        disabled={!fortuneId || !ready}
        disabledReason={!ready ? 'Ask becomes available when the reading is complete.' : undefined}
        flowFocus={FLOW_FOCUS[functionId]}
        contextLabel={context?.sectionLabel}
      />
    </div>
  );

  if (functionId === 'occasion') {
    const topPicks = (dataModel?.occasion?.topPicks || []) as OccasionPick[];
    return (
      <motion.div
        key="ask"
        variants={tabContentVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        className="flex flex-col gap-4 pb-24"
      >
        {topPicks.length > 0 && (
          <div>
            <div
              className="flex items-center justify-between gap-3 rounded-xl border p-3"
              style={{
                borderColor: accentAlpha(accent.primary, 0.25),
                background: accentAlpha(accent.primary, 0.04),
              }}
            >
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-amber-500/20 bg-amber-500/10">
                  <TrendingUp size={14} className="text-amber-500" />
                </div>
                <div className="flex min-w-0 flex-col">
                  <span className="text-[10px] font-bold uppercase tracking-tighter text-white/40">
                    Current Recommendation
                  </span>
                  <span className="truncate text-xs font-medium text-white">
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
        <div className="min-h-[400px] flex-1">{chat}</div>
      </motion.div>
    );
  }

  if (functionId === 'compatibility') {
    const interactionsCount = dataModel?.compatibility?.pairInteractions?.length || 0;
    const mechanismsCount = dataModel?.compatibility?.mechanisms?.length || 0;
    return (
      <motion.div
        key="ask"
        variants={tabContentVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        className="space-y-4"
      >
        <div
          className="relative flex items-center gap-4 overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.02] p-4"
          style={{ fontFamily: OBSERVATORY_MONO }}
        >
          <div className="absolute right-0 top-0 p-1 opacity-5">
            <Brain size={60} />
          </div>
          <div className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-rose-500/10">
            <MessageSquareQuote size={20} className="text-rose-400" />
          </div>
          <div className="min-w-0 flex-1">
            <h4 className="text-[11px] font-bold uppercase tracking-widest text-slate-300">
              Analysis Summary
            </h4>
            <p className="mt-0.5 truncate text-[10px] text-slate-500">
              The agent analyzed {interactionsCount} interactions and {mechanismsCount}{' '}
              mechanisms to calculate your compatibility.
            </p>
          </div>
        </div>
        {chat}
      </motion.div>
    );
  }

  return (
    <motion.div
      key="ask"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className={functionId === 'cycle' ? 'pb-20' : 'pb-8'}
    >
      {header.title && (
        <div className="mb-4 px-1">
          <h3
            className={`text-[10px] font-bold uppercase tracking-[0.2em] ${
              functionId === 'cycle' ? 'text-slate-400' : 'text-slate-500'
            }`}
          >
            {header.title}
          </h3>
          {header.subtitle && (
            <p className="mt-1 text-[11px] leading-tight text-slate-500">
              {header.subtitle}
            </p>
          )}
        </div>
      )}
      {chat}
    </motion.div>
  );
};
