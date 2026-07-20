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


def test_validate_output_clamps_enum_and_length():
    # Valid types: unknown enum coerces to "", quick_replies clamp to 3.
    out = ia._validate_output({
        "reply": "hi",
        "brief": {"desired_outcome": "y"},
        "quick_replies": ["a", "b", "c", "d"],
        "complete": True,
        "recommended_next_step": "bogus",
    })
    assert out["recommended_next_step"] == ""  # invalid enum -> ""
    assert len(out["quick_replies"]) == 3
    assert out["reply"] == "hi"


def test_validate_output_rejects_type_violations():
    # Strict: type violations RAISE (no silent coercion), incl. bool("false").
    with pytest.raises(ValueError):
        ia._validate_output("not an object")
    with pytest.raises(ValueError):  # complete: "false" must not become True
        ia._validate_output({"reply": "hi", "brief": {}, "complete": "false", "recommended_next_step": ""})
    with pytest.raises(ValueError):  # numeric brief field, not stringified
        ia._validate_output({"reply": "hi", "brief": {"desired_outcome": 42}, "complete": True, "recommended_next_step": ""})
    with pytest.raises(ValueError):  # non-string quick_reply item
        ia._validate_output({"reply": "hi", "brief": {}, "quick_replies": ["a", 5], "complete": True, "recommended_next_step": ""})
    with pytest.raises(ValueError):  # non-string open_question
        ia._validate_output({"reply": "hi", "brief": {"open_questions": [1]}, "complete": True, "recommended_next_step": ""})
    with pytest.raises(ValueError):  # non-string reply
        ia._validate_output({"reply": 5, "brief": {}, "complete": True, "recommended_next_step": ""})


def test_run_turn_retries_once_then_fails(monkeypatch):
    # First model output malformed, second valid -> run_turn recovers on retry.
    calls = {"n": 0}

    def _flaky_create(**kwargs):
        calls["n"] += 1
        payload = ({"reply": 5} if calls["n"] == 1
                   else {"reply": "ok", "brief": {}, "quick_replies": [], "complete": False, "recommended_next_step": ""})
        return _FakeResp(payload)

    class _Msgs:
        create = staticmethod(_flaky_create)

    class _Client:
        messages = _Msgs()

    monkeypatch.setattr(ia, "_get_client", lambda: _Client())
    res = ia.run_turn(ia.new_state("business"), "hi")
    assert calls["n"] == 2 and res["reply"] == "ok"

    # Both malformed -> raises (endpoint turns this into a 502 / form fallback).
    calls["n"] = 0

    def _always_bad(**kwargs):
        calls["n"] += 1
        return _FakeResp({"reply": 5})

    class _Msgs2:
        create = staticmethod(_always_bad)

    class _Client2:
        messages = _Msgs2()

    monkeypatch.setattr(ia, "_get_client", lambda: _Client2())
    with pytest.raises(ValueError):
        ia.run_turn(ia.new_state("business"), "hi")
    assert calls["n"] == 2


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


def test_intake_message_cap_thin_brief_not_complete(monkeypatch):
    # Cap reached with a ONE-field brief: capped, but NOT complete — the min-brief
    # invariant holds on the cap path, so the client hands off to the form.
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    capped = main.intake_sign_session({"sid": "sidcapthin", "path": "business", "turns": main.MAX_USER_TURNS,
                                       "transcript": [], "brief": {"desired_outcome": "g"}})
    r = client.post("/api/intake/message", json={"path": "business", "session": capped, "message": "one more"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("capped") is True
    assert body["complete"] is False  # thin brief cannot auto-complete at the cap


def test_intake_message_cap_full_brief_completes(monkeypatch):
    # Cap reached with a useful brief: capped AND complete -> booking handoff.
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    full = {"desired_outcome": "goal", "current_workflow": "manual", "success_metric": "hrs"}
    capped = main.intake_sign_session({"sid": "sidcapfull", "path": "business", "turns": main.MAX_USER_TURNS,
                                       "transcript": [], "brief": full})
    r = client.post("/api/intake/message", json={"path": "business", "session": capped, "message": "one more"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("capped") is True and body["complete"] is True


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


# --- Token expiry -----------------------------------------------------------

def test_session_expiry():
    import time as _t
    fresh = ia.new_state("business")
    assert ia.verify_session(ia.sign_session(fresh)) is not None
    # Backdate iat past the TTL -> token is rejected (verify returns None).
    stale = {**fresh, "iat": int(_t.time()) - ia.SESSION_TTL_SECONDS - 60}
    assert ia.session_expired(stale) is True
    assert ia.verify_session(ia.sign_session(stale)) is None
    # A state with no iat never expires (legacy/non-time-bound fixtures).
    assert ia.session_expired({"path": "business", "turns": 0}) is False


def test_intake_message_rejects_expired_token(monkeypatch):
    import time as _t
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    expired = main.intake_sign_session({
        "sid": "sidexpired", "iat": int(_t.time()) - ia.SESSION_TTL_SECONDS - 60,
        "path": "business", "turns": 2, "transcript": [], "brief": {},
    })
    r = client.post("/api/intake/message", json={"path": "business", "session": expired, "message": "hi"})
    assert r.status_code == 400  # expired -> invalid -> client falls back to form


# --- Replay / stale-turn rejection ------------------------------------------

def test_intake_message_rejects_stale_turn_replay(monkeypatch):
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    # Turn 1 (fresh) -> token1; advance to turn 2 -> token2.
    tok1 = client.post("/api/intake/message", json={"path": "business", "message": "hi"}).json()["session"]
    tok2 = client.post("/api/intake/message", json={"path": "business", "session": tok1, "message": "again"}).json()["session"]
    assert main.intake_verify_session(tok2)["turns"] == 2
    # Replaying the OLD turn-1 token now that the sid has advanced -> 409 stale.
    replay = client.post("/api/intake/message", json={"path": "business", "session": tok1, "message": "replayed"})
    assert replay.status_code == 409
    # The current token still works.
    ok = client.post("/api/intake/message", json={"path": "business", "session": tok2, "message": "keep going"})
    assert ok.status_code == 200


# --- Max-size session walk (field cap) --------------------------------------

def test_max_session_walk_fits_field_cap_and_endpoint(monkeypatch):
    # A legally-maximal session token must be BELOW the request-model cap (the old
    # 16 KB cap 422'd valid tokens) and be accepted by the endpoint.
    msg = "x" * ia.MAX_TRANSCRIPT_MSG_CHARS
    transcript = [{"role": "user" if i % 2 == 0 else "assistant", "content": msg}
                  for i in range(2 * ia.MAX_USER_TURNS + 2)]
    brief = {f: "y" * ia.MAX_FIELD_CHARS for f in ia.BRIEF_STR_FIELDS}
    brief["open_questions"] = ["q" * ia.MAX_OPEN_QUESTION_CHARS] * ia.MAX_OPEN_QUESTIONS
    state = {"sid": "sidmax", "iat": int(__import__("time").time()), "path": "business",
             "turns": ia.MAX_USER_TURNS, "transcript": transcript, "brief": brief}
    token = ia.sign_session(state)
    assert len(token) < ia.MAX_SESSION_TOKEN_CHARS
    assert len(token) > 16000  # would have 422'd under the old cap

    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    # At the cap with a full brief -> 200 (capped completion), NOT a 422 on size.
    r = client.post("/api/intake/message", json={"path": "business", "session": token, "message": "hi"})
    assert r.status_code == 200
    assert r.json().get("capped") is True


# --- Trust-mode IP derivation -----------------------------------------------

class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeReq:
    def __init__(self, headers, host="10.0.0.1"):
        self.headers = headers
        self.client = _FakeClient(host)


def test_guest_ip_trust_off_ignores_spoofed_headers(monkeypatch):
    import rate_limiter as rl
    monkeypatch.setattr(rl, "TRUST_FORWARDED_IP", False)
    req = _FakeReq({"cf-connecting-ip": "1.2.3.4", "x-forwarded-for": "5.6.7.8"}, host="10.0.0.1")
    # Trust off: forwarded headers are spoofable -> use the peer only.
    assert rl._guest_ip(req) == "10.0.0.1"


def test_guest_ip_trust_on_uses_forwarded(monkeypatch):
    import rate_limiter as rl
    monkeypatch.setattr(rl, "TRUST_FORWARDED_IP", True)
    # CF header wins when present.
    assert rl._guest_ip(_FakeReq({"cf-connecting-ip": "1.2.3.4", "x-forwarded-for": "5.6.7.8"})) == "1.2.3.4"
    # Falls back to the XFF first hop when CF is absent.
    assert rl._guest_ip(_FakeReq({"x-forwarded-for": "5.6.7.8, 9.9.9.9"})) == "5.6.7.8"
    # No forwarded headers -> peer.
    assert rl._guest_ip(_FakeReq({}, host="10.0.0.2")) == "10.0.0.2"


# --- Brief -> booking DB linkage --------------------------------------------

def test_link_brief_to_booking_executes_update(monkeypatch):
    import asyncio
    captured = {}

    class _Conn:
        async def execute(self, sql, *args):
            captured["sql"] = sql
            captured["args"] = args

    class _Acquire:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *a):
            return False

    class _Pool:
        def acquire(self):
            return _Acquire()

    async def _fake_pool():
        return _Pool()

    monkeypatch.setattr(main, "_get_booking_pool", _fake_pool)
    brief_id = "123e4567-e89b-12d3-a456-426614174000"
    asyncio.run(main._link_brief_to_booking(brief_id, "booking-77", "c@d.com"))
    assert "UPDATE intake_briefs" in captured["sql"]
    assert "booking_id" in captured["sql"]
    # UUID-parsed brief id, booking id, and email are threaded into the UPDATE.
    assert str(captured["args"][2]) == brief_id
    assert captured["args"][0] == "booking-77"
    assert captured["args"][1] == "c@d.com"


def test_link_brief_to_booking_ignores_bad_uuid(monkeypatch):
    import asyncio
    called = {"n": 0}

    class _Pool:
        def acquire(self):
            called["n"] += 1
            raise AssertionError("should not acquire on bad uuid")

    async def _fake_pool():
        return _Pool()

    monkeypatch.setattr(main, "_get_booking_pool", _fake_pool)
    # Bad UUID and empty id are no-ops (never touch the pool).
    asyncio.run(main._link_brief_to_booking("not-a-uuid", "booking-77", None))
    asyncio.run(main._link_brief_to_booking(None, "booking-77", None))
    assert called["n"] == 0
