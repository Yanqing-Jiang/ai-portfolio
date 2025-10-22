## Tool & Artifact Reuse Optimization Plan

### 1. Enrich Tool Receipts With Intent Signatures
1. Instrument current reuse checks to log session id, tool name, cached intent, and actual slot payloads ahead of `_receipt_is_fresh` to establish a baseline (`backend/analytics/flows/multi_agent.py:792`, `backend/analytics/flows/planner_executor.py:276`).
2. Extend `ToolInvocationReceipt.metadata` in `_record_tool_receipt_from_event` to include the normalized intent signature and slot hash generated via `build_intent_signature` so every persisted receipt carries structured provenance (`backend/analytics/flows/planner_executor.py:276-347`, `backend/analytics/core/revision_snapshot.py:23`).
3. Update `_receipt_is_fresh` callers to verify signature equality before enabling reuse, while retaining today’s behaviour when metadata is absent to protect legacy sessions (`backend/analytics/flows/multi_agent.py:1151-1166`, `backend/analytics/flows/planner_executor.py:2976`).
4. Replay existing cached sessions and add negative tests where slot drift occurs to confirm the new guard forces live runs only when required.

### 2. Persist Lane-Scoped Deltas
1. Define a lightweight delta schema for `planner_bundle` (stock, web, chart, analysis shards) and document it alongside `SessionStateSnapshot.tool_cache` so consumers know to expect both full payloads and keyed summaries (`backend/analytics/core/session_state.py:83-99`).
2. Enhance `_build_revision_snapshot_payload` to capture full artifacts plus deltas, letting `record_artifacts` keep history capped at five versions (`backend/analytics/flows/planner_executor.py:1948-1976`).
3. Modify multi-agent `_maybe_queue_*` routines to emit cached deltas immediately and schedule refreshes only for lanes missing deltas or flagged stale (`backend/analytics/flows/multi_agent.py:2446-2468`).
4. Add unit coverage around `collect_tool_bundle` to verify hybrid cached/fresh bundles merge deterministically.

### 3. Share Cross-Session Assets Through Redis
1. Introduce helper methods in `CacheService` to manage shared lane keys (for example `analytics:market_snapshot:<ticker_hash>`) and guard writes with optimistic locking so readers never observe partial data (`backend/analytics/core/cache.py:37-147`).
2. When market or web lanes finish, persist sanitized payloads in both the session snapshot and the shared cache, storing the shared key + timestamp reference inside `tool_cache` (`backend/analytics/flows/tooling.py:703-714`, `backend/analytics/flows/multi_agent.py:2153-2194`).
3. Extend follow-up routing to consult shared cache freshness before defaulting to `FULL_PIPELINE`, falling back to targeted lane refreshes when a cached asset exists but the session snapshot diverged (`backend/analytics/routing/follow_up_classifier.py:78-88`).
4. Load-test overlapping sessions to validate Redis eviction, TTL sizing, and shared cache hit rates under concurrency.

### 4. Tag Provenance Throughout the Flow
1. Add a provenance enum (`"live"`, `"cached_session"`, `"cached_shared"`, `"revision"`) to artifact events before instrumentation, and thread it into SSE payloads consumed by the frontend (`backend/analytics/flows/multi_agent.py:2446-2483`, `backend/analytics/flows/instrumentation.py:186-229`).
2. Update the follow-up classifier to exploit provenance signals, allowing automatic selection of `REUSE_SQL` or `STOCK_ONLY` when cached assets remain within TTL (`backend/analytics/routing/follow_up_classifier.py:78-88`).
3. Surface provenance in `useAnalyticsSqlStream` so testers and users can confirm reuse visually without consulting logs (`components/analytics/hooks/useAnalyticsSqlStream.ts:80-214`).

### 5. Operational Safeguards and Rollout
1. Wrap each enhancement behind feature flags (for example `ANALYTICS_CACHE_ENHANCED_RECEIPTS`) so changes can be staged per-lane while preserving current behaviour (`backend/analytics/flows/workflow.py:184-206`).
2. Deploy sequentially: enable enriched receipts first, then deltas, then shared caches, validating after each step with automated smoke runs and manual session replays.
3. Post-deploy, monitor Redis hit/miss ratios via `CacheService.get_stats()` to tune TTLs or fallback thresholds before unflagging for full traffic (`backend/analytics/core/cache.py:135-167`).
4. Document rollback steps that detail which flags to disable and which Redis keys to flush if regressions surface.

### 6. Testing Strategy
1. Expand pytest suites with fixtures that seed Redis receipts/artifacts, execute planner and multi-agent flows, and assert reuse decisions honour provenance (`backend/tests/analytics/`).
2. Add integration tests covering chart and analysis revision flows to ensure delta persistence and shared caches never regress revision UX (`backend/analytics/flows/chart_revision.py:54-120`).
3. Maintain a regression playbook listing representative user queries (fresh, follow-up, revision) to replay after each rollout or rollback.

No open questions.
