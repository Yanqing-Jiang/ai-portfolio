from __future__ import annotations

import hashlib
import hmac
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from homer_play import rate_limit, routes  # noqa: E402
from homer_play.bridge import BridgeClient, BridgeFailure  # noqa: E402
from homer_play.handlers.memory import HandlerResult as MemoryHandlerResult  # noqa: E402
from homer_play.handlers.scheduler import HandlerResult as SchedulerHandlerResult  # noqa: E402
from homer_play.handlers.web import HandlerResult as WebHandlerResult  # noqa: E402
from homer_play.models import (  # noqa: E402
    InterpretedQuery,
    PLAY_REQUEST_ADAPTER,
    PLAY_SUCCESS_ADAPTER,
)
from homer_play.parsers import (  # noqa: E402
    SchedulerParseResult,
    keyword_scheduler_parser,
    map_web_activity,
    parse_scheduler_query,
)
from homer_play.replays import MANIFEST, REPLAYS  # noqa: E402
from homer_play.spend import SpendLedger  # noqa: E402


def _app_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "false")
    monkeypatch.setenv("HOMER_PLAY_DAILY_CAP_USD", "2.0")
    monkeypatch.setattr(rate_limit.shared_rate_limiter, "redis_pool", None)
    rate_limit._in_memory_usage.clear()
    monkeypatch.setattr(routes, "spend_ledger", SpendLedger(None, allow_in_memory=True))
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _base(tab: str, action: str, message: str = "show me the public example") -> dict:
    return {"version": "1", "tab": tab, "action": action, "message": message, "input": {}}


@pytest.mark.parametrize(
    ("tab", "action", "extra"),
    [
        ("memory", "search", {"input": {"limit": 4}}),
        ("memory", "extract_dry_run", {"input": {"target": "architecture"}}),
        ("scheduler", "query", {"input": {"max_jobs": 8, "max_runs_per_job": 3}}),
        ("executors", "route_and_answer", {"input": {"answer_max_tokens": 160}}),
        ("mcp", "list_tools", {"message": "/tools"}),
        (
            "mcp",
            "call_tool",
            {"message": "/call memory_search", "input": {"tool": "memory_search", "arguments": {"query": "memory"}}},
        ),
        ("voice", "synthesize", {"message": "Homer uses public-safe examples.", "input": {"format": "ogg_opus"}}),
        ("web", "activity", {"message": "What happened today?", "input": {"window": "24h"}}),
    ],
)
def test_discriminated_request_union_accepts_every_tab_action(tab, action, extra):
    payload = _base(tab, action)
    payload.update(extra)
    validated = PLAY_REQUEST_ADAPTER.validate_python(payload)
    assert validated.tab == tab
    assert validated.action == action


def test_endpoint_live_and_degraded_envelopes_per_tab(monkeypatch):
    client = _app_client(monkeypatch)

    async def fake_search(_payload):
        fixture = REPLAYS["memory.search"]
        return MemoryHandlerResult(fixture["data"], 4)

    async def fake_extract(_payload, _bridge, *, request_id):
        assert request_id
        return MemoryHandlerResult(REPLAYS["memory.extract_dry_run"]["data"], 320)

    async def fake_parse(_message):
        return SchedulerParseResult(InterpretedQuery(), 10, 5, True, False)

    async def fake_scheduler(_payload, parsed, _bridge, *, request_id):
        data = dict(REPLAYS["scheduler.query"]["data"])
        data["interpreted_query"] = parsed.query.model_dump(mode="json")
        return SchedulerHandlerResult(data)

    async def fake_web(_payload, _bridge, *, request_id):
        assert request_id
        return WebHandlerResult(REPLAYS["web.activity"]["data"])

    monkeypatch.setattr(routes, "run_search", fake_search)
    monkeypatch.setattr(routes, "run_extract", fake_extract)
    monkeypatch.setattr(routes, "parse_scheduler_query", fake_parse)
    monkeypatch.setattr(routes, "run_scheduler_query", fake_scheduler)
    monkeypatch.setattr(routes, "run_web_activity", fake_web)

    payloads = [
        _base("memory", "search", "sqlite memory"),
        {**_base("memory", "extract_dry_run", "We switched to SQLite."), "input": {"target": "architecture"}},
        _base("scheduler", "query", "failed jobs this week"),
        _base("executors", "route_and_answer", "review this plan"),
        {**_base("mcp", "list_tools", "/tools")},
        {
            **_base("mcp", "call_tool", "/call memory_search"),
            "input": {"tool": "memory_search", "arguments": {"query": "conflict"}},
        },
        {**_base("voice", "synthesize", "Homer is read only."), "input": {"format": "ogg_opus"}},
        _base("web", "activity", "today overview"),
    ]
    for index, payload in enumerate(payloads):
        response = client.post("/api/homer/play", json=payload)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store, private"
        body = response.json()
        PLAY_SUCCESS_ADAPTER.validate_python(body)
        assert body["tab"] == payload["tab"]
        assert body["action"] == payload["action"]
        assert body["limits"]["remaining_this_hour"] == 9 - index
        if payload["tab"] in {"executors", "mcp", "voice"}:
            assert body["mode"] == "degraded"
            assert body["degraded"]["reason"] == "not_yet_enabled"
        else:
            assert body["mode"] == "live"
            assert body["degraded"] is None


def test_unknown_and_extra_fields_return_400_without_echo(monkeypatch):
    client = _app_client(monkeypatch)
    payload = _base("memory", "search", "private sentinel text")
    payload["input"] = {"limit": 4, "private_path": "/secret/sentinel"}
    response = client.post("/api/homer/play", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert "private sentinel text" not in response.text
    assert "/secret/sentinel" not in response.text


def test_non_allowlisted_mcp_tool_returns_403(monkeypatch):
    client = _app_client(monkeypatch)
    payload = _base("mcp", "call_tool", "/call call_person")
    payload["input"] = {"tool": "call_person", "arguments": {}}
    response = client.post("/api/homer/play", json=payload)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "tool_not_allowed"


def test_body_cap_returns_public_413_shape(monkeypatch):
    client = _app_client(monkeypatch)
    response = client.post(
        "/api/homer/play",
        content=json.dumps(_base("memory", "search", "x" * 9000)),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert response.headers["cache-control"] == "no-store, private"


def test_shared_hourly_limit_returns_429_and_limits(monkeypatch):
    client = _app_client(monkeypatch)
    monkeypatch.setattr(rate_limit, "HOURLY_LIMIT", 1)
    first = client.post("/api/homer/play", json=_base("executors", "route_and_answer"))
    second = client.post("/api/homer/play", json=_base("mcp", "list_tools", "/tools"))
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers.get("retry-after")
    assert second.json()["error"]["code"] == "rate_limited"
    assert second.json()["limits"]["remaining_this_hour"] == 0


@pytest.mark.asyncio
async def test_spend_reservation_exact_cap_refund_and_idempotency(monkeypatch):
    monkeypatch.setenv("HOMER_PLAY_DAILY_CAP_USD", "0.002")
    ledger = SpendLedger(None, allow_in_memory=True)
    now = datetime(2026, 8, 29, 12, tzinfo=timezone.utc)

    extract = await ledger.reserve("memory.extract_dry_run", "req-a", now=now)
    scheduler = await ledger.reserve("scheduler.query", "req-b", now=now)
    capped = await ledger.reserve("memory.search", "req-c", now=now)
    assert extract.allowed and scheduler.allowed
    assert scheduler.total_micro_usd == 2_000
    assert not capped.allowed and capped.reason == "daily_spend_cap"

    actual = await ledger.finalize(extract, 400, now=now)
    repeated = await ledger.finalize(extract, 1_200, now=now)
    assert actual == repeated == 400
    after_refund = await ledger.reserve("scheduler.query", "req-d", now=now)
    assert after_refund.allowed
    duplicate = await ledger.reserve("scheduler.query", "req-d", now=now)
    assert duplicate.allowed
    assert duplicate.total_micro_usd == after_refund.total_micro_usd
    conflict = await ledger.reserve("memory.extract_dry_run", "req-d", now=now)
    assert not conflict.allowed
    assert conflict.reason == "reservation_conflict"


@pytest.mark.asyncio
async def test_bridge_hmac_covers_exact_sent_body_and_required_headers():
    observed = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        observed["body"] = request.content
        observed["headers"] = request.headers
        return httpx.Response(200, json={"ok": True, "request_id": "r", "command": "web.activity", "data": {"ok": "data-shape-placeholder"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        bridge = BridgeClient(
            base_url="http://bridge.test:3012",
            secret="test-secret",
            client=client,
            clock=lambda: 1_777_777_777,
        )
        result = await bridge.execute(
            "web.activity",
            {"window": "24h", "view": "overview"},
            request_id="00000000-0000-4000-8000-000000000099",
            timeout_seconds=0.75,
        )

    assert result == {"ok": "data-shape-placeholder"}
    expected = hmac.new(
        b"test-secret",
        b"1777777777.00000000-0000-4000-8000-000000000099." + observed["body"],
        hashlib.sha256,
    ).hexdigest()
    assert observed["headers"]["x-homer-bridge-timestamp"] == "1777777777"
    assert observed["headers"]["x-homer-bridge-request-id"] == "00000000-0000-4000-8000-000000000099"
    assert observed["headers"]["x-homer-bridge-signature"] == expected
    assert json.loads(observed["body"]) == {
        "command": "web.activity",
        "input": {"window": "24h", "view": "overview"},
    }


def test_bridge_timeout_becomes_degraded_replay(monkeypatch):
    client = _app_client(monkeypatch)

    class TimeoutBridge:
        async def execute(self, *args, **kwargs):
            raise BridgeFailure("live_timeout")

    monkeypatch.setattr(routes, "bridge_client", TimeoutBridge())
    response = client.post("/api/homer/play", json=_base("web", "activity", "events in the last hour"))
    assert response.status_code == 200
    assert response.json()["mode"] == "degraded"
    assert response.json()["degraded"]["reason"] == "live_timeout"


def test_html_entities_are_rejected_as_validation_errors(monkeypatch):
    client = _app_client(monkeypatch)
    response = client.post(
        "/api/homer/play",
        json=_base("memory", "search", "&lt;script&gt;private&lt;/script&gt;"),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_mcp_arguments_are_strictly_validated(monkeypatch):
    client = _app_client(monkeypatch)
    payload = _base("mcp", "call_tool", "/call memory_search")
    payload["input"] = {"tool": "memory_search", "arguments": {"limit": 99}}
    response = client.post("/api/homer/play", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_production_redis_failure_replays_without_live_call(monkeypatch):
    client = _app_client(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("live handler must not run without the production rate backend")

    monkeypatch.setattr(routes, "run_web_activity", fail_if_called)
    response = client.post("/api/homer/play", json=_base("web", "activity", "today overview"))
    assert response.status_code == 200
    assert response.json()["mode"] == "degraded"
    assert response.json()["degraded"]["reason"] == "rate_backend_unavailable"


def test_all_replay_fixtures_validate_against_response_union():
    assert len(MANIFEST.fixtures) == len(REPLAYS) == 8
    for key, fixture in REPLAYS.items():
        validated = PLAY_SUCCESS_ADAPTER.validate_python(fixture)
        assert f"{validated.tab}.{validated.action}" == key
        assert validated.degraded is not None


@pytest.mark.asyncio
async def test_keyword_parser_is_deterministic_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    parsed = await parse_scheduler_query("Which failed `memory-reindex` jobs ran this week, and when next?")
    assert parsed.used_fallback
    assert not parsed.provider_attempted
    assert parsed.query == keyword_scheduler_parser(
        "Which failed `memory-reindex` jobs ran this week, and when next?"
    )
    assert parsed.query.model_dump() == {
        "status": "failed",
        "since_hours": 168,
        "job_ids": ["memory-reindex"],
        "include_next_run": True,
    }


def test_web_mapping_is_deterministic_and_model_free():
    interpreted = map_web_activity("show tool events from the last hour", "24h")
    assert interpreted.window == "1h"
    assert interpreted.view == "events"
