import React from 'react';
import { Button, type ButtonProps } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * HolographicButton: Premium animated button with holographic/iridescent border effect.
 * Called from: Page.tsx for the Generate button
 * Why: Creates "exclusive" premium feel that differentiates from other tools.
 */

interface HolographicButtonProps extends ButtonProps {
    shimmerSpeed?: 'slow' | 'normal' | 'fast';
}

export const HolographicButton: React.FC<HolographicButtonProps> = ({
    children,
    className,
    shimmerSpeed = 'normal',
    disabled,
    ...props
}) => {
    const speedDuration = {
        slow: '4s',
        normal: '2.5s',
        fast: '1.5s',
    }[shimmerSpeed];

    return (
        <div className="relative group">
            {/* Holographic border effect */}
            {!disabled && (
                <div
                    className="absolute -inset-0.5 rounded-lg opacity-75 group-hover:opacity-100 transition-opacity blur-sm"
                    style={{
                        background: `conic-gradient(
              from var(--shimmer-angle, 0deg),
              #D4AF37 0deg,
              #0A66C2 60deg,
              #10b981 120deg,
              #D4AF37 180deg,
              #0A66C2 240deg,
              #10b981 300deg,
              #D4AF37 360deg
            )`,
                        animation: `shimmer-rotate ${speedDuration} linear infinite`,
                    }}
                />
            )}

            {/* Button */}
            <Button
                className={cn(
                    'relative bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400',
                    'text-white font-semibold shadow-lg',
                    'transition-all duration-300',
                    !disabled && 'hover:shadow-amber-500/25 hover:shadow-xl hover:scale-[1.02]',
                    className
                )}
                disabled={disabled}
                {...props}
            >
                {children}
            </Button>

            {/* Keyframes */}
            <style>{`
        @property --shimmer-angle {
          syntax: '<angle>';
          initial-value: 0deg;
          inherits: false;
        }
        @keyframes shimmer-rotate {
          0% {
            --shimmer-angle: 0deg;
          }
          100% {
            --shimmer-angle: 360deg;
          }
        }
      `}</style>
        </div>
    );
};
