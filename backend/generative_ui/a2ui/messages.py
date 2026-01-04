# --- A2UI Message Function/Class Map ---
# Class: BoundString
#   Role: Represents literal or data-bound string values.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent builders, backend.generative_ui.a2ui.emitter
#   Invokes: pydantic validation
#   Why: Encodes bound values per the A2UI spec.
# Class: BoundNumber
#   Role: Represents literal or data-bound numeric values.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent builders
#   Invokes: pydantic validation
#   Why: Encodes bound numbers per the A2UI spec.
# Class: BoundBoolean
#   Role: Represents literal or data-bound boolean values.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent builders
#   Invokes: pydantic validation
#   Why: Encodes bound booleans per the A2UI spec.
# Class: BoundArray
#   Role: Represents literal or data-bound array values.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent builders
#   Invokes: pydantic validation
#   Why: Encodes bound arrays per the A2UI spec.
# Class: DataEntry
#   Role: Encode data model adjacency list entries.
#   Called from: backend.generative_ui.a2ui.emitter.A2UIMessageEmitter
#   Invokes: pydantic validation
#   Why: Serializes nested data model updates for A2UI.
# Class: ChildrenExplicitList
#   Role: Explicit list of child component IDs.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.row/column
#   Invokes: n/a
#   Why: Encodes static children in A2UI layouts.
# Class: ChildrenTemplate
#   Role: Data-driven children template definitions.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.row_template/column_template
#   Invokes: n/a
#   Why: Supports dynamic child rendering.
# Class: ActionContext
#   Role: Key/value context pair for actions.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.button
#   Invokes: n/a
#   Why: Supplies context payloads for user actions.
# Class: ComponentAction
#   Role: Action definition for interactive components.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.button
#   Invokes: n/a
#   Why: Encodes action metadata per A2UI spec.
# Class: TextComponent
#   Role: A2UI text display component schema.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.text/text_bound
#   Invokes: n/a
#   Why: Defines text widget structure.
# Class: RowComponent
#   Role: A2UI horizontal layout component schema.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.row/row_template
#   Invokes: n/a
#   Why: Defines row layout structure.
# Class: ColumnComponent
#   Role: A2UI vertical layout component schema.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.column/column_template
#   Invokes: n/a
#   Why: Defines column layout structure.
# Class: CardComponent
#   Role: A2UI card container schema.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.card
#   Invokes: n/a
#   Why: Wraps child widgets with card styling.
# Class: ButtonComponent
#   Role: A2UI button schema.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.button
#   Invokes: n/a
#   Why: Defines interactive button payloads.
# Class: ImageComponent
#   Role: A2UI image schema.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.image (via generic component usage)
#   Invokes: n/a
#   Why: Encodes image widgets.
# Class: DividerComponent
#   Role: A2UI divider schema.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.divider (via generic component usage)
#   Invokes: n/a
#   Why: Encodes divider widgets.
# Class: PriceChartComponent
#   Role: Price chart schema for TradingView widgets.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.price_chart
#   Invokes: n/a
#   Why: Encodes price chart payloads.
# Class: KpiCardComponent
#   Role: KPI card schema for metric callouts.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.kpi_card
#   Invokes: n/a
#   Why: Encodes KPI widgets.
# Class: DataTableComponent
#   Role: Data table schema.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.data_table
#   Invokes: n/a
#   Why: Encodes sortable tables.
# Class: NewsTimelineComponent
#   Role: News timeline schema.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.news_timeline
#   Invokes: n/a
#   Why: Encodes news timeline widgets.
# Class: CorrelationMatrixComponent
#   Role: Correlation matrix schema.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.correlation_matrix
#   Invokes: n/a
#   Why: Encodes correlation heatmap widgets.
# Class: MetricChartComponent
#   Role: Metric chart schema for ECharts widgets.
#   Called from: backend.generative_ui.a2ui.messages.A2UIComponent.metric_chart
#   Invokes: n/a
#   Why: Encodes metric chart payloads.
# Class: A2UIComponent
#   Role: Wrapper for A2UI components and builder helpers.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: Pydantic model_dump
#   Why: Provides ergonomic construction for A2UI layouts.
# Method: A2UIComponent.text
#   Role: Build literal Text components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Simplifies text component creation.
# Method: A2UIComponent.text_bound
#   Role: Build data-bound Text components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Binds text to data model paths.
# Method: A2UIComponent.row
#   Role: Build Row layout components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encodes horizontal layouts.
# Method: A2UIComponent.row_template
#   Role: Build Row layouts from templates.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Supports data-driven row layouts.
# Method: A2UIComponent.column
#   Role: Build Column layout components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encodes vertical layouts.
# Method: A2UIComponent.column_template
#   Role: Build Column layouts from templates.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Supports data-driven column layouts.
# Method: A2UIComponent.card
#   Role: Build Card containers.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encapsulates widgets in card shells.
# Method: A2UIComponent.button
#   Role: Build interactive Button components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encodes actions for user interaction.
# Method: A2UIComponent.price_chart
#   Role: Build PriceChart components with bound interval support.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Powers TradingView price visuals.
# Method: A2UIComponent.kpi_card
#   Role: Build KPI card components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encodes KPI widgets for dashboards.
# Method: A2UIComponent.data_table
#   Role: Build DataTable components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encodes tabular outputs.
# Method: A2UIComponent.news_timeline
#   Role: Build NewsTimeline components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encodes news timeline widgets.
# Method: A2UIComponent.correlation_matrix
#   Role: Build CorrelationMatrix components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encodes correlation heatmaps.
# Method: A2UIComponent.explain_move_panel
#   Role: Build ExplainMovePanel components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encodes narrative/explanation panels.
# Method: A2UIComponent.error_panel
#   Role: Build ErrorPanel components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encodes error displays for A2UI.
# Method: A2UIComponent.metric_chart
#   Role: Build MetricChart components.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: n/a
#   Why: Encodes metric chart widgets.
# Class: BeginRendering
#   Role: BeginRendering message schema.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: BeginRendering.to_json
#   Why: Boots A2UI surfaces.
# Method: BeginRendering.to_json
#   Role: Serialize BeginRendering message to JSON.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: json.dumps
#   Why: Sends SSE payloads for surface initialization.
# Class: SurfaceUpdate
#   Role: SurfaceUpdate message schema.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: SurfaceUpdate.to_json
#   Why: Adds components to an A2UI surface.
# Method: SurfaceUpdate.to_json
#   Role: Serialize SurfaceUpdate message to JSON.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: json.dumps
#   Why: Sends SSE payloads for layout updates.
# Class: DataModelUpdate
#   Role: DataModelUpdate message schema.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: DataModelUpdate.to_json
#   Why: Updates surface data model state.
# Method: DataModelUpdate.to_json
#   Role: Serialize DataModelUpdate message to JSON.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: json.dumps, DataModelUpdate._serialize_entry
#   Why: Sends SSE payloads for data updates.
# Method: DataModelUpdate._serialize_entry
#   Role: Serialize DataEntry values recursively.
#   Called from: DataModelUpdate.to_json
#   Invokes: n/a
#   Why: Converts nested data entries to JSON.
# Class: UserAction
#   Role: Client-to-server action schema.
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: n/a
#   Why: Defines userAction payload shape.
# Class: DeleteSurface
#   Role: DeleteSurface message schema.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: DeleteSurface.to_json
#   Why: Removes A2UI surfaces.
# Method: DeleteSurface.to_json
#   Role: Serialize DeleteSurface message to JSON.
#   Called from: backend.generative_ui.a2ui.emitter
#   Invokes: json.dumps
#   Why: Sends SSE payloads for surface teardown.
# --- End A2UI Message Function/Class Map ---
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


class MetricChartComponent(BaseModel):
    """ECharts-based time-series chart for financial metrics."""
    title: Optional[BoundString] = None
    series: BoundArray  # Array of {ticker, data: [{period, value}]}
    annotations: Optional[BoundArray] = None # Array of {period, ticker, label, details}
    metric: Optional[BoundString] = None  # e.g., "Revenue", "Net Income"
    chartType: Optional[BoundString] = None  # "line", "bar", "area"


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
    def row_template(cls, id: str, template: str, data_path: str, alignment: str = None) -> "A2UIComponent":
        """Create a Row component using ChildrenTemplate."""
        comp = {"children": {"template": template, "dataPath": data_path}}
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
    def column_template(cls, id: str, template: str, data_path: str, alignment: str = None) -> "A2UIComponent":
        """Create a Column component using ChildrenTemplate."""
        comp = {"children": {"template": template, "dataPath": data_path}}
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
    def price_chart(
        cls,
        id: str,
        ticker_path: str,
        interval: str = "1D",
        show_volume: bool = True,
        interval_path: Optional[str] = None,
    ) -> "A2UIComponent":
        """Create a PriceChart component."""
        interval_value: Dict[str, Any] = {"literalString": interval}
        if interval_path:
            interval_value = {"path": interval_path}
        return cls(id=id, component={"PriceChart": {
            "ticker": {"path": ticker_path},
            "interval": interval_value,
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
    
    @classmethod
    def explain_move_panel(
        cls,
        id: str,
        title_path: str,
        explanation_path: str,
        factors_path: Optional[str] = None,
        citations_path: Optional[str] = None,
    ) -> "A2UIComponent":
        """Create an ExplainMovePanel component."""
        comp: Dict[str, Any] = {
            "title": {"path": title_path},
            "explanation": {"path": explanation_path},
        }
        if factors_path:
            comp["factors"] = {"path": factors_path}
        if citations_path:
            comp["citations"] = {"path": citations_path}
        return cls(id=id, component={"ExplainMovePanel": comp})
    
    @classmethod
    def error_panel(cls, id: str, code_path: str, message_path: str, details_path: Optional[str] = None) -> "A2UIComponent":
        """Create an ErrorPanel component."""
        payload = {
            "code": {"path": code_path},
            "message": {"path": message_path},
        }
        if details_path:
            payload["details"] = {"path": details_path}
        return cls(id=id, component={"ErrorPanel": payload})

    @classmethod
    def metric_chart(
        cls,
        id: str,
        series_path: str,
        title_path: Optional[str] = None,
        title_literal: Optional[str] = None,
        metric: str = "Value",
        chart_type: str = "line",
        annotations_path: Optional[str] = None,
    ) -> "A2UIComponent":
        """Create a MetricChart component (ECharts-based time-series)."""
        comp: Dict[str, Any] = {
            "series": {"path": series_path},
            "metric": {"literalString": metric},
            "chartType": {"literalString": chart_type},
        }
        if title_path:
            comp["title"] = {"path": title_path}
        elif title_literal:
            comp["title"] = {"literalString": title_literal}
        
        if annotations_path:
            comp["annotations"] = {"path": annotations_path}
            
        return cls(id=id, component={"MetricChart": comp})

    @classmethod
    def peer_compare_panel(
        cls,
        id: str,
        title_path: str,
        metric_literal: str,
        tickers_path: str,
        chart_series_path: str,
        table_columns_path: str,
        table_rows_path: str,
        explanation_title_path: str,
        explanation_text_path: str,
    ) -> "A2UIComponent":
        """Create a PeerComparePanel component - consolidated comparison view."""
        comp: Dict[str, Any] = {
            "title": {"path": title_path},
            "metric": {"literalString": metric_literal},
            "tickers": {"path": tickers_path},
            "chart": {
                "series": {"path": chart_series_path},
            },
            "table": {
                "columns": {"path": table_columns_path},
                "rows": {"path": table_rows_path},
            },
            "explanation": {
                "title": {"path": explanation_title_path},
                "text": {"path": explanation_text_path},
            },
        }
        return cls(id=id, component={"PeerComparePanel": comp})


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
