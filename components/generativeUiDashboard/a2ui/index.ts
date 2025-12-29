/**
 * A2UI Module Exports
 */

// Types
export type {
    BoundString,
    BoundNumber,
    BoundBoolean,
    BoundArray,
    BoundValue,
    DataEntry,
    DataModel,
    Children,
    ChildrenExplicitList,
    ChildrenTemplate,
    ActionContext,
    ComponentAction,
    TextProps,
    RowProps,
    ColumnProps,
    CardProps,
    ButtonProps,
    ImageProps,
    DividerProps,
    PriceChartProps,
    KpiCardProps,
    DataTableProps,
    NewsTimelineProps,
    CorrelationMatrixProps,
    ExplainMovePanelProps,
    ComponentType,
    A2UIComponent,
    BeginRenderingMessage,
    SurfaceUpdateMessage,
    DataModelUpdateMessage,
    DeleteSurfaceMessage,
    UserActionMessage,
    ErrorMessage,
    A2UIServerMessage,
    A2UIClientMessage,
    Surface,
    A2UIState,
} from './types';

// Message Processor
export {
    MessageProcessor,
    createMessageProcessor,
    processDataEntries,
    applyDataUpdate,
} from './MessageProcessor';

// Data Binder
export {
    getByPath,
    resolveBoundValue,
    resolveString,
    resolveNumber,
    resolveBoolean,
    resolveArray,
    resolveBoundProps,
} from './DataBinder';

// Hook
export {
    useA2UIStream,
    useSurface,
    type A2UIStreamState,
    type A2UIStreamActions,
    type UseA2UIStreamOptions,
} from './useA2UIStream';
