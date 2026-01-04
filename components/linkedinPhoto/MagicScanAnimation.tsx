import React from 'react';
import { cn } from '@/lib/utils';

/**
 * MagicScanAnimation: A glowing vertical scanning bar that animates across an image.
 * Called from: Page.tsx during photo analysis
 * Why: Creates "AI Analysis" effect that adds perceived value during processing time.
 */

interface MagicScanAnimationProps {
    isActive: boolean;
    className?: string;
}

export const MagicScanAnimation: React.FC<MagicScanAnimationProps> = ({
    isActive,
    className,
}) => {
    if (!isActive) return null;

    return (
        <div
            className={cn(
                'absolute inset-0 overflow-hidden rounded-xl pointer-events-none',
                className
            )}
        >
            {/* Scanning bar */}
            <div
                className="absolute top-0 bottom-0 w-1 animate-scan-horizontal"
                style={{
                    background:
                        'linear-gradient(180deg, transparent 0%, rgba(212, 175, 55, 0.8) 20%, rgba(212, 175, 55, 1) 50%, rgba(212, 175, 55, 0.8) 80%, transparent 100%)',
                    boxShadow:
                        '0 0 20px 8px rgba(212, 175, 55, 0.4), 0 0 40px 16px rgba(212, 175, 55, 0.2)',
                }}
            />
            {/* Overlay glow */}
            <div
                className="absolute inset-0 animate-pulse-slow"
                style={{
                    background:
                        'radial-gradient(ellipse at center, rgba(212, 175, 55, 0.1) 0%, transparent 70%)',
                }}
            />
            {/* Corner accents */}
            <div className="absolute top-2 left-2 w-6 h-6 border-l-2 border-t-2 border-amber-400/60" />
            <div className="absolute top-2 right-2 w-6 h-6 border-r-2 border-t-2 border-amber-400/60" />
            <div className="absolute bottom-2 left-2 w-6 h-6 border-l-2 border-b-2 border-amber-400/60" />
            <div className="absolute bottom-2 right-2 w-6 h-6 border-r-2 border-b-2 border-amber-400/60" />

            {/* Add keyframes via style tag */}
            <style>{`
        @keyframes scan-horizontal {
          0% {
            left: 0%;
            opacity: 0;
          }
          10% {
            opacity: 1;
          }
          90% {
            opacity: 1;
          }
          100% {
            left: 100%;
            opacity: 0;
          }
        }
        .animate-scan-horizontal {
          animation: scan-horizontal 2s ease-in-out infinite;
        }
        @keyframes pulse-slow {
          0%, 100% {
            opacity: 0.3;
          }
          50% {
            opacity: 0.6;
          }
        }
        .animate-pulse-slow {
          animation: pulse-slow 2s ease-in-out infinite;
        }
      `}</style>
        </div>
    );
};
