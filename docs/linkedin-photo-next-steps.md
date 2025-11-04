# LinkedIn Photo Tokens & Payments — Next Steps

## 1. Supabase Schema & Access
- [ ] Run the DDL from `docs/linkedin-photo-rate-limit-plan.md` to create `prompt_token_balances` and `prompt_token_ledger`.
- [ ] Enable Row Level Security and policies so users can read/write only their own rows; grant service-role access for the FastAPI backend.
- [ ] Store the Supabase service key (`SUPABASE_SERVICE_KEY`) and database URL (`SUPABASE_DB_URL`) in the backend `.env`.

## 2. Environment Configuration
- [ ] Backend `.env` additions: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PROMPT_PACK`, `STRIPE_WEBHOOK_SECRET`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`, `SUPABASE_DB_URL`, `SUPABASE_DB_DISABLE_SSL` (optional), `STRIPE_TOKEN_UNITS`, `PAYPAL_TOKEN_UNITS`.
- [ ] Frontend `.env` updates: ensure Supabase anon URL/key already present; add `VITE_APP_URL` if needed for OAuth redirects.
- [ ] Document the midnight UTC reset in README and developer onboarding notes.

## 3. Stripe Integration
- [ ] Create a $1.00 price in Stripe Dashboard (one-time, no trial) and capture the price ID for `STRIPE_PRICE_PROMPT_PACK`.
- [ ] Verify the domain in Stripe for Apple Pay, enable Payment Request Button, and test Google Pay in supported browsers.
- [ ] Deploy Stripe webhook endpoint (`/api/payments/stripe/webhook`) on a public URL; use Stripe CLI to test events and confirm tokens credit.

## 4. PayPal Integration
- [ ] Set up PayPal REST app (sandbox first), record client ID/secret/webhook ID, and update `.env`.
- [ ] Configure webhook to point at `/api/payments/paypal/webhook`; replay test payloads to validate signature verification and capture flow.
- [ ] Decide on live vs sandbox mode via `PAYPAL_ENV`; perform end-to-end capture in sandbox before switching.

## 5. Frontend Experience
- [ ] Implement a token wallet modal/page showing free quota, purchased balance, next reset, and purchase calls-to-action.
- [ ] Add purchase buttons (Stripe Checkout redirect and PayPal JS SDK button) to the LinkedIn photo flow and any global navigation surface.
- [ ] Show reminder text for guests: free quota resets nightly; encourage sign-in to keep tokens available across devices.

## 6. Observability & QA
- [ ] Add logging/metrics dashboards for token consumption vs. purchases; monitor Stripe/PayPal error logs.
- [ ] Expand automated tests: backend integration tests for new endpoints, frontend tests for quota messaging, Cypress/Playwright for purchase flow smoke.
- [ ] Run regression testing on LinkedIn photo generation (free + paid paths) before launch; confirm fallback behavior when Supabase/Stripe/PayPal are unavailable.

