"""
A2UI Protocol Message Types (v0.8)

Pydantic models matching the A2UI specification.
See: https://a2ui.org/specification/v0.8-a2ui/
"""

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
import json


# ============================================================================
# Bound Value Types
# ============================================================================

class BoundString(BaseModel):
    """A string value that can be literal or data-bound."""
    literalString: Optional[str] = None
    path: Optional[str] = None  # JSON Pointer, e.g., "/data/title"


class BoundNumber(BaseModel):
    """A number value that can be literal or data-bound."""
    literalNumber: Optional[float] = None
    path: Optional[str] = None


class BoundBoolean(BaseModel):
    """A boolean value that can be literal or data-bound."""
    literalBoolean: Optional[bool] = None
    path: Optional[str] = None


class BoundArray(BaseModel):
    """An array value that can be literal or data-bound."""
    literalArray: Optional[List[Any]] = None
    path: Optional[str] = None


# Union type for any bound value
BoundValue = Union[BoundString, BoundNumber, BoundBoolean, BoundArray]


# ============================================================================
# Data Model Types
# ============================================================================

class DataEntry(BaseModel):
    """A single entry in the data model adjacency list."""
    key: str
    valueString: Optional[str] = None
    valueNumber: Optional[float] = None
    valueBoolean: Optional[bool] = None
    valueMap: Optional[List["DataEntry"]] = None
    valueArray: Optional[List[Any]] = None


# ============================================================================
# Component Types
# ============================================================================

class ChildrenExplicitList(BaseModel):
    """Explicit list of child component IDs."""
    explicitList: List[str]


class ChildrenTemplate(BaseModel):
    """Template for dynamic children based on data array."""
    template: str
    dataPath: str


Children = Union[ChildrenExplicitList, ChildrenTemplate]


class ActionContext(BaseModel):
    """Context to include with an action."""
    key: str
    value: BoundValue


class ComponentAction(BaseModel):
    """Action definition for interactive components."""
    name: str
    context: Optional[List[ActionContext]] = None


# ============================================================================
# Standard Components
# ============================================================================

class TextComponent(BaseModel):
    """Text display component."""
    text: BoundString
    usageHint: Optional[Literal["h1", "h2", "h3", "body", "caption"]] = None


class RowComponent(BaseModel):
    """Horizontal layout component."""
    children: Children
    alignment: Optional[Literal["start", "center", "end", "spaceBetween", "spaceAround"]] = None


class ColumnComponent(BaseModel):
    """Vertical layout component."""
    children: Children
    alignment: Optional[Literal["start", "center", "end", "stretch"]] = None


class CardComponent(BaseModel):
    """Container with border/shadow."""
    child: str  # ID of child component


class ButtonComponent(BaseModel):
    """Interactive button."""
    label: BoundString
    action: ComponentAction
    variant: Optional[Literal["primary", "secondary", "text"]] = None


class ImageComponent(BaseModel):
    """Image display."""
    url: BoundString
    alt: Optional[BoundString] = None


class DividerComponent(BaseModel):
    """Visual divider."""
    pass


# ============================================================================
# Custom Financial Components
# ============================================================================

class PriceChartComponent(BaseModel):
    """TradingView-powered candlestick chart."""
    ticker: BoundString
    interval: Optional[BoundString] = None  # 1D, 1W, 1M, etc.
    showVolume: Optional[BoundBoolean] = None


class KpiCardComponent(BaseModel):
    """Single metric KPI display."""
    label: BoundString
    value: BoundNumber
    unit: Optional[BoundString] = None
    delta: Optional[BoundNumber] = None
    deltaType: Optional[BoundString] = None  # "percentage" or "absolute"


class DataTableComponent(BaseModel):
    """Sortable financial data table."""
    columns: BoundArray
    data: BoundArray
    sortable: Optional[BoundBoolean] = None


class NewsTimelineComponent(BaseModel):
    """Vertical timeline of news events with sentiment."""
    events: BoundArray


class CorrelationMatrixComponent(BaseModel):
    """ECharts heatmap for correlations."""
    tickers: BoundArray
    matrix: BoundArray


# ============================================================================
# A2UI Component Wrapper
# ============================================================================

class A2UIComponent(BaseModel):
    """
    A single component in the A2UI component tree.
    
    Each component has a unique ID and exactly one component type definition.
    """
    id: str
    weight: Optional[float] = None  # Flex weight when child of Row/Column
    component: Dict[str, Any]  # The actual component, e.g., {"Text": {...}}
    
    @classmethod
    def text(cls, id: str, text: str, usage_hint: str = None) -> "A2UIComponent":
        """Create a Text component."""
        comp = {"text": {"literalString": text}}
        if usage_hint:
            comp["usageHint"] = usage_hint
        return cls(id=id, component={"Text": comp})
    
    @classmethod
    def text_bound(cls, id: str, path: str, usage_hint: str = None) -> "A2UIComponent":
        """Create a data-bound Text component."""
        comp = {"text": {"path": path}}
        if usage_hint:
            comp["usageHint"] = usage_hint
        return cls(id=id, component={"Text": comp})
    
    @classmethod
    def row(cls, id: str, children: List[str], alignment: str = None) -> "A2UIComponent":
        """Create a Row component."""
        comp = {"children": {"explicitList": children}}
        if alignment:
            comp["alignment"] = alignment
        return cls(id=id, component={"Row": comp})
    
    @classmethod
    def column(cls, id: str, children: List[str], alignment: str = None) -> "A2UIComponent":
        """Create a Column component."""
        comp = {"children": {"explicitList": children}}
        if alignment:
            comp["alignment"] = alignment
        return cls(id=id, component={"Column": comp})
    
    @classmethod
    def card(cls, id: str, child: str) -> "A2UIComponent":
        """Create a Card component."""
        return cls(id=id, component={"Card": {"child": child}})
    
    @classmethod
    def button(cls, id: str, label: str, action_name: str, context: Dict[str, Any] = None) -> "A2UIComponent":
        """Create a Button component."""
        action = {"name": action_name}
        if context:
            action["context"] = [
                {"key": k, "value": {"literalString": str(v)} if isinstance(v, str) else {"literalNumber": v}}
                for k, v in context.items()
            ]
        return cls(id=id, component={"Button": {"label": {"literalString": label}, "action": action}})
    
    @classmethod
    def price_chart(cls, id: str, ticker_path: str, interval: str = "1D", show_volume: bool = True) -> "A2UIComponent":
        """Create a PriceChart component."""
        return cls(id=id, component={"PriceChart": {
            "ticker": {"path": ticker_path},
            "interval": {"literalString": interval},
            "showVolume": {"literalBoolean": show_volume}
        }})
    
    @classmethod
    def kpi_card(cls, id: str, label: str, value_path: str, unit: str = None, delta_path: str = None) -> "A2UIComponent":
        """Create a KpiCard component."""
        comp = {
            "label": {"literalString": label},
            "value": {"path": value_path}
        }
        if unit:
            comp["unit"] = {"literalString": unit}
        if delta_path:
            comp["delta"] = {"path": delta_path}
        return cls(id=id, component={"KpiCard": comp})
    
    @classmethod
    def data_table(cls, id: str, columns_path: str, data_path: str, sortable: bool = True) -> "A2UIComponent":
        """Create a DataTable component."""
        return cls(id=id, component={"DataTable": {
            "columns": {"path": columns_path},
            "data": {"path": data_path},
            "sortable": {"literalBoolean": sortable}
        }})
    
    @classmethod
    def news_timeline(cls, id: str, events_path: str) -> "A2UIComponent":
        """Create a NewsTimeline component."""
        return cls(id=id, component={"NewsTimeline": {"events": {"path": events_path}}})
    
    @classmethod
    def correlation_matrix(cls, id: str, tickers_path: str, matrix_path: str) -> "A2UIComponent":
        """Create a CorrelationMatrix component."""
        return cls(id=id, component={"CorrelationMatrix": {
            "tickers": {"path": tickers_path},
            "matrix": {"path": matrix_path}
        }})


# ============================================================================
# A2UI Messages
# ============================================================================

class BeginRendering(BaseModel):
    """Initialize a surface and set the root component."""
    surfaceId: str
    root: str
    catalogId: Optional[str] = None
    
    def to_json(self) -> str:
        return json.dumps({"beginRendering": self.model_dump(exclude_none=True)})


class SurfaceUpdate(BaseModel):
    """Add or update components in a surface."""
    surfaceId: str
    components: List[A2UIComponent]
    
    def to_json(self) -> str:
        return json.dumps({
            "surfaceUpdate": {
                "surfaceId": self.surfaceId,
                "components": [c.model_dump(exclude_none=True) for c in self.components]
            }
        })


class DataModelUpdate(BaseModel):
    """Update the data model for a surface."""
    surfaceId: str
    contents: List[DataEntry]
    path: Optional[str] = None  # Optional path prefix
    
    def to_json(self) -> str:
        data = {
            "surfaceId": self.surfaceId,
            "contents": [self._serialize_entry(e) for e in self.contents]
        }
        if self.path:
            data["path"] = self.path
        return json.dumps({"dataModelUpdate": data})
    
    def _serialize_entry(self, entry: DataEntry) -> dict:
        result = {"key": entry.key}
        if entry.valueString is not None:
            result["valueString"] = entry.valueString
        elif entry.valueNumber is not None:
            result["valueNumber"] = entry.valueNumber
        elif entry.valueBoolean is not None:
            result["valueBoolean"] = entry.valueBoolean
        elif entry.valueMap is not None:
            result["valueMap"] = [self._serialize_entry(e) for e in entry.valueMap]
        elif entry.valueArray is not None:
            result["valueArray"] = entry.valueArray
        return result


class UserAction(BaseModel):
    """Client-to-server action message."""
    name: str
    surfaceId: str
    sourceComponentId: str
    timestamp: str  # ISO 8601
    context: Dict[str, Any] = Field(default_factory=dict)


class DeleteSurface(BaseModel):
    """Clean up a surface."""
    surfaceId: str
    
    def to_json(self) -> str:
        return json.dumps({"deleteSurface": {"surfaceId": self.surfaceId}})
