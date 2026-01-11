// --- Function/Class Map ---
// Component: A2UIColumn
//   Role: Render vertical A2UI columns with layout-aware ordering.
//   Called from: components/generativeUiDashboard/renderer/ComponentRenderer.tsx
//   Invokes: renderChild, LayoutContext preferences, getByPath
//   Why: Keeps column layout responsive to LLM-driven layout changes.
// Function: resolveChildIds
//   Role: Resolve explicit or templated child IDs for layout inference.
//   Called from: getWidgetTypeForComponent.
//   Invokes: getByPath.
//   Why: Allows widget-type discovery for nested containers.
// Function: getWidgetTypeForComponent
//   Role: Infer the primary widget type for a component subtree.
//   Called from: A2UIColumn.
//   Invokes: resolveChildIds, extractComponent.
//   Why: Maps layout commands to rendered components.
// Function: componentsHasId
//   Role: Guard for template-rendered component IDs.
//   Called from: A2UIColumn.
//   Invokes: Map.has.
//   Why: Prevents missing-ID rendering issues.
// --- End Function/Class Map ---
/**
 * A2UI Column Component
 *
 * Vertical flexbox layout container.
 */

import React from 'react';
import { extractComponent, type A2UIRendererProps } from '../Registry';
import type {
    CardProps,
    Children,
    ColumnProps,
    ComponentType as A2UIComponentType,
    DataModel,
    RowProps,
} from '../../a2ui/types';
import { getByPath } from '../../a2ui/DataBinder';
import LayoutContext from '../../context/LayoutContext';

const LAYOUT_WIDGET_TYPES = new Set([
    'KpiCard',
    'MetricChart',
    'PriceChart',
    'DataTable',
    'NewsTimeline',
    'ExplainMovePanel',
    'PeerComparePanel',
    'CorrelationMatrix',
]);

function resolveChildIds(children: Children, dataModel: DataModel): string[] {
    const resolved: string[] = [];
    if ('explicitList' in children) {
        resolved.push(...children.explicitList);
    } else if ('template' in children && children.template) {
        const dataArray = getByPath(dataModel, children.dataPath);
        const items = Array.isArray(dataArray) ? dataArray : [];
        items.forEach((item, idx) => {
            const childId =
                typeof item === 'string'
                    ? item
                    : children.template!.includes('{index}')
                        ? children.template!.replace('{index}', String(idx))
                        : `${children.template}_${idx}`;
            resolved.push(childId);
        });
    }
    return resolved;
}

function getWidgetTypeForComponent(
    componentId: string,
    components: Map<string, A2UIComponentType>,
    dataModel: DataModel,
    depth = 0
): string | null {
    if (depth > 4) return null;
    const componentDef = components.get(componentId);
    if (!componentDef) return null;
    const extracted = extractComponent(componentDef);
    if (!extracted) return null;

    const { type, props } = extracted;
    if (LAYOUT_WIDGET_TYPES.has(type)) return type;

    if (type === 'Card') {
        const childId = (props as CardProps).child;
        if (!childId) return null;
        return getWidgetTypeForComponent(childId, components, dataModel, depth + 1);
    }

    if (type === 'Row' || type === 'Column') {
        const nestedChildren = resolveChildIds((props as RowProps | ColumnProps).children, dataModel);
        const nestedTypes = new Set<string>();
        for (const nestedId of nestedChildren) {
            const nestedType = getWidgetTypeForComponent(nestedId, components, dataModel, depth + 1);
            if (nestedType) nestedTypes.add(nestedType);
        }
        if (nestedTypes.size === 1) {
            return Array.from(nestedTypes)[0];
        }
    }

    return null;
}

export function A2UIColumn({
    componentId,
    props,
    dataModel,
    components,
    renderChild,
}: A2UIRendererProps): React.ReactElement {
    const layoutContext = React.useContext(LayoutContext);
    const columnProps = props as unknown as ColumnProps;
    const children = columnProps.children;

    // Get child IDs (supports ChildrenTemplate)
    const childIds: string[] = [];
    let templateValue: string | undefined;
    if ('explicitList' in children) {
        childIds.push(...children.explicitList);
    } else if ('template' in children && children.template) {
        templateValue = children.template;
        const dataArray = getByPath(dataModel, children.dataPath);
        const items = Array.isArray(dataArray) ? dataArray : [];
        items.forEach((item, idx) => {
            const childId =
                typeof item === 'string'
                    ? item
                    : templateValue!.includes('{index}')
                        ? templateValue!.replace('{index}', String(idx))
                        : `${templateValue}_${idx}`;
            childIds.push(childId);
        });
    }

    const widgetOrder = layoutContext?.preferences.widgetOrder ?? [];
    const hiddenWidgets = new Set(layoutContext?.preferences.hiddenWidgets ?? []);
    const childMeta = childIds.map((childId, index) => ({
        id: childId,
        index,
        widgetType: getWidgetTypeForComponent(childId, components, dataModel),
    }));
    const visibleChildren = childMeta.filter(
        (child) => !child.widgetType || !hiddenWidgets.has(child.widgetType)
    );
    const orderedChildren = widgetOrder.length
        ? (() => {
            const orderIndex = new Map(widgetOrder.map((type, idx) => [type, idx]));
            const orderedOnly = visibleChildren
                .filter((child) => child.widgetType && orderIndex.has(child.widgetType))
                .sort((a, b) => (orderIndex.get(a.widgetType!) ?? 0) - (orderIndex.get(b.widgetType!) ?? 0));
            let cursor = 0;
            return visibleChildren.map((child) => {
                if (child.widgetType && orderIndex.has(child.widgetType)) {
                    const next = orderedOnly[cursor];
                    cursor += 1;
                    return next;
                }
                return child;
            });
        })()
        : visibleChildren;
    const finalChildIds = orderedChildren.map((child) => child.id);

    if (finalChildIds.length === 0) {
        return <></>;
    }

    // Map alignment to CSS
    const alignmentMap: Record<string, string> = {
        start: 'flex-start',
        center: 'center',
        end: 'flex-end',
        stretch: 'stretch',
    };

    const alignItems = columnProps.alignment
        ? alignmentMap[columnProps.alignment] || 'stretch'
        : 'stretch';

    return (
        <div
            className="a2ui-column"
            data-component-id={componentId}
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems,
                gap: '1rem',
                width: '100%',
            }}
        >
            {finalChildIds.map((childId) => (
                <div key={childId} className="a2ui-column__item">
                    {renderChild(componentsHasId(components, childId) ? childId : templateValue || childId)}
                </div>
            ))}
        </div>
    );
}

function componentsHasId(map: Map<string, any>, id: string): boolean {
    return map.has(id);
}
