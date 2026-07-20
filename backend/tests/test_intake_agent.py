"""Phase 2 AI Brief Agent — unit + mocked-endpoint tests.

Covers the security-critical logic the codex review flagged: server-authoritative
signed sessions, the turn cap, brief validation/clamping, the min-useful-brief
invariant, per-visitor rate limiting, and a mocked intake -> brief-persist flow
(no live model or DB needed).
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import intake_agent as ia  # noqa: E402
import main  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_buckets():
    main._RATE_BUCKETS.clear()
    yield
    main._RATE_BUCKETS.clear()


# --- Signed sessions --------------------------------------------------------

def test_session_roundtrip():
    state = {"path": "business", "turns": 2, "transcript": [{"role": "user", "content": "hi"}], "brief": {"desired_outcome": "x"}}
    token = ia.sign_session(state)
    assert ia.verify_session(token) == state


def test_session_tamper_rejected():
    token = ia.sign_session(ia.new_state("business"))
    payload, sig = token.split(".", 1)
    # Flip the payload; signature no longer matches.
    forged = payload[:-1] + ("A" if payload[-1] != "A" else "B") + "." + sig
    assert ia.verify_session(forged) is None
    assert ia.verify_session("garbage") is None
    assert ia.verify_session("") is None


# --- Brief validation / clamping -------------------------------------------

def test_clamp_brief_bounds_and_whitelist():
    raw = {
        "desired_outcome": "x" * 5000,
        "evil_field": "drop me",
        "open_questions": ["a"] * 50 + [123, {"nested": 1}],
    }
    out = ia.clamp_brief(raw)
    assert "evil_field" not in out
    assert len(out["desired_outcome"]) == ia.MAX_FIELD_CHARS
    assert len(out["open_questions"]) == ia.MAX_OPEN_QUESTIONS
    assert all(isinstance(q, str) for q in out["open_questions"])


def test_clamp_brief_non_dict():
    assert ia.clamp_brief("not a dict") == {}
    assert ia.clamp_brief(None) == {}


def test_min_brief_ok():
    assert not ia.min_brief_ok("business", {})
    assert not ia.min_brief_ok("business", {"desired_outcome": "goal"})  # only 1 field
    ok = {"desired_outcome": "goal", "current_workflow": "manual", "success_metric": "hrs"}
    assert ia.min_brief_ok("business", ok)


def test_validate_output_clamps_and_enum():
    out = ia._validate_output({
        "reply": "hi",
        "brief": {"desired_outcome": "y"},
        "quick_replies": ["a", 5, "b", "c", "d"],
        "complete": True,
        "recommended_next_step": "bogus",
    })
    assert out["recommended_next_step"] == ""  # invalid enum -> ""
    assert len(out["quick_replies"]) == 3
    assert out["reply"] == "hi"


def test_validate_output_malformed_raises():
    with pytest.raises(ValueError):
        ia._validate_output("not an object")


# --- run_turn (model faked) -------------------------------------------------

class _FakeBlock:
    type = "tool_use"
    name = "submit_turn"

    def __init__(self, payload):
        self.input = payload


class _FakeResp:
    def __init__(self, payload):
        self.content = [_FakeBlock(payload)]


def _fake_client(payload):
    class _Msgs:
        @staticmethod
        def create(**kwargs):
            return _FakeResp(payload)

    class _Client:
        messages = _Msgs()

    return _Client()


def test_run_turn_honors_complete_only_with_min_brief(monkeypatch):
    # Model says complete but brief is thin -> server downgrades complete.
    monkeypatch.setattr(ia, "_get_client", lambda: _fake_client({
        "reply": "ok", "brief": {"desired_outcome": "goal"},
        "quick_replies": [], "complete": True, "recommended_next_step": "fit",
    }))
    res = ia.run_turn(ia.new_state("business"), "hi")
    assert res["complete"] is False  # min-brief invariant not met

    # Now a full brief -> complete honored.
    monkeypatch.setattr(ia, "_get_client", lambda: _fake_client({
        "reply": "done", "brief": {
            "desired_outcome": "goal", "current_workflow": "manual", "success_metric": "hrs",
        },
        "quick_replies": [], "complete": True, "recommended_next_step": "fit",
    }))
    res2 = ia.run_turn(ia.new_state("business"), "hi")
    assert res2["complete"] is True
    assert res2["state"]["turns"] == 1
    # Transcript is server-owned and includes the assistant reply.
    roles = [m["role"] for m in res2["state"]["transcript"]]
    assert roles == ["user", "assistant"]


def test_run_turn_merges_brief_across_turns(monkeypatch):
    monkeypatch.setattr(ia, "_get_client", lambda: _fake_client({
        "reply": "q2", "brief": {"current_workflow": "manual"},
        "quick_replies": [], "complete": False, "recommended_next_step": "",
    }))
    prior = ia.new_state("business")
    prior["brief"] = {"desired_outcome": "goal"}
    res = ia.run_turn(prior, "hi")
    # Prior field preserved, new field added.
    assert res["brief"]["desired_outcome"] == "goal"
    assert res["brief"]["current_workflow"] == "manual"


# --- Endpoint: /api/intake/message -----------------------------------------

def _fake_turn(state, message):
    new_state = {**state, "turns": int(state.get("turns", 0)) + 1,
                 "transcript": (state.get("transcript") or []) + [{"role": "user", "content": message}, {"role": "assistant", "content": "next?"}],
                 "brief": {"desired_outcome": "goal"}}
    return {"state": new_state, "reply": "next?", "brief": {"desired_outcome": "goal"},
            "quick_replies": ["a"], "complete": False, "recommended_next_step": ""}


def test_intake_message_starts_and_signs_session(monkeypatch):
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    r = client.post("/api/intake/message", json={"path": "business", "message": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "next?"
    assert "session" in body and body["session"]
    # The returned session must verify server-side.
    assert main.intake_verify_session(body["session"]) is not None


def test_intake_message_rejects_forged_session(monkeypatch):
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    r = client.post("/api/intake/message", json={"path": "business", "session": "forged.token", "message": "hi"})
    assert r.status_code == 400


def test_intake_message_server_turn_cap(monkeypatch):
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    # Craft an over-cap session token server-side; the client cannot bypass it.
    capped = main.intake_sign_session({"path": "business", "turns": main.MAX_USER_TURNS, "transcript": [], "brief": {"desired_outcome": "g"}})
    r = client.post("/api/intake/message", json={"path": "business", "session": capped, "message": "one more"})
    assert r.status_code == 200
    assert r.json().get("capped") is True
    assert r.json()["complete"] is True


def test_intake_message_503_when_unconfigured(monkeypatch):
    monkeypatch.setattr(main, "intake_available", lambda: False)
    client = TestClient(main.app)
    r = client.post("/api/intake/message", json={"path": "business", "message": "hi"})
    assert r.status_code == 503


def test_intake_rate_limit(monkeypatch):
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    codes = [client.post("/api/intake/message", json={"path": "business", "message": "hi"}).status_code for _ in range(42)]
    assert 429 in codes  # bucket of 40 is exhausted


# --- Endpoint: /api/intake/brief (session-gated persist) --------------------

def test_intake_brief_requires_valid_session():
    client = TestClient(main.app)
    r = client.post("/api/intake/brief", json={"session": "forged.token", "brief": {"desired_outcome": "x"}})
    assert r.status_code == 400


def test_intake_brief_accepts_valid_session():
    # No DB in test env -> endpoint returns 200 with stored False, but the
    # session gate + validation path is exercised.
    client = TestClient(main.app)
    token = main.intake_sign_session(main.intake_new_state("business"))
    r = client.post("/api/intake/brief", json={
        "session": token,
        "brief": {"desired_outcome": "goal", "evil": "x" * 9000},
        "name": "A", "email": "a@b.com",
    })
    assert r.status_code == 200
    assert "brief_id" in r.json()


def test_mocked_end_to_end_intake_to_brief(monkeypatch):
    """intake message -> use the returned signed session to persist the brief."""
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    msg = client.post("/api/intake/message", json={"path": "business", "message": "hi"}).json()
    session = msg["session"]
    brief_res = client.post("/api/intake/brief", json={
        "session": session, "brief": {"desired_outcome": "goal", "current_workflow": "manual", "success_metric": "hrs"},
        "name": "A", "email": "a@b.com", "recommended_next_step": "fit",
    })
    assert brief_res.status_code == 200
