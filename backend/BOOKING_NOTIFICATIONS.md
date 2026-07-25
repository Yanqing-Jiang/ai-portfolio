# Booking setup — calendar invite + both emails

What has to be true for one click on **Book the free 30-min call** to produce
(a) a Google Calendar event with a Meet link, (b) an email to Yanqing, and
(c) an email + calendar invitation to the person booking.

The code path is `POST /api/booking/free` in `main.py`:
`create_booking_event` (calendar_service) → `send_admin_booking_alert` →
`send_booking_confirmation_email` (email_service) → `send_booking_notification`
(telegram_service, optional).

## Authorizing Google is one command

```bash
python3 backend/scripts/authorize_google.py --account yanqing.app@gmail.com
```

It opens a Google consent page, and one approval grants **both** Gmail (the two
emails) and Calendar (the event, the attendee invitation, the Meet link). The
token is written to `~/.gmail-mcp/credentials.json`, which both services already
read. Restart the backend afterwards — a settled "no credential" verdict is
cached for the life of the process.

The script refuses to replace a working token unless the grant is complete and
you signed in as `--account`: a partial consent, or the wrong Google account,
aborts with the old file untouched.

`GOOGLE_CALENDAR_ID` needs no value — unset means the authorized account's own
calendar. The other required settings (`GMAIL_FROM_EMAIL`, the credential mount)
are listed below and are already in place on this deployment.

### Google Cloud prerequisites (once)

In the project that owns the OAuth client — `gcp-oauth.keys.json` →
`installed.project_id`, currently `gen-lang-client-0190176797`:

1. **Enable the Gmail API and the Google Calendar API.** Without Calendar
   enabled the script still reports success and the first booking fails.
2. **Set the OAuth consent screen to "In production."** While it is *Testing*,
   Google expires every refresh token after 7 days — booking would break a week
   after each authorization. That is the most likely reason the previous token
   died with `invalid_grant`, though Google gives the same error for revocation,
   six months of disuse, and a password change on a token with Gmail scopes.

## Why not a service account

The event sets `sendUpdates="all"` and adds the requestor as an attendee, which
is all the API needs — but a service account is its own principal with no
mailbox, and Google will not send an invitation on its behalf to an external
address. The documented fix is domain-wide delegation, which requires **Google
Workspace**.

This calendar is on a consumer Gmail account (`yanqing.app@gmail.com`), where
domain-wide delegation does not exist. So the service-account route cannot
deliver an invite here at all, no matter how it is configured. Authenticating as
the owner is the only path that works — hence the OAuth user token.

The service-account branch is still in `calendar_service.py` for a future
Workspace setup. It activates only when `GOOGLE_SERVICE_ACCOUNT_JSON`,
`GOOGLE_CALENDAR_ID` **and** `GOOGLE_CALENDAR_IMPERSONATE_USER` are all set and
no OAuth token with calendar scope exists. Without the impersonated user it is
refused rather than used, because it would create events nobody gets invited to.

Note that it is a fallback for an *absent* OAuth token, not a rescue for a broken
one: a token file that exists but fails to refresh raises, and that error is
reported rather than silently falling through.

## Environment keys

| Key | Required for | Notes |
|---|---|---|
| `GMAIL_FROM_EMAIL` | both emails | Set |
| `GMAIL_CREDENTIALS_PATH` | both emails + calendar | Set. Must be readable by the backend process — mount it into the container |
| `GOOGLE_OAUTH_CREDENTIALS_PATH` | calendar | Optional; defaults to `GMAIL_CREDENTIALS_PATH` so one token serves both |
| `GOOGLE_CALENDAR_ID` | — | Optional; defaults to `primary`. Only the service-account path needs it |
| `ADMIN_ALERT_EMAIL` | owner alert | Optional; defaults to `yanqing.app@gmail.com,jiangyanqing91@gmail.com` |
| `BOOKING_TIMEZONE` | slot math, email times | Optional; defaults to `America/Los_Angeles` |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram ping | Optional |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Workspace-only fallback | base64 of the whole service-account JSON |
| `GOOGLE_CALENDAR_IMPERSONATE_USER` | Workspace-only fallback | The delegated user |

## What a booking needs besides Google

The bookings table in Supabase is not optional in production. It holds the slot,
which is the only thing stopping two visitors taking the same time, and it is the
record a reschedule or cancellation works from. `POST /api/booking/free` returns
503 rather than "confirming" a call it cannot record.

Its TLS is worth knowing about: Supabase's pooler presents a certificate from
*Supabase Root 2021 CA*, a private root that no OS trust store carries, so a
default SSL context rejects it with `CERTIFICATE_VERIFY_FAILED` — which is how
booking persistence was silently down. `certs/supabase-prod-ca-2021.pem` pins
that root (see `db_ssl.py`), keeping verification fully on.

## What happens when it is not configured

Availability falls back to `_mock_available_slots`, so the calendar would happily
show times that the booking endpoint then rejects. To stop that,
`GET /api/booking/slots` reports `"bookable": false` whenever the calendar has no
credential *or* the bookings table is unreachable, and the consult UI replaces the
picker with an email fallback. The flag is trusted only from a current, successful
response — loading, an error, or an older backend that omits it all read as not
bookable.

So an unconfigured deploy degrades to "email me" instead of a dead button — but
nobody can self-serve a call until the command above has been run.

## Smoke test after authorizing

```bash
# 1. Availability should now be live, and bookable true.
curl -s "http://localhost:8101/api/booking/slots?date=$(date -v+3d +%F)&session_type=30"

# 2. Book a slot to an address you control. This sends real email and creates a
#    real calendar event — use a throwaway slot and delete it afterwards.
curl -s -X POST http://localhost:8101/api/booking/free \
  -H 'Content-Type: application/json' \
  -d '{"slot_start":"<an offered ISO start>","name":"Smoke Test","email":"you+test@gmail.com","notes":"smoke test"}'
```

The response reports the outcome of each send — that the Gmail API accepted the
message, which is not the same as it reaching an inbox:

```json
{"status":"confirmed","meet_link":"https://meet.google.com/...",
 "notification_status":{"owner_email":"sent","requestor_email":"sent"}}
```

`"failed"` on either side means the booking exists but that party was **not**
told — the backend logs an error naming the address to contact manually, and the
confirmation screen stops claiming an email is on its way.

If `meet_link` comes back empty the booking still stands, but nothing retries the
Meet room: you get an "ACTION NEEDED — no Meet link" alert, and the visitor is
told *you* will email the link. That promise is only kept by hand.

Check, in order: both inboxes have the confirmation, the requestor's invitation
shows up on their calendar, and the Meet link in the email opens.
