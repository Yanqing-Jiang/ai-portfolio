import React from 'react';
import { motion } from 'framer-motion';
import { Check, X, Eye, AlertTriangle } from 'lucide-react';
import { useComponentSwap } from '../context/ComponentSwapContext';

export function SwapPreviewOverlay({ componentId }: { componentId: string }) {
    const { commitSwap, cancelPreview, getSwapState } = useComponentSwap();
    const state = getSwapState(componentId);
    const warnings = state?.warnings || [];

    return (
        <div className="absolute inset-0 z-50 pointer-events-none flex flex-col items-end justify-start p-4">
            {/* Border effect - inset slightly to match component bounds */}
            <div className={`absolute inset-0 border-2 border-dashed rounded-xl pointer-events-none ${
                warnings.length > 0 ? 'border-amber-500/80' : 'border-emerald-400/50'
            }`} />
            
            {/* Controls - Top Right */}
            <motion.div 
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-slate-900/95 backdrop-blur-md border border-slate-700 rounded-lg p-1.5 shadow-2xl pointer-events-auto flex items-center gap-1 relative z-50"
            >
                <div className={`flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-2 ${
                    warnings.length > 0 ? 'text-amber-400' : 'text-emerald-400'
                }`}>
                    <Eye size={12} />
                    Preview
                </div>
                
                <div className="h-4 w-px bg-slate-700 mx-1" />
                
                <button 
                    onClick={(e) => {
                        e.stopPropagation();
                        commitSwap(componentId);
                    }}
                    className="flex items-center gap-1.5 text-xs font-semibold text-slate-200 hover:bg-emerald-500/20 hover:text-emerald-300 px-2 py-1 rounded-md transition-all duration-200"
                    title="Apply this view"
                >
                    <Check size={14} />
                    Apply
                </button>
                
                <button 
                    onClick={(e) => {
                        e.stopPropagation();
                        cancelPreview(componentId);
                    }}
                    className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:bg-slate-700 hover:text-white px-2 py-1 rounded-md transition-all duration-200"
                    title="Cancel preview"
                >
                    <X size={14} />
                    Cancel
                </button>
            </motion.div>

            {/* Warnings Container - Below Controls */}
            {warnings.length > 0 && (
                <motion.div
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-2 bg-amber-900/90 backdrop-blur-md border border-amber-500/50 rounded-lg p-2.5 shadow-xl pointer-events-auto max-w-[250px]"
                >
                    <div className="flex items-center gap-1.5 text-[10px] font-bold text-amber-200 mb-1 uppercase tracking-wide">
                        <AlertTriangle size={10} />
                        Data Quality Warning
                    </div>
                    <ul className="space-y-1">
                        {warnings.map((w, i) => (
                            <li key={i} className="text-[10px] text-amber-100/90 leading-tight">
                                • {w}
                            </li>
                        ))}
                    </ul>
                </motion.div>
            )}
        </div>
    );
}
