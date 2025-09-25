import React, { memo, useState } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { motion, AnimatePresence } from 'framer-motion';
import { ProcessStep } from '../types';
import { PulseAnimation, GlowAnimation, RippleAnimation, SuccessBurstAnimation } from './LottieAnimations';

interface ProcessNodeData {
  step: ProcessStep;
  phase: string;
  color: string;
  isActive: boolean;
  isCompleted: boolean;
  hasError: boolean;
}

interface ProcessNodeProps extends NodeProps<ProcessNodeData> {}

const nodeVariants = {
  idle: {
    scale: 1,
    boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)',
    transition: { duration: 0.3 },
  },
  activating: {
    scale: [1, 1.1, 1.05],
    boxShadow: [
      '0 4px 8px rgba(0, 0, 0, 0.1)',
      '0 8px 32px rgba(59, 130, 246, 0.4)',
      '0 6px 24px rgba(59, 130, 246, 0.3)',
    ],
    transition: {
      duration: 0.6,
      ease: 'easeOut',
    },
  },
  processing: {
    scale: 1.05,
    boxShadow: [
      '0 6px 24px rgba(59, 130, 246, 0.3)',
      '0 8px 32px rgba(59, 130, 246, 0.6)',
      '0 6px 24px rgba(59, 130, 246, 0.3)',
    ],
    transition: {
      repeat: Infinity,
      duration: 2,
      ease: 'easeInOut',
    },
  },
  completed: {
    scale: [1.05, 1],
    boxShadow: [
      '0 6px 24px rgba(59, 130, 246, 0.3)',
      '0 4px 16px rgba(34, 197, 94, 0.4)',
    ],
    transition: { duration: 0.4 },
  },
  error: {
    scale: [1, 1.1, 1],
    boxShadow: [
      '0 4px 8px rgba(0, 0, 0, 0.1)',
      '0 8px 32px rgba(239, 68, 68, 0.5)',
      '0 6px 24px rgba(239, 68, 68, 0.3)',
    ],
    transition: { duration: 0.5 },
  },
};

const ringVariants = {
  idle: { pathLength: 0, opacity: 0.3 },
  processing: {
    pathLength: [0, 0.8, 0.9, 0.8],
    opacity: [0.3, 0.8, 1, 0.8],
    transition: {
      repeat: Infinity,
      duration: 2,
      ease: 'easeInOut',
    },
  },
  completed: { pathLength: 1, opacity: 1 },
};

export const ProcessNode = memo<ProcessNodeProps>(({ data, selected }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const { step, phase, color, isActive, isCompleted, hasError } = data;
  const details = step.details ?? {};
  const decisionLog = step.thinking ?? [];
  const canExpand = Object.keys(details).length > 0 || decisionLog.length > 0;

  let animationState: keyof typeof nodeVariants = 'idle';
  if (hasError) {
    animationState = 'error';
  } else if (isCompleted) {
    animationState = 'completed';
  } else if (isActive) {
    animationState = 'processing';
  }

  const confidence = details.confidence;
  const confidencePercentage = typeof confidence === 'number' ? Math.round(confidence * 100) : null;

  const toggleExpand = () => {
    if (!canExpand) {
      return;
    }
    setIsExpanded((prev) => !prev);
  };

  const statusLabel = hasError ? 'ERR' : isCompleted ? 'DONE' : isActive ? 'RUN' : 'PEND';

  return (
    <>
      <Handle type="target" position={Position.Top} />

      <motion.div
        variants={nodeVariants}
        animate={animationState}
        className={`
          relative rounded-xl p-4 min-w-[220px] overflow-hidden
          ${canExpand ? 'cursor-pointer' : 'cursor-default'}
          ${selected ? 'border-blue-400' : 'border-gray-600'}
          ${hasError ?
            'border-red-500 bg-gradient-to-br from-red-900/30 via-gray-800 to-gray-900 border-2' :
            isActive ?
            'border-blue-400 bg-gradient-to-br from-blue-900/40 via-gray-800 to-gray-900 border-2' :
            isCompleted ?
            'border-green-400 bg-gradient-to-br from-emerald-900/30 via-gray-800 to-gray-900 border-2' :
            'border-gray-600 bg-gradient-to-br from-gray-800 to-gray-900 border backdrop-blur-sm'
          }
        `}
        onClick={toggleExpand}
        whileHover={canExpand ? { scale: 1.02, y: -2 } : undefined}
        style={{
          boxShadow: isActive ? `0 8px 32px ${color}40, 0 0 0 1px ${color}20` :
                     isCompleted ? '0 8px 32px rgba(34, 197, 94, 0.3), 0 0 0 1px rgba(34, 197, 94, 0.2)' :
                     hasError ? '0 8px 32px rgba(239, 68, 68, 0.3), 0 0 0 1px rgba(239, 68, 68, 0.2)' :
                     'none'
        }}
      >
        {isActive && (
          <div className="absolute inset-0 pointer-events-none">
            {/* Enhanced multi-layer animations */}
            <PulseAnimation color={color} size={220} speed={0.8} className="absolute -inset-2" />
            <GlowAnimation
              color={color}
              size={240}
              speed={1.2}
              intensity="medium"
              className="absolute -inset-4"
            />
            <RippleAnimation color={color} size={180} speed={1.5} className="absolute inset-6" />

            {/* Particle flow effect */}
            <div className="absolute inset-0">
              {[...Array(6)].map((_, i) => (
                <motion.div
                  key={i}
                  className="absolute w-1 h-1 bg-white rounded-full opacity-60"
                  animate={{
                    x: [0, Math.cos(i * 60 * Math.PI / 180) * 60, Math.cos(i * 60 * Math.PI / 180) * 100],
                    y: [0, Math.sin(i * 60 * Math.PI / 180) * 60, Math.sin(i * 60 * Math.PI / 180) * 100],
                    opacity: [0, 0.8, 0],
                    scale: [0, 1, 0]
                  }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                    delay: i * 0.3,
                    ease: "easeOut"
                  }}
                  style={{
                    left: '50%',
                    top: '50%',
                    transform: 'translate(-50%, -50%)'
                  }}
                />
              ))}
            </div>

            {/* Neural network connections */}
            <svg className="absolute inset-0 w-full h-full" viewBox="0 0 220 220">
              {[...Array(4)].map((_, i) => (
                <motion.path
                  key={i}
                  d={`M${110 + Math.cos(i * 90 * Math.PI / 180) * 50} ${110 + Math.sin(i * 90 * Math.PI / 180) * 50} L${110 + Math.cos(i * 90 * Math.PI / 180) * 80} ${110 + Math.sin(i * 90 * Math.PI / 180) * 80}`}
                  stroke={color}
                  strokeWidth="2"
                  strokeLinecap="round"
                  opacity="0.6"
                  animate={{
                    pathLength: [0, 1, 0],
                    opacity: [0.3, 0.8, 0.3]
                  }}
                  transition={{
                    duration: 1.5,
                    repeat: Infinity,
                    delay: i * 0.2,
                    ease: "easeInOut"
                  }}
                />
              ))}
            </svg>
          </div>
        )}

        {hasError ? null : isCompleted ? (
          <div className="absolute -top-4 -right-4 pointer-events-none">
            <SuccessBurstAnimation color="#10b981" size={40} className="animate-pulse" />
          </div>
        ) : null}

        {(isActive || isCompleted) && (
          <div className="absolute -top-2 -left-2 w-10 h-10 z-10">
            <svg className="w-10 h-10 transform -rotate-90" viewBox="0 0 40 40">
              {/* Background circle */}
              <circle cx="20" cy="20" r="16" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="2" />

              {/* Animated progress ring */}
              <motion.circle
                cx="20"
                cy="20"
                r="16"
                fill="none"
                stroke={isCompleted ? '#10b981' : color}
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeDasharray="100.53"
                variants={ringVariants}
                animate={isActive ? 'processing' : 'completed'}
                filter={`drop-shadow(0 0 4px ${isCompleted ? '#10b981' : color}40)`}
              />

              {/* Inner pulsing dot for active state */}
              {isActive && (
                <motion.circle
                  cx="20"
                  cy="20"
                  r="3"
                  fill={color}
                  animate={{
                    r: [3, 5, 3],
                    opacity: [0.8, 0.4, 0.8]
                  }}
                  transition={{
                    duration: 1.5,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                />
              )}

              {/* Success checkmark */}
              {isCompleted && (
                <motion.path
                  d="M14 20l3 3 6-6"
                  fill="none"
                  stroke="#ffffff"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 0.5, delay: 0.3 }}
                />
              )}
            </svg>
          </div>
        )}

        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <motion.span
                className={`
                  text-xs font-bold uppercase tracking-wider px-2 py-1 rounded-full
                  ${hasError ? 'bg-red-500/20 text-red-300 border border-red-500/30' :
                    isCompleted ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' :
                    isActive ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
                    'bg-gray-500/20 text-gray-300 border border-gray-500/30'
                  }
                `}
                animate={isActive ? {
                  boxShadow: [`0 0 0 0 ${color}40`, `0 0 0 4px ${color}20`, `0 0 0 0 ${color}40`]
                } : {}}
                transition={isActive ? {
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut"
                } : {}}
              >
                {statusLabel}
              </motion.span>
              <h3 className="text-sm font-semibold text-white truncate flex-1">{step.name}</h3>
            </div>

            <div className="flex items-center gap-2 mb-3">
              <motion.span
                className="px-3 py-1 text-xs rounded-full text-white font-medium backdrop-blur-sm"
                style={{
                  backgroundColor: `${color}40`,
                  border: `1px solid ${color}60`,
                  boxShadow: `0 2px 8px ${color}20`
                }}
                animate={isActive ? {
                  scale: [1, 1.05, 1],
                  boxShadow: [`0 2px 8px ${color}20`, `0 4px 16px ${color}40`, `0 2px 8px ${color}20`]
                } : {}}
                transition={isActive ? {
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut"
                } : {}}
              >
                {phase}
              </motion.span>
              {confidencePercentage !== null && (
                <motion.div className="flex items-center gap-1">
                  <span className="text-xs text-gray-400">{confidencePercentage}%</span>
                  <div className="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${confidencePercentage}%` }}
                      transition={{ duration: 1, delay: 0.5, ease: "easeOut" }}
                    />
                  </div>
                </motion.div>
              )}
            </div>

            {decisionLog.length > 0 && (
              <p className="text-xs text-gray-300 mb-2 line-clamp-2">
                {decisionLog[decisionLog.length - 1]}
              </p>
            )}

            {step.elapsed_ms && (
              <div className="text-xs text-gray-400">{step.elapsed_ms}ms</div>
            )}
          </div>

          {canExpand && (
            <motion.div
              className="text-gray-400 ml-2"
              animate={{ rotate: isExpanded ? 180 : 0 }}
              transition={{ duration: 0.3 }}
            >
              {isExpanded ? 'v' : '>'}
            </motion.div>
          )}
        </div>

        <AnimatePresence>
          {isExpanded && canExpand && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className="mt-4 pt-4 border-t border-gray-600 overflow-hidden"
            >
              <div className="space-y-3">
                {decisionLog.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-blue-300 mb-1">Decision Log</h4>
                    <ul className="space-y-1 text-xs text-gray-200">
                      {decisionLog.slice(-6).map((entry, idx) => (
                        <li key={`${step.id}-decision-${idx}`} className="flex items-start gap-2">
                          <span className="mt-0.5 text-blue-400">-</span>
                          <span className="flex-1 break-words">{entry}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {details.plan && (
                  <div>
                    <h4 className="text-xs font-medium text-purple-300 mb-1">Plan</h4>
                    <pre className="text-xs bg-gray-900 p-2 rounded border border-gray-600 overflow-x-auto max-h-24">
                      <code className="text-purple-200">{JSON.stringify(details.plan, null, 2)}</code>
                    </pre>
                  </div>
                )}

                {details.result && (
                  <div>
                    <h4 className="text-xs font-medium text-emerald-300 mb-1">Result</h4>
                    <pre className="text-xs bg-gray-900 p-2 rounded border border-gray-600 overflow-x-auto max-h-24">
                      <code className="text-emerald-200">{typeof details.result === 'string' ? details.result : JSON.stringify(details.result, null, 2)}</code>
                    </pre>
                  </div>
                )}

                {(details.sql || details.sql_executed) && (
                  <div>
                    <h4 className="text-xs font-medium text-green-300 mb-1">SQL</h4>
                    <pre className="text-xs bg-gray-900 p-2 rounded border border-gray-600 overflow-x-auto max-h-20">
                      <code className="text-green-200">{details.sql || details.sql_executed}</code>
                    </pre>
                  </div>
                )}

                {(details.reasoning || details.strategy) && (
                  <div>
                    <h4 className="text-xs font-medium text-purple-300 mb-1">Reasoning</h4>
                    <p className="text-xs text-gray-200">{details.reasoning || details.strategy}</p>
                  </div>
                )}

                {(details.sample_data || details.sampleData) && (
                  <div>
                    <h4 className="text-xs font-medium text-yellow-300 mb-1">
                      Data ({details.row_count || details.rowCount || 'N/A'} rows)
                    </h4>
                    <pre className="text-xs bg-gray-900 p-2 rounded border border-gray-600 overflow-x-auto max-h-20">
                      <code className="text-yellow-200">{JSON.stringify((details.sample_data || details.sampleData)?.slice(0, 2), null, 2)}</code>
                    </pre>
                  </div>
                )}

                {details.error && (
                  <div>
                    <h4 className="text-xs font-medium text-red-300 mb-1">Error</h4>
                    <p className="text-xs text-red-200 bg-red-900/20 p-2 rounded border border-red-600">{details.error}</p>
                  </div>
                )}

                <div className="pt-2 border-t border-gray-700">
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {details.duration_ms && (
                      <div className="text-gray-400">
                        Duration: <span className="text-gray-200">{details.duration_ms}ms</span>
                      </div>
                    )}
                    {details.confidence && (
                      <div className="text-gray-400">
                        Confidence: <span className="text-gray-200">{Math.round(details.confidence * 100)}%</span>
                      </div>
                    )}
                    {details.tool && (
                      <div className="text-gray-400">
                        Tool: <span className="text-gray-200">{details.tool}</span>
                      </div>
                    )}
                    {details.intent_key && (
                      <div className="text-gray-400">
                        Intent: <span className="text-gray-200">{details.intent_key}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      <Handle type="source" position={Position.Bottom} />
    </>
  );
});

ProcessNode.displayName = 'ProcessNode';
