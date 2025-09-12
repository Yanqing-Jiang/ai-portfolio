import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ProcessStep } from '../types';

interface ProcessPanelProps {
  steps: ProcessStep[];
  show: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
}

export const ProcessPanel: React.FC<ProcessPanelProps> = ({
  steps,
  show,
  onClose,
  title = "LangGraph Process",
  subtitle = "Real-time workflow visualization"
}) => {
  return (
    <AnimatePresence>
      {show && (
        <>
          {/* Mobile Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden"
            onClick={onClose}
          />
          {/* Panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed inset-y-0 right-0 w-full md:w-80 max-w-sm md:max-w-none bg-gray-800 md:border-l border-gray-700 shadow-2xl z-50 flex flex-col"
          >
            {/* Panel Header */}
            <div className="p-4 sm:p-6 border-b border-gray-700 flex items-center justify-between">
              <div>
                <h2 className="text-lg sm:text-xl font-semibold text-white">{title}</h2>
                <p className="text-sm text-gray-400">{subtitle}</p>
              </div>
              {/* Mobile Close Button */}
              <button 
                onClick={onClose}
                className="md:hidden p-2 hover:bg-gray-700 rounded-lg transition-colors"
              >
                <span className="w-5 h-5 text-gray-400 block">✕</span>
              </button>
            </div>
            {/* Panel Content */}
            <div className="flex-1 overflow-auto p-4 sm:p-6">
              <div className="space-y-3 sm:space-y-4">
                {steps.map((step) => (
                  <div key={step.id} className="flex items-start gap-3">
                    <div className={`w-3 h-3 rounded-full mt-1 flex-shrink-0 ${
                      step.status === 'completed' ? 'bg-green-500' :
                      step.status === 'in_progress' ? 'bg-blue-500 animate-pulse' :
                      step.status === 'error' ? 'bg-red-500' :
                      step.status === 'stopped' ? 'bg-yellow-500' :
                      'bg-gray-500'
                    }`} />
                    <div className="flex-1">
                      <div className="text-sm font-medium text-gray-200">{step.name}</div>
                      {step.thinking && step.thinking.length > 0 && (
                        <div className="text-xs text-gray-400 mt-1">
                          {step.thinking[step.thinking.length - 1]}
                        </div>
                      )}
                      {step.elapsed_ms && (
                        <div className="text-xs text-gray-500">
                          {step.elapsed_ms}ms
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};