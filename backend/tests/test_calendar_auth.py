"""Calendar credential selection, and the promise that we never offer a slot we
cannot book.

The booking flow authenticates as the calendar owner via an OAuth *user* token
rather than a service account, because this calendar lives on a consumer Gmail
account where domain-wide delegation does not exist — and without it Google will
not send the invitation to an external attendee. These tests pin that order of
preference, the scope check that keeps a half-authorized token from being used,
and the readiness flag the UI relies on.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import calendar_service as cs  # noqa: E402
import google_oauth as go  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CAL_EVENTS = "https://www.googleapis.com/auth/calendar.events"
CAL_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
CAL_FULL = "https://www.googleapis.com/auth/calendar"
GMAIL_MODIFY = "https://www.googleapis.com/auth/gmail.modify"


@pytest.fixture(autouse=True)
def _reset_calendar_client():
    """_get_calendar_service memoizes both success and failure — clear it."""
    cs._calendar_service = None
    cs._calendar_configured = False
    cs._calendar_auth_mode = "none"
    cs._calendar_unconfigured = False
    yield
    cs._calendar_service = None
    cs._calendar_configured = False
    cs._calendar_auth_mode = "none"
    cs._calendar_unconfigured = False


@pytest.fixture
def token_file(tmp_path) -> Path:
    """An authorized-user token granting Gmail + both calendar scopes."""
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({
        "token": "at",
        "refresh_token": "rt",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "cid",
        "client_secret": "csec",
        "scopes": [GMAIL_MODIFY, CAL_READONLY, CAL_EVENTS],
    }))
    return path


def _stub_build(monkeypatch, seen: dict):
    """Capture which credentials the Google client was built with.

    google-api-python-client is a container-only dependency, so stand in a fake
    module rather than requiring it to be installed to run the suite.
    """
    import types

    def fake_build(name, version, credentials=None, **kwargs):
        seen["name"] = name
        seen["credentials"] = credentials
        return object()

    discovery = types.ModuleType("googleapiclient.discovery")
    discovery.build = fake_build
    package = types.ModuleType("googleapiclient")
    package.discovery = discovery
    monkeypatch.setitem(sys.modules, "googleapiclient", package)
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", discovery)


# --- scope arithmetic --------------------------------------------------------

def test_space_separated_scope_string_is_understood():
    """gmail-mcp writes `scope` as a string; google-auth writes `scopes` as a list."""
    assert go.granted_scopes({"scope": f"{GMAIL_MODIFY} {CAL_EVENTS}"}) == {
        GMAIL_MODIFY, CAL_EVENTS,
    }
    assert go.granted_scopes({"scopes": [CAL_EVENTS]}) == {CAL_EVENTS}
    assert go.granted_scopes({}) == set()


def test_full_calendar_scope_satisfies_the_narrow_ones():
    assert go.missing_scopes({"scopes": [CAL_FULL]}, [CAL_READONLY, CAL_EVENTS]) == []


def test_missing_scope_is_named():
    assert go.missing_scopes({"scopes": [CAL_READONLY]}, [CAL_READONLY, CAL_EVENTS]) == [
        CAL_EVENTS,
    ]


def test_client_id_is_backfilled_from_the_sibling_keys_file(tmp_path):
    (tmp_path / "credentials.json").write_text(json.dumps({"refresh_token": "rt"}))
    (tmp_path / "gcp-oauth.keys.json").write_text(json.dumps({
        "installed": {"client_id": "cid", "client_secret": "csec"},
    }))
    info = go.read_credentials_info(tmp_path / "credentials.json")
    assert info["client_id"] == "cid"
    assert info["client_secret"] == "csec"
    assert info["token_uri"] == "https://oauth2.googleapis.com/token"


# --- auth mode selection ----------------------------------------------------

def test_oauth_user_token_is_preferred_over_a_service_account(monkeypatch, token_file):
    """A service account cannot invite external attendees here, so if both are
    configured the user token must win."""
    seen: dict = {}
    _stub_build(monkeypatch, seen)
    monkeypatch.setattr(cs, "GOOGLE_OAUTH_CREDENTIALS_PATH", str(token_file))
    monkeypatch.setattr(cs, "GOOGLE_SERVICE_ACCOUNT_JSON", "c2hvdWxkIG5vdCBiZSB1c2Vk")
    monkeypatch.setattr(cs, "GOOGLE_CALENDAR_ID", "cal@example.com")

    sentinel = object()
    monkeypatch.setattr(cs, "load_user_credentials", lambda *a, **k: sentinel)

    assert cs._get_calendar_service() is not None
    assert cs._calendar_auth_mode == "oauth_user"
    assert seen["credentials"] is sentinel


def test_service_account_is_used_when_there_is_no_oauth_token(monkeypatch, tmp_path):
    seen: dict = {}
    _stub_build(monkeypatch, seen)
    monkeypatch.setattr(cs, "GOOGLE_OAUTH_CREDENTIALS_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setattr(cs, "GOOGLE_CALENDAR_ID", "cal@example.com")
    monkeypatch.setattr(cs, "GOOGLE_SERVICE_ACCOUNT_JSON", "x")

    sentinel = object()
    monkeypatch.setattr(cs, "_service_account_credentials", lambda: sentinel)

    assert cs._get_calendar_service() is not None
    assert cs._calendar_auth_mode == "service_account"
    assert seen["credentials"] is sentinel


def test_no_credentials_means_not_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(cs, "GOOGLE_OAUTH_CREDENTIALS_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setattr(cs, "GOOGLE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setattr(cs, "GOOGLE_CALENDAR_ID", "")

    assert cs._get_calendar_service() is None
    assert cs.is_calendar_configured() is False
    assert cs._calendar_auth_mode == "none"


def test_a_token_without_calendar_scope_is_refused(monkeypatch, tmp_path):
    """Better a clear 'not configured' than an opaque 403 mid-booking.

    Stubs the Google client so the refusal comes from the scope gate and not from
    google-api-python-client being absent on the host.
    """
    _stub_build(monkeypatch, {})
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({
        "token": "at", "refresh_token": "rt", "client_id": "cid",
        "client_secret": "csec", "scopes": [GMAIL_MODIFY],
    }))
    monkeypatch.setattr(cs, "GOOGLE_OAUTH_CREDENTIALS_PATH", str(path))
    monkeypatch.setattr(cs, "GOOGLE_SERVICE_ACCOUNT_JSON", "")

    # Goes through the real loader: the token exists and is readable, so a pass
    # here would mean the scope gate let it through.
    assert cs._oauth_user_credentials() is None
    assert cs._get_calendar_service() is None


def test_service_account_without_an_explicit_calendar_id_is_not_used(monkeypatch):
    """A service account's own `primary` calendar is nobody's calendar."""
    monkeypatch.setattr(cs, "GOOGLE_SERVICE_ACCOUNT_JSON", "x")
    monkeypatch.setattr(cs, "GOOGLE_CALENDAR_ID", "")
    assert cs._service_account_credentials() is None


def test_service_account_without_impersonation_is_refused(monkeypatch):
    """It would book as itself and Google would not invite the attendee — the
    visitor ends up 'booked' with no invitation and no Meet link."""
    monkeypatch.setattr(cs, "GOOGLE_SERVICE_ACCOUNT_JSON", "x")
    monkeypatch.setattr(cs, "GOOGLE_CALENDAR_ID", "cal@example.com")
    monkeypatch.setattr(cs, "GOOGLE_CALENDAR_IMPERSONATE_USER", "")

    called = {"n": 0}
    monkeypatch.setattr(cs, "_calendar_id", lambda: "cal@example.com")

    # Refused before any credential is constructed, so no import is needed.
    assert cs._service_account_credentials() is None
    assert called["n"] == 0


def test_a_settled_unconfigured_verdict_is_not_re_decided(monkeypatch, tmp_path):
    """/api/booking/slots asks on every request; re-deciding costs a token refresh."""
    _stub_build(monkeypatch, {})
    calls = {"n": 0}

    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({"refresh_token": "rt", "scopes": [GMAIL_MODIFY]}))

    def counting_loader(*_a, **_k):
        calls["n"] += 1
        return None  # a settled verdict: the token lacks calendar scope

    monkeypatch.setattr(cs, "GOOGLE_OAUTH_CREDENTIALS_PATH", str(path))
    monkeypatch.setattr(cs, "GOOGLE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setattr(cs, "load_user_credentials", counting_loader)

    for _ in range(5):
        assert cs.is_calendar_configured() is False
    assert calls["n"] == 1, "the loader ran once and the verdict was reused"


def test_a_transient_failure_is_retried_rather_than_cached(monkeypatch, tmp_path):
    """A one-off token-endpoint timeout must not take booking offline until the
    next restart — that turns a blip into an outage nobody is watching for."""
    _stub_build(monkeypatch, {})
    calls = {"n": 0}

    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({
        "refresh_token": "rt", "scopes": [CAL_READONLY, CAL_EVENTS],
    }))

    def flaky_loader(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("token endpoint timed out")
        return object()

    monkeypatch.setattr(cs, "GOOGLE_OAUTH_CREDENTIALS_PATH", str(path))
    monkeypatch.setattr(cs, "GOOGLE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setattr(cs, "load_user_credentials", flaky_loader)

    assert cs.is_calendar_configured() is False  # the blip
    assert cs.is_calendar_configured() is True   # recovered without a restart
    assert calls["n"] == 2


# --- calendar id ------------------------------------------------------------

def test_calendar_id_defaults_to_primary(monkeypatch):
    monkeypatch.setattr(cs, "GOOGLE_CALENDAR_ID", "")
    assert cs._calendar_id() == "primary"


def test_explicit_calendar_id_wins(monkeypatch):
    monkeypatch.setattr(cs, "GOOGLE_CALENDAR_ID", "cal@example.com")
    assert cs._calendar_id() == "cal@example.com"


# --- token persistence ------------------------------------------------------

def test_refresh_does_not_strip_the_other_service_scopes(monkeypatch, token_file):
    """Gmail and Calendar share one token file. Loading it for Gmail alone used to
    be able to rewrite it with only Gmail's scopes, which would then read as
    'calendar not authorized' — one service silently de-authorizing the other."""
    from google.oauth2.credentials import Credentials

    def fake_refresh(self, _request):
        self.token = "refreshed"

    monkeypatch.setattr(Credentials, "refresh", fake_refresh)

    creds = go.load_user_credentials(token_file, [GMAIL_MODIFY])
    assert creds is not None

    after = json.loads(token_file.read_text())
    assert set(after["scopes"]) >= {GMAIL_MODIFY, CAL_READONLY, CAL_EVENTS}


# --- freebusy must fail closed ----------------------------------------------

class _FreeBusy:
    def __init__(self, payload):
        self.payload = payload

    def query(self, body=None):
        return self

    def execute(self):
        return self.payload


class _FreeBusyService:
    def __init__(self, payload):
        self.payload = payload

    def freebusy(self):
        return _FreeBusy(self.payload)


async def _slots_with_freebusy(monkeypatch, payload):
    from datetime import date, timedelta
    monkeypatch.setattr(cs, "_get_calendar_service", lambda: _FreeBusyService(payload))
    monkeypatch.setattr(cs, "GOOGLE_CALENDAR_ID", "")  # -> "primary"
    target = date.today() + timedelta(days=3)
    return await cs.get_available_slots(target, "30")


@pytest.mark.asyncio
async def test_a_per_calendar_error_is_not_read_as_a_free_day(monkeypatch):
    """Google answers HTTP 200 with `errors` for notFound/internalError. Reading
    `busy` off that yields [] — the whole day 'free' — and a booking lands on
    top of a real event. get_available_slots is also the revalidation source, so
    the POST would accept the same falsely-free slot."""
    with pytest.raises(RuntimeError, match="freebusy"):
        await _slots_with_freebusy(monkeypatch, {
            "calendars": {"primary": {"errors": [{"reason": "internalError"}]}},
        })


@pytest.mark.asyncio
async def test_a_missing_busy_list_is_treated_as_unknown(monkeypatch):
    with pytest.raises(RuntimeError, match="freebusy"):
        await _slots_with_freebusy(monkeypatch, {"calendars": {"primary": {}}})


@pytest.mark.asyncio
async def test_an_empty_busy_list_means_genuinely_free(monkeypatch):
    """The legitimate empty case must still work, or nothing is ever bookable."""
    slots = await _slots_with_freebusy(monkeypatch, {
        "calendars": {"primary": {"busy": []}},
    })
    assert slots, "an explicitly empty busy list is a free day"


@pytest.mark.asyncio
async def test_an_aliased_calendar_key_still_resolves(monkeypatch):
    """`primary` can come back keyed by the resolved address."""
    slots = await _slots_with_freebusy(monkeypatch, {
        "calendars": {"yanqing.app@gmail.com": {"busy": []}},
    })
    assert slots


# --- token file writes -------------------------------------------------------

def test_the_token_file_is_replaced_atomically_and_kept_private(tmp_path):
    """A truncate-in-place write can leave an empty credential if the process
    dies mid-write, and a concurrent reader then sees invalid JSON."""
    import stat

    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({"token": "old"}))
    go.write_token_file({"token": "new", "scopes": [CAL_EVENTS]}, path)

    assert json.loads(path.read_text())["token"] == "new"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    # No temporary file left behind.
    assert [p.name for p in tmp_path.iterdir()] == ["credentials.json"]


def test_a_failed_write_leaves_the_previous_token_intact(tmp_path, monkeypatch):
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({"token": "old"}))

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(go.json, "dump", boom)
    with pytest.raises(OSError):
        go.write_token_file({"token": "new"}, path)

    assert json.loads(path.read_text())["token"] == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["credentials.json"]


# --- readiness reaches the client ------------------------------------------

@pytest.fixture(autouse=True)
def _reset_rate_buckets():
    main._RATE_BUCKETS.clear()
    yield
    main._RATE_BUCKETS.clear()


def _slots_response(monkeypatch, *, configured: bool):
    async def fake_slots(_target_date, _session_type="30"):
        return [{"start": "2099-01-01T13:00:00-08:00", "end": "2099-01-01T13:30:00-08:00"}]

    async def no_pool():
        return None

    monkeypatch.setattr(main, "get_available_slots", fake_slots)
    monkeypatch.setattr(main, "_get_booking_pool", no_pool)
    monkeypatch.setattr(cs, "is_calendar_configured", lambda: configured)

    from datetime import date, timedelta
    target = (date.today() + timedelta(days=3)).isoformat()
    with TestClient(main.app) as client:
        return client.get(f"/api/booking/slots?date={target}&session_type=30")


def test_slots_report_bookable_when_a_calendar_is_connected(monkeypatch):
    res = _slots_response(monkeypatch, configured=True)
    assert res.status_code == 200
    assert res.json()["bookable"] is True


def test_slots_report_not_bookable_when_no_calendar_is_connected(monkeypatch):
    """The times are mock data in this state — the UI must not offer them."""
    res = _slots_response(monkeypatch, configured=False)
    assert res.status_code == 200
    body = res.json()
    assert body["bookable"] is False
    assert body["slots"], "slots are still returned; only the flag tells the truth"
