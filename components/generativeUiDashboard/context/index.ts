/**
 * Context exports for Generative UI Dashboard.
 *
 * File: context/index.ts
 * Called from: GenerativeUIPage.tsx, widgets, hooks
 * Why: Central barrel export for all context providers and hooks.
 */

export {
    LayoutProvider,
    useLayoutPreferences,
    type LayoutPreferences,
    type LayoutEmphasis,
    type LayoutContextValue,
} from './LayoutContext';

export {
    ComponentSwapProvider,
    useComponentSwap,
    canSwapTo,
    getSwapOptions,
    type SwapOverride,
    type SwapContextValue,
} from './ComponentSwapContext';

export {
    ComponentSelectionProvider,
    useComponentSelection,
    findComponentByKeyword,
    type SelectedComponent,
    type SelectionContextValue,
} from './ComponentSelectionContext';
