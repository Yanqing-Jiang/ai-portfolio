#!/usr/bin/env python3
"""Re-mint the Google OAuth token the booking flow runs on.

One consent grants everything: Gmail (both booking emails) and Calendar (the
event, the attendee invitation, the Meet link). Writes the token where both
email_service and calendar_service already look for it.

    python3 backend/scripts/authorize_google.py

Run it on the machine with a browser — it opens the consent page and catches the
redirect on localhost. Deliberately stdlib-only: google-auth-oauthlib is not a
backend dependency and a once-in-a-while admin script is no reason to add one to
the runtime image.

The existing token is replaced only if everything checks out: the account you
signed in as matches the expected owner, and every required scope was granted.
A partial consent aborts without touching the file, because overwriting a working
Gmail credential with a Calendar-only one would take booking emails down.

Prerequisites in the Google Cloud project that owns the OAuth client
(gcp-oauth.keys.json → installed.project_id):
  * Gmail API and Google Calendar API enabled.
  * OAuth consent screen publishing status "In production" — while it is
    "Testing", Google expires every refresh token after 7 days, which breaks
    booking a week after each authorization.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import http.server
import json
import os
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_oauth import missing_scopes, write_token_file  # noqa: E402

DEFAULT_CREDENTIALS = Path("~/.gmail-mcp/credentials.json").expanduser()
CLIENT_KEYS_NAME = "gcp-oauth.keys.json"

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
GMAIL_PROFILE_URI = "https://gmail.googleapis.com/gmail/v1/users/me/profile"

# gmail.settings.basic is not needed by this backend, but the same token file is
# shared with the gmail-mcp setup, which does use it — dropping it here would
# quietly de-authorize that. Calendar is split readonly (freebusy) + events
# (write) rather than taking full `calendar`.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
# What the booking flow cannot run without. A grant missing any of these is
# treated as a failure; the others are best-effort.
REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

CALLBACK_TIMEOUT_S = 300


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Catches Google's redirect and hands the query back to the main thread."""

    expected_state = ""
    result: dict = {}

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler's naming
        parsed = urllib.parse.urlparse(self.path)
        params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        # Only a callback carrying our state counts. Anything else on this port
        # (a probe, a stray localhost request) must not consume the one callback
        # we are waiting for, or the real redirect would find nothing listening.
        recognized = params.get("state") == _CallbackHandler.expected_state and (
            "code" in params or "error" in params
        )
        if recognized:
            _CallbackHandler.result = params

        if recognized and "code" in params:
            body = "<h2>Authorized.</h2><p>You can close this tab and return to the terminal.</p>"
            status = 200
        elif recognized:
            body = f"<h2>Authorization failed.</h2><pre>{html.escape(params.get('error', ''))}</pre>"
            status = 400
        else:
            body = "<h2>Not the expected callback.</h2><p>Still waiting.</p>"
            status = 404

        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *_args):
        pass  # the flow narrates itself; suppress the access log


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _load_client(keys_path: Path) -> dict:
    with open(keys_path, "r", encoding="utf-8") as fh:
        keys = json.load(fh)
    section = keys.get("installed") or keys.get("web")
    if not section or not section.get("client_id"):
        raise SystemExit(f"No installed/web OAuth client in {keys_path}")
    return section


def _post_form(url: str, fields: dict) -> dict:
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(fields).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Token exchange failed ({exc.code}): {exc.read().decode()}")


def _gmail_address(access_token: str) -> str:
    """Which mailbox the new token actually belongs to."""
    req = urllib.request.Request(
        GMAIL_PROFILE_URI, headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read()).get("emailAddress", "")
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"Could not read the authorized account ({exc.code}): {exc.read().decode()}\n"
            "Refusing to replace the existing token without knowing whose it is."
        )


def _serve_callback(server: http.server.HTTPServer) -> dict:
    """Keep answering requests until the real callback arrives or time runs out."""
    server.timeout = 1.0
    deadline = time.monotonic() + CALLBACK_TIMEOUT_S
    while time.monotonic() < deadline:
        if _CallbackHandler.result:
            return _CallbackHandler.result
        server.handle_request()  # returns after ~1s if nothing connects
    return _CallbackHandler.result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--credentials", type=Path, default=DEFAULT_CREDENTIALS,
        help=f"where to write the token (default: {DEFAULT_CREDENTIALS})",
    )
    parser.add_argument(
        "--account", default=os.getenv("GMAIL_FROM_EMAIL", ""),
        help="the Google account that owns the calendar and mailbox. The grant is "
             "rejected if you sign in as anyone else. Defaults to $GMAIL_FROM_EMAIL.",
    )
    args = parser.parse_args()

    creds_path: Path = args.credentials.expanduser()
    keys_path = creds_path.parent / CLIENT_KEYS_NAME
    if not keys_path.exists():
        raise SystemExit(f"OAuth client file not found: {keys_path}")
    if not args.account:
        raise SystemExit(
            "Pass --account (or set GMAIL_FROM_EMAIL). Without an expected owner, "
            "approving with the wrong Google account would silently point booking "
            "at the wrong calendar."
        )

    client = _load_client(keys_path)
    port = _free_port()
    redirect_uri = f"http://localhost:{port}/"
    state = secrets.token_urlsafe(16)
    _CallbackHandler.expected_state = state
    _CallbackHandler.result = {}

    # PKCE: current guidance for native apps. State alone does not stop an
    # intercepted authorization code from being redeemed.
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    auth_url = client.get("auth_uri", AUTH_URI) + "?" + urllib.parse.urlencode({
        "client_id": client["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        # Without this Google returns no refresh_token on a repeat authorization,
        # and a token we cannot refresh is exactly the state we are fixing.
        "prompt": "consent",
        "state": state,
        "login_hint": args.account,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })

    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)

    print(f"Project:  {client.get('project_id', '?')}")
    print(f"Account:  sign in as {args.account}")
    print("Scopes:")
    for scope in SCOPES:
        print(f"  - {scope}")
    print(f"\nOpening the consent page. If nothing opens, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    result = _serve_callback(server)
    server.server_close()

    if not result:
        raise SystemExit("Timed out waiting for the consent redirect.")
    if "error" in result:
        raise SystemExit(f"Authorization denied: {result['error']}")

    tokens = _post_form(client.get("token_uri", TOKEN_URI), {
        "code": result["code"],
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    })

    if "refresh_token" not in tokens:
        raise SystemExit(
            "Google returned no refresh_token, so this token could not be renewed. "
            "Revoke this app at https://myaccount.google.com/permissions and retry. "
            "The existing credential file was left untouched."
        )

    # Everything below must pass BEFORE the existing token is replaced.
    if "scope" not in tokens:
        raise SystemExit(
            "The token response did not report its scopes, so the grant cannot be "
            "verified. The existing credential file was left untouched."
        )
    granted = tokens["scope"].split()

    absent = missing_scopes({"scopes": granted}, REQUIRED_SCOPES)
    if absent:
        print("\nThese required permissions were not granted:")
        for scope in absent:
            print(f"  - {scope}")
        raise SystemExit(
            "Partial consent — approve every box on the consent screen (or enable "
            "the missing API in the project). The existing credential file was "
            "left untouched."
        )

    authorized_as = _gmail_address(tokens["access_token"])
    if authorized_as.lower() != args.account.lower():
        raise SystemExit(
            f"Signed in as {authorized_as}, expected {args.account}. Booking would "
            "have read availability from the wrong calendar and written visitor "
            "details there. The existing credential file was left untouched."
        )

    # google-auth's authorized-user format, so both services read it directly.
    payload = {
        "token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_uri": client.get("token_uri", TOKEN_URI),
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "scopes": granted,
        "account": authorized_as,
    }
    if tokens.get("expires_in"):
        # Without an expiry google-auth treats the brand-new access token as
        # expired and refreshes it on the very first load.
        payload["expiry"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(time.time() + int(tokens["expires_in"])),
        )

    creds_path.parent.mkdir(parents=True, exist_ok=True)
    write_token_file(payload, creds_path)

    print(f"\nAuthorized as {authorized_as}")
    print(f"Token written to {creds_path}")
    print("Granted scopes:")
    for scope in granted:
        print(f"  - {scope}")
    print("\nNext: restart the backend so it picks the token up, then run the "
          "smoke test in backend/BOOKING_NOTIFICATIONS.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
