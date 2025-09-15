import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { SqlCardProps } from '../types';

export const SqlCard: React.FC<SqlCardProps> = ({ sqlQuery, compact = false, showCopy = true }) => {
  const [copied, setCopied] = useState(false);

  if (!sqlQuery) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(sqlQuery);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy SQL:', err);
    }
  };

  if (compact) {
    return (
      <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3 overflow-x-auto">
        {showCopy && (
          <div className="flex justify-end mb-2">
            <button
              onClick={handleCopy}
              className="text-xs text-gray-400 hover:text-white transition-colors px-2 py-1 rounded bg-gray-800/50 hover:bg-gray-700/50"
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
        )}
        <pre className="text-green-400 text-xs font-mono whitespace-pre-wrap leading-relaxed">{sqlQuery}</pre>
      </div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8">
      <div className="flex items-center justify-between mb-4 sm:mb-6">
        <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white">Generated SQL Query</h2>
        {showCopy && (
          <button
            onClick={handleCopy}
            className="text-sm text-gray-400 hover:text-white transition-colors px-3 py-1 rounded bg-gray-700/50 hover:bg-gray-600/50"
          >
            {copied ? 'Copied!' : 'Copy SQL'}
          </button>
        )}
      </div>
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 sm:p-6 overflow-x-auto">
        <pre className="text-green-400 text-sm sm:text-base font-mono whitespace-pre-wrap">{sqlQuery}</pre>
      </div>
    </motion.div>
  );
};