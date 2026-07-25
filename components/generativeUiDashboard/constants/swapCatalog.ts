/**
 * SwapCatalog - Metadata registry for component swapping.
 *
 * Module: constants/swapCatalog
 * Called from: ComponentSwapContext, SwapButton, ComponentActionMenu
 * Invokes: None (data only)
 * Why: Centralizes swap configuration for universal component swapping feature.
 */

// ============================================================================
// Types
// ============================================================================

export type SwapMode = 'client' | 'server';

export interface SwapTarget {
    /** Target component type */
    targetType: string;
    /** Mode: 'client' = instant swap, 'server' = backend data transform */
    mode: SwapMode;
    /** Display label */
    label: string;
    /** Icon for UI */
    icon: string;
    /** Description shown in menu */
    description?: string;
    /** Tags for filtering/grouping */
    tags?: string[];
}

export interface SwapCatalogEntry {
    /** Available swap targets */
    targets: SwapTarget[];
    /** Display label for this component type */
    label: string;
    /** Icon for this component type */
    icon: string;
    /** Whether split mode is available */
    canSplit?: boolean;
    /** Components to create when splitting */
    splitInto?: string[];
}

// ============================================================================
// Swap Catalog
// ============================================================================

export const SWAP_CATALOG: Record<string, SwapCatalogEntry> = {
    // Time-series visualizations
    PriceChart: {
        label: 'Price Chart',
        icon: '📈',
        targets: [
            {
                targetType: 'MetricChart',
                mode: 'client',
                label: 'Metric Chart',
                icon: '📊',
                description: 'Switch to bar/line chart view',
                tags: ['chart', 'visualization'],
            },
            {
                targetType: 'DataTable',
                mode: 'server',
                label: 'Data Table',
                icon: '📋',
                description: 'View as tabular data',
                tags: ['table', 'data'],
            },
        ],
    },

    MetricChart: {
        label: 'Metric Chart',
        icon: '📊',
        targets: [
            {
                targetType: 'PriceChart',
                mode: 'client',
                label: 'Price Chart',
                icon: '📈',
                description: 'Switch to candlestick/price view',
                tags: ['chart', 'visualization'],
            },
            {
                targetType: 'DataTable',
                mode: 'server',
                label: 'Data Table',
                icon: '📋',
                description: 'View as tabular data',
                tags: ['table', 'data'],
            },
        ],
    },

    // Tabular data
    DataTable: {
        label: 'Data Table',
        icon: '📋',
        targets: [
            {
                targetType: 'MetricChart',
                mode: 'server',
                label: 'Metric Chart',
                icon: '📊',
                description: 'Visualize as chart',
                tags: ['chart', 'visualization'],
            },
            {
                targetType: 'CorrelationMatrix',
                mode: 'client',
                label: 'Correlation Matrix',
                icon: '🔗',
                description: 'Show correlation heatmap',
                tags: ['matrix', 'analysis'],
            },
        ],
    },

    CorrelationMatrix: {
        label: 'Correlation Matrix',
        icon: '🔗',
        targets: [
            {
                targetType: 'DataTable',
                mode: 'client',
                label: 'Data Table',
                icon: '📋',
                description: 'View as tabular data',
                tags: ['table', 'data'],
            },
        ],
    },

    // Narrative/explanation
    ExplainMovePanel: {
        label: 'AI Explanation',
        icon: '💡',
        targets: [
            {
                targetType: 'NewsTimeline',
                mode: 'client',
                label: 'News Timeline',
                icon: '📰',
                description: 'View related news events',
                tags: ['news', 'timeline'],
            },
            {
                targetType: 'SummaryCard',
                mode: 'server',
                label: 'Summary Card',
                icon: '🎯',
                description: 'Condensed key insights',
                tags: ['summary', 'compact'],
            },
        ],
    },

    NewsTimeline: {
        label: 'News Timeline',
        icon: '📰',
        targets: [
            {
                targetType: 'ExplainMovePanel',
                mode: 'client',
                label: 'AI Explanation',
                icon: '💡',
                description: 'View AI analysis',
                tags: ['ai', 'analysis'],
            },
        ],
    },

    // KPI cards
    KpiCard: {
        label: 'KPI Card',
        icon: '🎯',
        targets: [
            {
                targetType: 'MetricChart',
                mode: 'server',
                label: 'Metric Chart',
                icon: '📊',
                description: 'View historical trend',
                tags: ['chart', 'trend'],
            },
        ],
    },

    // Peer comparison - NEW: extended swap options
    PeerComparePanel: {
        label: 'Peer Comparison',
        icon: '⚖️',
        canSplit: true,
        splitInto: ['MetricChart', 'DataTable', 'ExplainMovePanel'],
        targets: [
            {
                targetType: 'DataTable',
                mode: 'server',
                label: 'Data Table',
                icon: '📋',
                description: 'View raw comparison data',
                tags: ['table', 'data'],
            },
            {
                targetType: 'MetricChart',
                mode: 'server',
                label: 'Metric Chart',
                icon: '📊',
                description: 'Chart-focused comparison',
                tags: ['chart', 'visualization'],
            },
            {
                targetType: 'SplitView',
                mode: 'server',
                label: 'Split into Components',
                icon: '🔀',
                description: 'Break into separate chart, table, insight panels',
                tags: ['split', 'decompose'],
            },
        ],
    },
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get swap options for a component type from the catalog.
 */
export function getSwapOptionsFromCatalog(componentType: string): SwapTarget[] {
    return SWAP_CATALOG[componentType]?.targets || [];
}

/**
 * Check if a swap requires backend transformation.
 */
export function requiresServerSwap(fromType: string, toType: string): boolean {
    const targets = getSwapOptionsFromCatalog(fromType);
    const target = targets.find(t => t.targetType === toType);
    return target?.mode === 'server';
}

/**
 * Check if a component type can be split into multiple components.
 */
export function canSplit(componentType: string): boolean {
    return SWAP_CATALOG[componentType]?.canSplit ?? false;
}

/**
 * Get icon for a component type.
 */
export function getComponentIcon(componentType: string): string {
    return SWAP_CATALOG[componentType]?.icon || '📦';
}

/**
 * Get label for a component type.
 */
export function getComponentLabel(componentType: string): string {
    return SWAP_CATALOG[componentType]?.label || componentType;
}

/**
 * Check if swap from source to target is valid.
 */
export function isValidSwap(fromType: string, toType: string): boolean {
    const targets = getSwapOptionsFromCatalog(fromType);
    return targets.some(t => t.targetType === toType);
}

export default SWAP_CATALOG;
