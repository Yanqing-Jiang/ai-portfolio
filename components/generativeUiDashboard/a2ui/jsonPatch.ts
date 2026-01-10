/**
 * JSON Patch (RFC 6902) utilities for A2UI incremental data updates.
 *
 * Module: jsonPatch.ts
 * Role: Apply RFC 6902 patches client-side for efficient data updates.
 * Called from: MessageProcessor.ts
 * Why: Enables incremental updates with significant bandwidth savings.
 *
 * Implements Optimization #18 from optimization-recommendations.md.
 */

// ============================================================================
// Types
// ============================================================================

export type PatchOperation =
    | { op: 'add'; path: string; value: unknown }
    | { op: 'remove'; path: string }
    | { op: 'replace'; path: string; value: unknown }
    | { op: 'move'; from: string; path: string }
    | { op: 'copy'; from: string; path: string }
    | { op: 'test'; path: string; value: unknown };

export type Patch = PatchOperation[];

// ============================================================================
// Path Utilities
// ============================================================================

/**
 * Escape special characters in JSON Pointer keys per RFC 6901.
 */
export function escapeKey(key: string): string {
    return key.replace(/~/g, '~0').replace(/\//g, '~1');
}

/**
 * Unescape JSON Pointer key.
 */
function unescapeKey(key: string): string {
    return key.replace(/~1/g, '/').replace(/~0/g, '~');
}

/**
 * Parse JSON Pointer path into segments.
 */
function parsePath(path: string): string[] {
    if (!path || path === '/') {
        return [];
    }
    if (!path.startsWith('/')) {
        throw new Error(`Invalid JSON Pointer: ${path}`);
    }
    return path.slice(1).split('/').map(unescapeKey);
}

/**
 * Navigate to parent of path and return [parent, key].
 */
function getParentAndKey(
    document: Record<string, unknown>,
    path: string
): [Record<string, unknown> | unknown[], string] {
    const segments = parsePath(path);
    if (segments.length === 0) {
        throw new Error('Cannot get parent of root');
    }

    let parent: unknown = document;
    for (let i = 0; i < segments.length - 1; i++) {
        const seg = segments[i];
        if (typeof parent === 'object' && parent !== null) {
            if (Array.isArray(parent)) {
                parent = parent[parseInt(seg, 10)];
            } else {
                parent = (parent as Record<string, unknown>)[seg];
            }
        } else {
            throw new Error(`Cannot navigate path: ${path}`);
        }
    }

    return [parent as Record<string, unknown> | unknown[], segments[segments.length - 1]];
}

// ============================================================================
// Patch Application
// ============================================================================

/**
 * Apply RFC 6902 JSON Patch to a document.
 *
 * @param document - Original document
 * @param patch - List of patch operations
 * @returns Patched document (new object, original is not modified)
 */
export function applyPatch(
    document: Record<string, unknown>,
    patch: Patch
): Record<string, unknown> {
    // Deep clone to avoid mutation
    let result = JSON.parse(JSON.stringify(document)) as Record<string, unknown>;

    for (const op of patch) {
        switch (op.op) {
            case 'add':
                applyAdd(result, op.path, op.value);
                break;
            case 'remove':
                applyRemove(result, op.path);
                break;
            case 'replace':
                applyReplace(result, op.path, op.value);
                break;
            case 'move':
                applyMove(result, op.from, op.path);
                break;
            case 'copy':
                applyCopy(result, op.from, op.path);
                break;
            case 'test':
                applyTest(result, op.path, op.value);
                break;
            default:
                console.warn('Unknown patch operation:', op);
        }
    }

    return result;
}

function applyAdd(document: Record<string, unknown>, path: string, value: unknown): void {
    if (!path || path === '/') {
        // Replace entire document
        Object.keys(document).forEach((key) => delete document[key]);
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            Object.assign(document, value);
        }
        return;
    }

    const [parent, key] = getParentAndKey(document, path);

    if (Array.isArray(parent)) {
        const idx = key === '-' ? parent.length : parseInt(key, 10);
        parent.splice(idx, 0, value);
    } else {
        (parent as Record<string, unknown>)[key] = value;
    }
}

function applyRemove(document: Record<string, unknown>, path: string): void {
    const [parent, key] = getParentAndKey(document, path);

    if (Array.isArray(parent)) {
        parent.splice(parseInt(key, 10), 1);
    } else {
        delete (parent as Record<string, unknown>)[key];
    }
}

function applyReplace(document: Record<string, unknown>, path: string, value: unknown): void {
    if (!path || path === '/') {
        Object.keys(document).forEach((key) => delete document[key]);
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            Object.assign(document, value);
        }
        return;
    }

    const [parent, key] = getParentAndKey(document, path);

    if (Array.isArray(parent)) {
        parent[parseInt(key, 10)] = value;
    } else {
        (parent as Record<string, unknown>)[key] = value;
    }
}

function applyMove(document: Record<string, unknown>, fromPath: string, toPath: string): void {
    const [fromParent, fromKey] = getParentAndKey(document, fromPath);
    const value = Array.isArray(fromParent)
        ? fromParent[parseInt(fromKey, 10)]
        : (fromParent as Record<string, unknown>)[fromKey];

    applyRemove(document, fromPath);
    applyAdd(document, toPath, value);
}

function applyCopy(document: Record<string, unknown>, fromPath: string, toPath: string): void {
    const [fromParent, fromKey] = getParentAndKey(document, fromPath);
    const value = Array.isArray(fromParent)
        ? fromParent[parseInt(fromKey, 10)]
        : (fromParent as Record<string, unknown>)[fromKey];

    // Deep clone the value
    const clonedValue = JSON.parse(JSON.stringify(value));
    applyAdd(document, toPath, clonedValue);
}

function applyTest(document: Record<string, unknown>, path: string, expected: unknown): void {
    let actual: unknown;

    if (!path || path === '/') {
        actual = document;
    } else {
        const [parent, key] = getParentAndKey(document, path);
        actual = Array.isArray(parent)
            ? parent[parseInt(key, 10)]
            : (parent as Record<string, unknown>)[key];
    }

    if (JSON.stringify(actual) !== JSON.stringify(expected)) {
        throw new Error(`Test failed at ${path}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    }
}

// ============================================================================
// Patch Validation
// ============================================================================

/**
 * Validate that a patch can be safely applied.
 *
 * @param patch - Patch to validate
 * @returns True if valid, throws on invalid
 */
export function validatePatch(patch: Patch): boolean {
    for (const op of patch) {
        if (!op.op || !op.path) {
            throw new Error(`Invalid patch operation: missing op or path`);
        }
        if (!['add', 'remove', 'replace', 'move', 'copy', 'test'].includes(op.op)) {
            throw new Error(`Invalid patch operation: ${op.op}`);
        }
        // Check if move/copy has 'from' field
        const opType = op.op;
        if ((opType === 'move' || opType === 'copy') && !('from' in op)) {
            throw new Error(`${opType} operation requires 'from' field`);
        }
    }
    return true;
}

// ============================================================================
// Safe Apply with Fallback
// ============================================================================

/**
 * Safely apply a patch with fallback to full replacement.
 *
 * @param existing - Current document
 * @param patch - Patch to apply
 * @param fallbackData - Full data to use if patch fails
 * @returns Updated document
 */
export function safeApplyPatch(
    existing: Record<string, unknown>,
    patch: Patch,
    fallbackData?: Record<string, unknown>
): Record<string, unknown> {
    try {
        validatePatch(patch);
        return applyPatch(existing, patch);
    } catch (error) {
        console.warn('Patch application failed, using fallback:', error);
        if (fallbackData) {
            return { ...existing, ...fallbackData };
        }
        return existing;
    }
}
