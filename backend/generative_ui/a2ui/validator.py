"""
A2UI Catalog Validator

Provides lightweight validation for surfaceUpdate payloads against the merged
standard (vendored JSON) and financial catalogs.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Set

from .catalog import FINANCIAL_CATALOG


def _load_standard_components() -> Set[str]:
    """
    Function: _load_standard_components — called from allowed_component_names;
    reads the vendored standard catalog JSON and returns the set of component
    names; exists to align validation with the official A2UI spec.
    """
    catalog_path = Path(__file__).with_name("standard_catalog_definition.json")
    if not catalog_path.exists():
        return set()
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    components = data.get("components", {})
    return set(components.keys())


@lru_cache(maxsize=1)
def allowed_component_names() -> Set[str]:
    """
    Function: allowed_component_names — called from validate_components and
    A2UIMessageGenerator.surface_update; merges standard + financial catalog
    component names to form the permitted set for rendering.
    """
    standard = _load_standard_components()
    financial = set(FINANCIAL_CATALOG.components.keys())
    return standard.union(financial)


def validate_components(component_names: Iterable[str]) -> List[str]:
    """
    Function: validate_components — called from A2UIMessageGenerator to ensure
    outgoing surfaceUpdate messages use only known catalog component types;
    returns a list of validation errors (empty when valid).
    """
    allowed = allowed_component_names()
    errors: List[str] = []
    for name in component_names:
        if name not in allowed:
            errors.append(f"Unknown component type: {name}")
    return errors
