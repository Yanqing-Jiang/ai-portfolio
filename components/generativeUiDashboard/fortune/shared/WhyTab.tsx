/**
 * Unified Why tab — parametrized per fortune function.
 * Preserves each mode's existing markup (grouped / flat / filtered / occasion).
 */
import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useShallow } from 'zustand/react/shallow';
import { BookOpen, Filter, Layers, ShieldAlert, Zap } from 'lucide-react';
import { useFortuneStore } from '../../stores/fortuneStore';
import { MechanismCard, CitationBlock, ChineseToggle, StreamingText } from './index';
import { FLOW_ACCENTS, GLASS, CITATION_GOLD, ELEMENT_COLORS } from '../designTokens';
import {
  staggerContainer,
  tabContentVariants,
  pickVariants,
  fadeInUp,
} from '../animations';
import type {
  Mechanism,
  Citation,
  Interaction,
  WishModel,
  ElementType,
  FortuneFunctionId,
} from '../../lib/fortuneTypes';
import type { CanonicalFortuneFunction } from '../../../../lib/fortuneRoutes';

const SESSION_ID: Record<CanonicalFortuneFunction, FortuneFunctionId> = {
  wish: 'wish',
  cycle: 'luck-cycle',
  compatibility: 'compatibility',
  occasion: 'lucky-day',
};

const COMPAT_CATEGORIES = ['all', 'combination', 'clash', 'harm', 'support'];

export interface WhyTabProps {
  functionId: CanonicalFortuneFunction;
  isReplay?: boolean;
}

export const WhyTab: React.FC<WhyTabProps> = ({
  functionId,
  isReplay = false,
}) => {
  const accent = FLOW_ACCENTS[SESSION_ID[functionId]];
  const [showChinese, setShowChinese] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState(
    functionId === 'compatibility' ? 'all' : 'All',
  );

  const { dataModel, status } = useFortuneStore(
    useShallow((s) => ({ dataModel: s.dataModel, status: s.status })),
  );

  const citations = (dataModel?.classics?.references || []) as Citation[];
  const wish = dataModel?.wish as WishModel | undefined;
  const wishMechanisms = wish?.mechanisms || [];
  const rawInteractions = (dataModel?.interactions?.items || []) as Interaction[];
  const cycleMechanisms = (dataModel?.luckCycle?.mechanisms || []) as Mechanism[];
  const occasionAnalysis = dataModel?.occasion?.analysis;
  const occasionMechanisms = (dataModel?.occasion?.mechanisms || []) as Mechanism[];
  const compatMechanisms = (dataModel?.compatibility?.mechanisms || []) as Mechanism[];

  const wishGroups = useMemo(() => {
    const interactionMechanisms: Mechanism[] = rawInteractions.map((inter, i) => ({
      id: `inter-${i}`,
      title: `${inter.type}: ${inter.from} → ${inter.to}`,
      type: 'interaction',
      bullets: [inter.description, inter.effect].filter(Boolean) as string[],
    }));

    const luckMechanisms = wishMechanisms.filter(
      (m) =>
        m.type === 'luck' ||
        m.title.toLowerCase().includes('luck') ||
        m.title.toLowerCase().includes('cycle'),
    );
    const chartMechanisms = wishMechanisms.filter((m) => !luckMechanisms.includes(m));

    return [
      {
        id: 'interactions',
        label: 'Chart Interactions',
        icon: <Layers className="h-3 w-3" />,
        items: [...chartMechanisms, ...interactionMechanisms],
      },
      {
        id: 'luck',
        label: 'Luck Drivers',
        icon: <Zap className="h-3 w-3" />,
        items: luckMechanisms,
      },
      {
        id: 'classics',
        label: 'Classical Patterns',
        icon: <BookOpen className="h-3 w-3" />,
        items: [] as Mechanism[],
        citations,
      },
    ].filter((g) => g.items.length > 0 || (g.citations && g.citations.length > 0));
  }, [wishMechanisms, rawInteractions, citations]);

  const occasionFiltered = useMemo(() => {
    if (filter === 'All') return occasionMechanisms;
    return occasionMechanisms.filter((m) => m.type === filter);
  }, [occasionMechanisms, filter]);

  const occasionFilterOptions = useMemo(() => {
    const types = new Set<string>();
    occasionMechanisms.forEach((m) => {
      if (m.type) types.add(m.type);
    });
    return ['All', ...Array.from(types)];
  }, [occasionMechanisms]);

  const compatFiltered = useMemo(() => {
    if (filter === 'all') return compatMechanisms;
    return compatMechanisms.filter((m) => m.type?.toLowerCase().includes(filter));
  }, [compatMechanisms, filter]);

  const toggleExpand = (id: string) =>
    setExpandedId((prev) => (prev === id ? null : id));

  if (functionId === 'wish') {
    return (
      <motion.div
        key="why"
        variants={tabContentVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        className="space-y-6 pb-8"
      >
        <div className="flex justify-end px-1">
          <ChineseToggle
            showChinese={showChinese}
            onToggle={() => setShowChinese(!showChinese)}
          />
        </div>

        {wishGroups.length === 0 ? (
          <div className={`${GLASS} border-dashed p-12 text-center`}>
            <p className="text-xs italic text-slate-500">Deep analysis in progress...</p>
          </div>
        ) : (
          <div className="space-y-8">
            {wishGroups.map((group) => (
              <div key={group.id} className="space-y-3">
                <div className="flex items-center gap-2 px-1">
                  <div
                    className="rounded-lg border border-white/10 bg-white/5 p-1.5"
                    style={{
                      color: group.id === 'classics' ? CITATION_GOLD : accent.primary,
                    }}
                  >
                    {group.icon}
                  </div>
                  <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
                    {group.label}
                  </h3>
                </div>

                <motion.div
                  variants={pickVariants(isReplay, staggerContainer(0.1))}
                  initial="hidden"
                  animate="visible"
                  className="space-y-3"
                >
                  {group.items.map((m, i) => {
                    const id = m.id || String(i);
                    return (
                      <MechanismCard
                        key={id}
                        mechanism={m}
                        citations={citations}
                        accentColor={accent.primary}
                        showChinese={showChinese}
                        isExpanded={expandedId === id}
                        onToggle={() => toggleExpand(id)}
                        isReplay={isReplay}
                      />
                    );
                  })}

                  {group.id === 'classics' &&
                    group.citations?.map((c) => (
                      <CitationBlock
                        key={c.id}
                        citation={c}
                        showChinese={showChinese}
                      />
                    ))}
                </motion.div>
              </div>
            ))}
          </div>
        )}
      </motion.div>
    );
  }

  if (functionId === 'cycle') {
    return (
      <motion.div
        key="why"
        variants={tabContentVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        className="space-y-6 pb-20"
      >
        <div className="flex items-center justify-between px-1">
          <div className="max-w-[70%]">
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
              Mechanism Analysis
            </h3>
            <p className="mt-1 text-[11px] leading-tight text-slate-500">
              How the agent synthesized your chart against the cycles.
            </p>
          </div>
          <ChineseToggle
            showChinese={showChinese}
            onToggle={() => setShowChinese(!showChinese)}
          />
        </div>

        {cycleMechanisms.length === 0 ? (
          <div className="flex flex-col items-center justify-center space-y-4 rounded-3xl border border-white/5 bg-slate-900/40 px-8 py-16 text-center">
            <div className="flex h-10 w-10 animate-pulse items-center justify-center rounded-full bg-indigo-500/10">
              <div className="h-5 w-5 rounded-full bg-indigo-500/20" />
            </div>
            <p className="text-xs leading-relaxed text-slate-500">
              The agent is currently tracing elemental interactions and clashing
              pillars...
            </p>
          </div>
        ) : (
          <motion.div
            variants={pickVariants(isReplay, staggerContainer(0.12))}
            initial="hidden"
            animate="visible"
            className="space-y-3"
          >
            {cycleMechanisms.map((m, i) => {
              const id = m.id || String(i);
              return (
                <MechanismCard
                  key={id}
                  mechanism={m}
                  citations={citations}
                  accentColor={accent.primary}
                  showChinese={showChinese}
                  isExpanded={expandedId === id}
                  onToggle={() => toggleExpand(id)}
                  isReplay={isReplay}
                />
              );
            })}
          </motion.div>
        )}

        {status === 'streaming' && cycleMechanisms.length > 0 && (
          <div className="flex items-center justify-center gap-2 py-4">
            <span className="h-1 w-1 animate-bounce rounded-full bg-indigo-500" />
            <span className="h-1 w-1 animate-bounce rounded-full bg-indigo-500 [animation-delay:0.2s]" />
            <span className="h-1 w-1 animate-bounce rounded-full bg-indigo-500 [animation-delay:0.4s]" />
            <span className="ml-1 text-[10px] font-medium uppercase tracking-wider text-slate-500">
              Agent is Thinking
            </span>
          </div>
        )}
      </motion.div>
    );
  }

  if (functionId === 'occasion') {
    return (
      <div className="flex flex-col gap-6 pb-24">
        <motion.div
          variants={pickVariants(isReplay, fadeInUp)}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-2 gap-3"
        >
          <div className={`${GLASS} flex flex-col gap-2 border-green-500/20 p-4`}>
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-green-400">
              <Zap size={12} /> Key Boosters
            </div>
            <div className="flex flex-wrap gap-1.5">
              {occasionAnalysis?.keyElements?.map((el: ElementType) => (
                <span
                  key={el}
                  className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-medium"
                  style={{ color: ELEMENT_COLORS[el]?.hex }}
                >
                  {el}
                </span>
              ))}
            </div>
          </div>
          <div className={`${GLASS} flex flex-col gap-2 border-red-500/20 p-4`}>
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-red-400">
              <ShieldAlert size={12} /> Elements to Avoid
            </div>
            <div className="flex flex-wrap gap-1.5">
              {occasionAnalysis?.avoidElements?.map((el: ElementType) => (
                <span
                  key={el}
                  className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-medium line-through decoration-red-500/50"
                  style={{ color: `${ELEMENT_COLORS[el]?.hex}80` }}
                >
                  {el}
                </span>
              ))}
            </div>
          </div>
        </motion.div>

        {occasionAnalysis?.description && (
          <div className={`${GLASS} bg-amber-500/[0.02] p-5`}>
            <StreamingText
              text={occasionAnalysis.description}
              isStreaming={!dataModel?.narrative?.isComplete}
              isReplay={isReplay}
              cursorColor={accent.primary}
            />
          </div>
        )}

        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between gap-3">
            <span className="shrink-0 text-[11px] font-bold uppercase tracking-widest text-white/30">
              Detailed Mechanisms
            </span>
            <div className="flex gap-2 overflow-x-auto scrollbar-hide">
              {occasionFilterOptions.map((opt) => (
                <button
                  type="button"
                  key={opt}
                  onClick={() => setFilter(opt)}
                  className={`shrink-0 rounded-full border px-3 py-1 text-[10px] font-medium transition-colors ${
                    filter === opt
                      ? 'border-amber-500 bg-amber-500 text-slate-950'
                      : 'border-white/10 bg-white/5 text-white/40'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>

          <motion.div
            variants={pickVariants(isReplay, staggerContainer(0.08))}
            initial="hidden"
            animate="visible"
            className="flex flex-col gap-3"
          >
            <AnimatePresence mode="popLayout">
              {occasionFiltered.map((mech, idx) => {
                const id = mech.id || String(idx);
                return (
                  <MechanismCard
                    key={id}
                    mechanism={mech}
                    citations={citations}
                    accentColor={accent.primary}
                    isExpanded={expandedId === id}
                    onToggle={() => toggleExpand(id)}
                    isReplay={isReplay}
                  />
                );
              })}
            </AnimatePresence>
          </motion.div>
        </div>

        <div className="mt-4 border-t border-white/10 pt-6 text-center">
          <span className="font-serif text-[10px] uppercase tracking-[0.2em] text-white/20">
            Derived from Classical Sources
          </span>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      key="why"
      variants={tabContentVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6 pb-12"
    >
      <div className="sticky top-0 z-20 -mx-1 border-b border-white/5 bg-[#0B1120]/80 px-1 py-2 backdrop-blur-md">
        <div className="no-scrollbar flex items-center gap-2 overflow-x-auto pb-1">
          <div className="flex-none rounded-lg bg-white/5 p-1.5 text-slate-500">
            <Filter size={14} />
          </div>
          {COMPAT_CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setFilter(cat)}
              className={`flex-none rounded-full px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
                filter === cat
                  ? 'bg-rose-500 text-white shadow-lg shadow-rose-500/20'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <div className="flex justify-end">
        <ChineseToggle
          showChinese={showChinese}
          onToggle={() => setShowChinese(!showChinese)}
        />
      </div>

      <AnimatePresence mode="popLayout">
        {compatFiltered.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="py-12 text-center text-xs italic text-slate-500"
          >
            No {filter} mechanisms found for this pair.
          </motion.div>
        ) : (
          <motion.div
            variants={pickVariants(isReplay, staggerContainer(0.08))}
            initial="hidden"
            animate="visible"
            className="space-y-3"
          >
            {compatFiltered.map((m, i) => {
              const id = m.id || String(i);
              return (
                <MechanismCard
                  key={id}
                  mechanism={m}
                  citations={citations}
                  accentColor={accent.primary}
                  showChinese={showChinese}
                  isExpanded={expandedId === id}
                  onToggle={() => toggleExpand(id)}
                  isReplay={isReplay}
                />
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
