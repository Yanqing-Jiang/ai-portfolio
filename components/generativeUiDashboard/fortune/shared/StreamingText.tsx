import React from 'react';
import { motion } from 'framer-motion';

interface StreamingTextProps {
  text: string;
  isStreaming?: boolean;
  isReplay?: boolean;
  cursorColor?: string;
  className?: string;
}

export const StreamingText: React.FC<StreamingTextProps> = ({
  text,
  isStreaming = false,
  isReplay = false,
  cursorColor = '#14b8a6',
  className = '',
}) => {
  return (
    <div className={`text-sm leading-relaxed text-slate-200 ${className}`} aria-live="polite">
      {text}
      {isStreaming && !isReplay && (
        <motion.span
          className="inline-block w-0.5 h-4 ml-0.5 align-text-bottom rounded-full"
          style={{ background: cursorColor }}
          animate={{ opacity: [1, 0, 1] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
        />
      )}
    </div>
  );
};
