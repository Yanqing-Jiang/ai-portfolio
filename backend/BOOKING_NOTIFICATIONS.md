# Booking notifications — required configuration

What has to be true for one click on **Book the free 30-min call** to result in
(a) a Google Calendar event with a Meet link, (b) an email to Yanqing, and
(c) an email + calendar invitation to the person booking.

The code path is `POST /api/booking/free` in `main.py`:
`create_booking_event` (calendar_service) → `send_admin_booking_alert` →
`send_booking_confirmation_email` (email_service) → `send_booking_notification`
(telegram_service, optional).

## Status as of 2026-07-24

| Piece | State | Who can fix |
|---|---|---|
| Calendar event + Meet link | **Blocked** — `GOOGLE_CALENDAR_ID` and `GOOGLE_SERVICE_ACCOUNT_JSON` are unset, so `create_booking_event` raises and the endpoint returns 502. Nobody gets booked. | Yanqing (Google Cloud) |
| Attendee invitation | **Unreliable until impersonation is set** — see `GOOGLE_CALENDAR_IMPERSONATE_USER` below | Yanqing (Workspace admin) |
| Email to Yanqing | **Blocked** — the Gmail OAuth refresh token in `~/.gmail-mcp/credentials.json` is rejected with `invalid_grant`; it has expired or been revoked | Yanqing (re-run OAuth consent) |
| Email to the requestor | **Blocked** — same Gmail client | Yanqing |
| Telegram ping | Optional, unset (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) | Yanqing |

Availability currently comes from `_mock_available_slots`, which is why the
calendar shows times even though bookings cannot complete.

## Required keys

| Key | Required for | Notes |
|---|---|---|
| `GOOGLE_CALENDAR_ID` | event creation, real availability | The calendar's ID, not its name |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Calendar auth | **base64 of the whole service-account JSON** |
| `GOOGLE_CALENDAR_IMPERSONATE_USER` | attendee invitations | See below. Optional but strongly recommended |
| `GMAIL_FROM_EMAIL` | both emails | Set |
| `GMAIL_CREDENTIALS_PATH` | both emails | Set; the file must be readable by the backend process |
| `ADMIN_ALERT_EMAIL` | owner alert | Optional; defaults to `yanqing.app@gmail.com,jiangyanqing91@gmail.com` |
| `BOOKING_TIMEZONE` | slot math, email times | Optional; defaults to `America/Los_Angeles` |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram ping | Optional |

## Why `GOOGLE_CALENDAR_IMPERSONATE_USER` matters

The event sets `sendUpdates="all"` and adds the requestor as an attendee, which
is all that the API needs — but a *plain* service account is its own principal
with no mailbox, and Google will not reliably send invitations on its behalf to
an external address. With domain-wide delegation the service account acts **as**
a real user, and invitations are delivered normally.

Setup:

1. Google Cloud → the service account → enable domain-wide delegation, note the
   client ID.
2. Workspace Admin → Security → API controls → Domain-wide delegation → add that
   client ID with scope `https://www.googleapis.com/auth/calendar.events`.
3. Set `GOOGLE_CALENDAR_IMPERSONATE_USER` to the calendar owner's address.

Without it the backend logs a warning at startup and still books — the event is
created, but treat attendee delivery as unverified.

## Re-authorizing Gmail

`_get_gmail_service()` loads an OAuth **user** token (from the gmail-mcp setup)
and refreshes it. `invalid_grant` means the refresh token is dead — most often
because the OAuth app is still in *Testing* publishing status, where refresh
tokens expire after 7 days. Fixes, in order of durability:

1. Move the OAuth consent screen to **In production** (removes the 7-day expiry),
   then re-run the gmail-mcp auth flow to mint a fresh token.
2. Or re-run the auth flow whenever it expires (not viable for a booking flow).

The credentials file must also be writable if you want the refreshed access
token persisted — mounting it read-only is fine, it just re-refreshes each boot.

## Smoke test after configuring

```bash
# 1. Real availability (not mock) — mock mode logs a warning on first call
curl -s "http://localhost:8101/api/booking/slots?date=$(date -v+3d +%F)&session_type=30"

# 2. Book a slot to a test address you control. This sends real email and
#    creates a real calendar event — use a throwaway slot and delete it after.
curl -s -X POST http://localhost:8101/api/booking/free \
  -H 'Content-Type: application/json' \
  -d '{"slot_start":"<an offered ISO start>","name":"Smoke Test","email":"you+test@gmail.com","notes":"smoke test"}'
```

The response now carries the truth about delivery:

```json
{"status":"confirmed","meet_link":"https://meet.google.com/...",
 "notification_status":{"owner_email":"sent","requestor_email":"sent"}}
```

`"failed"` on either side means the booking exists but that party was **not**
told — the backend logs an error naming the address to contact manually, and the
confirmation screen stops claiming an email is on its way.
