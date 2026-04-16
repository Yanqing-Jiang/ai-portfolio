import React from 'react';
import type { PairInteraction } from '../../lib/fortuneTypes';

interface ConnectionLinesProps {
  interactions: PairInteraction[];
  width?: number;
  height?: number;
}

const TYPE_STYLES: Record<string, { color: string; dash: string; label: string }> = {
  combination: { color: '#4ade80', dash: '6 4', label: '合' },
  clash:       { color: '#f87171', dash: '',    label: '冲' },
  harm:        { color: '#fb923c', dash: '3 3', label: '害' },
  support:     { color: '#60a5fa', dash: '',    label: '助' },
  punishment:  { color: '#a855f7', dash: '4 2', label: '刑' },
};

export const ConnectionLines: React.FC<ConnectionLinesProps> = ({
  interactions,
  width = 400,
  height = 120,
}) => {
  if (interactions.length === 0) return null;

  // Layout: Person A pillars on left (y-spaced), Person B on right
  const spacing = height / (interactions.length + 1);

  return (
    <div className="relative" style={{ width, height }}>
      <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height}>
        {interactions.map((inter, i) => {
          const style = TYPE_STYLES[inter.type] || TYPE_STYLES.support;
          const y = spacing * (i + 1);
          const x1 = 40;
          const x2 = width - 40;
          const cpx = width / 2;
          const cpy = y + (i % 2 === 0 ? -15 : 15);

          return (
            <g key={i}>
              <path
                d={`M ${x1} ${y} Q ${cpx} ${cpy} ${x2} ${y}`}
                fill="none"
                stroke={style.color}
                strokeWidth={1.5}
                strokeDasharray={style.dash}
                opacity={0.7}
              />
              {/* Label in the middle */}
              <text
                x={cpx}
                y={cpy}
                textAnchor="middle"
                fill={style.color}
                fontSize={10}
                fontFamily="'Noto Serif SC', serif"
              >
                {style.label}
              </text>
              {/* From label */}
              <text x={x1 - 5} y={y + 4} textAnchor="end" fill="#94a3b8" fontSize={9}>
                {inter.from}
              </text>
              {/* To label */}
              <text x={x2 + 5} y={y + 4} textAnchor="start" fill="#94a3b8" fontSize={9}>
                {inter.to}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-2">
        {Object.entries(TYPE_STYLES).map(([type, { color, label }]) => {
          if (!interactions.some((i) => i.type === type)) return null;
          return (
            <div key={type} className="flex items-center gap-1 text-[9px]">
              <div className="w-3 h-0.5 rounded-full" style={{ background: color }} />
              <span style={{ color }}>{label}</span>
              <span className="text-slate-500 capitalize">{type}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
