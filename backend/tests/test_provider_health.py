"""Tests for provider_health.py — taxonomy, redaction, cadence-safety.

Uses httpx.MockTransport (built into httpx 0.28) so no network and no new dep.
"""
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import /app module
import provider_health as ph  # noqa: E402

FULL_ENV = {
    "OPENAI_API_KEY": "sk-secretOPENAI",
    "GEMINI_API_KEY": "secretGEMINI",
    "CLAUDE_API_KEY": "sk-ant-secretCLAUDE",
    "ELEVEN_LABS_API_KEY": "secretELEVEN",
    "STRIPE_SECRET_KEY": "sk_live_secretSTRIPE",
    "SUPABASE_ANON_KEY": "secretANON",
    "SUPABASE_URL": "https://proj.supabase.co",
    "SUPABASE_JWT_SECRET": "secretJWT",
    "SERPER_API_KEY": "secretSERPER",
    "POLYGON_API_KEY": "secretPOLYGON",
    "BROWSERLESS_API_KEY": "secretBROWSERLESS",
    "GITHUB_TOKEN": "ghp_secretGITHUB",
}

SECRET_VALUES = [v for v in FULL_ENV.values() if v.startswith(("sk", "secret", "ghp"))]


def make_client(handler):
    return ph.build_client(transport=httpx.MockTransport(handler))


def all_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"ok": True})


def test_all_ok_is_healthy():
    report = ph.run_all(FULL_ENV, make_client(all_ok))
    assert report["overall"] == "healthy"
    assert {p["provider"] for p in report["providers"]} == {
        "openai", "gemini", "anthropic", "elevenlabs", "stripe",
        "supabase_anon", "supabase_jwt", "serper", "polygon",
        "browserless", "github",
    }
    assert all(p["status"] == "ok" for p in report["providers"])


def test_supabase_anon_reads_bookings_for_keepalive():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=[])

    probe = ph.probe_supabase_anon(FULL_ENV, make_client(handler))
    assert requests[0].url.path == "/rest/v1/bookings"
    assert "select=id" in requests[0].url.query.decode()
    assert "limit=1" in requests[0].url.query.decode()
    assert probe.status == "ok"
    assert probe.probe == "bookings.select"


def test_missing_keys_are_degraded_and_no_request():
    called = {"n": 0}

    def handler(request):
        called["n"] += 1
        return httpx.Response(200, json={})

    report = ph.run_all({}, make_client(handler))  # empty env
    assert report["overall"] == "degraded"
    assert all(p["status"] == "missing" for p in report["providers"])
    assert called["n"] == 0  # missing config must never hit the network


def test_invalid_auth_401():
    def handler(request):
        if request.url.host == "api.openai.com":
            return httpx.Response(401, json={"error": {"code": "invalid_api_key"}})
        return httpx.Response(200, json={})

    report = ph.run_all(FULL_ENV, make_client(handler))
    openai = [p for p in report["providers"] if p["provider"] == "openai"][0]
    assert openai["status"] == "invalid_auth"
    assert openai["http_status"] == 401
    assert report["overall"] == "degraded"


def test_openai_modellist_ok_but_generation_quota_exhausted():
    def handler(request):
        if request.url.host == "api.openai.com":
            if request.url.path.endswith("/models"):
                return httpx.Response(200, json={"data": []})  # auth fine
            # the canary generation hits insufficient_quota
            return httpx.Response(429, json={"error": {"type": "insufficient_quota"}})
        return httpx.Response(200, json={})

    report = ph.run_all(FULL_ENV, make_client(handler))
    openai = [p for p in report["providers"] if p["provider"] == "openai"][0]
    assert openai["status"] == "quota_or_billing"
    assert openai["probe"] == "chat.canary"


def test_generic_429_without_code_is_ambiguous_not_quota():
    def handler(request):
        if request.url.host == "api.stripe.com":
            return httpx.Response(429, text="Too Many Requests")  # no JSON code
        return httpx.Response(200, json={})

    report = ph.run_all(FULL_ENV, make_client(handler))
    stripe = [p for p in report["providers"] if p["provider"] == "stripe"][0]
    assert stripe["status"] == "rate_limited_or_quota"  # never guessed as quota


def test_elevenlabs_exhausted_subscription_is_quota():
    def handler(request):
        if request.url.host == "api.elevenlabs.io":
            return httpx.Response(200, json={"character_count": 100000,
                                             "character_limit": 100000,
                                             "can_extend_character_limit": False})
        return httpx.Response(200, json={})

    report = ph.run_all(FULL_ENV, make_client(handler))
    el = [p for p in report["providers"] if p["provider"] == "elevenlabs"][0]
    assert el["status"] == "quota_or_billing"


def test_5xx_is_upstream_unknown():
    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(503, text="upstream down")
        return httpx.Response(200, json={})

    report = ph.run_all(FULL_ENV, make_client(handler))
    gh = [p for p in report["providers"] if p["provider"] == "github"][0]
    assert gh["status"] == "upstream"
    assert report["overall"] == "unknown"  # no degraded class present


def test_unexpected_redirect_is_probe_contract():
    def handler(request):
        if request.url.host == "api.polygon.io":
            return httpx.Response(302, headers={"location": "https://elsewhere"})
        return httpx.Response(200, json={})

    report = ph.run_all(FULL_ENV, make_client(handler))
    poly = [p for p in report["providers"] if p["provider"] == "polygon"][0]
    assert poly["status"] == "probe_contract"  # not reinterpreted as auth failure


def test_network_error_then_retry_recovers(monkeypatch):
    monkeypatch.setattr(ph.time, "sleep", lambda *_: None)  # no 15s wait in test
    state = {"first": True}

    def handler(request):
        if request.url.host == "api.github.com" and state["first"]:
            state["first"] = False
            raise httpx.ConnectError("boom")  # str must never reach output
        return httpx.Response(200, json={})

    report = ph.run_all(FULL_ENV, make_client(handler))
    gh = [p for p in report["providers"] if p["provider"] == "github"][0]
    assert gh["status"] == "ok"  # retry succeeded


def test_no_secret_or_url_leaks_into_output():
    def handler(request):
        # respond with errors that echo nothing sensitive
        return httpx.Response(401, json={"error": {"code": "bad"}})

    report = ph.run_all(FULL_ENV, make_client(handler))
    blob = json.dumps(report)
    for secret in SECRET_VALUES:
        assert secret not in blob
    # no credential-bearing URL or query token in output
    assert "token=" not in blob
    assert "supabase.co" not in blob
    assert "api.openai.com" not in blob


def test_2xx_html_is_probe_contract_not_healthy():
    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(200, text="<html>captive portal</html>",
                                  headers={"content-type": "text/html"})
        return httpx.Response(200, json={})

    report = ph.run_all(FULL_ENV, make_client(handler))
    gh = [p for p in report["providers"] if p["provider"] == "github"][0]
    assert gh["status"] == "probe_contract"  # a 200 HTML page is NOT healthy
    assert report["overall"] == "unknown"


def test_metered_canary_network_failure_is_not_retried(monkeypatch):
    monkeypatch.setattr(ph.time, "sleep", lambda *_: None)
    calls = {"chat": 0}

    def handler(request):
        if request.url.host == "api.openai.com":
            if request.url.path.endswith("/models"):
                return httpx.Response(200, json={"data": []})  # D1 auth ok
            calls["chat"] += 1
            raise httpx.ConnectError("boom on metered canary")
        return httpx.Response(200, json={})

    report = ph.run_all(FULL_ENV, make_client(handler))
    openai = [p for p in report["providers"] if p["provider"] == "openai"][0]
    assert openai["status"] == "network"
    assert calls["chat"] == 1  # the billable canary was NOT re-issued (no double-spend)


def test_jwt_mint_is_three_part_hs256():
    tok = ph.mint_anon_jwt("topsecret", 1_000_000)
    parts = tok.split(".")
    assert len(parts) == 3
    import base64
    hdr = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    assert hdr == {"alg": "HS256", "typ": "JWT"}
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
    assert payload["role"] == "anon"
    assert payload["exp"] - payload["iat"] == 60


def test_canary_models_are_pinned_cheap_constants():
    # guards against silently swapping in an expensive/thinking model
    assert ph.OPENAI_CANARY_MODEL == "gpt-4o-mini"
    assert ph.GEMINI_CANARY_MODEL == "gemini-2.0-flash"
    assert ph.ANTHROPIC_CANARY_MODEL == "claude-haiku-4-5-20251001"


def test_main_emits_json_and_exit_code(capsys, monkeypatch):
    # build a real httpx.Client with a mock transport WITHOUT recursing into build_client
    mock_client = httpx.Client(timeout=httpx.Timeout(ph.TOTAL_TIMEOUT, connect=ph.CONNECT_TIMEOUT),
                               transport=httpx.MockTransport(all_ok), follow_redirects=False)
    monkeypatch.setattr(ph, "build_client", lambda **_: mock_client)
    monkeypatch.setattr(ph.os, "environ", FULL_ENV)
    rc = ph.main(["--json"])
    out = capsys.readouterr().out
    report = json.loads(out)
    assert report["overall"] == "healthy"
    assert rc == 0
