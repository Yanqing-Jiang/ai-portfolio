/**
 * LayoutSwitcher - Dropdown to switch dashboard layouts.
 *
 * Function: LayoutSwitcher
 * Called from: GenerativeUIPage.tsx
 * Invokes: sendAction from useA2UIStream via onLayoutChange prop
 * Why: Provides quick layout switching without agent involvement.
 *      Implements Approach C from layout-switching-implementation-plan.md.
 */

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export interface LayoutSwitcherProps {
    currentLayout?: string;
    surfaceId: string;
    onLayoutChange: (emphasis: string) => void;
    disabled?: boolean;
}

interface LayoutOption {
    id: string;
    label: string;
    icon: string;
    description: string;
}

const LAYOUTS: LayoutOption[] = [
    { id: 'balanced', label: 'Balanced View', icon: '⚖️', description: 'All widgets equally sized' },
    { id: 'focus_chart', label: 'Chart Focus', icon: '📈', description: 'Larger charts, compact data' },
    { id: 'focus_table', label: 'Table Focus', icon: '📋', description: 'Data table prominent' },
    { id: 'focus_news', label: 'News Focus', icon: '📰', description: 'News timeline first' },
];

/**
 * LayoutSwitcher component for quick dashboard layout changes.
 * Renders a dropdown menu with emphasis modes for the dashboard.
 */
export function LayoutSwitcher({
    currentLayout = 'balanced',
    surfaceId: _surfaceId, // Reserved for future use (e.g., surface-specific layout persistence)
    onLayoutChange,
    disabled = false,
}: LayoutSwitcherProps) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const selected = LAYOUTS.find((l) => l.id === currentLayout) || LAYOUTS[0];

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Close on escape key
    useEffect(() => {
        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setIsOpen(false);
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, []);

    const handleSelect = (layoutId: string) => {
        onLayoutChange(layoutId);
        setIsOpen(false);
    };

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                onClick={() => !disabled && setIsOpen(!isOpen)}
                disabled={disabled}
                aria-haspopup="listbox"
                aria-expanded={isOpen}
                aria-label={`Current layout: ${selected.label}. Click to change.`}
                className={`
          flex items-center gap-2 px-3 py-1.5 rounded-lg 
          bg-slate-800/60 border border-slate-700 
          transition-all duration-200
          ${disabled
                        ? 'opacity-50 cursor-not-allowed'
                        : 'hover:border-rose-500/30 hover:bg-slate-700/60 cursor-pointer'
                    }
        `}
            >
                <span className="text-base" role="img" aria-label={selected.label}>
                    {selected.icon}
                </span>
                <span className="text-sm text-slate-300 font-medium">{selected.label}</span>
                <svg
                    className={`w-4 h-4 text-slate-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden="true"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: -10, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -10, scale: 0.95 }}
                        transition={{ duration: 0.15, ease: 'easeOut' }}
                        role="listbox"
                        aria-label="Layout options"
                        className="
              absolute top-full left-0 mt-2 w-64 
              bg-slate-800/95 backdrop-blur-xl
              border border-slate-700/80 rounded-xl 
              shadow-2xl shadow-black/40 
              z-50 overflow-hidden
            "
                    >
                        {/* Header */}
                        <div className="px-4 py-2 border-b border-slate-700/50">
                            <p className="text-xs font-medium text-slate-400 uppercase tracking-wide">
                                Dashboard Layout
                            </p>
                        </div>

                        {/* Options */}
                        <div className="py-1">
                            {LAYOUTS.map((layout) => (
                                <button
                                    key={layout.id}
                                    role="option"
                                    aria-selected={layout.id === currentLayout}
                                    onClick={() => handleSelect(layout.id)}
                                    className={`
                    w-full text-left px-4 py-3 
                    transition-all duration-150
                    ${layout.id === currentLayout
                                            ? 'bg-rose-500/15 border-l-2 border-rose-500'
                                            : 'border-l-2 border-transparent hover:bg-slate-700/50'
                                        }
                  `}
                                >
                                    <div className="flex items-center gap-3">
                                        <span
                                            className="text-lg"
                                            role="img"
                                            aria-hidden="true"
                                        >
                                            {layout.icon}
                                        </span>
                                        <div>
                                            <span className={`
                        text-sm font-medium block
                        ${layout.id === currentLayout ? 'text-rose-400' : 'text-slate-200'}
                      `}>
                                                {layout.label}
                                            </span>
                                            <p className="text-xs text-slate-500 mt-0.5">
                                                {layout.description}
                                            </p>
                                        </div>
                                        {layout.id === currentLayout && (
                                            <svg
                                                className="w-4 h-4 text-rose-400 ml-auto"
                                                fill="currentColor"
                                                viewBox="0 0 20 20"
                                                aria-hidden="true"
                                            >
                                                <path
                                                    fillRule="evenodd"
                                                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                                    clipRule="evenodd"
                                                />
                                            </svg>
                                        )}
                                    </div>
                                </button>
                            ))}
                        </div>

                        {/* Footer hint */}
                        <div className="px-4 py-2 border-t border-slate-700/50 bg-slate-900/50">
                            <p className="text-[10px] text-slate-500">
                                Layout changes apply to the current dashboard
                            </p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

export default LayoutSwitcher;
