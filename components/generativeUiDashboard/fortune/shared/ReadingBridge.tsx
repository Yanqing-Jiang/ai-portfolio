import React from 'react';
import { ArrowRight, MessageCircle, Microscope } from 'lucide-react';
import type { CanonicalFortuneFunction } from '../../../../lib/fortuneRoutes';
import type { FortuneDataModel } from '../../lib/fortuneTypes';
import { FLOW_ACCENTS } from '../designTokens';

interface ReadingBridgeProps {
  functionId: CanonicalFortuneFunction;
  dataModel: FortuneDataModel | null | undefined;
  onTabChange?: (id: string) => void;
}

function factorCount(
  functionId: CanonicalFortuneFunction,
  dataModel: FortuneDataModel | null | undefined,
): number {
  if (functionId === 'wish') {
    return dataModel?.wish?.mechanisms?.length ?? dataModel?.narrative?.insights?.length ?? 0;
  }
  if (functionId === 'cycle') return dataModel?.luckCycle?.mechanisms?.length ?? 0;
  if (functionId === 'compatibility') return dataModel?.compatibility?.mechanisms?.length ?? 0;
  return dataModel?.occasion?.mechanisms?.length ?? 0;
}

function evidenceLine(
  functionId: CanonicalFortuneFunction,
  dataModel: FortuneDataModel | null | undefined,
): string {
  const count = factorCount(functionId, dataModel);
  const references = dataModel?.classics?.references?.length ?? 0;
  const parts: string[] = [];
  if (count > 0) {
    const noun = functionId === 'wish' ? 'theme' : 'chart factor';
    parts.push(`${count} ${noun}${count === 1 ? '' : 's'}`);
  }
  if (references > 0) {
    parts.push(`${references} classical source${references === 1 ? '' : 's'} cited`);
  }
  return parts.length > 0
    ? parts.join(' · ')
    : 'The chart evidence and limits are in Why.';
}

export const ReadingBridge: React.FC<ReadingBridgeProps> = ({
  functionId,
  dataModel,
  onTabChange,
}) => {
  if (!onTabChange) return null;

  const accent = FLOW_ACCENTS[
    functionId === 'cycle' ? 'luck-cycle' : functionId === 'occasion' ? 'lucky-day' : functionId
  ].primary;

  return (
    <div
      className="overflow-hidden rounded-xl border border-white/[0.07] bg-white/[0.02]"
      aria-label="Continue exploring this reading"
    >
      <button
        type="button"
        onClick={() => onTabChange('Why')}
        className="flex min-h-16 w-full items-center gap-3 border-b border-white/[0.06] px-4 py-3 text-left transition-colors hover:bg-white/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
      >
        <span
          className="flex h-8 w-8 flex-none items-center justify-center rounded-full"
          style={{ color: accent, background: `${accent}14` }}
        >
          <Microscope size={15} aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12px] font-medium text-[#f4e9c8]">Why the chart says this</span>
          <span className="mt-0.5 block truncate text-[11px] text-[#8a8f98]">
            {evidenceLine(functionId, dataModel)}
          </span>
        </span>
        <ArrowRight size={15} className="flex-none text-[#7a7f88]" aria-hidden />
      </button>

      <button
        type="button"
        onClick={() => onTabChange('Ask')}
        className="flex min-h-16 w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
      >
        <span
          className="flex h-8 w-8 flex-none items-center justify-center rounded-full"
          style={{ color: accent, background: `${accent}14` }}
        >
          <MessageCircle size={15} aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12px] font-medium text-[#f4e9c8]">Ask the chart</span>
          <span className="mt-0.5 block truncate text-[11px] text-[#8a8f98]">
            Challenge this outlook or ask what would change it.
          </span>
        </span>
        <ArrowRight size={15} className="flex-none text-[#7a7f88]" aria-hidden />
      </button>
    </div>
  );
};

export default ReadingBridge;
