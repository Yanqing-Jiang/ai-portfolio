// --- Function/Class Map ---
// Component: A2UIRow
//   Role: Render horizontal A2UI row containers with layout-aware ordering.
//   Called from: components/generativeUiDashboard/renderer/ComponentRenderer.tsx
//   Invokes: renderChild, LayoutContext preferences, getByPath
//   Why: Keeps row layout responsive to LLM-driven layout changes.
// Function: resolveChildIds
//   Role: Resolve explicit or templated child IDs for layout inference.
//   Called from: getWidgetTypeForComponent.
//   Invokes: getByPath.
//   Why: Allows widget-type discovery for nested containers.
// Function: getWidgetTypeForComponent
//   Role: Infer the primary widget type for a component subtree.
//   Called from: A2UIRow.
//   Invokes: resolveChildIds, extractComponent.
//   Why: Maps layout commands to rendered components.
// Function: componentsHasId
//   Role: Guard for template-rendered component IDs.
//   Called from: A2UIRow.
//   Invokes: Map.has.
//   Why: Prevents missing-ID rendering issues.
// --- End Function/Class Map ---
/**
 * A2UI Row Component
 *
 * Horizontal flexbox layout container with drag-and-drop reordering.
 * Supports per-container ordering via LayoutContext.containerOrder.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Reorder, useDragControls } from 'framer-motion';
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
import { InlineDragHandle } from '../../widgets/DragHandle';

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
        const childId = (props as unknown as CardProps).child;
        if (!childId) return null;
        return getWidgetTypeForComponent(childId, components, dataModel, depth + 1);
    }

    if (type === 'Row' || type === 'Column') {
        const nestedChildren = resolveChildIds((props as unknown as RowProps | ColumnProps).children, dataModel);
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

export function A2UIRow({
    componentId,
    props,
    dataModel,
    components,
    renderChild,
}: A2UIRendererProps): React.ReactElement | null {
    const layoutContext = React.useContext(LayoutContext);
    const rowProps = props as unknown as RowProps;
    const children = rowProps.children;

    // Get child IDs (support ChildrenTemplate)
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
    const reorderModeEnabled = layoutContext?.preferences.reorderModeEnabled ?? false;

    // Check for container-specific order
    const containerOrder = layoutContext?.getContainerOrder?.(componentId);

    const childMeta = childIds.map((childId, index) => ({
        id: childId,
        index,
        widgetType: getWidgetTypeForComponent(childId, components, dataModel),
    }));
    const visibleChildren = childMeta.filter(
        (child) => !child.widgetType || !hiddenWidgets.has(child.widgetType)
    );

    // Apply container-specific order if exists, then fall back to widget order
    let orderedChildren = visibleChildren;
    if (containerOrder && containerOrder.length > 0) {
        // Use container-specific order
        const orderMap = new Map(containerOrder.map((id, idx) => [id, idx]));
        orderedChildren = [...visibleChildren].sort((a, b) => {
            const aOrder = orderMap.get(a.id) ?? 999;
            const bOrder = orderMap.get(b.id) ?? 999;
            return aOrder - bOrder;
        });
    } else if (widgetOrder.length > 0) {
        // Fall back to legacy widget type ordering
        const orderIndex = new Map(widgetOrder.map((type, idx) => [type, idx]));
        const orderedOnly = visibleChildren
            .filter((child) => child.widgetType && orderIndex.has(child.widgetType))
            .sort((a, b) => (orderIndex.get(a.widgetType!) ?? 0) - (orderIndex.get(b.widgetType!) ?? 0));
        let cursor = 0;
        orderedChildren = visibleChildren.map((child) => {
            if (child.widgetType && orderIndex.has(child.widgetType)) {
                const next = orderedOnly[cursor];
                cursor += 1;
                return next;
            }
            return child;
        });
    }

    const [localOrder, setLocalOrder] = useState(() => orderedChildren.map(c => c.id));

    // Sync local order with context changes
    useEffect(() => {
        setLocalOrder(orderedChildren.map(c => c.id));
    }, [containerOrder?.join(','), orderedChildren.length]);

    const handleReorder = useCallback((newOrder: string[]) => {
        setLocalOrder(newOrder);
        // Debounce persistence to avoid excessive writes
        layoutContext?.reorderContainer?.(componentId, newOrder);
    }, [layoutContext, componentId]);

    const finalChildIds = reorderModeEnabled ? localOrder : orderedChildren.map((child) => child.id);

    if (finalChildIds.length === 0) {
        return null;
    }

    // Map alignment to CSS
    const alignmentMap: Record<string, string> = {
        start: 'flex-start',
        center: 'center',
        end: 'flex-end',
        spaceBetween: 'space-between',
        spaceAround: 'space-around',
    };

    const justifyContent = rowProps.alignment
        ? alignmentMap[rowProps.alignment] || 'flex-start'
        : 'flex-start';

    // Render with Reorder when mode enabled, otherwise standard div
    if (reorderModeEnabled) {
        return (
            <Reorder.Group
                axis="x"
                values={localOrder}
                onReorder={handleReorder}
                className="a2ui-row a2ui-row--reorder"
                data-component-id={componentId}
                style={{
                    display: 'flex',
                    flexDirection: 'row',
                    flexWrap: 'wrap',
                    justifyContent,
                    gap: 'clamp(0.5rem, 2vw, 1rem)',
                    width: '100%',
                    listStyle: 'none',
                    padding: 0,
                    margin: 0,
                }}
            >
                {localOrder.map((childId) => (
                    <ReorderableRowItem
                        key={childId}
                        childId={childId}
                        templateValue={templateValue}
                        components={components}
                        renderChild={renderChild}
                    />
                ))}
            </Reorder.Group>
        );
    }

    // Use CSS Grid so layout span classes (col-span-2, row-span-2) work properly
    // Apply emphasis classes to direct grid children for CSS Grid spans to work
    const getEmphasisClasses = layoutContext?.getEmphasisClasses;

    return (
        <div
            className="a2ui-row"
            data-component-id={componentId}
            style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)', // Fixed 3-column grid for span classes
                gap: 'clamp(0.5rem, 2vw, 1rem)',
                width: '100%',
            }}
        >
            {finalChildIds.map((childId) => {
                // Get widget type to apply emphasis classes to direct grid children
                const widgetType = getWidgetTypeForComponent(childId, components, dataModel);
                const emphasisClasses = widgetType && getEmphasisClasses
                    ? getEmphasisClasses(widgetType)
                    : '';

                return (
                    <div
                        key={childId}
                        className={`a2ui-row__item ${emphasisClasses}`.trim()}
                    >
                        {renderChild(componentsHasId(components, childId) ? childId : templateValue || childId)}
                    </div>
                );
            })}
        </div>
    );
}

/**
 * Reorderable row item wrapper with drag handle.
 */
function ReorderableRowItem({
    childId,
    templateValue,
    components,
    renderChild,
}: {
    childId: string;
    templateValue?: string;
    components: Map<string, A2UIComponentType>;
    renderChild: (id: string) => React.ReactNode;
}) {
    const dragControls = useDragControls();
    const [isDragging, setIsDragging] = useState(false);

    return (
        <Reorder.Item
            value={childId}
            dragListener={false}
            dragControls={dragControls}
            onDragStart={() => setIsDragging(true)}
            onDragEnd={() => setIsDragging(false)}
            className="a2ui-row__item a2ui-row__item--reorderable"
            style={{
                flex: '1 1 280px',
                minWidth: '280px',
                maxWidth: '100%',
                position: 'relative',
                listStyle: 'none',
            }}
            whileDrag={{
                scale: 1.02,
                boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
                zIndex: 50,
            }}
            layout
        >
            <InlineDragHandle
                isDragging={isDragging}
                dragControls={dragControls}
                ariaLabel={`Drag ${childId} to reorder`}
                className="absolute -left-2 top-1/2 -translate-y-1/2 z-10"
            />
            {renderChild(componentsHasId(components, childId) ? childId : templateValue || childId)}
        </Reorder.Item>
    );
}

function componentsHasId(map: Map<string, any>, id: string): boolean {
    return map.has(id);
}
