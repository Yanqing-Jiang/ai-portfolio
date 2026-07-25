"""Shared loader for Google OAuth **user** credentials.

Both email_service (Gmail) and calendar_service (Calendar) authenticate as
Yanqing himself using one authorized-user token file — the one the gmail-mcp
setup created at ~/.gmail-mcp/credentials.json. This module owns that loading
so the two services cannot drift apart on it.

Why a user token rather than a service account for Calendar: a service account
is its own principal with no mailbox, so Google will not send an invitation on
its behalf to an external attendee. The usual fix is domain-wide delegation,
which requires Google Workspace — and this calendar lives on a consumer Gmail
account, where DWD does not exist. Acting as the real owner is the only path
that gets the attendee an invite and a Meet link.

Re-mint the token with `python3 backend/scripts/authorize_google.py`.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

# The full-access scopes that subsume the narrower ones we request, so a token
# granted `.../auth/calendar` still satisfies a need for `.../calendar.events`.
_SCOPE_SUPERSETS = {
    "https://www.googleapis.com/auth/gmail.send": (
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://mail.google.com/",
    ),
    "https://www.googleapis.com/auth/gmail.modify": (
        "https://mail.google.com/",
    ),
    # freebusy also accepts these narrower reads.
    "https://www.googleapis.com/auth/calendar.readonly": (
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.freebusy",
        "https://www.googleapis.com/auth/calendar.events.freebusy",
    ),
    # Writing to a calendar the authenticated user owns.
    "https://www.googleapis.com/auth/calendar.events": (
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events.owned",
    ),
}


def resolve_credentials_path(raw: str) -> Optional[Path]:
    """Expand ~ in a configured credentials path. None when unset."""
    if not raw:
        return None
    return Path(raw).expanduser()


def granted_scopes(creds_info: dict) -> set[str]:
    """Scopes the stored token actually carries.

    gmail-mcp writes `scope` as a space-separated string; google-auth's
    `to_json()` writes `scopes` as a list. A file that has been refreshed once
    is in the second format, so both have to be understood.
    """
    raw = creds_info.get("scopes") or creds_info.get("scope") or []
    if isinstance(raw, str):
        raw = raw.split()
    return {s for s in raw if s}


def missing_scopes(creds_info: dict, required: Sequence[str]) -> list[str]:
    """Required scopes the token has neither directly nor via a superset."""
    have = granted_scopes(creds_info)
    return [
        scope for scope in required
        if scope not in have and not have.intersection(_SCOPE_SUPERSETS.get(scope, ()))
    ]


def read_credentials_info(creds_path: Path) -> dict:
    """Load the token file, backfilling the OAuth client from its sibling.

    The token file stores only the tokens; refreshing also needs client_id and
    client_secret, which live in gcp-oauth.keys.json next to it.
    """
    with open(creds_path, "r", encoding="utf-8") as fh:
        creds_info = json.load(fh)

    if "client_id" not in creds_info or "client_secret" not in creds_info:
        keys_path = creds_path.parent / "gcp-oauth.keys.json"
        if keys_path.exists():
            with open(keys_path, "r", encoding="utf-8") as fh:
                keys_info = json.load(fh)
            section = keys_info.get("installed") or keys_info.get("web") or {}
            creds_info.setdefault("client_id", section.get("client_id", ""))
            creds_info.setdefault("client_secret", section.get("client_secret", ""))
            creds_info.setdefault(
                "token_uri",
                section.get("token_uri", "https://oauth2.googleapis.com/token"),
            )

    return creds_info


def load_user_credentials(
    creds_path: Path,
    required_scopes: Sequence[str],
    *,
    log_prefix: str = "[GOOGLE]",
):
    """Return refreshed google.oauth2 user Credentials, or None with a reason logged.

    Refuses a token that lacks `required_scopes` rather than handing back
    credentials that will fail mid-request with an opaque 403.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds_info = read_credentials_info(creds_path)

    absent = missing_scopes(creds_info, required_scopes)
    if absent:
        logger.warning(
            "%s Token at %s is missing scope(s): %s. Re-run "
            "`python3 backend/scripts/authorize_google.py` to grant them.",
            log_prefix, creds_path, ", ".join(absent),
        )
        return None

    # Load with everything the token was granted, not just what this caller
    # needs: _persist() rewrites the file from these scopes, so narrowing here
    # would strip the other service's scopes off the shared token file.
    credentials = Credentials.from_authorized_user_info(
        creds_info, scopes=sorted(granted_scopes(creds_info)) or list(required_scopes)
    )

    # gmail-mcp stores the access token under `access_token`, which google-auth
    # does not read — so `token` is None on a fresh file and we always refresh.
    if credentials.expired or not credentials.token:
        credentials.refresh(Request())

        # The refresh response is authoritative about what the token can now do;
        # the stored metadata is only what was once requested. Google may return
        # a narrower grant, and google-auth logs that without raising.
        actually_granted = getattr(credentials, "granted_scopes", None)
        if actually_granted:
            still_absent = missing_scopes({"scopes": actually_granted}, required_scopes)
            if still_absent:
                logger.warning(
                    "%s Refreshed token no longer carries: %s. Re-run "
                    "`python3 backend/scripts/authorize_google.py`.",
                    log_prefix, ", ".join(still_absent),
                )
                return None

        _persist(credentials, creds_path, log_prefix, actually_granted)

    return credentials


def write_token_file(payload: dict, creds_path: Path) -> None:
    """Replace the token file atomically, owner-readable only.

    Truncate-in-place would leave an empty or half-written credential if the
    process died mid-write, and a concurrent reader would then see invalid JSON.
    os.replace() is atomic within a directory, so a reader sees either the whole
    old file or the whole new one.
    """
    tmp = creds_path.with_name(f".{creds_path.name}.{os.getpid()}.tmp")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, creds_path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _persist(
    credentials, creds_path: Path, log_prefix: str,
    granted: Optional[Sequence[str]] = None,
) -> None:
    """Save the refreshed token so the next process start does not re-refresh.

    A read-only mount is fine — it just costs one refresh per boot.
    """
    try:
        payload = json.loads(credentials.to_json())
        if granted:
            # Persist what the server says we hold, not what we asked for.
            payload["scopes"] = sorted(set(granted))
        write_token_file(payload, creds_path)
    except Exception as exc:
        logger.warning("%s Could not persist refreshed token: %s", log_prefix, exc)
