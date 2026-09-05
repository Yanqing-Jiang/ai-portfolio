"""Terminal failures must survive a reload without breaking approved readings."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Request, Response

from fortune import routes
from fortune.stream_bridge import READING_ERROR_MESSAGE, FortuneStreamBridge

FORTUNE_ID = "11111111-1111-1111-1111-111111111111"


def _row(**changes):
    return {
        "focus": "career", "tone": None, "locale": "en", "created_at": None,
        "snapshot_status": "partial", "snapshot_version": 3, "schema_version": 2,
        "latest_reading_run_id": "22222222-2222-2222-2222-222222222222",
        "latest_reading_run_status": "error",
        "data_model": {"pillars": {"day": {"stem": "Metal"}},
                       "meta": {"status": "streaming", "progress": {"percent": 20}}},
        **changes,
    }


async def _get(monkeypatch, row, etag=None):
    repo = SimpleNamespace(available=True, get_fortune_with_snapshot=AsyncMock(return_value=row))
    monkeypatch.setattr(routes, "get_repository", AsyncMock(return_value=repo))
    monkeypatch.setattr(routes, "smart_rate_limit", AsyncMock())
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    return await routes.get_fortune_replay(FORTUNE_ID, request, Response(), if_none_match=etag)


@pytest.mark.asyncio
@pytest.mark.parametrize("run_status", ["error", "interrupted", "failed_guardrail"])
async def test_failed_partial_replay_is_terminal_and_invalidates_old_etag(monkeypatch, run_status):
    row = _row(latest_reading_run_status=run_status)
    result = await _get(monkeypatch, row, f'"fortune-{FORTUNE_ID}-v3"')
    assert result.status_code == 200
    body = json.loads(result.body)
    assert body["status"] == "error"
    assert body["data_model"]["meta"] == {"status": "error", "error_message": READING_ERROR_MESSAGE}
    assert body["data_model"]["pillars"] == row["data_model"]["pillars"]
    assert result.headers["cache-control"] == "no-store"
    if run_status == "failed_guardrail":
        assert body["data_model"]["guardrail"] == {
            "level": "critical", "message": "We can’t safely present this reading.",
        }
    assert row["data_model"]["meta"]["status"] == "streaming"  # no mutation of stored data


@pytest.mark.asyncio
async def test_failure_before_first_snapshot_is_not_pending(monkeypatch):
    result = await _get(monkeypatch, _row(snapshot_version=None, snapshot_status=None,
                                       schema_version=None, data_model=None))
    body = json.loads(result.body)
    assert result.status_code == 200
    assert body["status"] == "error"
    assert body["schema_version"] == 2
    assert body["snapshot_version"] == 0


@pytest.mark.asyncio
async def test_failed_followup_does_not_replace_completed_reading(monkeypatch):
    row = _row(snapshot_status="done")
    result = await _get(monkeypatch, row)
    assert json.loads(result.body)["status"] == "done"
    cached = await _get(monkeypatch, row, result.headers["etag"])
    assert cached.status_code == 304


@pytest.mark.asyncio
async def test_active_run_remains_partial_or_pending(monkeypatch):
    row = _row(latest_reading_run_status="streaming")
    result = await _get(monkeypatch, row)
    assert json.loads(result.body)["status"] == "partial"
    result = await _get(monkeypatch, {**row, "snapshot_version": None})
    assert result.status_code == 202
    assert json.loads(result.body)["status"] == "pending"


def test_empty_terminal_error_has_a_friendly_message_and_done_signal():
    chunks = FortuneStreamBridge(surface_id="fortune_main").emit_error("")
    assert any(READING_ERROR_MESSAGE in chunk for chunk in chunks)
    assert json.loads(chunks[-1]) == {"done": True}
