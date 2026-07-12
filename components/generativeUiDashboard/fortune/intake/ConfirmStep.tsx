/**
 * Shared confirm / recap step shell for fortune intake wizards.
 * Wizards keep function-specific CTAs via `children` or `cta`.
 */
import React from 'react';

export interface ConfirmRecapRow {
  label: string;
  value: string;
}

export interface ConfirmStepProps {
  title?: string;
  subtitle?: string;
  rows?: ConfirmRecapRow[];
  /** Optional custom content above the CTA (e.g. synastry preview, question card). */
  children?: React.ReactNode;
  ctaLabel?: string;
  onConfirm?: () => void;
  disabled?: boolean;
  loading?: boolean;
  loadingLabel?: string;
  /** RGB triple for gradient CTA, e.g. "244, 63, 94". */
  accentRgb?: string;
  /** Override CTA style entirely when needed. */
  ctaClassName?: string;
  ctaStyle?: React.CSSProperties;
  hideDefaultCta?: boolean;
}

export const ConfirmStep: React.FC<ConfirmStepProps> = ({
  title,
  subtitle,
  rows,
  children,
  ctaLabel = 'Continue →',
  onConfirm,
  disabled = false,
  loading = false,
  loadingLabel = 'Working…',
  accentRgb = '212, 175, 55',
  ctaClassName,
  ctaStyle,
  hideDefaultCta = false,
}) => {
  return (
    <div className="flex flex-col gap-4">
      {(title || subtitle) && (
        <div className="px-1">
          {title && (
            <h3 className="text-base font-semibold text-slate-100">{title}</h3>
          )}
          {subtitle && (
            <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
          )}
        </div>
      )}

      {rows && rows.length > 0 && (
        <div
          className="rounded-2xl px-4 py-3"
          style={{
            background: 'rgba(148,163,184,0.04)',
            border: `1px solid rgba(${accentRgb},0.14)`,
          }}
        >
          {rows.map((row, i) => (
            <div
              key={`${row.label}-${i}`}
              className="flex items-baseline justify-between gap-3 py-2"
              style={{
                borderBottom:
                  i === rows.length - 1
                    ? 'none'
                    : '1px dashed rgba(148,163,184,0.12)',
              }}
            >
              <span className="shrink-0 text-[11px] uppercase tracking-wide text-slate-500">
                {row.label}
              </span>
              <span className="text-right text-sm text-slate-200">{row.value}</span>
            </div>
          ))}
        </div>
      )}

      {children}

      {!hideDefaultCta && onConfirm && (
        <button
          type="button"
          disabled={disabled || loading}
          onClick={onConfirm}
          className={
            ctaClassName ??
            'mt-1 min-h-[52px] w-full rounded-xl px-4 py-3.5 text-sm font-semibold transition-all active:scale-[0.98]'
          }
          style={
            ctaStyle ?? {
              background:
                disabled || loading
                  ? 'rgba(148, 163, 184, 0.1)'
                  : `linear-gradient(135deg, rgba(${accentRgb}, 1), rgba(${accentRgb}, 0.75))`,
              color: disabled || loading ? '#64748b' : '#fff',
              cursor: disabled || loading ? 'not-allowed' : 'pointer',
            }
          }
        >
          {loading ? loadingLabel : ctaLabel}
        </button>
      )}
    </div>
  );
};
