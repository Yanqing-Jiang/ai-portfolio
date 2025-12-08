# --- Analytics Function/Class Map ---
# Module: analytics.core.charting
#   Role: Facade exports for chart revision context, classifiers, emitters, and patch ops.
#   Called from: analytics.flows.chart_revision (facade), analytics.flows.multi_agent, tests.analytics.test_chart_revision
#   Invokes: analytics.core.charting.revision_context, revision_classifiers, revision_emitters, patch_ops
#   Why: Centralizes chart revision primitives under core/charting while keeping a thin flow-level wrapper. Also re-exports shared chart planning/build helpers for downstream flows.
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

