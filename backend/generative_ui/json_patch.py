# --- JSON Patch Utilities (Optimization #18) ---
# Function: make_patch
#   Role: Compute RFC 6902 JSON Patch between two objects.
#   Called from: A2UIMessageEmitter.data_patch, runtime.py
#   Invokes: jsonpatch library (or custom implementation)
#   Why: Reduces payload sizes by sending only differences.
#
# Function: apply_patch
#   Role: Apply RFC 6902 patch to an object.
#   Called from: Frontend MessageProcessor (via TypeScript equivalent)
#   Why: Reconstructs full state from patches.
"""
JSON Patch (RFC 6902) utilities for A2UI incremental data updates.

This module implements Optimization #18 from optimization-recommendations.md.
Provides efficient incremental updates by computing and applying JSON patches
instead of sending full data models.

Benefits:
- Reduced payload sizes (up to 90% smaller for large tables)
- Faster UI updates
- Lower bandwidth usage
- Better perceived performance

Usage:
    # Server-side
    patch = make_patch(old_data, new_data)
    
    # Client-side (TypeScript)
    import { applyPatch } from './json_patch';
    const updated = applyPatch(existing, patch);
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# ============================================================================
# Types
# ============================================================================

# RFC 6902 operation types
PatchOperation = Dict[str, Any]  # {op, path, value?, from?}
Patch = List[PatchOperation]  # Array of operations


# ============================================================================
# Patch Generation
# ============================================================================

def make_patch(
    source: Dict[str, Any],
    target: Dict[str, Any],
    path: str = "",
) -> Patch:
    """
    Generate RFC 6902 JSON Patch from source to target.
    
    Function: make_patch
    Role: Compute minimal patch to transform source into target.
    Called from: A2UIMessageEmitter.data_patch_message
    Why: Enables efficient incremental updates.
    
    Args:
        source: Original object
        target: Desired object
        path: Base JSON pointer path (default: root)
        
    Returns:
        List of patch operations (RFC 6902 format)
    
    Example:
        >>> source = {"kpis": {"revenue": 100}}
        >>> target = {"kpis": {"revenue": 150, "margin": 25}}
        >>> make_patch(source, target)
        [
            {"op": "replace", "path": "/kpis/revenue", "value": 150},
            {"op": "add", "path": "/kpis/margin", "value": 25}
        ]
    """
    patch: Patch = []
    
    if source == target:
        return patch
    
    if not isinstance(source, dict) or not isinstance(target, dict):
        # If types differ or non-dict, replace entirely
        if source != target:
            patch.append({"op": "replace", "path": path or "/", "value": target})
        return patch
    
    # Find removed keys
    for key in source:
        if key not in target:
            patch.append({
                "op": "remove",
                "path": f"{path}/{_escape_key(key)}",
            })
    
    # Find added and changed keys
    for key, target_value in target.items():
        key_path = f"{path}/{_escape_key(key)}"
        
        if key not in source:
            # Key was added
            patch.append({
                "op": "add",
                "path": key_path,
                "value": target_value,
            })
        elif source[key] != target_value:
            source_value = source[key]
            
            # Recurse into nested dicts
            if isinstance(source_value, dict) and isinstance(target_value, dict):
                patch.extend(make_patch(source_value, target_value, key_path))
            # Handle arrays specially
            elif isinstance(source_value, list) and isinstance(target_value, list):
                # For arrays, we do a simple replace for now
                # (full array diff is complex and often not worth it)
                patch.append({
                    "op": "replace",
                    "path": key_path,
                    "value": target_value,
                })
            else:
                # Simple value change
                patch.append({
                    "op": "replace",
                    "path": key_path,
                    "value": target_value,
                })
    
    return patch


def _escape_key(key: str) -> str:
    """Escape special characters in JSON Pointer keys per RFC 6901."""
    return key.replace("~", "~0").replace("/", "~1")


def _unescape_key(key: str) -> str:
    """Unescape JSON Pointer key."""
    return key.replace("~1", "/").replace("~0", "~")


# ============================================================================
# Patch Application
# ============================================================================

def apply_patch(
    document: Dict[str, Any],
    patch: Patch,
    in_place: bool = False,
) -> Dict[str, Any]:
    """
    Apply RFC 6902 JSON Patch to a document.
    
    Function: apply_patch
    Role: Apply patch operations to reconstruct target state.
    Called from: Backend tests (frontend uses TypeScript equivalent)
    Why: Validates patches and enables server-side patch application.
    
    Args:
        document: Original document
        patch: List of patch operations
        in_place: If True, modify document in place (default: False)
        
    Returns:
        Patched document
        
    Raises:
        ValueError: If patch operation is invalid
    """
    if not in_place:
        document = copy.deepcopy(document)
    
    for op in patch:
        operation = op.get("op")
        path = op.get("path", "")
        
        if operation == "add":
            _apply_add(document, path, op.get("value"))
        elif operation == "remove":
            _apply_remove(document, path)
        elif operation == "replace":
            _apply_replace(document, path, op.get("value"))
        elif operation == "move":
            _apply_move(document, op.get("from", ""), path)
        elif operation == "copy":
            _apply_copy(document, op.get("from", ""), path)
        elif operation == "test":
            _apply_test(document, path, op.get("value"))
        else:
            raise ValueError(f"Unknown patch operation: {operation}")
    
    return document


def _parse_path(path: str) -> List[str]:
    """Parse JSON Pointer path into segments."""
    if not path or path == "/":
        return []
    if not path.startswith("/"):
        raise ValueError(f"Invalid JSON Pointer: {path}")
    return [_unescape_key(seg) for seg in path[1:].split("/")]


def _get_parent_and_key(document: Dict[str, Any], path: str) -> tuple:
    """Navigate to parent of path and return (parent, key)."""
    segments = _parse_path(path)
    if not segments:
        raise ValueError("Cannot get parent of root")
    
    parent = document
    for seg in segments[:-1]:
        if isinstance(parent, dict):
            parent = parent.get(seg, {})
        elif isinstance(parent, list):
            parent = parent[int(seg)]
        else:
            raise ValueError(f"Cannot navigate path: {path}")
    
    return parent, segments[-1]


def _apply_add(document: Dict[str, Any], path: str, value: Any) -> None:
    """Apply 'add' operation."""
    if not path or path == "/":
        # Replace entire document (not typical)
        document.clear()
        if isinstance(value, dict):
            document.update(value)
        return
    
    parent, key = _get_parent_and_key(document, path)
    
    if isinstance(parent, dict):
        parent[key] = value
    elif isinstance(parent, list):
        idx = int(key) if key != "-" else len(parent)
        parent.insert(idx, value)


def _apply_remove(document: Dict[str, Any], path: str) -> None:
    """Apply 'remove' operation."""
    parent, key = _get_parent_and_key(document, path)
    
    if isinstance(parent, dict):
        del parent[key]
    elif isinstance(parent, list):
        del parent[int(key)]


def _apply_replace(document: Dict[str, Any], path: str, value: Any) -> None:
    """Apply 'replace' operation."""
    if not path or path == "/":
        document.clear()
        if isinstance(value, dict):
            document.update(value)
        return
    
    parent, key = _get_parent_and_key(document, path)
    
    if isinstance(parent, dict):
        parent[key] = value
    elif isinstance(parent, list):
        parent[int(key)] = value


def _apply_move(document: Dict[str, Any], from_path: str, to_path: str) -> None:
    """Apply 'move' operation."""
    # Get value from source
    parent, key = _get_parent_and_key(document, from_path)
    value = parent[key] if isinstance(parent, dict) else parent[int(key)]
    
    # Remove from source
    _apply_remove(document, from_path)
    
    # Add to destination
    _apply_add(document, to_path, value)


def _apply_copy(document: Dict[str, Any], from_path: str, to_path: str) -> None:
    """Apply 'copy' operation."""
    # Get value from source
    parent, key = _get_parent_and_key(document, from_path)
    value = copy.deepcopy(
        parent[key] if isinstance(parent, dict) else parent[int(key)]
    )
    
    # Add to destination
    _apply_add(document, to_path, value)


def _apply_test(document: Dict[str, Any], path: str, expected: Any) -> None:
    """Apply 'test' operation."""
    if not path or path == "/":
        actual = document
    else:
        parent, key = _get_parent_and_key(document, path)
        actual = parent[key] if isinstance(parent, dict) else parent[int(key)]
    
    if actual != expected:
        raise ValueError(f"Test failed at {path}: expected {expected}, got {actual}")


# ============================================================================
# Patch Optimization
# ============================================================================

def optimize_patch(patch: Patch) -> Patch:
    """
    Optimize a patch by combining operations.
    
    Function: optimize_patch
    Role: Reduce patch size by merging redundant operations.
    Called from: make_patch (optionally)
    Why: Further reduces payload sizes.
    
    Args:
        patch: Original patch
        
    Returns:
        Optimized patch
    """
    if len(patch) <= 1:
        return patch
    
    optimized: Patch = []
    
    for op in patch:
        # Skip removes followed by adds to same path (replace)
        if optimized and op.get("op") == "add":
            last = optimized[-1]
            if last.get("op") == "remove" and last.get("path") == op.get("path"):
                optimized[-1] = {
                    "op": "replace",
                    "path": op.get("path"),
                    "value": op.get("value"),
                }
                continue
        
        optimized.append(op)
    
    return optimized


# ============================================================================
# Patch Statistics
# ============================================================================

def patch_stats(source: Dict[str, Any], target: Dict[str, Any], patch: Patch) -> Dict[str, Any]:
    """
    Compute statistics about patch efficiency.
    
    Function: patch_stats
    Role: Measure patch vs full replacement size savings.
    Called from: logging, debugging
    Why: Validates that patching provides real benefits.
    
    Args:
        source: Original document
        target: Target document
        patch: Generated patch
        
    Returns:
        Statistics dict with size comparisons
    """
    import json
    
    full_size = len(json.dumps(target))
    patch_size = len(json.dumps(patch))
    source_size = len(json.dumps(source))
    
    savings_bytes = full_size - patch_size
    savings_pct = (savings_bytes / full_size * 100) if full_size > 0 else 0
    
    return {
        "source_bytes": source_size,
        "target_bytes": full_size,
        "patch_bytes": patch_size,
        "patch_ops": len(patch),
        "savings_bytes": savings_bytes,
        "savings_percent": round(savings_pct, 1),
        "worth_patching": savings_pct > 10 and len(patch) < 50,
    }


__all__ = [
    "make_patch",
    "apply_patch",
    "optimize_patch",
    "patch_stats",
    "Patch",
    "PatchOperation",
]
