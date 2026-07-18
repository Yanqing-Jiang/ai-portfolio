#!/usr/bin/env python3
"""provider_health.py — out-of-band provider credential/quota prober.

Runs INSIDE the backend container so it sees the real `.env.production`
environment and network path the app uses:

    docker exec portfolio-backend python -m provider_health --json

It reads secrets ONLY from os.environ and emits a fixed, secret-free JSON
schema describing each provider's health. The yanqing.app watchdog parses the
JSON; it never has to see a key, a balance, a response body, or a URL.

Tiers
  D0 config    required env vars present and non-empty
  D1 auth      cheapest authenticated, NON-generative request (no tokens)
  D2 capacity  OpenAI/Gemini/Anthropic ONLY: a 1-token generation, because a
               models.list proves the key is accepted but NOT that generation
               quota/billing is available.

Hard rules (enforced throughout):
  * No secret value, response body, account identity, quota balance, credential
    fingerprint, or credential-bearing URL ever enters stdout, stderr, or logs.
  * On any exception we record only the provider name + exception class name —
    never str(exc) (it can contain a query-string token).
  * An unexpected shape (redirect, HTML, malformed JSON, surprising status) is
    `probe_contract` — never silently reinterpreted as an invalid credential.

Exit codes: 0 healthy · 1 degraded · 2 unknown · 10 internal prober error.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

import httpx

SCHEMA_VERSION = 1

# ---- D2 canary models: cheap, NON-thinking, production-compatible -----------
# Pinned constants, updated deliberately (covered by a test). Do NOT auto-pick
# the newest model from a models.list — that would silently change cost.
OPENAI_CANARY_MODEL = "gpt-4o-mini"
GEMINI_CANARY_MODEL = "gemini-2.0-flash"
ANTHROPIC_CANARY_MODEL = "claude-haiku-4-5-20251001"

CONNECT_TIMEOUT = 5.0
TOTAL_TIMEOUT = 10.0
MAX_CONCURRENCY = 3
MAX_BODY_BYTES = 1_048_576               # 1 MiB cap; larger 2xx body -> probe_contract

# probes that SPEND money/credits: a NETWORK failure on these is NOT retried
# (the request may already have been dispatched and billed)
METERED_PROBES = {"chat.canary", "generate.canary", "messages.canary", "search.canary"}

# ---- status taxonomy ---------------------------------------------------------
OK = "ok"
MISSING = "missing"
INVALID_AUTH = "invalid_auth"
FORBIDDEN_SCOPE = "forbidden_scope"
QUOTA_OR_BILLING = "quota_or_billing"
RATE_LIMITED = "rate_limited"
RATE_LIMITED_OR_QUOTA = "rate_limited_or_quota"  # 429 we cannot disambiguate
NETWORK = "network"
UPSTREAM = "upstream"
PROBE_CONTRACT = "probe_contract"

# classes that mean "a human must act; an LLM must NOT try to code-fix this"
DEGRADED_CLASSES = {
    MISSING, INVALID_AUTH, FORBIDDEN_SCOPE, QUOTA_OR_BILLING,
    RATE_LIMITED, RATE_LIMITED_OR_QUOTA,
}
UNKNOWN_CLASSES = {NETWORK, UPSTREAM, PROBE_CONTRACT}

NETWORK_EXC = (
    httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout,
    httpx.WriteTimeout, httpx.PoolTimeout, httpx.ReadError, httpx.WriteError,
    httpx.RemoteProtocolError, httpx.NetworkError,
)


# ---- helpers -----------------------------------------------------------------
def _now() -> int:
    return int(time.time())


def _b64url(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def mint_anon_jwt(secret: str, now: int) -> str:
    """Mint a 60s HS256 JWT carrying only role/iat/exp (no PII), dependency-free."""
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(json.dumps({"role": "anon", "iat": now, "exp": now + 60}, separators=(",", ":")).encode())
    signing_input = header + b"." + payload
    sig = _b64url(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    return (signing_input + b"." + sig).decode()


def _err_code(resp: httpx.Response) -> str:
    """Pull a stable provider error CODE/TYPE (never the human message) for triage."""
    try:
        body = resp.json()
    except Exception:
        return ""
    if not isinstance(body, dict):
        return ""
    err = body.get("error", body)
    if isinstance(err, dict):
        for k in ("type", "code", "status"):
            v = err.get(k)
            if isinstance(v, str):
                return v.lower()
    elif isinstance(err, str):
        return err.lower()
    return ""


def classify(resp: httpx.Response) -> str:
    """Map an HTTP response to the taxonomy using status + stable error code only."""
    code = resp.status_code
    if 200 <= code < 300:
        # a 2xx is only healthy if it is a bounded, parseable JSON body — a proxy,
        # captive page, or changed API returning 200 text/html is probe_contract
        if len(resp.content) > MAX_BODY_BYTES:
            return PROBE_CONTRACT
        ctype = resp.headers.get("content-type", "").lower()
        if "json" not in ctype:
            return PROBE_CONTRACT
        try:
            resp.json()
        except Exception:
            return PROBE_CONTRACT
        return OK
    if code == 401:
        return INVALID_AUTH
    if code == 403:
        ec = _err_code(resp)
        if any(t in ec for t in ("quota", "billing", "insufficient", "exceeded")):
            return QUOTA_OR_BILLING
        return FORBIDDEN_SCOPE
    if code in (402, 413):
        return QUOTA_OR_BILLING
    if code == 429:
        ec = _err_code(resp)
        if any(t in ec for t in ("insufficient_quota", "quota", "billing", "credit")):
            return QUOTA_OR_BILLING
        if "rate" in ec or ec == "":
            return RATE_LIMITED if ec else RATE_LIMITED_OR_QUOTA
        return RATE_LIMITED_OR_QUOTA
    if code == 400:
        ec = _err_code(resp)
        if any(t in ec for t in ("credit", "billing", "quota", "insufficient")):
            return QUOTA_OR_BILLING
        return PROBE_CONTRACT  # our minimal payload should not normally 400
    if 500 <= code < 600:
        return UPSTREAM
    return PROBE_CONTRACT


class Probe:
    """A single provider observation. Carries ONLY safe-to-emit fields."""

    __slots__ = ("provider", "status", "probe", "http_status", "latency_ms")

    def __init__(self, provider: str, status: str, probe: str,
                 http_status: Optional[int] = None, latency_ms: Optional[int] = None):
        self.provider = provider
        self.status = status
        self.probe = probe
        self.http_status = http_status
        self.latency_ms = latency_ms

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "status": self.status,
            "probe": self.probe,
            "http_status": self.http_status,
            "latency_ms": self.latency_ms,
        }


def _timed(client: httpx.Client, method: str, url: str, probe_id: str,
           **kw) -> tuple[str, Optional[int], Optional[int], Optional[httpx.Response]]:
    """Make one request; return (status, http_status, latency_ms, response).

    NEVER raises and NEVER leaks: on transport failure we return NETWORK and the
    exception class name is the most we would ever log elsewhere.
    """
    start = time.perf_counter()
    try:
        resp = client.request(method, url, **kw)
    except NETWORK_EXC:
        return NETWORK, None, int((time.perf_counter() - start) * 1000), None
    except Exception:
        # unknown transport/parse failure — fail closed, do not guess auth
        return PROBE_CONTRACT, None, int((time.perf_counter() - start) * 1000), None
    latency = int((time.perf_counter() - start) * 1000)
    return classify(resp), resp.status_code, latency, resp


# ---- per-provider probes -----------------------------------------------------
# Each takes (env, client) and returns a Probe. They must be pure w.r.t. env so
# tests can inject a fake environment + httpx.MockTransport client.

def probe_openai(env: dict, client: httpx.Client) -> Probe:
    key = env.get("OPENAI_API_KEY", "").strip()
    if not key:
        return Probe("openai", MISSING, "config")
    h = {"Authorization": f"Bearer {key}"}
    st, code, lat, _ = _timed(client, "GET", "https://api.openai.com/v1/models", "models.list", headers=h)
    if st != OK:
        return Probe("openai", st, "models.list", code, lat)
    # D2 capacity canary (1 output token) — proves generation billing/quota
    st2, code2, lat2, _ = _timed(
        client, "POST", "https://api.openai.com/v1/chat/completions", "chat.canary",
        headers=h, json={"model": OPENAI_CANARY_MODEL,
                          "messages": [{"role": "user", "content": "OK"}],
                          "max_tokens": 1},
    )
    return Probe("openai", st2, "chat.canary", code2, lat2)


def probe_gemini(env: dict, client: httpx.Client) -> Probe:
    key = env.get("GEMINI_API_KEY", "").strip()
    if not key:
        return Probe("gemini", MISSING, "config")
    h = {"x-goog-api-key": key}  # header auth -> no credential in URL
    st, code, lat, _ = _timed(
        client, "GET",
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
        "models.list", headers=h,
    )
    if st != OK:
        return Probe("gemini", st, "models.list", code, lat)
    st2, code2, lat2, _ = _timed(
        client, "POST",
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_CANARY_MODEL}:generateContent",
        "generate.canary", headers=h,
        json={"contents": [{"parts": [{"text": "OK"}]}],
              "generationConfig": {"maxOutputTokens": 1}},
    )
    return Probe("gemini", st2, "generate.canary", code2, lat2)


def probe_anthropic(env: dict, client: httpx.Client) -> Probe:
    key = env.get("CLAUDE_API_KEY", "").strip()
    if not key:
        return Probe("anthropic", MISSING, "config")
    h = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    st, code, lat, _ = _timed(client, "GET", "https://api.anthropic.com/v1/models?limit=1",
                              "models.list", headers=h)
    if st != OK:
        return Probe("anthropic", st, "models.list", code, lat)
    st2, code2, lat2, _ = _timed(
        client, "POST", "https://api.anthropic.com/v1/messages", "messages.canary",
        headers=h, json={"model": ANTHROPIC_CANARY_MODEL, "max_tokens": 1,
                         "messages": [{"role": "user", "content": "OK"}]},
    )
    return Probe("anthropic", st2, "messages.canary", code2, lat2)


def probe_elevenlabs(env: dict, client: httpx.Client) -> Probe:
    key = env.get("ELEVEN_LABS_API_KEY", "").strip()
    if not key:
        return Probe("elevenlabs", MISSING, "config")
    st, code, lat, resp = _timed(
        client, "GET", "https://api.elevenlabs.io/v1/user/subscription",
        "subscription", headers={"xi-api-key": key},
    )
    if st == OK and resp is not None:
        try:
            body = resp.json()
            used = body.get("character_count")
            limit = body.get("character_limit")
            over = body.get("can_extend_character_limit") or body.get("allowed_to_extend")
            if isinstance(used, int) and isinstance(limit, int) and used >= limit and not over:
                return Probe("elevenlabs", QUOTA_OR_BILLING, "subscription", code, lat)
        except Exception:
            pass  # auth proved; ignore body-shape issues (do not log body)
    return Probe("elevenlabs", st, "subscription", code, lat)


def probe_stripe(env: dict, client: httpx.Client) -> Probe:
    key = env.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        return Probe("stripe", MISSING, "config")
    st, code, lat, _ = _timed(client, "GET", "https://api.stripe.com/v1/balance",
                              "balance", headers={"Authorization": f"Bearer {key}"})
    return Probe("stripe", st, "balance", code, lat)


def probe_supabase_anon(env: dict, client: httpx.Client) -> Probe:
    key = env.get("SUPABASE_ANON_KEY", "").strip()
    url = env.get("SUPABASE_URL", "").strip().rstrip("/")
    if not key or not url:
        return Probe("supabase_anon", MISSING, "config")
    # This real table read also resets Supabase's free-tier 7-day inactivity timer;
    # the PostgREST root does not.
    st, code, lat, _ = _timed(
        client, "GET", f"{url}/rest/v1/bookings?select=id&limit=1", "bookings.select",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    return Probe("supabase_anon", st, "bookings.select", code, lat)


def probe_supabase_jwt(env: dict, client: httpx.Client) -> Probe:
    secret = env.get("SUPABASE_JWT_SECRET", "").strip()
    key = env.get("SUPABASE_ANON_KEY", "").strip()
    url = env.get("SUPABASE_URL", "").strip().rstrip("/")
    if not secret or not key or not url:
        return Probe("supabase_jwt", MISSING, "config")
    token = mint_anon_jwt(secret, _now())
    st, code, lat, _ = _timed(
        client, "GET", f"{url}/rest/v1/", "rest.jwt",
        headers={"apikey": key, "Authorization": f"Bearer {token}"},
    )
    return Probe("supabase_jwt", st, "rest.jwt", code, lat)


def probe_serper(env: dict, client: httpx.Client) -> Probe:
    key = env.get("SERPER_API_KEY", "").strip()
    if not key:
        return Probe("serper", MISSING, "config")
    # Serper has no free auth endpoint; one minimal search credit is the
    # deliberate, disclosed exception (see watchdog plan).
    st, code, lat, _ = _timed(
        client, "POST", "https://google.serper.dev/search", "search.canary",
        headers={"X-API-KEY": key}, json={"q": "site:example.com", "num": 1},
    )
    return Probe("serper", st, "search.canary", code, lat)


def probe_polygon(env: dict, client: httpx.Client) -> Probe:
    key = env.get("POLYGON_API_KEY", "").strip()
    if not key:
        return Probe("polygon", MISSING, "config")
    st, code, lat, _ = _timed(
        client, "GET", "https://api.polygon.io/v1/marketstatus/now", "marketstatus",
        headers={"Authorization": f"Bearer {key}"},  # header auth -> no URL cred
    )
    return Probe("polygon", st, "marketstatus", code, lat)


def probe_browserless(env: dict, client: httpx.Client) -> Probe:
    key = env.get("BROWSERLESS_API_KEY", "").strip()
    if not key:
        return Probe("browserless", MISSING, "config")
    # token must go in the query string for browserless; never log this URL.
    st, code, lat, _ = _timed(
        client, "GET", "https://chrome.browserless.io/metrics/total",
        "metrics", params={"token": key},
    )
    return Probe("browserless", st, "metrics", code, lat)


def probe_github(env: dict, client: httpx.Client) -> Probe:
    key = env.get("GITHUB_TOKEN", "").strip()
    if not key:
        return Probe("github", MISSING, "config")
    st, code, lat, _ = _timed(
        client, "GET", "https://api.github.com/rate_limit", "rate_limit",
        headers={"Authorization": f"Bearer {key}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    return Probe("github", st, "rate_limit", code, lat)


PROBES: list[Callable[[dict, httpx.Client], Probe]] = [
    probe_openai, probe_gemini, probe_anthropic, probe_elevenlabs, probe_stripe,
    probe_supabase_anon, probe_supabase_jwt, probe_serper, probe_polygon,
    probe_browserless, probe_github,
]


# ---- orchestration -----------------------------------------------------------
def build_client(transport: Optional[httpx.BaseTransport] = None) -> httpx.Client:
    timeout = httpx.Timeout(TOTAL_TIMEOUT, connect=CONNECT_TIMEOUT)
    return httpx.Client(timeout=timeout, transport=transport, follow_redirects=False)


def _overall(probes: list[Probe]) -> str:
    statuses = {p.status for p in probes}
    if statuses & DEGRADED_CLASSES:
        return "degraded"
    if statuses & UNKNOWN_CLASSES:
        return "unknown"
    return "healthy"


def run_all(env: dict, client: httpx.Client,
            checked_at: Optional[str] = None) -> dict:
    """Run every probe (bounded concurrency) and assemble the fixed schema."""
    results: list[Probe] = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        for p in pool.map(lambda fn: fn(env, client), PROBES):
            results.append(p)
    # one in-run retry for transient NETWORK only, and ONLY when the failed probe
    # was non-metered — re-running a provider whose metered D2/search request may
    # already have been dispatched would double-spend (H9)
    transient = [i for i, p in enumerate(results)
                 if p.status == NETWORK and p.probe not in METERED_PROBES]
    if transient:
        time.sleep(15)
        retry_fns = [PROBES[i] for i in transient]
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
            for idx, p in zip(transient, pool.map(lambda fn: fn(env, client), retry_fns)):
                results[idx] = p
    results.sort(key=lambda p: p.provider)
    return {
        "schema": SCHEMA_VERSION,
        "checked_at": checked_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall": _overall(results),
        "providers": [p.as_dict() for p in results],
    }


_EXIT = {"healthy": 0, "degraded": 1, "unknown": 2}


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    as_json = "--json" in argv or True  # JSON is the contract; flag kept for clarity
    try:
        client = build_client()
        try:
            report = run_all(dict(os.environ), client)
        finally:
            client.close()
    except Exception:
        # never leak: emit a fixed internal-error envelope, no exception text
        print(json.dumps({"schema": SCHEMA_VERSION, "overall": "unknown",
                          "error": "prober_internal_error", "providers": []}))
        return 10
    if as_json:
        print(json.dumps(report))
    return _EXIT.get(report["overall"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
