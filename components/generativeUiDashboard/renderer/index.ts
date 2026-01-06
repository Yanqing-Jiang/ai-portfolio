/**
 * Renderer Module Exports
 */

export { A2UISurface, A2UISurfaceLoading, A2UISurfaceError } from './A2UISurface';
export { ComponentRenderer } from './ComponentRenderer';
export { WidgetErrorBoundary, WidgetErrorFallback } from './WidgetErrorBoundary';
export {
    componentRegistry,
    extractComponent,
    resolveComponent,
    isRegistered,
    getRegisteredTypes,
    type A2UIRendererProps,
} from './Registry';

