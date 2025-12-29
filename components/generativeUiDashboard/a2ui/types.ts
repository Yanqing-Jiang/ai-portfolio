/**
 * A2UI TypeScript Types
 *
 * Type definitions matching the A2UI v0.8 protocol specification.
 * @see https://a2ui.org/specification/v0.8-a2ui/
 */

// ============================================================================
// Bound Value Types
// ============================================================================

export interface BoundString {
    literalString?: string;
    path?: string; // JSON Pointer, e.g., "/data/title"
}

export interface BoundNumber {
    literalNumber?: number;
    path?: string;
}

export interface BoundBoolean {
    literalBoolean?: boolean;
    path?: string;
}

export interface BoundArray {
    literalArray?: unknown[];
    path?: string;
}

export type BoundValue = BoundString | BoundNumber | BoundBoolean | BoundArray;

// ============================================================================
// Data Model Types
// ============================================================================

export interface DataEntry {
    key: string;
    valueString?: string;
    valueNumber?: number;
    valueBoolean?: boolean;
    valueMap?: DataEntry[];
    valueArray?: unknown[];
}

export type DataModel = Record<string, unknown>;

// ============================================================================
// Component Types
// ============================================================================

export interface ChildrenExplicitList {
    explicitList: string[];
}

export interface ChildrenTemplate {
    template: string;
    dataPath: string;
}

export type Children = ChildrenExplicitList | ChildrenTemplate;

export interface ActionContext {
    key: string;
    value: BoundValue;
}

export interface ComponentAction {
    name: string;
    context?: ActionContext[];
}

// ============================================================================
// Standard Components
// ============================================================================

export interface TextProps {
    text: BoundString;
    usageHint?: 'h1' | 'h2' | 'h3' | 'body' | 'caption';
}

export interface RowProps {
    children: Children;
    alignment?: 'start' | 'center' | 'end' | 'spaceBetween' | 'spaceAround';
}

export interface ColumnProps {
    children: Children;
    alignment?: 'start' | 'center' | 'end' | 'stretch';
}

export interface CardProps {
    child: string;
}

export interface ButtonProps {
    label: BoundString;
    action: ComponentAction;
    variant?: 'primary' | 'secondary' | 'text';
}

export interface ImageProps {
    url: BoundString;
    alt?: BoundString;
}

export interface DividerProps { }

// ============================================================================
// Custom Financial Components
// ============================================================================

export interface PriceChartProps {
    ticker: BoundString;
    interval?: BoundString;
    showVolume?: BoundBoolean;
}

export interface KpiCardProps {
    label: BoundString;
    value: BoundNumber;
    unit?: BoundString;
    delta?: BoundNumber;
    deltaType?: BoundString;
}

export interface DataTableProps {
    columns: BoundArray;
    data: BoundArray;
    sortable?: BoundBoolean;
}

export interface NewsTimelineProps {
    events: BoundArray;
}

export interface CorrelationMatrixProps {
    tickers: BoundArray;
    matrix: BoundArray;
}

export interface ExplainMovePanelProps {
    title: BoundString;
    explanation: BoundString;
    factors?: BoundArray;
    citations?: BoundArray;
}

// ============================================================================
// Component Definitions
// ============================================================================

export type ComponentType =
    | { Text: TextProps }
    | { Row: RowProps }
    | { Column: ColumnProps }
    | { Card: CardProps }
    | { Button: ButtonProps }
    | { Image: ImageProps }
    | { Divider: DividerProps }
    | { PriceChart: PriceChartProps }
    | { KpiCard: KpiCardProps }
    | { DataTable: DataTableProps }
    | { NewsTimeline: NewsTimelineProps }
    | { CorrelationMatrix: CorrelationMatrixProps }
    | { ExplainMovePanel: ExplainMovePanelProps };

export interface A2UIComponent {
    id: string;
    weight?: number;
    component: ComponentType;
}

// ============================================================================
// A2UI Messages
// ============================================================================

export interface BeginRenderingMessage {
    beginRendering: {
        surfaceId: string;
        root: string;
        catalogId?: string;
    };
}

export interface SurfaceUpdateMessage {
    surfaceUpdate: {
        surfaceId: string;
        components: A2UIComponent[];
    };
}

export interface DataModelUpdateMessage {
    dataModelUpdate: {
        surfaceId: string;
        contents: DataEntry[];
        path?: string;
    };
}

export interface DeleteSurfaceMessage {
    deleteSurface: {
        surfaceId: string;
    };
}

export interface UserActionMessage {
    userAction: {
        name: string;
        surfaceId: string;
        sourceComponentId: string;
        timestamp: string;
        context: Record<string, unknown>;
    };
}

export interface ErrorMessage {
    error: {
        message: string;
        details?: unknown;
    };
}

export type A2UIServerMessage =
    | BeginRenderingMessage
    | SurfaceUpdateMessage
    | DataModelUpdateMessage
    | DeleteSurfaceMessage;

export type A2UIClientMessage =
    | UserActionMessage
    | ErrorMessage;

// ============================================================================
// Surface State
// ============================================================================

export interface Surface {
    surfaceId: string;
    root: string | null;
    components: Map<string, ComponentType>;
    catalogId?: string;
}

export interface A2UIState {
    surfaces: Map<string, Surface>;
    dataModels: Map<string, DataModel>;
}
