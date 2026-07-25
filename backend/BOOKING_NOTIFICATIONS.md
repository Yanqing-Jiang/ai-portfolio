# Booking setup — availability, emails, and the optional calendar

The code path is `POST /api/booking/free` in `main.py`:
`create_booking_event` (calendar_service) → `send_admin_booking_alert` →
`send_booking_confirmation_email` (email_service) → `send_booking_notification`
(telegram_service, optional).

## Google Calendar is optional

**This deployment currently runs without a calendar, and that is a supported
mode.** Availability comes from the published hours in `calendar_service.py` —
Mon-Fri 9am-4pm (a few windows per day, staggered deterministically by date),
Sat-Sun 1pm-4pm, all `America/Los_Angeles` — narrowed by the `bookings` table,
which refuses any slot already held or confirmed. A booking taken this way is
real: it has a row, a hold, and an email to both parties, and it can be
rescheduled or cancelled.

What it does *not* have is a calendar event or a Meet link. The requestor's email
says Yanqing will send the link before the call, and the owner alert is subject
`ACTION NEEDED — no Meet link`. **That alert is the mechanism** — ignore it and
the client joins nothing.

The limit worth knowing: with no calendar, the site cannot see commitments made
anywhere else, so a slot Yanqing is personally busy for is still offered. The
`bookings` table only knows what was booked through the site.

Connecting a calendar upgrades this path in place — freebusy filtering, a real
event, an attendee invitation and a Meet link — with no other change. That is
what the rest of this document is for.

## Authorizing Google is one command (optional)

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
   enabled the script still reports success, and bookings keep working in the
   calendar-free mode above — you just never get events or Meet links.
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

## What makes a day unbookable

`GET /api/booking/slots` reports `"bookable": false` when the booking endpoint
could not honour a pick, and the consult UI then replaces the picker with an
email fallback rather than offering a dead button. That means:

- **the bookings table is unreachable in production** — no hold is possible, so
  two visitors could take the same slot and neither would get a row to
  reschedule from; or
- **the table could not be read** — it is the only thing that knows which slots
  are taken (more so with no calendar), so we offer nothing rather than offer a
  slot the insert would reject with a 409 at the last click.

A missing Google Calendar does **not** make a day unbookable.

The flag is trusted only from a current, successful response — loading, an error,
or an older backend that omits the field all read as not bookable.

One filtering detail that bit us: asyncpg returns `slot_start` as UTC while
offered slots are Pacific, so comparing ISO *strings* never matched and booked
slots stayed on offer. The comparison is on instants, and excludes any
*overlapping* slot rather than only an identical start — a 60-minute booking
consumes two 30-minute slots.

## Smoke test

Works in either mode; with no calendar connected, expect `meet_link` to be empty
and an `ACTION NEEDED` alert instead of an event.

```bash
# 1. Availability should be live, and bookable true.
curl -s "http://localhost:8101/api/booking/slots?date=$(date -v+3d +%F)&session_type=30"

# 2. Book a slot to an address you control. This sends real email (and, with a
#    calendar connected, creates a real event) — use a throwaway slot and delete
#    the booking row afterwards.
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

## Reschedule and cancel (signed-in visitors)

`GET /api/booking/my-bookings`, `POST /api/booking/{id}/cancel` and
`POST /api/booking/{id}/reschedule` all require a Supabase JWT (`require_auth`,
verified HS256 against `SUPABASE_JWT_SECRET` with `aud=authenticated`). The UI is
`MyBookingsSection`, rendered on `/consult` only when `authService` reports a
user.

Bookings are claimed **by email**: the free-booking form does not know who is
signed in, so `my-bookings` backfills `user_id` onto rows whose `client_email`
matches the token's verified email. Book while signed out, sign in with the same
address, and the call is there to manage.

Cancel refunds via Stripe when the session was paid and is more than 24 hours
out, and deletes the calendar event when there is one. Reschedule needs more than
2 hours' notice. Neither needs a calendar.

Known gap (`DEBT`, task #10): reschedule inserts the new row before doing the
calendar work and suppresses a calendar failure, and cancel suppresses a deletion
failure — so a booking can end up correct in the database and stale on the
calendar, with no email either way. Fixing it properly needs a `calendar_pending`
status and a repair path; the trigger is the first real reschedule or
cancellation.
