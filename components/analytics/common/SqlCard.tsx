import React from 'react';
import { motion } from 'framer-motion';
import { SqlCardProps } from '../types';

export const SqlCard: React.FC<SqlCardProps> = ({ sqlQuery }) => {
  if (!sqlQuery) return null;

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8">
      <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Generated SQL Query</h2>
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 sm:p-6 overflow-x-auto">
        <pre className="text-green-400 text-sm sm:text-base font-mono whitespace-pre-wrap">{sqlQuery}</pre>
      </div>
    </motion.div>
  );
};