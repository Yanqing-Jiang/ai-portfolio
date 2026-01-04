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
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

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

        # Explain panel
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

        def priority(name: str, default: int) -> int:
            return order_index.get(name, default)

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
            root = A2UIComponent.column("layout_root", ["header_row", "peer_compare_panel"])
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
                key=lambda cid: priority("PriceChart" if "chart" in cid else "CorrelationMatrix", 50)
            )

        body_blocks: List[tuple[str, str]] = []
        charts_row = None
        if chart_row_children:
            charts_row = A2UIComponent.row("charts_row", chart_row_children)
            components.append(charts_row)
            # Use generic names for ordering
            for cid in chart_row_children:
                if "chart" in cid:
                    body_blocks.append(("PriceChart", "charts_row"))
                elif "correlation" in cid:
                    body_blocks.append(("CorrelationMatrix", "charts_row"))

        if table_card:
            body_blocks.append(("DataTable", "peer_table_card"))

        # Deduplicate body blocks while preserving ordering priority
        seen = set()
        dedup_blocks: List[tuple[str, str]] = []
        for name, cid in body_blocks:
            if cid in seen:
                continue
            seen.add(cid)
            dedup_blocks.append((name, cid))

        dedup_blocks.sort(key=lambda pair: priority(pair[0], 100))
        root_children = ["header_row"] + [cid for _name, cid in dedup_blocks]
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

        def priority(name: str) -> int:
            base_priority = {
                "MetricChart": 0 if active_variant == "focus_chart" else 1,
                "PriceChart": 0 if active_variant == "focus_chart" else 1,
                "KpiCard": 1,
                "DataTable": 2,
                "ExplainMovePanel": 3,
            }
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
