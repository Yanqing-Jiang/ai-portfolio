import React, { useState } from 'react';
import { ClarificationOptionsProps } from '../types';

export const ClarificationOptions: React.FC<ClarificationOptionsProps> = ({ 
  clarification, 
  onSubmit, 
  disabled 
}) => {
  const [selectedValue, setSelectedValue] = useState<any>(clarification.proposed ?? clarification.default);
  const [submitting, setSubmitting] = useState(false);

  const doSubmit = async (value: any) => {
    if (submitting || disabled) return;
    setSubmitting(true);
    try {
      await onSubmit(value);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mt-3 space-y-3">
      {clarification.reason && (
        <div className="text-xs text-gray-400 bg-gray-800/50 rounded-lg px-2 py-1">
          💡 {clarification.reason}
        </div>
      )}

      <div className="space-y-2">
        {clarification.type === 'single' && (
          <div className="flex flex-wrap gap-2">
            {clarification.options.map((opt) => (
              <button
                key={opt}
                onClick={() => setSelectedValue(opt)}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  selectedValue === opt 
                    ? 'bg-blue-600 text-white hover:bg-blue-700' 
                    : 'bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        )}
        {clarification.type === 'multi' && (
          <div className="space-y-2">
            {clarification.options.map((opt) => {
              const arr: any[] = Array.isArray(selectedValue) ? selectedValue : [];
              const checked = arr.includes(opt);
              return (
                <label 
                  key={opt} 
                  className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all duration-200 ${
                    checked 
                      ? 'bg-gray-700/50 border border-gray-600' 
                      : 'bg-gray-800/30 hover:bg-gray-700/30'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      if (e.target.checked) setSelectedValue([...arr, opt]);
                      else setSelectedValue(arr.filter((v) => v !== opt));
                    }}
                    className="w-4 h-4 text-blue-600 rounded border-gray-500 focus:ring-blue-500 focus:ring-2 bg-gray-700"
                  />
                  <span className="text-sm text-gray-200">{opt}</span>
                </label>
              );
            })}
          </div>
        )}
        {clarification.type === 'free' && (
          <input
            type="text"
            value={selectedValue ?? ''}
            onChange={(e) => setSelectedValue(e.target.value)}
            className="w-full px-3 py-2 border border-gray-600 rounded-lg text-sm bg-gray-700 text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder-gray-400"
            placeholder="Type your answer..."
          />
        )}
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => doSubmit(selectedValue)}
          disabled={submitting || disabled}
          className="flex-1 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
        >
          {submitting ? (
            <div className="flex items-center justify-center gap-2">
              <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              Sending...
            </div>
          ) : (
            'Submit'
          )}
        </button>
        <button
          onClick={() => doSubmit(clarification.default)}
          disabled={submitting || disabled}
          className="px-3 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm font-medium transition-all duration-200 disabled:opacity-50"
        >
          Default
        </button>
      </div>
    </div>
  );
};