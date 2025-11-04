# LinkedIn Photo Rate Limits & Token Monetization Plan

## 1. Goals & User Experience
- Share a single daily prompt budget for chats and image generations. LinkedIn photo generations should consume 10 prompt units apiece, equating to “one generation per day” for guests and “two per day” for members.
- Track free quota resets at midnight UTC, regardless of server restarts.
- Persist purchased prompt tokens (100 units per $1) until consumed, using Supabase so balances survive across devices.
- Allow guests to complete a purchase without signing in, but clearly tell them that their free guest allowance still resets at midnight UTC and encourage conversion to a full account.
- Support buy-more flows via Stripe Checkout (including Apple Pay, Google Pay, Link) and PayPal “Buy Me a Coffee”-style one-offs.

## 2. Current State Summary
- `backend/rate_limiter.py` enforces 5 guest vs 20 member calls per 24 hours via Redis keys, with in-memory fallback and manual Redis increment logic.
- `/api/user-input` (FastAPI) calls `smart_rate_limit` for analytics/chat flows; LinkedIn photo endpoints do not currently count against the limiter.
- Frontend tracks usage via `apiService.countUserInput()` and displays quota messaging primarily in `components/Chat.tsx`.
- Supabase OAuth manages authenticated users; guests fall back to IP-based identifiers.
- No on-disk persistence exists for purchased credits or payments.

## 3. Rate Limiter Enhancements
1. **Prompt-Unit Weighting**
   - Add a `weight: int = 1` parameter to `smart_rate_limit`, `manual_increment_counter`, and all internal helpers.
   - Replace `+ 1` increments with `+ weight` or Redis `INCRBY`.
   - Update return payloads from `/api/user-input` to report `current_usage` and `limit` in prompt units plus a derived `prompt_units_spent_today`.
2. **Daily Caps**
   - Set global guest limit to 10 units, member limit to 20 units inside `SCOPE_LIMITS`.
   - Factor in LinkedIn photo and future workflows by carrying scope → weight recommendations in a mapping (e.g., `WORKFLOW_WEIGHTS`).
3. **Midnight UTC Reset**
   - When creating Redis keys, calculate TTL as seconds until the next midnight UTC (e.g., `datetime.now(timezone.utc)` → next midnight).
   - For in-memory fallback, store `(count, window_start)` and reset when `datetime.utcnow() >= next_midnight_cached`.
4. **LinkedIn Photo Integration**
   - Add `request: Request` dependency in `backend/linkedin_photo/router.py` endpoints and call `await smart_rate_limit(request, weight=10, scope=RateLimitScope.GLOBAL)` before file parsing.
   - Ensure error messages reference “daily photo quota” for clarity.

## 4. Supabase Persistence
1. **Schema**
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
     source text not null,        -- e.g. 'stripe_checkout', 'paypal_capture', 'manual_adjust'
     reference_id text,           -- payment intent or order id
     created_at timestamptz not null default now()
   );
   ```
2. **Access Control**
   - Use Supabase Row Level Security to allow users to read only their own balance & ledger entries.
   - Create service-role functions for the backend to update balances atomically (`select` → `for update`).
3. **Guest Identity Handling**
   - On initial visit, call `supabase.auth.signInAnonymously()` (or a lightweight magic link flow) to mint a stable `user_id` for guests; store it in local storage so purchased tokens persist.
   - Display a reminder in purchase dialogs: “Free guest quota still resets nightly (00:00 UTC); sign in to retain tokens across browsers.”

## 5. Backend Implementation Steps
1. **Refactor rate limiter**
   - Introduce helper `seconds_until_midnight_utc()` and reuse in Redis key creation & fallback resets.
   - Extend logging lines to include weight and post-purchase fallback usage.
2. **Token Store Module**
   - Create `backend/token_store.py` with async functions `get_balance(user_id)`, `increment(user_id, delta, source, reference_id)`, `consume(user_id, amount)` that use Supabase client / PostgREST.
   - Fetch Supabase service key from environment (`SUPABASE_SERVICE_KEY`) and reuse existing HTTP client utilities if present.
3. **Limiter + Tokens**
   - In `smart_rate_limit`, when the free quota is exhausted for authenticated users, attempt to `consume(weight)`; on success, continue without raising 429.
   - For guests (anonymous Supabase users), same fallback applies; log a warning if no user_id is present.
4. **API Endpoints**
   - `GET /api/token-balance`: returns `{ balance, last_updated, daily_free_remaining }`.
   - `POST /api/token-spend`: accepts `{ amount }` for future workflows; primarily an admin/testing endpoint.
   - `POST /api/payments/stripe/session`: accepts `{ successUrl, cancelUrl }`, creates Stripe Checkout Session, returns session URL.
   - `POST /api/payments/paypal/order`: creates PayPal order and returns approval link.
   - Webhook endpoints: `/api/payments/stripe/webhook`, `/api/payments/paypal/webhook` to credit balances on successful payments after validating signatures.
5. **Guest Messaging**
   - Include `daily_reset_notice` string in `/api/token-balance` so the frontend can show “Free guest quota restarts at 00:00 UTC.”

## 6. Frontend Updates
1. **Shared Services**
   - Extend `apiService.countUserInput({ weight })` to pass weight through body.
   - Add `apiService.getTokenBalance()` and `apiService.createStripeSession()` / `createPayPalOrder()` wrappers.
2. **LinkedIn Photo Flow**
   - Before uploading, call `countUserInput({ weight: 10 })`; display returned `remaining` units and friendly error if quota empty.
   - After a successful generation, refresh balance/usage badges.
3. **Purchase UI**
   - Add a new `TokenWalletModal` component keyed off auth state; show free quota, remaining tokens, and purchase buttons.
   - For guests, highlight “Tokens persist while this browser remains signed in; free daily photo resets nightly (00:00 UTC).”
   - Integrate Stripe Checkout redirect (client-only) and PayPal button via JS SDK.
4. **Header/Banner**
   - Surface a badge near the LinkedIn project card indicating photo quota status (e.g., “1 daily generation remaining”).

## 7. Payments Integration Details
1. **Stripe Checkout**
   - Backend: generate checkout session with one-off `price` (e.g., `price_prompt_100`). Use `customer_email` from Supabase profile when available.
   - Frontend: call backend endpoint, redirect to returned URL. Handle `success_url` route (e.g., `/tokens/success?session_id=`) to poll backend for updated balance.
   - Webhook: listen for `checkout.session.completed`; fetch session, verify status, credit 100 units.
2. **Apple Pay / Google Pay**
   - Apple Pay: verify domain through Stripe Dashboard, host `.well-known/apple-developer-merchantid-domain-association` in Vite public folder.
   - Google Pay: ensure Payment Request Button is enabled in Stripe; add `merchantId` for production.
   - Link support is automatic with Checkout.
3. **PayPal**
   - Fetch OAuth token server-side, create order (`intent="CAPTURE"`). Return `approve` link to frontend for JS SDK to render button.
   - Webhook: handle `CHECKOUT.ORDER.APPROVED` → call `capture` if not already done, then credit tokens and log ledger row.

## 8. Guest Purchase Handling
- Anonymous Supabase sessions provide consistent `user_id`; store ID + flag in local storage and sync with Supabase on load.
- When a guest purchases tokens, remind them in the confirmation view: “Daily guest photo limit still resets at 00:00 UTC. Tokens remain until spent while you keep this account.”
- Offer a call-to-action to upgrade to full membership (sign-up) without forfeiting existing balance.

## 9. Operations & Configuration
- **Environment Variables**
  - Stripe: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PROMPT_PACK`, `STRIPE_WEBHOOK_SECRET`.
  - PayPal: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`.
  - Supabase: ensure `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY` available to backend.
- **Logging & Monitoring**
  - Emit structured logs for rate limit decisions: `{ identifier, scope, weight, result, source }`.
  - Store payment webhook receipts in Supabase ledger for reconciliation.
  - Consider Grafana/Prometheus counters for `prompt_units_consumed`, `token_units_consumed`.

## 10. Testing Strategy
- Unit tests (Pytest) for weighted limiter, midnight reset calculations, and token store consumption logic.
- Integration tests hitting `/api/user-input` with different weights and verifying Supabase ledger updates via mocking.
- Frontend Vitest/React Testing Library specs for quota banners, paywall modals, and purchase flows (mock fetch).
- Sandbox payment tests using Stripe test mode and PayPal sandbox accounts; verify webhook handlers by replaying sample payloads.

## 11. Rollout Checklist
1. Implement backend changes behind feature flag `ENABLE_PROMPT_TOKENS`.
2. Deploy Supabase schema migrations and RLS policies.
3. Validate Redis-based limits in staging with midnight rollover simulation.
4. Test Stripe/PayPal integrations in their respective sandboxes; document success URLs.
5. Launch frontend updates with clear user messaging; monitor logs for first 48 hours.
6. Once stable, remove feature flag and announce the new credit system within the LinkedIn photo project page.

