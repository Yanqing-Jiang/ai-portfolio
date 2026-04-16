import React from 'react';
import { motion } from 'framer-motion';

interface DualRingGaugeProps {
  score: number;
  personAName?: string;
  personBName?: string;
  accentColor?: string;
  size?: number;
  isReplay?: boolean;
}

export const DualRingGauge: React.FC<DualRingGaugeProps> = ({
  score,
  personAName = 'Person A',
  personBName = 'Person B',
  accentColor = '#f43f5e',
  size = 160,
  isReplay = false,
}) => {
  const strokeWidth = 10;
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(Math.max(score, 0), 100) / 100;
  const offset = circumference * (1 - progress);

  // Inner ring (decorative)
  const innerRadius = radius - 18;
  const innerCircumference = 2 * Math.PI * innerRadius;

  return (
    <div className="relative inline-flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Outer bg ring */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="rgba(51,65,85,0.3)" strokeWidth={strokeWidth}
        />
        {/* Outer score arc */}
        <motion.circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={accentColor} strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={isReplay ? offset : circumference}
          animate={{ strokeDashoffset: offset }}
          transition={isReplay ? { duration: 0 } : { duration: 1.8, ease: [0.25, 0.46, 0.45, 0.94] }}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ filter: `drop-shadow(0 0 8px ${accentColor}66)` }}
        />
        {/* Inner decorative ring */}
        <circle
          cx={size / 2} cy={size / 2} r={innerRadius}
          fill="none" stroke={`${accentColor}1A`} strokeWidth={4}
          strokeDasharray={`${innerCircumference * 0.05} ${innerCircumference * 0.05}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold text-white">{Math.round(score)}</span>
        <span className="text-[10px] text-slate-400 mt-0.5">Harmony</span>
      </div>
      {/* Names */}
      <div className="flex items-center gap-3 mt-2 text-[11px]">
        <span style={{ color: accentColor }}>{personAName}</span>
        <span className="text-slate-600">×</span>
        <span className="text-slate-300">{personBName}</span>
      </div>
    </div>
  );
};
