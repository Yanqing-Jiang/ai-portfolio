import React, { useMemo, useState } from 'react';
import { ClarificationOptionsProps } from '../types';

const hasValue = (value: any) => {
  if (value === null || value === undefined) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'string') return value.trim().length > 0;
  return true;
};

export const ClarificationOptions: React.FC<ClarificationOptionsProps> = ({
  clarification,
  onSubmit,
  disabled,
}) => {
  const allowCustom = clarification.allow_custom !== false;
  const initialValue = useMemo(() => {
    const proposal = clarification.proposed ?? clarification.default;
    if (proposal !== undefined && proposal !== null) {
      return proposal;
    }
    if (clarification.type === 'single' && clarification.options.length === 1) {
      return clarification.options[0];
    }
    return clarification.type === 'multi' ? [] : '';
  }, [clarification]);

  const [selectedValue, setSelectedValue] = useState<any>(initialValue);
  const [customValue, setCustomValue] = useState<string>(
    typeof initialValue === 'string' ? initialValue : '',
  );
  const [submitting, setSubmitting] = useState(false);

  const doSubmit = async (value: any) => {
    if (submitting || disabled || !hasValue(value)) return;
    setSubmitting(true);
    try {
      await onSubmit(value);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleOption = (opt: string) => {
    if (clarification.type === 'multi') {
      const arr: string[] = Array.isArray(selectedValue) ? selectedValue : [];
      if (arr.includes(opt)) {
        const next = arr.filter((entry) => entry !== opt);
        setSelectedValue(next);
      } else {
        setSelectedValue([...arr, opt]);
      }
    } else {
      setSelectedValue(opt);
      setCustomValue(opt);
    }
  };

  const handleCustomChange = (nextValue: string) => {
    setCustomValue(nextValue);
    setSelectedValue(nextValue);
  };

  const submitDisabled =
    submitting ||
    disabled ||
    !hasValue(selectedValue) ||
    (Array.isArray(selectedValue) && selectedValue.length === 0);

  return (
    <div className="mt-3 space-y-4 rounded-xl border border-blue-500/30 bg-gray-900/60 p-4 shadow-lg">
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-blue-200">
          <span className="rounded-full border border-blue-500/50 px-2 py-0.5 font-semibold">
            {clarification.slot.replace(/_/g, ' ')}
          </span>
          <span className="text-blue-300/80">Additional detail required</span>
        </div>
        <div className="text-sm text-gray-100">{clarification.question}</div>
        {clarification.reason && (
          <div className="mt-2 flex items-start gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 px-3 py-2 text-xs text-blue-100">
            <span aria-hidden="true" className="pt-0.5">
              💡
            </span>
            <span>{clarification.reason}</span>
          </div>
        )}
      </div>

      <div className="space-y-3">
        {clarification.type === 'single' && clarification.options.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {clarification.options.map((opt) => {
              const isSelected = selectedValue === opt;
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => toggleOption(opt)}
                  className={`rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 ${
                    isSelected
                      ? 'bg-blue-600 text-white shadow-md shadow-blue-900/40'
                      : 'border border-gray-600/70 bg-gray-800/60 text-gray-200 hover:border-blue-500/40 hover:text-white'
                  }`}
                >
                  {opt}
                </button>
              );
            })}
          </div>
        )}

        {clarification.type === 'multi' && clarification.options.length > 0 && (
          <div className="space-y-2">
            {clarification.options.map((opt) => {
              const arr: string[] = Array.isArray(selectedValue) ? selectedValue : [];
              const checked = arr.includes(opt);
              return (
                <label
                  key={opt}
                  className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-all duration-200 ${
                    checked
                      ? 'border-blue-500/50 bg-blue-500/10 text-blue-100'
                      : 'border-gray-600/70 bg-gray-800/50 text-gray-200 hover:border-blue-500/30'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleOption(opt)}
                    className="h-4 w-4 rounded border-gray-500 bg-gray-700 text-blue-500 focus:ring-blue-400"
                  />
                  <span>{opt}</span>
                </label>
              );
            })}
          </div>
        )}

        {clarification.type === 'free' && (
          <input
            type="text"
            value={typeof selectedValue === 'string' ? selectedValue : customValue}
            onChange={(e) => handleCustomChange(e.target.value)}
            className="w-full rounded-lg border border-gray-600/60 bg-gray-800/60 px-3 py-2 text-sm text-gray-100 placeholder-gray-400 focus:border-blue-500/60 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            placeholder="Type your answer..."
          />
        )}

        {clarification.type === 'single' && allowCustom && (
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-300">Custom value</label>
            <input
              type="text"
              value={customValue}
              onChange={(e) => handleCustomChange(e.target.value)}
              placeholder="Enter a custom value"
              className="w-full rounded-lg border border-gray-600/60 bg-gray-800/60 px-3 py-2 text-sm text-gray-100 placeholder-gray-400 focus:border-blue-500/60 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            />
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => doSubmit(selectedValue)}
          disabled={submitDisabled}
          className="flex-1 min-w-[120px] rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow-md shadow-blue-900/40 transition-all duration-200 hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? (
            <span className="flex items-center justify-center gap-2">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              Sending…
            </span>
          ) : (
            'Submit'
          )}
        </button>
        {hasValue(clarification.default) && (
          <button
            type="button"
            onClick={() => doSubmit(clarification.default)}
            disabled={submitting || disabled}
            className="rounded-lg border border-gray-600/70 bg-gray-800/60 px-3 py-2 text-sm font-semibold text-gray-200 transition-all duration-200 hover:border-blue-500/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            Use Default
          </button>
        )}
      </div>
    </div>
  );
};
