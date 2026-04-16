import React from 'react';
import { Info, AlertTriangle, XCircle } from 'lucide-react';
import type { GuardrailPayload } from '../../lib/fortuneTypes';

interface GuardrailBannerProps {
  guardrail: GuardrailPayload;
}

const SEVERITY_MAP = {
  info:    { Icon: Info,            color: '#60a5fa', bg: 'rgba(96,165,250,0.06)', border: 'rgba(96,165,250,0.2)' },
  warning: { Icon: AlertTriangle,   color: '#eab308', bg: 'rgba(234,179,8,0.06)',  border: 'rgba(234,179,8,0.2)' },
  error:   { Icon: XCircle,         color: '#f87171', bg: 'rgba(248,113,113,0.06)', border: 'rgba(248,113,113,0.2)' },
} as const;

export const GuardrailBanner: React.FC<GuardrailBannerProps> = ({ guardrail }) => {
  // Backend emits `level`, frontend uses `severity` — accept both
  const severity = guardrail.severity || guardrail.level || 'info';
  const { Icon, color, bg, border } = SEVERITY_MAP[severity];

  return (
    <div
      className="flex items-start gap-3 rounded-xl border p-3"
      style={{ background: bg, borderColor: border }}
      role="status"
      aria-live="polite"
    >
      <Icon className="w-4 h-4 flex-none mt-0.5" style={{ color }} />
      <p className="text-xs leading-relaxed text-slate-300">{guardrail.message}</p>
    </div>
  );
};
