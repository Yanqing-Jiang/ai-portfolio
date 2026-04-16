import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import type { Pillar } from '../../lib/fortuneTypes';
import { ELEMENT_COLORS, GLASS } from '../designTokens';
import { fadeInUp, slideDown, pickVariants } from '../animations';

interface PillarCardProps {
  pillar: Pillar;
  label: string;
  isDayMaster?: boolean;
  showChinese?: boolean;
  accentColor?: string;
  isReplay?: boolean;
}

export const PillarCard: React.FC<PillarCardProps> = ({
  pillar,
  label,
  isDayMaster = false,
  showChinese = false,
  accentColor = '#14b8a6',
  isReplay = false,
}) => {
  const [showHidden, setShowHidden] = useState(false);
  const element = pillar.element || 'Wood';
  const ec = ELEMENT_COLORS[element];
  const hiddenStems = pillar.hiddenStems || [];

  return (
    <motion.div
      variants={pickVariants(isReplay, fadeInUp)}
      className={`relative ${GLASS} p-4 text-center ${isDayMaster ? 'ring-2 shadow-lg' : ''}`}
      style={isDayMaster ? {
        boxShadow: `0 0 15px ${accentColor}4D, inset 0 0 0 2px ${accentColor}99`,
        borderColor: `${accentColor}33`,
      } as React.CSSProperties : undefined}
    >
      {isDayMaster && (
        <div
          className="absolute -top-2.5 left-1/2 -translate-x-1/2 rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest"
          style={{ background: accentColor, color: '#0B1120' }}
        >
          Day Master
        </div>
      )}

      <div className="text-[10px] font-medium uppercase tracking-[0.2em] text-slate-400 mb-2">
        {label}
      </div>

      {/* Stem */}
      <div className={`text-2xl font-bold ${ec.text}`}>
        {showChinese && pillar.stemChinese ? pillar.stemChinese : pillar.stem}
      </div>

      {/* Branch */}
      <div className="text-lg text-slate-200 mt-1">
        {showChinese && pillar.branchChinese ? pillar.branchChinese : pillar.branch}
      </div>

      {/* Element badge */}
      <div className={`mt-2 inline-block rounded-full px-2.5 py-0.5 text-[10px] font-medium ${ec.bg} ${ec.text} ${ec.border} border`}>
        {element}
      </div>

      {/* Na Yin */}
      {pillar.naYin && (
        <div className="mt-1.5 text-[10px] text-slate-500 italic">
          {pillar.naYin}
        </div>
      )}

      {/* Hidden stems toggle */}
      {hiddenStems.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setShowHidden(!showHidden)}
            className="inline-flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-200 transition-colors"
          >
            Hidden
            <ChevronDown className={`w-3 h-3 transition-transform ${showHidden ? 'rotate-180' : ''}`} />
          </button>
          <AnimatePresence>
            {showHidden && (
              <motion.div
                variants={slideDown}
                initial="hidden"
                animate="visible"
                exit="hidden"
                className="mt-1.5 space-y-1 overflow-hidden"
              >
                {hiddenStems.map((hs, i) => {
                  const hec = ELEMENT_COLORS[hs.element];
                  return (
                    <div key={i} className={`text-[10px] ${hec.text}`}>
                      {hs.stem} ({hs.strength})
                    </div>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
};
