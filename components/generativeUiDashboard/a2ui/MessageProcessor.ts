/**
 * A2UI Message Processor
 *
 * Processes A2UI JSONL messages and updates surface/dataModel state.
 */

import type {
    A2UIServerMessage,
    Surface,
    DataModel,
    DataEntry,
} from './types';


/**
 * Process a DataEntry array into a nested object structure.
 */
export function processDataEntries(entries: DataEntry[]): Record<string, unknown> {
    const result: Record<string, unknown> = {};

    for (const entry of entries) {
        if (entry.valueString !== undefined) {
            result[entry.key] = entry.valueString;
        } else if (entry.valueNumber !== undefined) {
            result[entry.key] = entry.valueNumber;
        } else if (entry.valueBoolean !== undefined) {
            result[entry.key] = entry.valueBoolean;
        } else if (entry.valueArray !== undefined) {
            result[entry.key] = entry.valueArray;
        } else if (entry.valueMap !== undefined) {
            result[entry.key] = processDataEntries(entry.valueMap);
        }
    }

    return result;
}

/**
 * Apply a data update at a specific path within the data model.
 */
export function applyDataUpdate(
    existing: DataModel,
    path: string | undefined,
    contents: DataEntry[]
): DataModel {
    const newData = processDataEntries(contents);

    if (!path || path === '' || path === '/') {
        // Apply at root
        return { ...existing, ...newData };
    }

    // Navigate to path and merge
    const segments = path.replace(/^\//, '').split('/');
    const result = { ...existing };
    let current: Record<string, unknown> = result;

    for (let i = 0; i < segments.length - 1; i++) {
        const segment = segments[i];
        if (!(segment in current) || typeof current[segment] !== 'object') {
            current[segment] = {};
        }
        current[segment] = { ...(current[segment] as Record<string, unknown>) };
        current = current[segment] as Record<string, unknown>;
    }

    const lastSegment = segments[segments.length - 1];
    current[lastSegment] = {
        ...(current[lastSegment] as Record<string, unknown> || {}),
        ...newData,
    };

    return result;
}

/**
 * A2UI Message Processor class.
 *
 * Manages surface and data model state as messages arrive.
 */
export class MessageProcessor {
    private surfaces: Map<string, Surface> = new Map();
    private dataModels: Map<string, DataModel> = new Map();
    private onUpdate: (() => void) | null = null;
    private onAudit: ((event: any) => void) | null = null;

    constructor(onUpdate?: () => void, onAudit?: (event: any) => void) {
        this.onUpdate = onUpdate || null;
        this.onAudit = onAudit || null;
    }

    /**
     * Process a single A2UI message.
     */
    processMessage(message: A2UIServerMessage): void {
        if ('beginRendering' in message) {
            const { surfaceId, root, catalogId } = message.beginRendering;
            this.surfaces.set(surfaceId, {
                surfaceId,
                root,
                components: new Map(),
                catalogId,
            });
            // Initialize empty data model for surface
            if (!this.dataModels.has(surfaceId)) {
                this.dataModels.set(surfaceId, {});
            }
        } else if ('surfaceUpdate' in message) {
            const { surfaceId, components } = message.surfaceUpdate;
            const surface = this.surfaces.get(surfaceId);

            if (surface) {
                for (const comp of components) {
                    surface.components.set(comp.id, comp.component);
                }
            } else {
                // Auto-create surface if not exists
                const newSurface: Surface = {
                    surfaceId,
                    root: null,
                    components: new Map(),
                };
                for (const comp of components) {
                    newSurface.components.set(comp.id, comp.component);
                }
                this.surfaces.set(surfaceId, newSurface);
            }
        } else if ('dataModelUpdate' in message) {
            const { surfaceId, contents, path } = message.dataModelUpdate;
            const existing = this.dataModels.get(surfaceId) || {};
            const updated = applyDataUpdate(existing, path, contents);
            this.dataModels.set(surfaceId, updated);
        } else if ('deleteSurface' in message) {
            const { surfaceId } = message.deleteSurface;
            this.surfaces.delete(surfaceId);
            this.dataModels.delete(surfaceId);
        } else if ('audit' in message) {
            this.onAudit?.(message.audit);
        }

        // Trigger update callback
        this.onUpdate?.();
    }

    /**
     * Process a JSONL line (single JSON object).
     */
    processLine(line: string): void {
        if (!line.trim()) return;

        try {
            const message = JSON.parse(line) as A2UIServerMessage;
            this.processMessage(message);
        } catch (error) {
            console.error('Failed to parse A2UI message:', error, line);
        }
    }

    /**
     * Get current state snapshot.
     */
    getState(): { surfaces: Map<string, Surface>; dataModels: Map<string, DataModel> } {
        return {
            surfaces: new Map(this.surfaces),
            dataModels: new Map(this.dataModels),
        };
    }

    /**
     * Get a specific surface.
     */
    getSurface(surfaceId: string): Surface | undefined {
        return this.surfaces.get(surfaceId);
    }

    /**
     * Get data model for a surface.
     */
    getDataModel(surfaceId: string): DataModel {
        return this.dataModels.get(surfaceId) || {};
    }

    /**
     * Clear all state.
     */
    clear(): void {
        this.surfaces.clear();
        this.dataModels.clear();
        this.onUpdate?.();
    }
}

/**
 * Create a new message processor instance.
 */
export function createMessageProcessor(onUpdate?: () => void, onAudit?: (event: any) => void): MessageProcessor {
    return new MessageProcessor(onUpdate, onAudit);
}
