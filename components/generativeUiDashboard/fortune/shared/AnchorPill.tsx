import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import { slideDown } from '../animations';

interface AnchorPillProps {
  id: string;
  label: string;
  symbol: string;
  relevance: number;
  bullets: string[];
  accentColor: string;
  isReplay?: boolean;
}

export const AnchorPill: React.FC<AnchorPillProps> = ({
  label,
  symbol,
  relevance,
  bullets,
  accentColor,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  // Scale size based on relevance (0-1)
  const sizeClass = relevance > 0.8 ? 'px-4 py-2 text-sm' : relevance > 0.5 ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-[10px]';
  const glowOpacity = Math.round(relevance * 40);

  return (
    <div className="flex flex-col gap-1 w-full">
      <motion.button
        onClick={() => setIsOpen(!isOpen)}
        whileTap={{ scale: 0.98 }}
        className={`flex items-center gap-2 rounded-xl border transition-all duration-300 ${
          isOpen ? 'bg-white/10' : 'bg-white/5'
        }`}
        style={{
          borderColor: isOpen ? `${accentColor}80` : `${accentColor}30`,
          boxShadow: isOpen ? `0 0 15px ${accentColor}${glowOpacity}` : 'none',
        }}
      >
        <div className={`flex flex-1 items-center gap-2 ${sizeClass}`}>
          <span className="font-serif text-lg leading-none" style={{ color: accentColor }}>{symbol}</span>
          <span className="font-bold text-white/90">{label}</span>
          <div className="ml-auto flex items-center gap-1.5">
            <div className="h-1 w-8 rounded-full bg-white/10 overflow-hidden">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: `${relevance * 100}%` }}
                className="h-full" 
                style={{ backgroundColor: accentColor }}
              />
            </div>
            <ChevronDown 
              className={`h-3.5 w-3.5 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} 
              style={{ color: accentColor }}
            />
          </div>
        </div>
      </motion.button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            variants={slideDown}
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="overflow-hidden"
          >
            <div className="mx-2 mb-2 rounded-xl bg-black/20 p-3 space-y-2 border border-white/5">
              {bullets.map((bullet, i) => (
                <div key={i} className="flex gap-2">
                  <div className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ backgroundColor: accentColor }} />
                  <p className="text-[11px] leading-relaxed text-slate-300">{bullet}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
