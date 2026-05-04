import React, { useEffect, useState } from 'react';
import { motion, useSpring } from 'framer-motion';
import { ScoreGauge } from './ScoreGauge';

interface VerdictProgressiveGaugeProps {
  finalScore: number;
  streamedFraction: number; // 0 to 1
  accentColor: string;
  isReplay?: boolean;
}

export const VerdictProgressiveGauge: React.FC<VerdictProgressiveGaugeProps> = ({
  finalScore,
  streamedFraction,
  accentColor,
  isReplay = false,
}) => {
  // Use a spring for smooth score climbing
  const displayScore = useSpring(0, {
    stiffness: 60,
    damping: 20,
    restDelta: 0.001
  });

  useEffect(() => {
    if (isReplay) {
      displayScore.set(finalScore);
    } else {
      displayScore.set(finalScore * streamedFraction);
    }
  }, [finalScore, streamedFraction, isReplay, displayScore]);

  // Use state to force re-render when spring value changes
  const [currentScore, setCurrentScore] = useState(0);
  
  useEffect(() => {
    const unsubscribe = displayScore.on('change', (v) => {
      setCurrentScore(v);
    });
    return () => unsubscribe();
  }, [displayScore]);

  return (
    <div className="relative flex flex-col items-center">
      <div className="relative">
        {/* Outer glow ring */}
        <motion.div
          animate={{
            scale: [1, 1.05, 1],
            opacity: [0.3, 0.5, 0.3],
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="absolute inset-0 rounded-full blur-2xl"
          style={{ backgroundColor: `${accentColor}30` }}
        />
        
        <ScoreGauge
          score={currentScore}
          accentColor={accentColor}
          size={160}
          strokeWidth={10}
          isReplay={isReplay}
        />
      </div>
    </div>
  );
};
