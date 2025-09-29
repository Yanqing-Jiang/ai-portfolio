import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]
for candidate in (ROOT, BACKEND_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from backend.analytics.core.events import EventEmitter, TimedEventEmitter
from backend.analytics.core.state import (
    ClarificationArtifactModel,
    SupervisorWorkflowState,
    WorkflowState,
)


def test_supervisor_workflow_state_defaults():
    state = SupervisorWorkflowState(session_id="s-123", current_phase="planning")
    assert state.execution_steps == []
    assert state.errors == []
    assert state.session_id == "s-123"


def test_clarification_artifact_defaults():
    artifact = ClarificationArtifactModel(session_id="abc")
    assert artifact.clarification_state == "pending"
    assert artifact.pending_requests == []


def test_event_emitter_progress_payload():
    event = EventEmitter.progress("sql_planning", message="planning sql")
    assert event["event"] == "progress"
    assert event["data"]["step"] == "sql_planning"
    assert "ts" in event["data"]
    assert event["data"]["message"] == "planning sql"


def test_timed_event_emitter_includes_elapsed():
    emitter = TimedEventEmitter()
    emitter.step_times["analysis"] = time.time() - 1
    event = emitter.timed_status("analysis", "done")
    assert event["event"] == "status"
    assert event["data"]["step"] == "analysis"
    assert event["data"]["msg"] == "done"
    assert event["data"].get("elapsed") is not None


def test_workflow_state_typed_dict_fields():
    state: WorkflowState = {"query": "How is revenue?", "step": "intent"}
    assert state["query"].startswith("How")
    assert state["step"] == "intent"
