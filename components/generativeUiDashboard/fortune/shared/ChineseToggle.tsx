import React from 'react';

interface ChineseToggleProps {
  showChinese: boolean;
  onToggle: () => void;
}

export const ChineseToggle: React.FC<ChineseToggleProps> = ({
  showChinese,
  onToggle,
}) => {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] font-medium tracking-wider transition-colors hover:bg-white/[0.06]"
      style={{ color: showChinese ? '#eab308' : '#94a3b8' }}
    >
      <span style={{ fontFamily: "'Noto Serif SC', serif" }}>中</span>
      <span className="text-slate-500">/</span>
      <span>EN</span>
    </button>
  );
};
