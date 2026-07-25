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

## Why a service account cannot work here (don't re-add one)

The owner's OAuth token is the *only* credential path, and that is a constraint
of Google's, not a preference. The event sets `sendUpdates="all"` and adds the
requestor as an attendee, which is all the API needs — but a service account is
its own principal with no mailbox, and Google will not send an invitation on its
behalf to an external address. The documented fix is domain-wide delegation,
which requires **Google Workspace**.

This calendar is on a consumer Gmail account (`yanqing.app@gmail.com`), where
domain-wide delegation does not exist. So a service account cannot deliver an
invite here at all, however it is configured — it would produce events nobody is
invited to. A service-account branch used to sit in `calendar_service.py` for a
hypothetical future Workspace move; it was deleted as dead code, since it could
never activate (its env vars were unset) and could not have worked if it had.

If this ever does move to Workspace, write it then against that account's actual
setup rather than restoring a branch that was never once executed.

## Environment keys

| Key | Required for | Notes |
|---|---|---|
| `GMAIL_FROM_EMAIL` | both emails | Set |
| `GMAIL_CREDENTIALS_PATH` | both emails + calendar | Set. Must be readable by the backend process — mount it into the container |
| `GOOGLE_OAUTH_CREDENTIALS_PATH` | calendar | Optional; defaults to `GMAIL_CREDENTIALS_PATH` so one token serves both |
| `GOOGLE_CALENDAR_ID` | — | Optional; defaults to `primary` (the authorized account's own calendar). Set it to book onto a different calendar on that account |
| `ADMIN_ALERT_EMAIL` | owner alert | Optional; defaults to `yanqing.app@gmail.com,jiangyanqing91@gmail.com` |
| `BOOKING_TIMEZONE` | slot math, email times | Optional; defaults to `America/Los_Angeles` |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram ping | Optional |

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

## Blocking your own time (the built-in calendar)

The `bookings` table is the single availability ledger: client bookings and your
own busy time are both rows in it, so availability is one query with no second
source to keep in sync. To take time off the market, insert a `blocked` row — one
row can cover an hour or a fortnight, because the filters are range-overlap:

```sql
INSERT INTO bookings (stripe_session_id, session_type, slot_start, slot_end,
                      client_name, client_email, status, amount_cents)
VALUES ('block_' || gen_random_uuid(), 'block',
        '2026-08-11 09:00-07', '2026-08-11 17:00-07',   -- Pacific offsets
        'BLOCKED', 'yanqing.app@gmail.com', 'blocked', 0);
```

Migration 012 enforces that no two occupying rows overlap, so this fails loudly if
you try to block time that is already booked — which is the answer you want.
Supabase Studio's table view is the owner dashboard; there is deliberately no
owner UI at this volume.

To hand a day back, `UPDATE ... SET status = 'cancelled'` — only
`hold`/`confirmed`/`calendar_failed`/`blocked` occupy time.

## A meeting link without Google Calendar

Set `BOOKING_FALLBACK_MEET_URL` to a standing room (a personal Google Meet room,
Zoom PMI, or Jitsi URL) and every booking carries a joinable link the moment it is
confirmed — in the client's email, their calendar file, and the Join button.

Leave it unset and there is no link: the client is told you'll email one and you
get an `ACTION NEEDED — no Meet link` alert. That alert is the only mechanism
keeping that promise, so setting this variable is the difference between a
guarantee and a reminder.

Note the email and the Join button both say **Google Meet**. A personal Meet room
keeps that wording true for free; a Jitsi or Zoom URL would make it a lie, so
change the copy in `email_service.py` and `BookingCard.tsx` if you go that way.

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

Cancel refunds via Stripe when the session was **paid** and is more than 24 hours
out, and deletes the calendar event when there is one. Reschedule needs more than
2 hours' notice and revalidates the new time against the published hours. Neither
needs a calendar.

Both operations claim the row before doing anything outside the database, so a
double click cannot refund twice or produce two calendar events. Cancel claims by
flipping `confirmed` → `cancelled` directly: a crash mid-cancellation therefore
leaves a booking that is genuinely cancelled, with only the reason and refund
details missing. Migration 013 still lists a `cancelling` status and carries a
`DEBT` note about rows stranded in it — both are obsolete, kept only because an
applied migration is immutable. Nothing writes `cancelling`, and there is nothing
to sweep.

Reschedule supersedes the old row rather than editing it, and has to hand over
*both* unique Stripe columns: `stripe_session_id` (UNIQUE) gets a `superseded_`
placeholder and `stripe_event_id` (UNIQUE where non-null, migration 013) is
released to NULL, so the live row owns them. Leaving either behind makes the
insert violate its index and reports a free slot as taken — that bug shipped
twice, once per column.

Both now email the client. The message carries a calendar file that updates the
one they already have rather than adding another: same `UID` (the root of the
reschedule chain) with a rising `SEQUENCE` to move the event, and `METHOD:CANCEL`
to withdraw it. If the send fails, the log names the address to contact by hand —
the booking change itself has already happened.

### When the calendar and the ledger disagree

Reschedule and cancel do not fail the request when a Google Calendar call fails.
That is deliberate: the change is already committed to the `bookings` table, which
is the record of truth, and the client's `.ics` has already moved or withdrawn
their copy. Refusing at that point would tell them their change did not happen
when it did.

What it does mean is that **your** calendar can be left wrong — a ghost event at a
cancelled or old time, or nothing at a new one. Each such failure now sends you an
owner alert naming the event id and what to fix, in the same spirit as the
`ACTION NEEDED — no Meet link` alert. It is not automatic repair; it is a
guarantee that the drift is never silent. Automatic repair (a `calendar_pending`
status and a reconciliation pass) stays unbuilt until these alerts prove frequent
enough to be worth it.

`calendar_failed` is a **confirmed** booking that merely failed to get a calendar
event. It is cancellable and reschedulable, and the UI shows it as Confirmed,
which is the truth: the person is booked. Only the calendar artifact is missing.
