import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import type { ElementCounts, ElementType } from '../../lib/fortuneTypes';
import { ELEMENT_COLORS } from '../designTokens';
import { drawPath, pickVariants } from '../animations';

interface ElementRadarProps {
  scores: ElementCounts;
  dominant?: ElementType;
  weak?: ElementType;
  accentColor?: string;
  size?: number;
  secondaryScores?: ElementCounts;
  secondaryColor?: string;
  isReplay?: boolean;
}

const ELEMENTS: ElementType[] = ['Wood', 'Fire', 'Earth', 'Metal', 'Water'];
const ANGLE_OFFSET = -Math.PI / 2; // Start from top

function polarToXY(angle: number, radius: number, cx: number, cy: number): [number, number] {
  return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)];
}

export const ElementRadar: React.FC<ElementRadarProps> = ({
  scores,
  dominant,
  weak,
  accentColor = '#14b8a6',
  size = 200,
  secondaryScores,
  secondaryColor = '#f43f5e',
  isReplay = false,
}) => {
  const cx = size / 2;
  const cy = size / 2;
  const maxRadius = size * 0.4;
  const maxVal = Math.max(...Object.values(scores), 1);

  const buildPolygon = useMemo(() => {
    return (vals: ElementCounts) => {
      return ELEMENTS.map((el, i) => {
        const angle = ANGLE_OFFSET + (2 * Math.PI * i) / 5;
        const val = vals[el] || 0;
        const r = (val / maxVal) * maxRadius;
        return polarToXY(angle, r, cx, cy);
      });
    };
  }, [maxVal, maxRadius, cx, cy]);

  const primaryPoints = buildPolygon(scores);
  const primaryPath = primaryPoints.map(([x, y]) => `${x},${y}`).join(' ');

  const secondaryPath = secondaryScores
    ? buildPolygon(secondaryScores).map(([x, y]) => `${x},${y}`).join(' ')
    : null;

  // Grid rings at 25%, 50%, 75%, 100%
  const gridRings = [0.25, 0.5, 0.75, 1].map((pct) => {
    const r = pct * maxRadius;
    return ELEMENTS.map((_, i) => {
      const angle = ANGLE_OFFSET + (2 * Math.PI * i) / 5;
      return polarToXY(angle, r, cx, cy);
    }).map(([x, y]) => `${x},${y}`).join(' ');
  });

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
        {/* Grid */}
        {gridRings.map((pts, i) => (
          <polygon
            key={i}
            points={pts}
            fill="none"
            stroke="rgba(148,163,184,0.12)"
            strokeWidth={0.5}
          />
        ))}

        {/* Axis lines */}
        {ELEMENTS.map((_, i) => {
          const angle = ANGLE_OFFSET + (2 * Math.PI * i) / 5;
          const [x, y] = polarToXY(angle, maxRadius, cx, cy);
          return (
            <line
              key={i}
              x1={cx}
              y1={cy}
              x2={x}
              y2={y}
              stroke="rgba(148,163,184,0.12)"
              strokeWidth={0.5}
            />
          );
        })}

        {/* Secondary polygon (dual mode for compatibility) */}
        {secondaryPath && (
          <polygon
            points={secondaryPath}
            fill={`${secondaryColor}1A`}
            stroke={secondaryColor}
            strokeWidth={1.5}
            strokeDasharray="4 3"
            opacity={0.6}
          />
        )}

        {/* Primary polygon */}
        <motion.polygon
          points={primaryPath}
          fill={`${accentColor}26`}
          stroke={accentColor}
          strokeWidth={2}
          variants={pickVariants(isReplay, drawPath)}
          initial="hidden"
          animate="visible"
        />

        {/* Vertex dots */}
        {primaryPoints.map(([x, y], i) => {
          const el = ELEMENTS[i];
          const isDominant = el === dominant;
          const isWeak = el === weak;
          return (
            <circle
              key={el}
              cx={x}
              cy={y}
              r={isDominant ? 5 : isWeak ? 3 : 4}
              fill={ELEMENT_COLORS[el].hex}
              stroke={isDominant ? '#fff' : 'none'}
              strokeWidth={isDominant ? 1.5 : 0}
            />
          );
        })}
      </svg>

      {/* Element labels */}
      {ELEMENTS.map((el, i) => {
        const angle = ANGLE_OFFSET + (2 * Math.PI * i) / 5;
        const [x, y] = polarToXY(angle, maxRadius + 18, cx, cy);
        const isDominant = el === dominant;
        return (
          <div
            key={el}
            className={`absolute text-[10px] font-medium ${isDominant ? 'font-bold' : ''}`}
            style={{
              left: x,
              top: y,
              transform: 'translate(-50%, -50%)',
              color: ELEMENT_COLORS[el].hex,
            }}
          >
            {el}
            <span className="ml-1 text-slate-500">{scores[el]}</span>
          </div>
        );
      })}
    </div>
  );
};
