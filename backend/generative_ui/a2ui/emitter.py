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

    def build_components_for_skill(self, skill: A2UISkillMeta, context: SkillRenderContext, variant: str | None = None) -> List[A2UIComponent]:
        """Build the component tree for a given skill (variant is optional hook)."""
        # Currently variants are not differentiated; this hook allows future
        # variant-specific builders without changing the call sites.
        if skill.skill_id == "a2ui_explain_move":
            return self._build_explain_move_layout(context)
        if skill.skill_id == "a2ui_peer_compare":
            return self._build_peer_compare_layout(context)
        if skill.skill_id == "a2ui_margin_analysis":
            return self._build_margin_analysis_layout(context)
        if skill.skill_id == "a2ui_revenue_trend":
            return self._build_revenue_trend_layout(context)
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

    def _build_explain_move_layout(self, context: SkillRenderContext) -> List[A2UIComponent]:
        """Layout for explain-move dashboards."""
        title = A2UIComponent.text_bound("title_text", "/data/title", "h2")
        header = A2UIComponent.row("header_row", ["title_text"])

        price_chart = A2UIComponent.price_chart(
            "main_visual",
            ticker_path="/data/ticker",
            interval=context.time_range,
            show_volume=True,
            interval_path="/data/time_range",
        )
        price_card = A2UIComponent.card("main_visual_card", "main_visual")

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

        news = A2UIComponent.news_timeline("news_timeline", "/data/news/events")
        news_card = A2UIComponent.card("news_card", "news_timeline")
        right_panel = A2UIComponent.column("right_panel", ["kpi_row", "news_card"])

        main_row = A2UIComponent.row("main_row", ["main_visual_card", "right_panel"])

        explain = A2UIComponent.explain_move_panel(
            "explain_panel",
            title_path="/data/explanation/title",
            explanation_path="/data/explanation/text",
            factors_path="/data/explanation/factors",
            citations_path="/data/explanation/citations",
        )
        explain_card = A2UIComponent.card("explain_card", "explain_panel")

        root = A2UIComponent.column("layout_root", ["header_row", "main_row", "explain_card"])

        return [
            title,
            header,
            price_chart,
            price_card,
            kpi_revenue,
            kpi_net_income,
            kpi_margin,
            kpi_row,
            news,
            news_card,
            right_panel,
            main_row,
            explain,
            explain_card,
            root,
        ]

    def _build_peer_compare_layout(self, context: SkillRenderContext) -> List[A2UIComponent]:
        """Layout for peer comparison dashboards - uses consolidated PeerComparePanel."""
        title = A2UIComponent.text_bound("title_text", "/data/title", "h2")
        header = A2UIComponent.row("header_row", ["title_text"])

        # Single consolidated panel for entire comparison
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

        root = A2UIComponent.column("layout_root", ["header_row", "peer_compare_panel"])

        return [
            title,
            header,
            peer_panel,
            root,
        ]

    def _build_margin_analysis_layout(self, context: SkillRenderContext) -> List[A2UIComponent]:
        """Layout for margin analysis dashboards."""
        title = A2UIComponent.text_bound("title_text", "/data/title", "h2")
        header = A2UIComponent.row("header_row", ["title_text"])

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

        # Add MetricChart for margin trends over time
        margin_chart = A2UIComponent.metric_chart(
            "main_visual",
            series_path="/data/chart/series",
            title_literal=f"{context.primary_ticker} Margin Trends",
            metric="Margin %",
            chart_type="line",
            annotations_path="/data/chart/annotations",
        )
        chart_card = A2UIComponent.card("main_visual_card", "main_visual")

        table = A2UIComponent.data_table(
            "main_data_table",
            columns_path="/data/table/columns",
            data_path="/data/table/rows",
            sortable=True,
        )
        table_card = A2UIComponent.card("table_card", "main_data_table")

        explain = A2UIComponent.explain_move_panel(
            "explain_panel",
            title_path="/data/explanation/title",
            explanation_path="/data/explanation/text",
            factors_path="/data/explanation/factors",
            citations_path="/data/explanation/citations",
        )
        explain_card = A2UIComponent.card("explain_card", "explain_panel")

        root = A2UIComponent.column("layout_root", ["header_row", "kpi_row", "main_visual_card", "table_card", "explain_card"])

        return [
            title,
            header,
            kpi_gross,
            kpi_operating,
            kpi_net,
            kpi_row,
            margin_chart,
            chart_card,
            table,
            table_card,
            explain,
            explain_card,
            root,
        ]

    def _build_revenue_trend_layout(self, context: SkillRenderContext) -> List[A2UIComponent]:
        """Layout for revenue trend dashboards."""
        title = A2UIComponent.text_bound("title_text", "/data/title", "h2")
        header = A2UIComponent.row("header_row", ["title_text"])

        # Use MetricChart (ECharts) instead of PriceChart (TradingView) for revenue data
        metric_chart = A2UIComponent.metric_chart(
            "main_visual",
            series_path="/data/chart/series",
            title_literal=f"{context.primary_ticker} Revenue Trend",
            metric="Revenue",
            chart_type="area",
            annotations_path="/data/chart/annotations",
        )
        chart_card = A2UIComponent.card("main_visual_card", "main_visual")

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

        main_row = A2UIComponent.row("main_row", ["main_visual_card", "kpi_column"])

        table = A2UIComponent.data_table(
            "main_data_table",
            columns_path="/data/table/columns",
            data_path="/data/table/rows",
            sortable=True,
        )
        table_card = A2UIComponent.card("table_card", "main_data_table")

        explain = A2UIComponent.explain_move_panel(
            "explain_panel",
            title_path="/data/explanation/title",
            explanation_path="/data/explanation/text",
            factors_path="/data/explanation/factors",
            citations_path="/data/explanation/citations",
        )
        explain_card = A2UIComponent.card("explain_card", "explain_panel")

        root = A2UIComponent.column("layout_root", ["header_row", "main_row", "table_card", "explain_card"])

        return [
            title,
            header,
            metric_chart,
            chart_card,
            kpi_latest,
            kpi_yoy,
            kpi_column,
            main_row,
            table,
            table_card,
            explain,
            explain_card,
            root,
        ]


__all__ = [
    "A2UIMessageEmitter",
    "SkillRenderContext",
]
