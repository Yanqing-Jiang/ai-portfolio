"""
A2UI Protocol Implementation

Core A2UI v0.8 message types, emitter, and utilities.
"""

from .messages import (
    BeginRendering,
    SurfaceUpdate,
    DataModelUpdate,
    UserAction,
    DeleteSurface,
    A2UIComponent,
    BoundString,
    BoundNumber,
    BoundBoolean,
    BoundArray,
    DataEntry,
)
from .emitter import A2UIMessageEmitter, SkillRenderContext
from .catalog import FinancialCatalog, get_catalog

__all__ = [
    # Messages
    "BeginRendering",
    "SurfaceUpdate",
    "DataModelUpdate",
    "UserAction",
    "DeleteSurface",
    "A2UIComponent",
    # Bound values
    "BoundString",
    "BoundNumber",
    "BoundBoolean",
    "BoundArray",
    "DataEntry",
    # Emitter (replaces legacy A2UIMessageGenerator)
    "A2UIMessageEmitter",
    "SkillRenderContext",
    # Catalog
    "FinancialCatalog",
    "get_catalog",
]
