/**
 * Data Binder
 *
 * Resolves BoundValue objects against the data model.
 */

import type { BoundValue, DataModel } from './types';

/**
 * Get a value from the data model using a JSON Pointer path.
 *
 * @param dataModel - The data model object
 * @param path - JSON Pointer path (e.g., "/data/price")
 * @returns The value at the path, or undefined if not found
 */
export function getByPath(dataModel: DataModel, path: string): unknown {
    if (!path) return undefined;

    // Remove leading slash and split
    const segments = path.replace(/^\//, '').split('/');
    let current: unknown = dataModel;

    for (const segment of segments) {
        if (current == null || typeof current !== 'object') {
            return undefined;
        }
        current = (current as Record<string, unknown>)[segment];
    }

    return current;
}

/**
 * Resolve a BoundValue to its actual value.
 *
 * Resolution logic:
 * - If path exists and value is found in dataModel, use that
 * - Otherwise, fall back to literal values
 * - If both path and literal are provided, literal serves as default
 *
 * @param boundValue - The bound value to resolve
 * @param dataModel - The data model to resolve paths against
 * @returns The resolved value
 */
export function resolveBoundValue(
    boundValue: BoundValue | undefined,
    dataModel: DataModel
): unknown {
    if (!boundValue) return undefined;

    // Check for path first
    if ('path' in boundValue && boundValue.path) {
        const pathValue = getByPath(dataModel, boundValue.path);
        if (pathValue !== undefined) {
            return pathValue;
        }
    }

    // Fall back to literal values
    if ('literalString' in boundValue) return boundValue.literalString;
    if ('literalNumber' in boundValue) return boundValue.literalNumber;
    if ('literalBoolean' in boundValue) return boundValue.literalBoolean;
    if ('literalArray' in boundValue) return boundValue.literalArray;

    return undefined;
}

/**
 * Resolve a string bound value.
 */
export function resolveString(
    boundValue: BoundValue | undefined,
    dataModel: DataModel,
    defaultValue: string = ''
): string {
    const value = resolveBoundValue(boundValue, dataModel);
    return typeof value === 'string' ? value : defaultValue;
}

/**
 * Resolve a number bound value.
 */
export function resolveNumber(
    boundValue: BoundValue | undefined,
    dataModel: DataModel,
    defaultValue: number = 0
): number {
    const value = resolveBoundValue(boundValue, dataModel);
    return typeof value === 'number' ? value : defaultValue;
}

/**
 * Resolve a boolean bound value.
 */
export function resolveBoolean(
    boundValue: BoundValue | undefined,
    dataModel: DataModel,
    defaultValue: boolean = false
): boolean {
    const value = resolveBoundValue(boundValue, dataModel);
    return typeof value === 'boolean' ? value : defaultValue;
}

/**
 * Resolve an array bound value.
 */
export function resolveArray<T = unknown>(
    boundValue: BoundValue | undefined,
    dataModel: DataModel,
    defaultValue: T[] = []
): T[] {
    const value = resolveBoundValue(boundValue, dataModel);
    return Array.isArray(value) ? value as T[] : defaultValue;
}

/**
 * Resolve all bound values in a props object.
 *
 * This recursively resolves any BoundValue objects found in the props.
 */
export function resolveBoundProps(
    props: Record<string, unknown>,
    dataModel: DataModel
): Record<string, unknown> {
    const resolved: Record<string, unknown> = {};

    for (const [key, value] of Object.entries(props)) {
        if (isBoundValue(value)) {
            resolved[key] = resolveBoundValue(value as BoundValue, dataModel);
        } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            // Recurse into nested objects
            resolved[key] = resolveBoundProps(value as Record<string, unknown>, dataModel);
        } else {
            resolved[key] = value;
        }
    }

    return resolved;
}

/**
 * Check if a value looks like a BoundValue object.
 */
function isBoundValue(value: unknown): boolean {
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
        return false;
    }

    const obj = value as Record<string, unknown>;
    return (
        'literalString' in obj ||
        'literalNumber' in obj ||
        'literalBoolean' in obj ||
        'literalArray' in obj ||
        'path' in obj
    );
}
