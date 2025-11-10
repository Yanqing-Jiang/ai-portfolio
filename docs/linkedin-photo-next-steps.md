# LinkedIn Photo Tokens, Rate Limits & Payments Plan

## 1. Goals & User Experience
- Share a single daily prompt budget for chats and LinkedIn photo generations so usage feels consistent across workflows.
- Each LinkedIn photo run consumes 10 prompt units (˜1 generation/day for guests, 2/day for members) while retaining the existing chat weights.
- Reset free quota nightly at 00:00 UTC regardless of server restarts, and message that timing in product copy.
- Persist purchased prompt tokens (100 units per $1) in Supabase so balances survive across devices and anonymous sessions.
- Let guests purchase without signing in but remind them that anonymous tokens stay with the browser profile and free quota still resets nightly.
- Support “buy more” flows via Stripe Checkout (Apple Pay, Google Pay, Link) and PayPal one-offs.

## 2. Supabase Schema & Access
- [ ] Run the DDL below to create persistent token tables before deploying app changes.
```sql
create table public.prompt_token_balances (
  user_id uuid primary key references auth.users (id) on delete cascade,
  balance integer not null default 0,
  updated_at timestamptz not null default now()
);

create table public.prompt_token_ledger (
  id bigserial primary key,
  user_id uuid references auth.users (id) on delete cascade,
  delta integer not null,
  source text not null,
  reference_id text,
  created_at timestamptz not null default now()
);
```
- Enable Row Level Security so users can read/write only their own balances; grant service-role access for the FastAPI backend to perform atomic updates (`select ... for update`).
- Store Supabase service credentials (`SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL`, optional `SUPABASE_DB_DISABLE_SSL`) in `backend/.env` and keep anon URL/key in the frontend `.env`.
- For guests, mint an anonymous Supabase session (`signInAnonymously` or equivalent) and store the resulting `user_id` in local storage so purchased tokens persist.

## 3. Environment Configuration
- Backend `.env`: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PROMPT_PACK`, `STRIPE_WEBHOOK_SECRET`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_DISABLE_SSL` (optional), `STRIPE_TOKEN_UNITS`, `PAYPAL_TOKEN_UNITS`.
- Frontend `.env`: ensure Supabase anon URL/key plus `VITE_APP_URL` when redirects need an absolute origin.
- Document the midnight UTC reset (README + onboarding) so support and contributors can explain quota timing consistently.

## 4. Rate Limiter Enhancements
1. **Prompt-unit weighting** – add `weight: int = 1` to `smart_rate_limit`, `manual_increment_counter`, and helpers; replace `+1` with `+ weight`/`INCRBY` and expose `prompt_units_spent_today` in API responses.
2. **Daily caps** – configure global guest limit = 10 units, member limit = 20 units within `SCOPE_LIMITS`, and keep a `WORKFLOW_WEIGHTS` map so future flows (e.g., image variations) can reuse the math.
3. **Midnight UTC reset** – create `seconds_until_midnight_utc()` used for Redis TTLs and in-memory fallback so counters always expire at 00:00 UTC.
4. **LinkedIn photo integration** – inject `Request` into `backend/linkedin_photo/router.py` endpoints and call `await smart_rate_limit(..., weight=10, scope=RateLimitScope.GLOBAL)` before file parsing; return errors referencing “daily photo quota”.
5. **Token fallback** – when authenticated users exceed the free quota, attempt to consume purchased tokens before returning 429; log if no `user_id` is available.

## 5. Token Store Module
- Create `backend/token_store.py` with async helpers `get_balance(user_id)`, `increment(user_id, delta, source, reference_id)`, and `consume(user_id, amount)` that talk to Supabase/PostgREST using the service key.
- Ledger entries should capture source strings like `stripe_checkout`, `paypal_capture`, `manual_adjust`, plus payment intent/order IDs for reconciliation.
- Expose `GET /api/token-balance`, `POST /api/token-spend`, and include a `daily_reset_notice` string so the frontend can surface messaging consistently.

## 6. Backend Implementation & Payment Integrations
### 6.1 Core API Work
- Update `/api/user-input` (and LinkedIn photo endpoints) to pass `weight` values, returning `{ current_usage, limit, prompt_units_spent_today }`.
- Introduce endpoints:
  - `POST /api/payments/stripe/session` – accepts `{ successUrl, cancelUrl }`, creates Checkout Session, returns `url`.
  - `POST /api/payments/paypal/order` – creates PayPal order and returns approval data for the JS SDK.
  - Webhooks: `/api/payments/stripe/webhook`, `/api/payments/paypal/webhook` to credit balances after signature verification.
- Guard everything with `ENABLE_PROMPT_TOKENS` feature flag during rollout.

### 6.2 Stripe
- [ ] Create a $1.00 one-time price (100 token units) inside the Stripe Dashboard and capture the `price` ID for `STRIPE_PRICE_PROMPT_PACK`.
- [ ] Verify the production domain for Apple Pay and host `.well-known/apple-developer-merchantid-domain-association` in `public/`.
- [ ] Enable the Payment Request Button so Google Pay/Link work automatically; test via supported browsers.
- Deploy the Stripe webhook endpoint on a public URL, then use Stripe CLI to replay `checkout.session.completed` and confirm ledger credits.

### 6.3 PayPal
- [ ] Configure a PayPal REST app (start with sandbox), capture `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and webhook ID.
- [ ] Point the webhook at `/api/payments/paypal/webhook`, replay sandbox payloads, and ensure signature verification plus `capture` handling.
- Support anonymous purchases but remind buyers that free guest quota still resets nightly; use `PAYPAL_ENV` to control sandbox vs live.

## 7. Frontend Experience & Purchase Flow
- Build a token wallet modal/page showing free quota, purchased balance, next reset timestamp, and CTAs; refresh after successful generations and purchases.
- Add purchase entry points to the LinkedIn photo flow plus global navigation; include Stripe Checkout redirect button and PayPal JS SDK button.
- Call `apiService.countUserInput({ weight })` before uploads, and handle the enriched payload to show remaining units or friendly errors when exhausted.
- Implement `apiService.getTokenBalance()`, `createStripeSession()`, and `createPayPalOrder()` wrappers; for anonymous users, highlight that tokens persist only while the browser keeps the Supabase session.
- Surface a header/badge near the LinkedIn card (“1 daily generation remaining”, “100 tokens available”) and remind guests about the 00:00 UTC reset.

## 8. Observability, QA & Testing
- Instrument structured logs for rate-limit decisions (`identifier`, `scope`, `weight`, `result`, `source`) plus token ledger mutations.
- Add dashboards for token consumption vs purchases; monitor Stripe/PayPal webhook failures and Supabase errors.
- Testing expectations:
  - Pytest unit coverage for weighted limiter, midnight reset helper, and token store operations (mock Supabase, Stripe, PayPal, Redis).
  - Integration tests hitting `/api/user-input` with different weights and verifying ledger updates.
  - Frontend Vitest/RTL specs for quota banners, wallet modal, and purchase buttons; consider Playwright smoke for end-to-end flows.
  - Sandbox payment tests (Stripe CLI + PayPal sandbox) with webhook replay before shipping.

## 9. Rollout & Operations Checklist
- [ ] Implement backend changes behind `ENABLE_PROMPT_TOKENS` and deploy Supabase schema/RLS policies first.
- [ ] Validate Redis-based limits in staging, including midnight rollover simulation.
- [ ] Update README/onboarding docs with environment variables, midnight reset behavior, and purchase flow details.
- [ ] Deploy Stripe/PayPal integrations to staging, document success URLs, and monitor logs for the first 48 hours post-launch.
- [ ] Once stable, remove the feature flag and announce the new credit system within the LinkedIn photo project page.
