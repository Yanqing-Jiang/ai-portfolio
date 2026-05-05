import React from 'react';
import { motion } from 'framer-motion';
import type { ElementType } from '../../lib/fortuneTypes';
import { ELEMENT_COLORS, GLASS } from '../designTokens';
import { fadeInUp, pickVariants } from '../animations';

interface DayMasterCardProps {
  stem: string;
  element: ElementType;
  strength: 'strong' | 'moderate' | 'weak';
  description?: string;
  accentColor?: string;
  isReplay?: boolean;
}

const STRENGTH_LABELS: Record<string, { label: string; color: string }> = {
  strong: { label: 'Strong', color: 'text-green-400' },
  moderate: { label: 'Moderate', color: 'text-yellow-400' },
  weak: { label: 'Weak', color: 'text-red-400' },
};

export const DayMasterCard: React.FC<DayMasterCardProps> = ({
  stem,
  element,
  strength,
  description,
  accentColor = '#14b8a6',
  isReplay = false,
}) => {
  const ec = ELEMENT_COLORS[element] || ELEMENT_COLORS.Wood;
  const sl = STRENGTH_LABELS[strength] || STRENGTH_LABELS.moderate;

  return (
    <motion.div
      variants={pickVariants(isReplay, fadeInUp)}
      className={`${GLASS} p-4`}
    >
      <div className="flex items-center gap-3">
        <div
          className="flex h-12 w-12 items-center justify-center rounded-xl border"
          style={{
            borderColor: `${accentColor}33`,
            background: `${accentColor}0D`,
            boxShadow: `0 0 12px ${accentColor}26`,
          }}
        >
          <span className={`text-xl font-bold ${ec.text}`}>{stem}</span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-medium uppercase tracking-[0.2em] text-slate-400">
            Day Master
          </div>
          <div className={`text-sm font-semibold ${ec.text}`}>
            {/* Avoid "Yin Earth Earth" duplication: stems are emitted as
                polarity-element labels (e.g. "Yin Earth"), so if the stem
                already contains the element, just render the stem. */}
            {stem.toLowerCase().includes(element.toLowerCase()) ? stem : `${stem} ${element}`}
          </div>
          <div className={`text-[11px] ${sl.color}`}>{sl.label}</div>
        </div>
      </div>
      {description && (
        <p className="mt-2.5 text-xs leading-relaxed text-slate-300">{description}</p>
      )}
    </motion.div>
  );
};
