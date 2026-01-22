/**
 * ReorderToggle - Mode toggle button for drag-and-drop reordering.
 *
 * Component: ReorderToggle
 * Called from: DashboardViewer, GenerativeUIPage
 * Invokes: useLayoutPreferences()
 * Why: Enables/disables reorder mode, essential for mobile-friendly interaction.
 */

import { GripVertical, Check } from 'lucide-react';
import { useLayoutPreferences } from '../context/LayoutContext';

// ============================================================================
// Types
// ============================================================================

export interface ReorderToggleProps {
    /** Optional additional class names */
    className?: string;
    /** Size variant */
    size?: 'sm' | 'md' | 'lg';
    /** Show label text */
    showLabel?: boolean;
}

// ============================================================================
// Component
// ============================================================================

export function ReorderToggle({
    className = '',
    size = 'md',
    showLabel = true,
}: ReorderToggleProps) {
    const { preferences, toggleReorderMode } = useLayoutPreferences();
    const isEnabled = preferences.reorderModeEnabled;

    const sizeClasses = {
        sm: 'text-xs px-2 py-1',
        md: 'text-sm px-3 py-1.5',
        lg: 'text-base px-4 py-2',
    };

    return (
        <button
            onClick={toggleReorderMode}
            className={`
                inline-flex items-center gap-2 rounded-lg
                transition-colors duration-200 font-medium
                ${sizeClasses[size]}
                ${isEnabled
                    ? 'bg-slate-600/50 border border-slate-500 text-slate-300'
                    : 'bg-slate-800/80 border border-slate-700 text-gray-400 hover:border-slate-600 hover:bg-slate-700/80'
                }
                ${className}
            `}
            aria-pressed={isEnabled}
            aria-label={isEnabled ? 'Disable reorder mode' : 'Enable reorder mode'}
        >
            {/* Icon */}
            {isEnabled ? (
                <Check size={16} className="text-slate-300" />
            ) : (
                <GripVertical size={16} className="text-gray-400" />
            )}

            {/* Label */}
            {showLabel && (
                <span>
                    {isEnabled ? 'Done Reordering' : 'Reorder Widgets'}
                </span>
            )}
        </button>
    );
}

/**
 * Compact icon-only variant for toolbar placement.
 */
export function ReorderToggleIcon({ className = '' }: { className?: string }) {
    const { preferences, toggleReorderMode } = useLayoutPreferences();
    const isEnabled = preferences.reorderModeEnabled;

    return (
        <button
            onClick={toggleReorderMode}
            className={`
                p-1.5 rounded-lg transition-colors duration-200
                ${isEnabled
                    ? 'bg-slate-600/50 border border-slate-500 text-slate-300'
                    : 'bg-slate-800/80 border border-slate-700 text-gray-400 hover:border-slate-600 hover:text-slate-300'
                }
                ${className}
            `}
            aria-pressed={isEnabled}
            aria-label={isEnabled ? 'Disable reorder mode' : 'Enable reorder mode'}
            title={isEnabled ? 'Done Reordering' : 'Reorder Widgets'}
        >
            {isEnabled ? (
                <Check size={16} className="text-slate-300" />
            ) : (
                <GripVertical size={16} className="text-gray-400" />
            )}
        </button>
    );
}

export default ReorderToggle;
