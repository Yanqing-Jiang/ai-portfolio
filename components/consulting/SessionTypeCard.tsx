import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, ChevronRight } from 'lucide-react';

interface SessionTypeCardProps {
  title: string;
  duration: '30' | '60';
  price: number;
  features: string[];
  active: boolean;
  showPrice?: boolean;
  onSelect: () => void;
}

export const SessionTypeCard: React.FC<SessionTypeCardProps> = ({
  title,
  duration,
  price,
  features,
  active,
  showPrice = true,
  onSelect,
}) => (
  <motion.div
    onClick={onSelect}
    whileHover={{ scale: 1.02 }}
    whileTap={{ scale: 0.98 }}
    className={`p-8 sm:p-10 rounded-[2rem] border transition-all cursor-pointer group relative overflow-hidden ${
      active
        ? 'bg-white/10 border-blue-500 ring-4 ring-blue-500/10'
        : 'bg-white/[0.03] border-white/10 hover:border-white/20'
    }`}
  >
    {active && (
      <div className="absolute top-4 right-4 sm:top-6 sm:right-6">
        <CheckCircle className="text-blue-500 w-7 h-7" />
      </div>
    )}
    <p className="text-sm font-bold text-blue-400 tracking-widest uppercase mb-2">
      {duration} Min Session
    </p>
    <h3 className="text-2xl sm:text-3xl font-bold mb-3">{title}</h3>
    {showPrice ? (
      <div className="text-4xl sm:text-5xl font-bold mb-8 tracking-tight">
        ${price}{' '}
        <span className="text-base sm:text-lg text-slate-500 font-normal">USD</span>
      </div>
    ) : (
      <div className="text-sm text-slate-500 mb-8">Sign in to see pricing</div>
    )}
    <ul className="space-y-3 mb-8">
      {features.map((f, i) => (
        <li key={i} className="flex items-center gap-3 text-slate-400 text-sm sm:text-base">
          <ChevronRight className="w-4 h-4 text-purple-500 flex-shrink-0" /> {f}
        </li>
      ))}
    </ul>
    <div
      className={`w-full py-3.5 rounded-2xl text-center font-bold transition-all ${
        active
          ? 'bg-blue-600 text-white'
          : 'bg-white/5 group-hover:bg-white/10 text-slate-300'
      }`}
    >
      {active ? 'Selected' : 'Choose Session'}
    </div>
  </motion.div>
);
