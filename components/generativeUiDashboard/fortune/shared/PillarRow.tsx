import React from 'react';
import { motion } from 'framer-motion';
import type { PillarSet } from '../../lib/fortuneTypes';
import { staggerContainer, pickVariants } from '../animations';
import { PillarCard } from './PillarCard';

const LABELS = ['Year', 'Month', 'Day', 'Hour'] as const;
const DAY_MASTER_INDEX = 2; // Day pillar is the Day Master

interface PillarRowProps {
  pillars: PillarSet;
  showChinese?: boolean;
  accentColor?: string;
  isReplay?: boolean;
}

export const PillarRow: React.FC<PillarRowProps> = ({
  pillars,
  showChinese = false,
  accentColor = '#14b8a6',
  isReplay = false,
}) => {
  const pillarArray = [pillars.year, pillars.month, pillars.day, pillars.hour].filter(Boolean);

  return (
    <motion.div
      variants={pickVariants(isReplay, staggerContainer(0.15))}
      initial="hidden"
      animate="visible"
      className="grid grid-cols-4 gap-2"
    >
      {pillarArray.map((p, i) => (
        <PillarCard
          key={LABELS[i]}
          pillar={p!}
          label={LABELS[i]}
          isDayMaster={i === DAY_MASTER_INDEX}
          showChinese={showChinese}
          accentColor={accentColor}
          isReplay={isReplay}
        />
      ))}
    </motion.div>
  );
};
