import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import { staggerItem, pickVariants } from '../animations';

interface ConditionCardProps {
  type: 'check' | 'warn' | 'cross';
  text: string;
  accentColor?: string;
  isReplay?: boolean;
}

const ICON_MAP = {
  check: { Icon: CheckCircle2, color: '#4ade80', bg: 'rgba(74,222,128,0.08)' },
  warn:  { Icon: AlertTriangle, color: '#eab308', bg: 'rgba(234,179,8,0.08)' },
  cross: { Icon: XCircle, color: '#f87171', bg: 'rgba(248,113,113,0.08)' },
} as const;

export const ConditionCard: React.FC<ConditionCardProps> = ({
  type,
  text,
  isReplay = false,
}) => {
  const { Icon, color, bg } = ICON_MAP[type];

  return (
    <motion.div
      variants={pickVariants(isReplay, staggerItem)}
      className="flex items-start gap-3 rounded-xl border border-white/5 p-3"
      style={{ background: bg }}
    >
      <Icon className="w-4 h-4 flex-none mt-0.5" style={{ color }} />
      <span className="text-xs leading-relaxed text-slate-200">{text}</span>
    </motion.div>
  );
};
