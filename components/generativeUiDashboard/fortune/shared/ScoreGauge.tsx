import React from 'react';
import { motion } from 'framer-motion';
import { scoreColor } from '../designTokens';

interface ScoreGaugeProps {
  score: number;
  label?: string;
  accentColor?: string;
  size?: number;
  strokeWidth?: number;
  isReplay?: boolean;
}

export const ScoreGauge: React.FC<ScoreGaugeProps> = ({
  score,
  label,
  accentColor,
  size = 120,
  strokeWidth = 8,
  isReplay = false,
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(Math.max(score, 0), 100) / 100;
  const offset = circumference * (1 - progress);
  const color = accentColor || (scoreColor(score).includes('green') ? '#4ade80' : scoreColor(score).includes('yellow') ? '#eab308' : '#f87171');

  return (
    <div className="relative inline-flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(51,65,85,0.4)"
          strokeWidth={strokeWidth}
        />
        {/* Score arc */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={isReplay ? offset : circumference}
          animate={{ strokeDashoffset: offset }}
          transition={isReplay ? { duration: 0 } : { duration: 1.5, ease: [0.25, 0.46, 0.45, 0.94] }}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ filter: `drop-shadow(0 0 6px ${color}66)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-white">{Math.round(score)}</span>
        {label && <span className="text-[10px] text-slate-400 mt-0.5">{label}</span>}
      </div>
    </div>
  );
};
