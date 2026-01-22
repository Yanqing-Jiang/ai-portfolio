/**
 * Widgets barrel export for Generative UI Dashboard.
 *
 * File: widgets/index.ts
 * Called from: GenerativeUIPage.tsx, renderer components
 * Why: Central export for all dashboard widgets.
 */

export { LayoutSwitcher } from './LayoutSwitcher';
export type { LayoutSwitcherProps } from './LayoutSwitcher';

export { SwapButton } from './SwapButton';
export type { SwapButtonProps } from './SwapButton';

export { SwapPreviewOverlay } from './SwapPreviewOverlay';

export { ComponentActionMenu } from './ComponentActionMenu';

export { AnomalyAlert, AnomalyAlertList } from './AnomalyAlert';
export type { AnomalyData, AnomalyAlertProps, AnomalyAlertListProps } from './AnomalyAlert';

export { DragHandle, InlineDragHandle } from './DragHandle';
export type { DragHandleProps } from './DragHandle';

export { ReorderToggle, ReorderToggleIcon } from './ReorderToggle';
export type { ReorderToggleProps } from './ReorderToggle';

export { ReasoningDisclosure } from './ReasoningDisclosure';
export type { ReasoningStep, ReasoningDisclosureProps } from './ReasoningDisclosure';
