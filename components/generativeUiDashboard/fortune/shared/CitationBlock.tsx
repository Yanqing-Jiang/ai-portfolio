import React from 'react';
import type { Citation } from '../../lib/fortuneTypes';
import { CITATION_GOLD, OBSERVATORY_SERIF } from '../designTokens';

interface CitationBlockProps {
  citation: Citation;
  showChinese?: boolean;
}

export const CitationBlock: React.FC<CitationBlockProps> = ({
  citation,
  showChinese = true,
}) => {
  return (
    <div
      className="rounded-r-xl border-l-2 py-3 pl-4 pr-3"
      style={{
        borderColor: `${CITATION_GOLD}99`,
        background: `${CITATION_GOLD}0D`,
      }}
    >
      {/* Book source */}
      <div
        className="text-[10px] font-semibold uppercase tracking-[0.2em] mb-1.5"
        style={{ color: CITATION_GOLD }}
      >
        {citation.sourceEnglish || citation.source}
        {citation.chapter && (
          <span className="text-slate-500 ml-1.5 normal-case tracking-normal">
            · {citation.chapter}
          </span>
        )}
      </div>

      {/* Chinese quote */}
      {showChinese && (
        <p
          className="text-sm leading-relaxed text-slate-300"
          style={{ fontFamily: OBSERVATORY_SERIF }}
        >
          「{citation.quote}」
        </p>
      )}

      {/* English translation */}
      {citation.translation && (
        <p className="mt-1.5 text-xs italic leading-relaxed text-slate-400">
          {citation.translation}
        </p>
      )}

      {/* Rationale */}
      {citation.rationale && (
        <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">
          {citation.rationale}
        </p>
      )}
    </div>
  );
};
