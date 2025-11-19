import React from 'react';
import { WebSearchTopicProgress } from '../types';

interface WebResearchQuestionsCardProps {
  topicProgress: WebSearchTopicProgress;
}

export const WebResearchQuestionsCard: React.FC<WebResearchQuestionsCardProps> = ({
  topicProgress,
}) => {
  if (!topicProgress || !topicProgress.branches) {
    return null;
  }

  const branches = Object.values(topicProgress.branches);
  if (branches.length === 0) {
    return null;
  }

  // Helper to determine status color/text
  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'ready':
        return {
          text: 'Ready',
          className: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/40',
        };
      case 'running':
        return {
          text: 'Searching…',
          className: 'text-blue-300 bg-blue-500/10 border-blue-500/40 animate-pulse',
        };
      case 'queued':
        return {
          text: 'Queued',
          className: 'text-slate-400 bg-slate-800/50 border-slate-700/50',
        };
      case 'error':
        return {
          text: 'Error',
          className: 'text-red-300 bg-red-500/10 border-red-500/40',
        };
      default:
        return {
          text: status,
          className: 'text-slate-400 bg-slate-800/50 border-slate-700/50',
        };
    }
  };

  return (
    <div className="rounded-xl border border-slate-700/70 bg-slate-900/50 overflow-hidden p-4 space-y-3">
      <h4 className="text-sm font-semibold text-slate-100">Research Progress</h4>
      <div className="space-y-2">
        {branches.map((branch) => {
          const config = getStatusConfig(branch.status);
          const label = branch.label || branch.questionKind || branch.id;
          const displayLabel = label === 'user' ? 'User question' : label === 'industry' ? 'Industry question' : label;

          return (
            <div key={branch.id} className="flex items-center justify-between text-xs">
              <span className="text-slate-300">{displayLabel}</span>
              <span
                className={`px-2 py-0.5 rounded-full border text-[10px] font-medium uppercase tracking-wide ${config.className}`}
              >
                {config.text}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
