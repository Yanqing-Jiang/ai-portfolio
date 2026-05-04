import React from 'react';
import { motion } from 'framer-motion';
import { pickVariants } from '../animations';

interface VerdictBadgeProps {
  score: number;
  isReplay?: boolean;
}

export const VerdictBadge: React.FC<VerdictBadgeProps> = ({ score, isReplay = false }) => {
  let label = 'Mixed';
  let colorClass = 'text-amber-400 bg-amber-400/10 border-amber-400/20';
  
  if (score >= 65) {
    label = 'Favorable';
    colorClass = 'text-teal-400 bg-teal-400/10 border-teal-400/20';
  } else if (score < 45) {
    label = 'Unfavorable';
    colorClass = 'text-rose-400 bg-rose-400/10 border-rose-400/20';
  }

  return (
    <motion.div
      variants={pickVariants(isReplay, {
        hidden: { opacity: 0, scale: 0.9, y: 10 },
        visible: { 
          opacity: 1, 
          scale: 1, 
          y: 0, 
          transition: { type: 'spring', damping: 12, stiffness: 200 } 
        }
      })}
      initial="hidden"
      animate="visible"
      className={`inline-flex items-center px-4 py-1.5 rounded-full border text-xs font-bold tracking-widest uppercase shadow-lg shadow-black/20 ${colorClass}`}
    >
      <span className="relative flex h-2 w-2 mr-2">
        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${colorClass.split(' ')[0].replace('text-', 'bg-')}`}></span>
        <span className={`relative inline-flex rounded-full h-2 w-2 ${colorClass.split(' ')[0].replace('text-', 'bg-')}`}></span>
      </span>
      {label}
    </motion.div>
  );
};
