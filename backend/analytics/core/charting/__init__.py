# --- Analytics Function/Class Map ---
# Module: analytics.core.charting
#   Role: Facade exports for chart revision context, classifiers, emitters, and patch ops.
#   Called from: analytics.flows.chart_revision (facade), analytics.flows.multi_agent, tests.analytics.test_chart_revision
#   Invokes: analytics.core.charting.revision_context, revision_classifiers, revision_emitters, patch_ops
#   Why: Centralizes chart revision primitives under core/charting while keeping a thin flow-level wrapper. Also re-exports shared chart planning/build helpers for downstream flows.
# Function: compose_series_column_key
#   Role: Export legacy series key helper for analytics_agent callers.
#   Called from: analytics_agent, analytics.core.charting
#   Invokes: analytics.core.charting_spec.compose_series_column_key
#   Why: Keeps series key formatting consistent during analytics_agent deprecation.
# Function: metric_label_from_series
#   Role: Export legacy metric label helper for analytics_agent callers.
#   Called from: analytics_agent
#   Invokes: analytics.core.charting_spec.metric_label_from_series
#   Why: Avoids duplicating label heuristics while analytics_agent is phased out.
# --- End Analytics Function/Class Map ---
import importlib.util
from pathlib import Path

_charting_spec_path = Path(__file__).resolve().parent.parent / "charting.py"
_charting_spec = importlib.util.spec_from_file_location("analytics.core.charting_spec", _charting_spec_path)
if _charting_spec and _charting_spec.loader:
    _charting_module = importlib.util.module_from_spec(_charting_spec)
    _charting_spec.loader.exec_module(_charting_module)
    build_chart_spec = _charting_module.build_chart_spec
    plan_chart_rule_based = _charting_module.plan_chart_rule_based
    compose_series_column_key = _charting_module.compose_series_column_key
    metric_label_from_series = _charting_module.metric_label_from_series
else:
    raise ImportError(f"Unable to load charting spec module from {_charting_spec_path}")
from .revision_context import (
    RevisionContext,
    RevisionContextError,
    MissingRevisionSnapshot,
    MissingChartSpec,
    MissingAnalysis,
)
from .revision_classifiers import (
    is_chart_revision_query,
    infer_chart_patch_from_query,
    is_analysis_revision_query,
    infer_analysis_revision_from_query,
)
from .revision_emitters import (
    ChartPatch,
    emit_chart_patch,
    emit_analysis_revision,
    build_patch_event,
    build_analysis_event,
)
from .patch_ops import normalize_chart_patch, apply_chart_patch_to_spec

__all__ = [
    "build_chart_spec",
    "plan_chart_rule_based",
    "compose_series_column_key",
    "metric_label_from_series",
    "RevisionContext",
    "RevisionContextError",
    "MissingRevisionSnapshot",
    "MissingChartSpec",
    "MissingAnalysis",
    "is_chart_revision_query",
    "infer_chart_patch_from_query",
    "is_analysis_revision_query",
    "infer_analysis_revision_from_query",
    "ChartPatch",
    "emit_chart_patch",
    "emit_analysis_revision",
    "build_patch_event",
    "build_analysis_event",
    "normalize_chart_patch",
    "apply_chart_patch_to_spec",
]

