"""
A2UI Message Generator

Converts structured dashboard plans into A2UI message streams.
"""

from __future__ import annotations
from typing import Any, Dict, Generator, List, Optional

from .messages import (
    A2UIComponent,
    BeginRendering,
    SurfaceUpdate,
    DataModelUpdate,
    DataEntry,
    DeleteSurface,
)
from ..models.dashboard_plan import DashboardPlan, DashboardWidget
from .validator import validate_components


class A2UIMessageGenerator:
    """
    Generates A2UI protocol messages for dashboard rendering.
    
    Usage:
        generator = A2UIMessageGenerator("dashboard_123")
        for msg in generator.generate_from_plan(plan):
            yield f"data: {msg}\\n\\n"
    """
    
    def __init__(self, surface_id: str, catalog_id: Optional[str] = None):
        """
        Function: __init__ — called from dashboard routes and agent; configures
        surface_id + catalog_id and sets up internal counters; exists to
        centralize catalog alignment across surfaces.
        """
        self.surface_id = surface_id
        self.catalog_id = catalog_id or "financial-standard-v1"
        self._component_counter = 0
    
    def _next_id(self, prefix: str = "comp") -> str:
        """Generate a unique component ID."""
        self._component_counter += 1
        return f"{prefix}_{self._component_counter}"
    
    # ========================================================================
    # Core Message Generators
    # ========================================================================
    
    def begin_rendering(self, root_id: str = "root") -> str:
        """Generate beginRendering message."""
        msg = BeginRendering(
            surfaceId=self.surface_id,
            root=root_id,
            catalogId=self.catalog_id
        )
        return msg.to_json()
    
    def surface_update(self, components: List[A2UIComponent]) -> str:
        """
        Generate surfaceUpdate message after validating component types.
        Raises ValueError when unknown components are present.
        """
        component_names = []
        for comp in components:
            # comp.component is dict like {"Text": {...}}
            if comp.component:
                component_names.extend(list(comp.component.keys()))
        errors = validate_components(component_names)
        if errors:
            raise ValueError("; ".join(errors))
        msg = SurfaceUpdate(surfaceId=self.surface_id, components=components)
        return msg.to_json()
    
    def data_model_update(
        self, 
        contents: List[DataEntry], 
        path: Optional[str] = None
    ) -> str:
        """Generate dataModelUpdate message."""
        msg = DataModelUpdate(
            surfaceId=self.surface_id,
            contents=contents,
            path=path
        )
        return msg.to_json()
    
    def delete_surface(self) -> str:
        """Generate deleteSurface message."""
        msg = DeleteSurface(surfaceId=self.surface_id)
        return msg.to_json()
    
    # ========================================================================
    # High-Level Plan to A2UI Conversion
    # ========================================================================
    
    def generate_from_plan(
        self, 
        plan: DashboardPlan
    ) -> Generator[str, None, None]:
        """
        Convert a DashboardPlan into a stream of A2UI messages.
        
        This streams the component structure progressively, allowing
        the UI to render incrementally as messages arrive.
        """
        # 1. Begin rendering with root
        yield self.begin_rendering()
        
        # 2. Build header section
        yield self._create_header(plan)
        
        # 3. Build widget grid
        widget_ids = []
        for i, widget in enumerate(plan.widgets):
            widget_id = f"widget_{i}"
            widget_ids.append(widget_id)
            yield self._create_widget(widget_id, widget)
        
        # 4. Create the main layout structure
        yield self._create_layout(widget_ids, plan)
        
        # 5. Initialize data model with params
        yield self._create_initial_data(plan)
    
    def _create_header(self, plan: DashboardPlan) -> str:
        """Create header components."""
        components = [
            A2UIComponent.text_bound("header_title", "/dashboard/title", "h2"),
            A2UIComponent.text_bound("header_subtitle", "/dashboard/subtitle", "caption"),
            A2UIComponent.column("header", ["header_title", "header_subtitle"]),
        ]
        return self.surface_update(components)
    
    def _create_widget(self, widget_id: str, widget: DashboardWidget) -> str:
        """Create a single widget component based on type."""
        if widget.type == "price_chart":
            component = A2UIComponent.price_chart(
                widget_id,
                ticker_path="/params/ticker",
                interval=widget.config.get("interval", "1D"),
                show_volume=widget.config.get("showVolume", True)
            )
        elif widget.type == "kpi":
            component = A2UIComponent.kpi_card(
                widget_id,
                label=widget.config.get("label", "Value"),
                value_path=f"/data/{widget.config.get('dataKey', 'value')}",
                unit=widget.config.get("unit"),
                delta_path=f"/data/{widget.config.get('deltaKey')}" if widget.config.get("deltaKey") else None
            )
        elif widget.type == "table":
            component = A2UIComponent.data_table(
                widget_id,
                columns_path="/data/tableColumns",
                data_path="/data/tableRows",
                sortable=widget.config.get("sortable", True)
            )
        elif widget.type == "news_timeline":
            component = A2UIComponent.news_timeline(
                widget_id,
                events_path="/data/newsEvents"
            )
        elif widget.type == "correlation":
            component = A2UIComponent.correlation_matrix(
                widget_id,
                tickers_path="/data/correlationTickers",
                matrix_path="/data/correlationMatrix"
            )
        elif widget.type == "explain_move":
            component = A2UIComponent.explain_move_panel(
                widget_id,
                title_path="/data/explain/title",
                explanation_path="/data/explain/summary",
                factors_path="/data/explain/factors",
                citations_path="/data/explain/citations",
            )
        else:
            # Default to text placeholder
            component = A2UIComponent.text(
                widget_id,
                f"Unknown widget type: {widget.type}"
            )
        
        # Wrap in card
        card_id = f"{widget_id}_card"
        card = A2UIComponent.card(card_id, widget_id)
        
        return self.surface_update([component, card])
    
    def _create_layout(self, widget_ids: List[str], plan: DashboardPlan) -> str:
        """Create the main layout structure."""
        # Wrap widget IDs in their cards
        card_ids = [f"{wid}_card" for wid in widget_ids]
        
        # Create grid layout
        # For simplicity, create rows of 2 widgets each
        rows = []
        for i in range(0, len(card_ids), 2):
            row_id = f"row_{i // 2}"
            row_children = card_ids[i:i+2]
            rows.append(A2UIComponent.row(row_id, row_children))
        
        row_ids = [f"row_{i}" for i in range(len(rows))]
        
        # Add action bar with timeframe buttons
        action_buttons = self._create_action_bar()
        
        # Create root structure
        components = [
            *rows,
            *action_buttons,
            A2UIComponent.row("action_bar", [ab.id for ab in action_buttons]),
            A2UIComponent.column("main_content", row_ids),
            A2UIComponent.column("root", ["header", "action_bar", "main_content"]),
        ]
        
        return self.surface_update(components)
    
    def _create_action_bar(self) -> List[A2UIComponent]:
        """Create timeframe selector buttons."""
        timeframes = ["1D", "1W", "1M", "3M", "6M", "1Y"]
        buttons = []
        
        for tf in timeframes:
            btn = A2UIComponent.button(
                f"btn_{tf.lower()}",
                label=tf,
                action_name="change_timeframe",
                context={"timeframe": tf}
            )
            buttons.append(btn)
        
        return buttons
    
    def _create_initial_data(self, plan: DashboardPlan) -> str:
        """Create initial data model with dashboard params."""
        contents = [
            DataEntry(
                key="dashboard",
                valueMap=[
                    DataEntry(key="title", valueString=plan.title),
                    DataEntry(key="subtitle", valueString=f"Analysis for {plan.ticker}"),
                ]
            ),
            DataEntry(
                key="params",
                valueMap=[
                    DataEntry(key="ticker", valueString=plan.ticker),
                    DataEntry(key="timeRange", valueString=plan.time_range),
                    *[DataEntry(key=f"peer_{i}", valueString=peer) for i, peer in enumerate(plan.peers)]
                ]
            ),
            DataEntry(
                key="data",
                valueMap=[]  # Will be populated by data fetch
            ),
        ]
        
        return self.data_model_update(contents)
    
    def error_surface(self, code: str, message: str) -> List[str]:
        """
        Create messages that render an ErrorPanel bound to /data/error.
        """
        components = [
            A2UIComponent.error_panel("error_panel", "/data/error/code", "/data/error/message", "/data/error/details"),
            A2UIComponent.card("error_card", "error_panel"),
            A2UIComponent.column("error_root", ["error_card"]),
            A2UIComponent.column("root", ["error_root"]),
        ]
        # Surface update + data
        surface_msg = self.surface_update(components)
        data_msg = self.data_model_update([
            DataEntry(
                key="error",
                valueMap=[
                    DataEntry(key="code", valueString=code),
                    DataEntry(key="message", valueString=message),
                ],
            )
        ], path="/data")
        return [surface_msg, data_msg]
    
    # ========================================================================
    # Data Update Helpers
    # ========================================================================
    
    def update_price_data(
        self,
        price: float,
        volume: int,
        change: float,
        change_percent: float
    ) -> str:
        """Update price-related KPI data."""
        contents = [
            DataEntry(key="price", valueNumber=price),
            DataEntry(key="volume", valueNumber=volume),
            DataEntry(key="change", valueNumber=change),
            DataEntry(key="changePercent", valueNumber=change_percent),
        ]
        return self.data_model_update(contents, path="/data")
    
    def update_table_data(
        self,
        columns: List[Dict[str, Any]],
        rows: List[Dict[str, Any]]
    ) -> str:
        """Update table data."""
        contents = [
            DataEntry(key="tableColumns", valueArray=columns),
            DataEntry(key="tableRows", valueArray=rows),
        ]
        return self.data_model_update(contents, path="/data")
    
    def update_news_data(self, events: List[Dict[str, Any]]) -> str:
        """Update news timeline data."""
        contents = [
            DataEntry(key="newsEvents", valueArray=events),
        ]
        return self.data_model_update(contents, path="/data")
    
    def update_correlation_data(
        self,
        tickers: List[str],
        matrix: List[List[float]]
    ) -> str:
        """Update correlation matrix data."""
        contents = [
            DataEntry(key="correlationTickers", valueArray=tickers),
            DataEntry(key="correlationMatrix", valueArray=matrix),
        ]
        return self.data_model_update(contents, path="/data")
