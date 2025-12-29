"""
A2UI Protocol Implementation

Core A2UI v0.8 message types, generator, and utilities.
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
from .generator import A2UIMessageGenerator
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
    # Generator
    "A2UIMessageGenerator",
    # Catalog
    "FinancialCatalog",
    "get_catalog",
]
