# --- Analytics Function/Class Map ---
# Function: test_record_tool_receipt_enriches_metadata — called from pytest; verifies SessionStateSnapshot.record_tool_receipt enriches receipts with schema_version, lane, cache, elapsed_ms, and retry metadata so agent telemetry stays aligned with the canonical tool registry.
# --- End Analytics Function/Class Map ---
from analytics.core.session_state import SessionStateSnapshot
from analytics.tools.definitions import TOOL_REGISTRY, ToolId


def test_record_tool_receipt_enriches_metadata() -> None:
    snapshot = SessionStateSnapshot(session_id="session-123")

    snapshot.record_tool_receipt(
        ToolId.CLASSIFICATION.value,
        {
            "status": "completed",
            "latency_ms": 123,
            "attempts": 2,
            "reused": True,
        },
    )

    receipts = snapshot.tool_cache.get("tool_receipts", {})
    receipt = receipts[ToolId.CLASSIFICATION.value]

    metadata = receipt["metadata"]
    canonical = TOOL_REGISTRY[ToolId.CLASSIFICATION]

    assert metadata["schema_version"] == canonical.schema_version
    assert metadata["lane"] == canonical.telemetry_step
    assert metadata["from_cache"] is True
    assert metadata["elapsed_ms"] == 123
    assert metadata["retry_count"] == 1
