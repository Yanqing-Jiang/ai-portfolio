"""Phase 2 AI Brief Agent — unit + mocked-endpoint tests.

Covers the security-critical logic the codex review flagged: server-authoritative
signed sessions, the turn cap, brief validation/clamping, the min-useful-brief
invariant, per-visitor rate limiting, and a mocked intake -> brief-persist flow
(no live model or DB needed).
"""
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_now = time.time

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
    assert not ia.min_brief_ok("business", {"desired_outcome": "goal"})
    assert not ia.min_brief_ok(
        "business",
        {"desired_outcome": "goal", "success_metric": "hrs"},
    )
    assert ia.min_brief_ok(
        "business",
        {"desired_outcome": "goal", "current_workflow": "manual"},
    )


def test_norm_path_preserves_supported_paths_and_defaults_unknown():
    assert ia._norm_path("business") == "business"
    assert ia._norm_path("individual") == "individual"
    assert ia._norm_path("training") == "training"
    assert ia._norm_path("unknown") == "individual"


def test_user_turn_cap_is_four():
    assert ia.MAX_USER_TURNS == 4


def test_system_prompts_enforce_two_core_questions_and_one_clarifier():
    for path in ("business", "individual", "training"):
        prompt = ia._system_prompt(path)
        assert "only TWO core questions long" in prompt
        # Question 1 is asked by the browser UI as a tappable choice, so the first
        # user message is its answer and the model must never re-ask it.
        assert "already asked question 1" in prompt.lower()
        assert "ALREADY ASKED by the UI" in prompt
        assert "ONE short clarifier" in prompt
        assert "Aim to finish in about 6 questions" not in prompt
        assert "`desired_outcome`" in prompt
        assert "`current_workflow`" in prompt

    training = ia._system_prompt("training")
    for name in ("GitHub Copilot", "Claude Code / Cowork", "Codex", "Pi", "OpenClaw", "Hermes"):
        assert name in training
    assert "first 30-minute call is FREE for every path" in training


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
    # Isolate the sonnet brief-turn retry from the SECOND (haiku) UI model call.
    monkeypatch.setattr(ia, "_generate_ui", lambda *a, **k: [])
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
            "desired_outcome": "goal", "current_workflow": "manual",
        },
        "quick_replies": [], "complete": True, "recommended_next_step": "fit",
    }))
    res2 = ia.run_turn(ia.new_state("business"), "hi")
    assert res2["complete"] is True
    assert res2["ui"] == [
        {"kind": "calendar", "session_type": "fit"},
        {"kind": "contact"},
    ]
    assert res2["state"]["turns"] == 1
    # Transcript is server-owned and includes the assistant reply.
    roles = [m["role"] for m in res2["state"]["transcript"]]
    assert roles == ["user", "assistant"]


def test_run_turn_force_closes_at_the_round_budget(monkeypatch):
    # The LAST allowed answer terminates the interview at booking even if the model
    # is still interviewing (complete=False) and the brief is thin. Its question is
    # replaced by a wrap-up so the reply can't contradict the calendar beneath it.
    monkeypatch.setattr(ia, "_get_client", lambda: _fake_client({
        "reply": "And how do you track them today?", "brief": {"desired_outcome": "get organized"},
        "quick_replies": ["An app", "Paper"], "complete": False, "recommended_next_step": "",
    }))
    last = ia.new_state("individual")
    last["turns"] = ia.MAX_USER_TURNS - 1
    res = ia.run_turn(last, "tasks & to-dos")

    assert res["state"]["turns"] == ia.MAX_USER_TURNS
    assert res["complete"] is True
    assert res["recommended_next_step"] == "fit"
    assert res["ui"] == [
        {"kind": "calendar", "session_type": "fit"},
        {"kind": "contact"},
    ]
    assert res["quick_replies"] == []           # calendar is the only next action
    assert "how do you track" not in res["reply"].lower()
    assert "pick a time" in res["reply"].lower()


def test_run_turn_does_not_force_close_before_the_budget(monkeypatch):
    # One answer short of the cap: still interviewing, no booking UI.
    monkeypatch.setattr(ia, "_get_client", lambda: _fake_client({
        "reply": "And how do you track them today?", "brief": {"desired_outcome": "get organized"},
        "quick_replies": ["An app"], "complete": False, "recommended_next_step": "",
    }))
    mid = ia.new_state("individual")
    mid["turns"] = ia.MAX_USER_TURNS - 2
    res = ia.run_turn(mid, "tasks & to-dos")
    assert res["complete"] is False
    assert [c["kind"] for c in res["ui"]] != ["calendar", "contact"]
    assert res["reply"] == "And how do you track them today?"


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
            "quick_replies": ["a"], "complete": False, "recommended_next_step": "", "ui": []}


@pytest.mark.parametrize("path", ["business", "individual", "training"])
def test_intake_message_starts_and_signs_session(monkeypatch, path):
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    r = client.post("/api/intake/message", json={"path": path, "message": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "next?"
    assert "session" in body and body["session"]
    state = main.intake_verify_session(body["session"])
    assert state is not None and state["path"] == path

    resumed = client.post(
        "/api/intake/message",
        json={"path": path, "session": body["session"], "message": "again"},
    )
    assert resumed.status_code == 200


def test_intake_message_rejects_forged_session(monkeypatch):
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    r = client.post("/api/intake/message", json={"path": "business", "session": "forged.token", "message": "hi"})
    assert r.status_code == 400


def test_intake_message_cap_thin_brief_still_ends_at_booking(monkeypatch):
    # Cap reached with a ONE-field brief: the round budget is spent, so the turn is
    # terminal — complete, with the booking UI. A capped interview never dead-ends
    # into "tell me more" or a hand-off to the form.
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    capped = main.intake_sign_session({"sid": "sidcapthin", "iat": int(_now()), "path": "business",
                                       "turns": main.MAX_USER_TURNS, "transcript": [], "brief": {"desired_outcome": "g"}})
    r = client.post("/api/intake/message", json={"path": "business", "session": capped, "message": "one more"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("capped") is True
    assert body["complete"] is True
    assert body["recommended_next_step"] == "fit"
    kinds = [c["kind"] for c in body["ui"]]
    assert "calendar" in kinds and "contact" in kinds


@pytest.mark.parametrize("path", ["business", "individual", "training"])
def test_intake_message_cap_full_brief_completes(monkeypatch, path):
    # Cap reached with a useful brief: capped AND complete -> free-call handoff.
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    full = {"desired_outcome": "goal", "current_workflow": "manual"}
    capped = main.intake_sign_session({"sid": f"sidcapfull-{path}", "iat": int(_now()), "path": path,
                                       "turns": main.MAX_USER_TURNS, "transcript": [], "brief": full})
    r = client.post("/api/intake/message", json={"path": path, "session": capped, "message": "one more"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("capped") is True and body["complete"] is True
    assert body["recommended_next_step"] == "fit"


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


def test_intake_message_502_releases_reservation_for_retry(monkeypatch):
    monkeypatch.setattr(main, "intake_available", lambda: True)
    calls = {"n": 0}

    def flaky_turn(state, message):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("transient model failure")
        return _fake_turn(state, message)

    monkeypatch.setattr(main, "intake_run_turn", flaky_turn)
    client = TestClient(main.app)
    tok1 = client.post("/api/intake/message", json={"path": "business", "message": "hi"}).json()["session"]
    # Second turn fails transiently -> 502; the reservation must be released.
    fail = client.post("/api/intake/message", json={"path": "business", "session": tok1, "message": "again"})
    assert fail.status_code == 502
    # Retrying the SAME valid token succeeds instead of 409ing forever.
    retry = client.post("/api/intake/message", json={"path": "business", "session": tok1, "message": "again"})
    assert retry.status_code == 200


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


# --- Unicode session size (serialized-length fitting) -----------------------

def test_fit_session_preserves_unicode_max_state_under_cap():
    # A legally max-bounded state whose transcript is emoji / CJG-heavy remains
    # under the request cap at three turns and should be preserved unchanged.
    for filler in ("😀", "漢字", "🚀🌍"):
        msg = filler * (ia.MAX_TRANSCRIPT_MSG_CHARS // len(filler))
        transcript = [{"role": "user" if i % 2 == 0 else "assistant", "content": msg}
                      for i in range(2 * ia.MAX_USER_TURNS + 2)]
        brief = {f: "outcome " + filler * 50 for f in ia.BRIEF_STR_FIELDS}
        brief["open_questions"] = [filler * 30] * ia.MAX_OPEN_QUESTIONS
        state = {"sid": "sidu", "iat": int(_now()), "path": "business",
                 "turns": ia.MAX_USER_TURNS, "transcript": transcript, "brief": brief}
        assert len(ia.sign_session(state)) <= ia.MAX_SESSION_TOKEN_CHARS
        fitted = ia.fit_session_to_cap(state)
        tok = ia.sign_session(fitted)
        assert len(tok) <= ia.MAX_SESSION_TOKEN_CHARS
        assert ia.verify_session(tok) is not None
        assert fitted == state
        assert fitted["brief"] == brief


def test_run_turn_issues_capped_token_for_unicode(monkeypatch):
    # End to end: a turn whose model reply + prior transcript are emoji-heavy still
    # issues a token within the cap (fit applied inside run_turn).
    big = "🚀" * ia.MAX_TRANSCRIPT_MSG_CHARS
    prior = ia.new_state("business")
    prior["transcript"] = [{"role": "user" if i % 2 == 0 else "assistant", "content": big}
                           for i in range(2 * ia.MAX_USER_TURNS)]
    prior["turns"] = ia.MAX_USER_TURNS - 1
    monkeypatch.setattr(ia, "_get_client", lambda: _fake_client({
        "reply": "🌍" * 2000, "brief": {"desired_outcome": "🚀" * 800},
        "quick_replies": [], "complete": False, "recommended_next_step": "",
    }))
    res = ia.run_turn(prior, "😀" * 2000)
    assert len(ia.sign_session(res["state"])) <= ia.MAX_SESSION_TOKEN_CHARS


# --- Atomic replay (concurrent identical token) -----------------------------

def test_intake_message_concurrent_identical_token_single_spend(monkeypatch):
    import concurrent.futures as cf
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    tok1 = TestClient(main.app).post("/api/intake/message", json={"path": "business", "message": "hi"}).json()["session"]

    def _fire(_):
        # Own client per thread (httpx clients aren't shared across threads).
        return TestClient(main.app).post(
            "/api/intake/message", json={"path": "business", "session": tok1, "message": "same"}).status_code

    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        codes = list(ex.map(_fire, range(2)))
    # Exactly one concurrent use of the identical token is honored; the other is
    # rejected as a stale/duplicate replay (no double model spend).
    assert codes.count(200) == 1
    assert 409 in codes


# --- Legacy (unbound) token hard-reject -------------------------------------

def test_intake_message_rejects_unbound_legacy_token(monkeypatch):
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    # A pre-fix token with neither sid nor iat must be hard-rejected (401), not
    # accepted with indefinite-replay behavior.
    legacy = main.intake_sign_session({"path": "business", "turns": 3, "transcript": [], "brief": {}})
    r = client.post("/api/intake/message", json={"path": "business", "session": legacy, "message": "hi"})
    assert r.status_code == 401
    # Missing just the iat is also rejected.
    no_iat = main.intake_sign_session({"sid": "x", "path": "business", "turns": 3, "transcript": [], "brief": {}})
    assert client.post("/api/intake/message", json={"path": "business", "session": no_iat, "message": "hi"}).status_code == 401
    # And the brief endpoint rejects an unbound token too.
    assert client.post("/api/intake/brief", json={"session": legacy, "brief": {"desired_outcome": "x"}}).status_code == 401


# --- Generative UI (A2UI) validation ----------------------------------------

def _choice(cid="systems_and_data", n=3):
    return {"kind": "choice", "id": cid, "label": "Which systems?",
            "options": [{"value": f"v{i}", "label": f"L{i}"} for i in range(n)], "multi": True}


def test_validate_ui_valid_components_pass():
    ui = ia._validate_ui(
        [
            _choice(),
            {"kind": "text", "id": "constraints", "label": "Any constraints?",
             "placeholder": "e.g. security review", "multiline": True},
        ],
        brief={}, min_ok=False, asked_ids=[],
    )
    assert len(ui) == 2
    assert ui[0]["kind"] == "choice" and ui[0]["multi"] is True
    assert len(ui[0]["options"]) == 3
    assert ui[1]["kind"] == "text" and ui[1]["multiline"] is True


def test_validate_ui_strips_unknown_and_malformed():
    ui = ia._validate_ui(
        [
            {"kind": "evil_script", "id": "x", "label": "y"},   # unknown kind -> stripped
            {"kind": "choice", "id": "a", "label": "q", "options": [{"value": "only"}]},  # <2 options -> stripped
            {"kind": "text", "id": "", "label": "no id"},        # missing id -> stripped
            _choice(cid="desired_outcome"),                        # valid -> kept
        ],
        brief={}, min_ok=False, asked_ids=[],
    )
    assert [c["kind"] for c in ui] == ["choice"]
    assert ui[0]["id"] == "desired_outcome"


def test_validate_ui_non_list_raises():
    with pytest.raises(ValueError):
        ia._validate_ui({"not": "a list"}, brief={}, min_ok=False, asked_ids=[])
    # None is a legitimate "no UI" -> [].
    assert ia._validate_ui(None, brief={}, min_ok=False, asked_ids=[]) == []


def test_validate_ui_calendar_gated_on_min_ok():
    cal = {"kind": "calendar", "session_type": "fit"}
    # min_ok False -> calendar stripped.
    assert ia._validate_ui([cal], brief={}, min_ok=False, asked_ids=[]) == []
    # min_ok True -> calendar kept.
    out = ia._validate_ui([cal], brief={}, min_ok=True, asked_ids=[])
    assert out == [{"kind": "calendar", "session_type": "fit"}]
    # Bad session_type stripped even when min_ok.
    assert ia._validate_ui([{"kind": "calendar", "session_type": "90"}], brief={}, min_ok=True, asked_ids=[]) == []


def test_validate_ui_at_most_one_calendar_and_contact():
    out = ia._validate_ui(
        [
            {"kind": "calendar", "session_type": "30"},
            {"kind": "calendar", "session_type": "60"},
            {"kind": "contact"},
            {"kind": "contact"},
        ],
        brief={}, min_ok=True, asked_ids=[],
    )
    kinds = [c["kind"] for c in out]
    assert kinds.count("calendar") == 1
    assert kinds.count("contact") == 1


def test_validate_ui_clamps_to_four_components():
    many = [_choice(cid=f"desired_outcome{i}") for i in range(8)]
    out = ia._validate_ui(many, brief={}, min_ok=False, asked_ids=[])
    assert len(out) == ia.UI_MAX_COMPONENTS == 4


def test_validate_ui_dedupes_ids():
    out = ia._validate_ui([_choice(cid="systems_and_data"), _choice(cid="systems_and_data")],
                          brief={}, min_ok=False, asked_ids=[])
    assert len(out) == 1


def test_validate_ui_clamps_lengths():
    out = ia._validate_ui(
        [{"kind": "text", "id": "x" * 100, "label": "y" * 400,
          "placeholder": "z" * 400, "multiline": False}],
        brief={}, min_ok=False, asked_ids=[],
    )
    c = out[0]
    assert len(c["id"]) == ia.UI_ID_CHARS
    assert len(c["label"]) == ia.UI_LABEL_CHARS
    assert len(c["placeholder"]) == ia.UI_PLACEHOLDER_CHARS


# --- Adaptive questioning (no repeats) --------------------------------------

def test_validate_ui_strips_already_filled_brief_field():
    # desired_outcome already answered -> its component is dropped; the empty one stays.
    out = ia._validate_ui(
        [_choice(cid="desired_outcome"), _choice(cid="constraints")],
        brief={"desired_outcome": "cut AP time"}, min_ok=False, asked_ids=[],
    )
    assert [c["id"] for c in out] == ["constraints"]


def test_validate_ui_strips_previously_asked_id():
    out = ia._validate_ui(
        [_choice(cid="systems_and_data"), _choice(cid="success_metric")],
        brief={}, min_ok=False, asked_ids=["systems_and_data"],
    )
    assert [c["id"] for c in out] == ["success_metric"]


# --- Two-model run_turn: UI generation round-trip + graceful degrade ---------

class _NamedBlock:
    type = "tool_use"

    def __init__(self, name, payload):
        self.name = name
        self.input = payload


class _NamedResp:
    def __init__(self, name, payload):
        self.content = [_NamedBlock(name, payload)]


def _dual_client(turn_payload, ui_payload, *, ui_raises=False):
    """One fake client serving BOTH model calls: routes by the forced tool name
    (submit_turn = sonnet brief turn, submit_ui = haiku UI turn)."""
    class _Msgs:
        @staticmethod
        def create(**kwargs):
            name = (kwargs.get("tool_choice") or {}).get("name")
            if name == "submit_ui":
                if ui_raises:
                    raise RuntimeError("haiku transport blew up")
                return _NamedResp("submit_ui", {"ui": ui_payload})
            return _NamedResp("submit_turn", turn_payload)

    class _Client:
        messages = _Msgs()

    return _Client()


def test_run_turn_generates_ui_and_records_asked_ids(monkeypatch):
    turn = {"reply": "Which systems does it touch?", "brief": {"desired_outcome": "goal"},
            "quick_replies": [], "complete": False, "recommended_next_step": ""}
    ui = [{"kind": "choice", "id": "systems_and_data", "label": "Which systems?",
           "options": [{"value": "sap", "label": "SAP"}, {"value": "excel", "label": "Excel"}], "multi": True}]
    monkeypatch.setattr(ia, "_get_client", lambda: _dual_client(turn, ui))
    res = ia.run_turn(ia.new_state("business"), "we reconcile invoices")
    assert res["ui"] and res["ui"][0]["id"] == "systems_and_data"
    # The shown id is recorded in the session so it won't be re-asked next turn.
    assert "systems_and_data" in res["state"]["asked_ids"]


def test_run_turn_haiku_failure_degrades_to_no_ui(monkeypatch):
    # The UI (haiku) call fails on both attempts -> turn STILL succeeds with ui=[].
    turn = {"reply": "ok", "brief": {"desired_outcome": "goal"},
            "quick_replies": [], "complete": False, "recommended_next_step": ""}
    monkeypatch.setattr(ia, "_get_client", lambda: _dual_client(turn, [], ui_raises=True))
    res = ia.run_turn(ia.new_state("business"), "hi")
    assert res["reply"] == "ok"
    assert res["ui"] == []  # degraded, not raised


def test_training_second_question_injects_exact_tool_choices(monkeypatch):
    turn = {
        "reply": "Which tools do you use or want to adopt, and what is your experience?",
        "brief": {"desired_outcome": "Train my team to ship agentic workflows"},
        "quick_replies": [],
        "complete": False,
        "recommended_next_step": "",
    }
    monkeypatch.setattr(ia, "_get_client", lambda: _fake_client(turn))
    monkeypatch.setattr(
        ia,
        "_generate_ui",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("training Q2 must be deterministic")),
    )

    res = ia.run_turn(ia.new_state("training"), "My team needs to ship with agents")
    choices = next(c for c in res["ui"] if c["kind"] == "choice")
    labels = [o["label"] for o in choices["options"]]
    assert labels == [
        "GitHub Copilot", "Claude Code / Cowork", "Codex", "Personal Pi",
        "OpenClaw", "Hermes agent setup", "Not sure — recommend for me",
    ]
    assert any(c["kind"] == "text" and c["id"] == "current_workflow" for c in res["ui"])


@pytest.mark.parametrize("path", ["business", "individual", "training"])
def test_run_turn_injects_booking_ui_without_haiku(monkeypatch, path):
    turn = {
        "reply": "Pick a time.",
        "brief": {"desired_outcome": "goal", "current_workflow": "manual"},
        "quick_replies": [],
        "complete": True,
        # Deliberately wrong: server policy must override model routing.
        "recommended_next_step": "30",
    }
    monkeypatch.setattr(ia, "_get_client", lambda: _fake_client(turn))
    monkeypatch.setattr(
        ia,
        "_generate_ui",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Haiku must be skipped")),
    )

    res = ia.run_turn(ia.new_state(path), "answer")

    assert res["recommended_next_step"] == "fit"
    assert res["ui"] == [
        {"kind": "calendar", "session_type": "fit"},
        {"kind": "contact"},
    ]


def test_generate_ui_no_client_returns_empty(monkeypatch):
    monkeypatch.setattr(ia, "_get_client", lambda: None)
    assert ia._generate_ui(ia.new_state("business"), "business", {}, "q?", False, []) == []


# --- Endpoint: a choice-answer message round-trips --------------------------

def test_intake_message_roundtrips_serialized_choice_answer(monkeypatch):
    # The client serializes component answers into the message string; the endpoint
    # must accept it and round-trip a coherent turn (with the ui array present).
    monkeypatch.setattr(main, "intake_available", lambda: True)
    monkeypatch.setattr(main, "intake_run_turn", _fake_turn)
    client = TestClient(main.app)
    tok1 = client.post("/api/intake/message", json={"path": "business", "message": "hi"}).json()["session"]
    r = client.post("/api/intake/message", json={
        "path": "business", "session": tok1,
        "message": "systems_and_data: SAP, Excel; urgency: this quarter; details: 3 FTEs reconcile manually",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "next?"
    assert "ui" in body and isinstance(body["ui"], list)
    assert main.intake_verify_session(body["session"]) is not None
