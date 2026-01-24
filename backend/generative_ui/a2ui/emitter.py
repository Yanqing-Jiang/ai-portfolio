# --- A2UI Emitter Function/Class Map ---
# Dataclass: SkillRenderContext
#   Role: Supplies normalized rendering inputs for A2UI layout builders.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent
#   Invokes: n/a
#   Why: Keeps A2UI layout generation independent of model selection details.
# Class: A2UIMessageEmitter
#   Role: Build A2UI JSON messages for skill-driven dashboard layouts.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent
#   Invokes: backend.generative_ui.a2ui.messages.BeginRendering/SurfaceUpdate/DataModelUpdate, backend.generative_ui.a2ui.validator.validate_components
#   Why: Centralizes A2UI message construction for the new agent flow.
# Method: A2UIMessageEmitter.__init__
#   Role: Initialize emitter with surface + catalog identifiers.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: backend.generative_ui.a2ui.catalog.get_catalog
#   Why: Ensures emitted messages declare the correct catalog.
# Method: A2UIMessageEmitter.begin_rendering
#   Role: Emit beginRendering JSON for a surface.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: BeginRendering.to_json
#   Why: Boots the A2UI surface before layout updates.
# Method: A2UIMessageEmitter.surface_update
#   Role: Emit surfaceUpdate JSON with catalog validation.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: validate_components, SurfaceUpdate.to_json
#   Why: Guarantees only allowed components are rendered.
# Method: A2UIMessageEmitter.data_update
#   Role: Emit dataModelUpdate JSON from nested dictionaries.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: A2UIMessageEmitter._data_entries_from_dict, DataModelUpdate.to_json
#   Why: Converts Python data into A2UI data model entries.
# Method: A2UIMessageEmitter.error_surface
#   Role: Emit ErrorPanel layout + bound error data.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: A2UIMessageEmitter.surface_update, A2UIMessageEmitter.data_update
#   Why: Provides consistent error rendering on failures.
# Method: A2UIMessageEmitter.build_components_for_skill
#   Role: Generate the component tree for a specific A2UI skill.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: A2UIMessageEmitter._build_* layout helpers
#   Why: Maps skill metadata into concrete A2UI layouts.
# Method: A2UIMessageEmitter._data_entries_from_dict
#   Role: Convert nested dictionaries into DataEntry lists.
#   Called from: A2UIMessageEmitter.data_update
#   Invokes: DataEntry
#   Why: Keeps data-model serialization in one place.
# Method: A2UIMessageEmitter._build_explain_move_layout
#   Role: Build the split-view layout for explain-move dashboards.
#   Called from: A2UIMessageEmitter.build_components_for_skill
#   Invokes: A2UIComponent builders
#   Why: Aligns explain-move widgets with A2UI layout expectations.
# Method: A2UIMessageEmitter._build_peer_compare_layout
#   Role: Build the grid layout for peer comparison dashboards with MetricChart + correlation.
#   Called from: A2UIMessageEmitter.build_components_for_skill
#   Invokes: A2UIComponent builders
#   Why: Arranges comparison widgets consistently.
# Method: A2UIMessageEmitter._build_margin_analysis_layout
#   Role: Build the compact layout for margin analysis dashboards.
#   Called from: A2UIMessageEmitter.build_components_for_skill
#   Invokes: A2UIComponent builders
#   Why: Keeps margin KPIs and history aligned.
# Method: A2UIMessageEmitter._build_revenue_trend_layout
#   Role: Build the standard layout for revenue trend dashboards.
#   Called from: A2UIMessageEmitter.build_components_for_skill
#   Invokes: A2UIComponent builders
#   Why: Presents trend KPIs alongside chart + table.
# --- End A2UI Emitter Function/Class Map ---
"""
A2UI message emitter for skill-driven dashboards.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

from .catalog import get_catalog
from .messages import (
    A2UIComponent,
    BeginRendering,
    SurfaceUpdate,
    DataModelUpdate,
    DataEntry,
)
from .validator import validate_components
from ..skills import A2UISkillMeta


@dataclass(frozen=True)
class SkillRenderContext:
    """Normalized render context for skill layouts."""

    title: str
    primary_ticker: str
    tickers: List[str]
    time_range: str
    metric: str


class A2UIMessageEmitter:
    """Builds A2UI JSON payloads for dashboards."""

    def __init__(self, surface_id: str, catalog_id: Optional[str] = None) -> None:
        """Initialize emitter with surface + catalog identifiers."""
        self.surface_id = surface_id
        self.catalog_id = catalog_id or get_catalog().catalog_id

    def begin_rendering(self, root_id: str = "layout_root") -> str:
        """Create a beginRendering message."""
        msg = BeginRendering(surfaceId=self.surface_id, root=root_id, catalogId=self.catalog_id)
        return msg.to_json()

    def surface_update(self, components: List[A2UIComponent]) -> str:
        """Create a surfaceUpdate message after validating components."""
        component_names: List[str] = []
        for comp in components:
            if comp.component:
                component_names.extend(list(comp.component.keys()))
        errors = validate_components(component_names)
        if errors:
            raise ValueError("; ".join(errors))
        msg = SurfaceUpdate(surfaceId=self.surface_id, components=components)
        return msg.to_json()

    def data_update(self, data: Dict[str, Any], path: str = "/data") -> str:
        """Create a dataModelUpdate message from nested data."""
        contents = self._data_entries_from_dict(data)
        msg = DataModelUpdate(surfaceId=self.surface_id, contents=contents, path=path)
        return msg.to_json()

    def audit(self, event: str, details: Optional[str] = None) -> str:
        """Create a custom audit event message (non-standard A2UI)."""
        return json.dumps({
            "audit": {
                "event": event,
                "details": details,
                "timestamp": datetime.now().isoformat()
            }
        })

    def error_surface(self, code: str, message: str) -> List[str]:
        """Create error layout + data payloads."""
        components = [
            A2UIComponent.error_panel("error_panel", "/data/error/code", "/data/error/message", "/data/error/details"),
            A2UIComponent.card("error_card", "error_panel"),
            A2UIComponent.column("error_root", ["error_card"]),
            A2UIComponent.column("layout_root", ["error_root"]),
        ]
        surface_msg = self.surface_update(components)
        data_msg = self.data_update({"error": {"code": code, "message": message}})
        return [surface_msg, data_msg]

    def delete_surface(self) -> str:
        """
        Create a deleteSurface message to clean up the surface.
        
        Per A2UI v0.8 spec, this message removes a surface and its contents from the UI.
        See: https://a2ui.org/specification/v0.8-a2ui/#section-5-event-handling
        
        Function: delete_surface
        Called from: backend.generative_ui.routes.dashboard.delete_dashboard
        Invokes: DeleteSurface.to_json
        Why: Proper surface lifecycle cleanup per A2UI spec.
        """
        from .messages import DeleteSurface
        msg = DeleteSurface(surfaceId=self.surface_id)
        return msg.to_json()

    def build_components_for_skill(
        self,
        skill: A2UISkillMeta,
        context: SkillRenderContext,
        *,
        variant: str | None = None,
        widget_order: Optional[List[str]] = None,
        hidden_widgets: Optional[List[str]] = None,
        emphasis: Optional[str] = None,
    ) -> List[A2UIComponent]:
        """Build the component tree for a given skill with optional overrides."""
        if skill.skill_id == "a2ui_explain_move":
            return self._build_explain_move_layout(
                context,
                variant=variant,
                widget_order=widget_order,
                hidden_widgets=hidden_widgets,
                emphasis=emphasis,
            )
        if skill.skill_id == "a2ui_peer_compare":
            return self._build_peer_compare_layout(
                context,
                variant=variant,
                widget_order=widget_order,
                hidden_widgets=hidden_widgets,
                emphasis=emphasis,
            )
        if skill.skill_id == "a2ui_margin_analysis":
            return self._build_margin_analysis_layout(
                context,
                variant=variant,
                widget_order=widget_order,
                hidden_widgets=hidden_widgets,
                emphasis=emphasis,
            )
        if skill.skill_id == "a2ui_revenue_trend":
            return self._build_revenue_trend_layout(
                context,
                variant=variant,
                widget_order=widget_order,
                hidden_widgets=hidden_widgets,
                emphasis=emphasis,
            )
        raise ValueError(f"Unsupported skill_id for layout: {skill.skill_id}")

    def build_components_from_selection(
        self,
        selection: "DashboardLayout",
        context: SkillRenderContext,
    ) -> List[A2UIComponent]:
        """
        Build A2UI component tree from LLM-generated selection.
        
        Method: build_components_from_selection - converts LLM selection to A2UI tree.
        Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard
        Invokes: _build_widget_from_selection, A2UIComponent builders
        Why: Enables dynamic component generation based on LLM choices.
        
        Args:
            selection: DashboardLayout with widget selections
            context: Render context with tickers, metrics, etc.
            
        Returns:
            List of A2UIComponent objects forming the dashboard
        """
        from ..component_selector import DashboardLayout, WidgetSelection
        
        components: List[A2UIComponent] = []
        
        # Build title header
        title_component = A2UIComponent(
            id="title_text",
            component={"Text": {
                "text": {"path": "/data/title"},
                "style": {"literalString": "h2"},
            }}
        )
        header_row = A2UIComponent(
            id="header_row",
            component={"Row": {
                "children": {"explicitList": ["title_text"]},
            }}
        )
        components.extend([title_component, header_row])
        
        # Sort widgets by priority
        sorted_widgets = sorted(selection.widgets, key=lambda w: w.priority)
        
        # Build each widget
        widget_ids = []
        for widget_sel in sorted_widgets:
            widget_component = self._build_widget_from_selection(widget_sel)
            if widget_component:
                components.append(widget_component)
                widget_ids.append(widget_sel.widget_id)
        
        # Determine layout based on emphasis
        if selection.emphasis == "focus_chart":
            # Chart-focused: stack chart prominently
            components.append(self._build_grid_layout(
                "main_grid", 
                widget_ids, 
                emphasis="chart"
            ))
        elif selection.emphasis == "focus_table":
            # Table-focused: make table prominent
            components.append(self._build_grid_layout(
                "main_grid", 
                widget_ids, 
                emphasis="table"
            ))
        else:
            # Balanced: simple column layout
            main_content = A2UIComponent(
                id="main_content",
                component={"Column": {
                    "children": {"explicitList": widget_ids},
                    "gap": {"literalNumber": 16},
                }}
            )
            components.append(main_content)
            widget_ids = ["main_content"]
        
        # Build layout root
        root_children = ["header_row"] + (["main_grid"] if selection.emphasis in ("focus_chart", "focus_table") else widget_ids)
        layout_root = A2UIComponent(
            id="layout_root",
            component={"Column": {
                "children": {"explicitList": root_children},
                "gap": {"literalNumber": 24},
            }}
        )
        components.append(layout_root)
        
        return components
    
    def _build_widget_from_selection(
        self,
        widget_sel: "WidgetSelection",
    ) -> Optional[A2UIComponent]:
        """
        Convert a WidgetSelection to an A2UIComponent.
        
        Method: _build_widget_from_selection - translates LLM selection to component.
        Called from: build_components_from_selection
        Invokes: widget-specific builders
        Why: Maps LLM widget choices to concrete A2UI components.
        """
        from ..component_selector import WidgetSelection
        
        widget_type = widget_sel.widget_type
        widget_id = widget_sel.widget_id
        bindings = widget_sel.data_bindings
        
        # Build component properties from bindings
        props = {}
        for prop_name, binding in bindings.items():
            if isinstance(binding, dict):
                props[prop_name] = binding
        
        # Create the component based on type
        if widget_type == "KpiCard":
            return self._build_kpi_from_bindings(widget_id, props)
        elif widget_type == "MetricChart":
            return self._build_chart_from_bindings(widget_id, props)
        elif widget_type == "DataTable":
            return self._build_table_from_bindings(widget_id, props)
        elif widget_type == "ExplainMovePanel":
            return self._build_explain_from_bindings(widget_id, props)
        elif widget_type == "PriceChart":
            return self._build_price_chart_from_bindings(widget_id, props)
        elif widget_type == "NewsTimeline":
            return self._build_news_from_bindings(widget_id, props)
        elif widget_type == "CorrelationMatrix":
            return self._build_correlation_from_bindings(widget_id, props)
        elif widget_type == "PeerComparePanel":
            return self._build_peer_compare_from_bindings(widget_id, props)
        else:
            # Generic fallback
            return A2UIComponent(
                id=widget_id,
                component={widget_type: props}
            )
    
    def _build_kpi_from_bindings(
        self,
        widget_id: str,
        props: Dict[str, Any],
    ) -> A2UIComponent:
        """Build KpiCard from LLM bindings."""
        # DEBUG: Log the bindings for KpiCard to debug path issues
        logger.info(f"[EMITTER] KpiCard {widget_id} bindings: {props}")
        return A2UIComponent(
            id=widget_id,
            component={"KpiCard": props}
        )
    
    def _build_chart_from_bindings(
        self,
        widget_id: str,
        props: Dict[str, Any],
    ) -> A2UIComponent:
        """Build MetricChart from LLM bindings."""
        return A2UIComponent(
            id=widget_id,
            component={"MetricChart": props}
        )
    
    def _build_table_from_bindings(
        self,
        widget_id: str,
        props: Dict[str, Any],
    ) -> A2UIComponent:
        """Build DataTable from LLM bindings."""
        return A2UIComponent(
            id=widget_id,
            component={"DataTable": props}
        )
    
    def _build_explain_from_bindings(
        self,
        widget_id: str,
        props: Dict[str, Any],
    ) -> A2UIComponent:
        """Build ExplainMovePanel from LLM bindings."""
        return A2UIComponent(
            id=widget_id,
            component={"ExplainMovePanel": props}
        )
    
    def _build_price_chart_from_bindings(
        self,
        widget_id: str,
        props: Dict[str, Any],
    ) -> A2UIComponent:
        """Build PriceChart from LLM bindings."""
        return A2UIComponent(
            id=widget_id,
            component={"PriceChart": props}
        )
    
    def _build_news_from_bindings(
        self,
        widget_id: str,
        props: Dict[str, Any],
    ) -> A2UIComponent:
        """Build NewsTimeline from LLM bindings."""
        return A2UIComponent(
            id=widget_id,
            component={"NewsTimeline": props}
        )
    
    def _build_correlation_from_bindings(
        self,
        widget_id: str,
        props: Dict[str, Any],
    ) -> A2UIComponent:
        """Build CorrelationMatrix from LLM bindings."""
        return A2UIComponent(
            id=widget_id,
            component={"CorrelationMatrix": props}
        )
    
    def _build_peer_compare_from_bindings(
        self,
        widget_id: str,
        props: Dict[str, Any],
    ) -> A2UIComponent:
        """Build PeerComparePanel from LLM bindings."""
        return A2UIComponent(
            id=widget_id,
            component={"PeerComparePanel": props}
        )
    
    def _build_grid_layout(
        self,
        grid_id: str,
        widget_ids: List[str],
        emphasis: str = "balanced",
    ) -> A2UIComponent:
        """Build a responsive grid layout for widgets."""
        # Create grid with emphasis-based weighting
        return A2UIComponent(
            id=grid_id,
            component={"Column": {
                "children": {"explicitList": widget_ids},
                "gap": {"literalNumber": 16},
            }}
        )


    def _data_entries_from_dict(self, data: Dict[str, Any]) -> List[DataEntry]:
        """Convert nested dictionaries into DataEntry lists."""
        entries: List[DataEntry] = []
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, bool):
                entries.append(DataEntry(key=key, valueBoolean=value))
            elif isinstance(value, (int, float)):
                entries.append(DataEntry(key=key, valueNumber=float(value)))
            elif isinstance(value, str):
                entries.append(DataEntry(key=key, valueString=value))
            elif isinstance(value, list):
                entries.append(DataEntry(key=key, valueArray=value))
            elif isinstance(value, dict):
                entries.append(DataEntry(key=key, valueMap=self._data_entries_from_dict(value)))
            else:
                entries.append(DataEntry(key=key, valueString=str(value)))
        return entries

    def _build_explain_move_layout(
        self,
        context: SkillRenderContext,
        *,
        variant: Optional[str] = None,
        widget_order: Optional[List[str]] = None,
        hidden_widgets: Optional[List[str]] = None,
        emphasis: Optional[str] = None,
    ) -> List[A2UIComponent]:
        """Layout for explain-move dashboards with variant/order/hide support."""
        hidden = set(hidden_widgets or [])
        order = widget_order or []
        order_index = {name: idx for idx, name in enumerate(order)}
        active_variant = variant or "split-view"
        if emphasis == "focus_news" and variant is None:
            active_variant = "focus_news"

        def priority(name: str, default: int) -> int:
            return order_index.get(name, default)

        title = A2UIComponent.text_bound("title_text", "/data/title", "h2")
        header = A2UIComponent.row("header_row", ["title_text"])

        components: List[A2UIComponent] = [title, header]

        # Price chart
        if "PriceChart" not in hidden:
            price_chart = A2UIComponent.price_chart(
                "main_visual",
                ticker_path="/data/ticker",
                interval=context.time_range,
                show_volume=True,
                interval_path="/data/time_range",
            )
            price_card = A2UIComponent.card("main_visual_card", "main_visual")
            components.extend([price_chart, price_card])
        else:
            price_card = None

        # KPIs
        if "KpiCard" not in hidden:
            kpi_revenue = A2UIComponent.kpi_card(
                "kpi_revenue",
                label="Revenue",
                value_path="/data/kpis/revenue",
                unit="$",
                delta_path="/data/kpis/revenue_delta",
            )
            kpi_net_income = A2UIComponent.kpi_card(
                "kpi_net_income",
                label="Net Income",
                value_path="/data/kpis/net_income",
                unit="$",
                delta_path="/data/kpis/net_income_delta",
            )
            kpi_margin = A2UIComponent.kpi_card(
                "kpi_gross_margin",
                label="Gross Margin",
                value_path="/data/kpis/gross_margin",
                unit="%",
            )
            kpi_row = A2UIComponent.row("kpi_row", ["kpi_revenue", "kpi_net_income", "kpi_gross_margin"])
            components.extend([kpi_revenue, kpi_net_income, kpi_margin, kpi_row])
        else:
            kpi_row = None

        # News
        if "NewsTimeline" not in hidden:
            news = A2UIComponent.news_timeline("news_timeline", "/data/news/events")
            news_card = A2UIComponent.card("news_card", "news_timeline")
            components.extend([news, news_card])
        else:
            news_card = None

        # Right panel assembly
        right_panel_children: List[str] = []
        if kpi_row:
            right_panel_children.append("kpi_row")
        if news_card:
            right_panel_children.append("news_card")

        if len(right_panel_children) > 1 and order_index:
            right_panel_children.sort(
                key=lambda cid: priority("NewsTimeline" if "news" in cid else "KpiCard", 50)
            )

        right_panel = None
        if right_panel_children:
            right_panel = A2UIComponent.column("right_panel", right_panel_children)
            components.append(right_panel)

        # Main row assembly
        main_children: List[str] = []
        if price_card:
            main_children.append("main_visual_card")
        if right_panel:
            main_children.append("right_panel")

        if active_variant == "focus_news" or emphasis == "focus_news":
            # Put right panel (news) first if present
            main_children = sorted(main_children, key=lambda cid: 0 if cid == "right_panel" else 1)

        main_row = None
        if main_children:
            main_row = A2UIComponent.row("main_row", main_children)
            components.append(main_row)

        # Explain panel (with reasoning_steps support for AI disclosure)
        explain_card = None
        if "ExplainMovePanel" not in hidden:
            explain = A2UIComponent.explain_move_panel(
                "explain_panel",
                title_path="/data/explanation/title",
                explanation_path="/data/explanation/text",
                factors_path="/data/explanation/factors",
                citations_path="/data/explanation/citations",
                reasoning_steps_path="/data/explanation/reasoning_steps",
            )
            explain_card = A2UIComponent.card("explain_card", "explain_panel")
            components.extend([explain, explain_card])

        # Root ordering using widget_order hints
        body_blocks: List[tuple[str, str]] = []
        if main_row:
            body_blocks.append(("PriceChart", "main_row"))
        if explain_card:
            body_blocks.append(("ExplainMovePanel", "explain_card"))

        body_blocks.sort(key=lambda pair: priority(pair[0], 100))
        root_children = ["header_row"] + [block[1] for block in body_blocks if block[1]]
        root = A2UIComponent.column("layout_root", root_children)
        components.append(root)

        return components

    def _build_peer_compare_layout(
        self,
        context: SkillRenderContext,
        *,
        variant: Optional[str] = None,
        widget_order: Optional[List[str]] = None,
        hidden_widgets: Optional[List[str]] = None,
        emphasis: Optional[str] = None,
    ) -> List[A2UIComponent]:
        """Layout for peer comparison dashboards with variant/order/hide support."""
        hidden = set(hidden_widgets or [])
        order = widget_order or []
        order_index = {name: idx for idx, name in enumerate(order)}
        use_expanded = (variant == "grid_focus_chart") or (emphasis == "focus_chart") or ("PeerComparePanel" in hidden)

        # Standard layout priority: KPIs first, charts middle, analysis bottom
        def priority(name: str) -> int:
            base_priority = {
                "KpiCard": 0,           # TOP
                "MetricChart": 1,       # MIDDLE
                "PriceChart": 1,        # MIDDLE
                "CorrelationMatrix": 2, # MIDDLE
                "DataTable": 3,         # MIDDLE-BOTTOM
                "ExplainMovePanel": 4,  # BOTTOM
            }
            return order_index.get(name, base_priority.get(name, 99))

        title = A2UIComponent.text_bound("title_text", "/data/title", "h2")
        header = A2UIComponent.row("header_row", ["title_text"])
        components: List[A2UIComponent] = [title, header]

        if not use_expanded:
            if "PeerComparePanel" in hidden:
                # Fallback to expanded layout if panel is hidden
                use_expanded = True

        if not use_expanded:
            peer_panel = A2UIComponent.peer_compare_panel(
                "peer_compare_panel",
                title_path="/data/title",
                metric_literal=context.metric,
                tickers_path="/data/tickers",
                chart_series_path="/data/chart/series",
                table_columns_path="/data/table/columns",
                table_rows_path="/data/table/rows",
                explanation_title_path="/data/explanation/title",
                explanation_text_path="/data/explanation/text",
            )
            components.append(peer_panel)
            
            # Add explanation panel after main panel
            explain_card = None
            if "ExplainMovePanel" not in hidden:
                explain = A2UIComponent.explain_move_panel(
                    "explain_panel",
                    title_path="/data/explanation/title",
                    explanation_path="/data/explanation/text",
                    factors_path="/data/explanation/factors",
                    citations_path="/data/explanation/citations",
                )
                explain_card = A2UIComponent.card("explain_card", "explain_panel")
                components.extend([explain, explain_card])
            
            root_children = ["header_row", "peer_compare_panel"]
            if explain_card:
                root_children.append("explain_card")
            root = A2UIComponent.column("layout_root", root_children)
            components.append(root)
            return components

        # Expanded layout: explicit chart + correlation + table
        chart = None
        if "PriceChart" not in hidden:
            chart = A2UIComponent.metric_chart(
                "peer_metric_chart",
                series_path="/data/chart/series",
                title_literal=f"{context.metric} Comparison",
                metric=context.metric,
                chart_type="line",
                annotations_path="/data/chart/annotations",
            )
            chart_card = A2UIComponent.card("peer_chart_card", "peer_metric_chart")
            components.extend([chart, chart_card])
        else:
            chart_card = None

        corr = None
        correlation_card = None
        if "CorrelationMatrix" not in hidden:
            corr = A2UIComponent.correlation_matrix(
                "correlation_matrix",
                tickers_path="/data/correlation/tickers",
                matrix_path="/data/correlation/matrix",
            )
            correlation_card = A2UIComponent.card("correlation_card", "correlation_matrix")
            components.extend([corr, correlation_card])

        table = None
        table_card = None
        if "DataTable" not in hidden:
            table = A2UIComponent.data_table(
                "peer_table",
                columns_path="/data/table/columns",
                data_path="/data/table/rows",
                sortable=True,
            )
            table_card = A2UIComponent.card("peer_table_card", "peer_table")
            components.extend([table, table_card])

        chart_row_children: List[str] = []
        if chart_card:
            chart_row_children.append("peer_chart_card")
        if correlation_card:
            chart_row_children.append("correlation_card")

        if len(chart_row_children) > 1 and order_index:
            chart_row_children.sort(
                key=lambda cid: priority("PriceChart" if "chart" in cid else "CorrelationMatrix")
            )

        # Add explanation panel for analysis
        explain_card = None
        if "ExplainMovePanel" not in hidden:
            explain = A2UIComponent.explain_move_panel(
                "explain_panel",
                title_path="/data/explanation/title",
                explanation_path="/data/explanation/text",
                factors_path="/data/explanation/factors",
                citations_path="/data/explanation/citations",
            )
            explain_card = A2UIComponent.card("explain_card", "explain_panel")
            components.extend([explain, explain_card])

        # Create charts_row if we have chart components
        charts_row = None
        if chart_row_children:
            charts_row = A2UIComponent.row("charts_row", chart_row_children)
            components.append(charts_row)

        # Build body blocks with consistent ordering: charts first, then table, then analysis
        body_blocks: List[tuple[str, str]] = []
        if charts_row:
            body_blocks.append(("MetricChart", "charts_row"))
        if table_card:
            body_blocks.append(("DataTable", "peer_table_card"))
        if explain_card:
            body_blocks.append(("ExplainMovePanel", "explain_card"))

        body_blocks.sort(key=lambda pair: priority(pair[0]))
        root_children = ["header_row"] + [cid for _name, cid in body_blocks]
        root = A2UIComponent.column("layout_root", root_children)
        components.append(root)

        return components

    def _build_margin_analysis_layout(
        self,
        context: SkillRenderContext,
        *,
        variant: Optional[str] = None,
        widget_order: Optional[List[str]] = None,
        hidden_widgets: Optional[List[str]] = None,
        emphasis: Optional[str] = None,
    ) -> List[A2UIComponent]:
        """Layout for margin analysis dashboards with variant/order/hide support."""
        hidden = set(hidden_widgets or [])
        order = widget_order or []
        order_index = {name: idx for idx, name in enumerate(order)}
        active_variant = variant or "compact"
        if emphasis == "focus_table" and variant is None:
            active_variant = "focus_table"

        def priority(name: str) -> int:
            base_priority = {
                "KpiCard": 0,
                "MetricChart": 1,
                "PriceChart": 1,
                "DataTable": 2,
                "ExplainMovePanel": 3,
            }
            if active_variant == "focus_table":
                base_priority["DataTable"] = 0
                base_priority["MetricChart"] = 1
            return order_index.get(name, base_priority.get(name, 99))

        title = A2UIComponent.text_bound("title_text", "/data/title", "h2")
        header = A2UIComponent.row("header_row", ["title_text"])
        components: List[A2UIComponent] = [title, header]

        kpi_row = None
        if "KpiCard" not in hidden:
            kpi_gross = A2UIComponent.kpi_card(
                "kpi_gross_margin",
                label="Gross Margin",
                value_path="/data/kpis/gross_margin",
                unit="%",
            )
            kpi_operating = A2UIComponent.kpi_card(
                "kpi_operating_margin",
                label="Operating Margin",
                value_path="/data/kpis/operating_margin",
                unit="%",
            )
            kpi_net = A2UIComponent.kpi_card(
                "kpi_net_margin",
                label="Net Margin",
                value_path="/data/kpis/net_margin",
                unit="%",
            )
            kpi_row = A2UIComponent.row("kpi_row", ["kpi_gross_margin", "kpi_operating_margin", "kpi_net_margin"])
            components.extend([kpi_gross, kpi_operating, kpi_net, kpi_row])

        chart_card = None
        if "PriceChart" not in hidden and "MetricChart" not in hidden:
            margin_chart = A2UIComponent.metric_chart(
                "main_visual",
                series_path="/data/chart/series",
                title_literal=f"{context.primary_ticker} Margin Trends",
                metric="Margin %",
                chart_type="line",
                annotations_path="/data/chart/annotations",
            )
            chart_card = A2UIComponent.card("main_visual_card", "main_visual")
            components.extend([margin_chart, chart_card])

        table_card = None
        if "DataTable" not in hidden:
            table = A2UIComponent.data_table(
                "main_data_table",
                columns_path="/data/table/columns",
                data_path="/data/table/rows",
                sortable=True,
            )
            table_card = A2UIComponent.card("table_card", "main_data_table")
            components.extend([table, table_card])

        explain_card = None
        if "ExplainMovePanel" not in hidden:
            explain = A2UIComponent.explain_move_panel(
                "explain_panel",
                title_path="/data/explanation/title",
                explanation_path="/data/explanation/text",
                factors_path="/data/explanation/factors",
                citations_path="/data/explanation/citations",
            )
            explain_card = A2UIComponent.card("explain_card", "explain_panel")
            components.extend([explain, explain_card])

        body_blocks: List[tuple[str, str]] = []
        if kpi_row:
            body_blocks.append(("KpiCard", "kpi_row"))
        if chart_card:
            body_blocks.append(("MetricChart", "main_visual_card"))
        if table_card:
            body_blocks.append(("DataTable", "table_card"))
        if explain_card:
            body_blocks.append(("ExplainMovePanel", "explain_card"))

        body_blocks.sort(key=lambda pair: priority(pair[0]))
        root_children = ["header_row"] + [cid for _name, cid in body_blocks]
        root = A2UIComponent.column("layout_root", root_children)
        components.append(root)

        return components

    def _build_revenue_trend_layout(
        self,
        context: SkillRenderContext,
        *,
        variant: Optional[str] = None,
        widget_order: Optional[List[str]] = None,
        hidden_widgets: Optional[List[str]] = None,
        emphasis: Optional[str] = None,
    ) -> List[A2UIComponent]:
        """Layout for revenue trend dashboards with variant/order/hide support."""
        hidden = set(hidden_widgets or [])
        order = widget_order or []
        order_index = {name: idx for idx, name in enumerate(order)}
        active_variant = variant or "standard"
        if emphasis == "focus_chart" and variant is None:
            active_variant = "focus_chart"

        # Standard layout priority: KPIs first, charts middle, analysis bottom
        def priority(name: str) -> int:
            base_priority = {
                "KpiCard": 0,           # TOP
                "MetricChart": 1,       # MIDDLE
                "PriceChart": 1,        # MIDDLE
                "DataTable": 2,         # MIDDLE-BOTTOM  
                "ExplainMovePanel": 3,  # BOTTOM
            }
            if active_variant == "focus_chart":
                base_priority["MetricChart"] = 0
                base_priority["PriceChart"] = 0
                base_priority["KpiCard"] = 1
            return order_index.get(name, base_priority.get(name, 99))

        title = A2UIComponent.text_bound("title_text", "/data/title", "h2")
        header = A2UIComponent.row("header_row", ["title_text"])
        components: List[A2UIComponent] = [title, header]

        chart_card = None
        if "PriceChart" not in hidden and "MetricChart" not in hidden:
            metric_chart = A2UIComponent.metric_chart(
                "main_visual",
                series_path="/data/chart/series",
                title_literal=f"{context.primary_ticker} Revenue Trend",
                metric="Revenue",
                chart_type="area",
                annotations_path="/data/chart/annotations",
            )
            chart_card = A2UIComponent.card("main_visual_card", "main_visual")
            components.extend([metric_chart, chart_card])

        kpi_column = None
        if "KpiCard" not in hidden:
            kpi_latest = A2UIComponent.kpi_card(
                "kpi_latest_revenue",
                label="Latest Revenue",
                value_path="/data/kpis/latest_revenue",
                unit="$",
            )
            kpi_yoy = A2UIComponent.kpi_card(
                "kpi_yoy_growth",
                label="YoY Growth",
                value_path="/data/kpis/yoy_growth",
                unit="%",
            )
            kpi_column = A2UIComponent.column("kpi_column", ["kpi_latest_revenue", "kpi_yoy_growth"])
            components.extend([kpi_latest, kpi_yoy, kpi_column])

        main_row = None
        if chart_card or kpi_column:
            row_children = []
            if chart_card:
                row_children.append("main_visual_card")
            if kpi_column:
                row_children.append("kpi_column")
            # Keep chart first when focus_chart is active
            if active_variant == "focus_chart":
                row_children.sort(key=lambda cid: 0 if "visual" in cid else 1)
            main_row = A2UIComponent.row("main_row", row_children)
            components.append(main_row)

        table_card = None
        if "DataTable" not in hidden:
            table = A2UIComponent.data_table(
                "main_data_table",
                columns_path="/data/table/columns",
                data_path="/data/table/rows",
                sortable=True,
            )
            table_card = A2UIComponent.card("table_card", "main_data_table")
            components.extend([table, table_card])

        explain_card = None
        if "ExplainMovePanel" not in hidden:
            explain = A2UIComponent.explain_move_panel(
                "explain_panel",
                title_path="/data/explanation/title",
                explanation_path="/data/explanation/text",
                factors_path="/data/explanation/factors",
                citations_path="/data/explanation/citations",
            )
            explain_card = A2UIComponent.card("explain_card", "explain_panel")
            components.extend([explain, explain_card])

        body_blocks: List[tuple[str, str]] = []
        if main_row:
            body_blocks.append(("MetricChart", "main_row"))
        if table_card:
            body_blocks.append(("DataTable", "table_card"))
        if explain_card:
            body_blocks.append(("ExplainMovePanel", "explain_card"))

        body_blocks.sort(key=lambda pair: priority(pair[0]))
        root_children = ["header_row"] + [cid for _name, cid in body_blocks]
        root = A2UIComponent.column("layout_root", root_children)
        components.append(root)

        return components


__all__ = [
    "A2UIMessageEmitter",
    "SkillRenderContext",
]
