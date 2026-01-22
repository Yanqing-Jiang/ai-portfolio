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
import { Scale, TrendingUp, Table2, Newspaper, ChevronDown, Check, type LucideIcon } from 'lucide-react';

export interface LayoutSwitcherProps {
    currentLayout?: string;
    surfaceId: string;
    onLayoutChange: (emphasis: string) => void;
    disabled?: boolean;
}

interface LayoutOption {
    id: string;
    label: string;
    Icon: LucideIcon;
    description: string;
}

const LAYOUTS: LayoutOption[] = [
    { id: 'balanced', label: 'Balanced View', Icon: Scale, description: 'All widgets equally sized' },
    { id: 'focus_chart', label: 'Chart Focus', Icon: TrendingUp, description: 'Larger charts, compact data' },
    { id: 'focus_table', label: 'Table Focus', Icon: Table2, description: 'Data table prominent' },
    { id: 'focus_news', label: 'News Focus', Icon: Newspaper, description: 'News timeline first' },
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
          transition-colors duration-200
          ${disabled
                        ? 'opacity-50 cursor-not-allowed'
                        : 'hover:border-slate-600 hover:bg-slate-700/60 cursor-pointer'
                    }
        `}
            >
                <selected.Icon size={16} className="text-slate-400" aria-label={selected.label} />
                <span className="text-sm text-slate-300 font-medium">{selected.label}</span>
                <ChevronDown
                    size={16}
                    className={`text-slate-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                    aria-hidden="true"
                />
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
                    transition-colors duration-150
                    ${layout.id === currentLayout
                                            ? 'bg-slate-700/50 border-l-2 border-slate-400'
                                            : 'border-l-2 border-transparent hover:bg-slate-700/50'
                                        }
                  `}
                                >
                                    <div className="flex items-center gap-3">
                                        <layout.Icon
                                            size={18}
                                            className={layout.id === currentLayout ? 'text-slate-300' : 'text-gray-400'}
                                            aria-hidden="true"
                                        />
                                        <div>
                                            <span className={`
                        text-sm font-medium block
                        ${layout.id === currentLayout ? 'text-slate-200' : 'text-slate-300'}
                      `}>
                                                {layout.label}
                                            </span>
                                            <p className="text-xs text-slate-500 mt-0.5">
                                                {layout.description}
                                            </p>
                                        </div>
                                        {layout.id === currentLayout && (
                                            <Check
                                                size={16}
                                                className="text-slate-300 ml-auto"
                                                aria-hidden="true"
                                            />
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
