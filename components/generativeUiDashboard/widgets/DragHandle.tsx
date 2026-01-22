/**
 * DragHandle - Accessible drag affordance for reorderable widgets.
 *
 * Component: DragHandle
 * Called from: Row, Column (when reorder mode enabled)
 * Invokes: Framer Motion Reorder.Item (via parent)
 * Why: Provides visual and accessible handle for drag-and-drop reordering.
 */

import { GripVertical } from 'lucide-react';
import { useLayoutPreferences } from '../context/LayoutContext';

// ============================================================================
// Types
// ============================================================================

export interface DragHandleProps {
    /** Whether the component is currently being dragged */
    isDragging?: boolean;
    /** Optional additional class names */
    className?: string;
    /** Drag controls from Reorder.Item */
    dragControls?: any;
    /** ARIA label for accessibility */
    ariaLabel?: string;
}

// ============================================================================
// Component
// ============================================================================

export function DragHandle({
    isDragging = false,
    className = '',
    dragControls,
    ariaLabel = 'Drag to reorder',
}: DragHandleProps) {
    const { preferences } = useLayoutPreferences();

    // Only show when reorder mode is enabled
    if (!preferences.reorderModeEnabled) return null;

    return (
        <button
            className={`
                absolute -left-1 top-1/2 -translate-y-1/2 z-30
                p-1.5 rounded-lg cursor-grab
                bg-slate-800/90 border border-slate-600
                text-gray-400 hover:text-slate-300 hover:border-slate-500
                transition-colors duration-150
                ${isDragging ? 'cursor-grabbing bg-slate-600/50 border-slate-500 text-slate-300' : ''}
                ${className}
            `}
            style={{ touchAction: 'none' }}
            onPointerDown={(e) => {
                if (dragControls) {
                    dragControls.start(e);
                }
            }}
            aria-label={ariaLabel}
            aria-roledescription="draggable"
            tabIndex={0}
        >
            <GripVertical size={12} className={isDragging ? 'text-slate-300' : 'text-gray-400'} />
        </button>
    );
}

/**
 * Inline DragHandle variant for use within cards/rows.
 */
export function InlineDragHandle({
    isDragging = false,
    className = '',
    dragControls,
    ariaLabel = 'Drag to reorder',
}: DragHandleProps) {
    const { preferences } = useLayoutPreferences();

    // Only show when reorder mode is enabled
    if (!preferences.reorderModeEnabled) return null;

    return (
        <button
            className={`
                flex-shrink-0 p-1 rounded cursor-grab
                text-gray-500 hover:text-slate-300
                transition-colors duration-150
                ${isDragging ? 'cursor-grabbing text-slate-300' : ''}
                ${className}
            `}
            style={{ touchAction: 'none' }}
            onPointerDown={(e) => {
                if (dragControls) {
                    dragControls.start(e);
                }
            }}
            aria-label={ariaLabel}
            aria-roledescription="draggable"
            tabIndex={0}
        >
            <GripVertical size={16} className={isDragging ? 'text-slate-300' : 'text-gray-500'} />
        </button>
    );
}

export default DragHandle;
