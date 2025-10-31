# Revision Hardening Ideas

## 1. Tighten Follow-Up Routes
- Emit lane-specific routes (`chart_revision`, `analysis_only`, `market_only`) even when SQL is reused so the UI stays in lane once revisions start.
- When the route is ambiguous (e.g. new helper still emits `reuse_sql`), use `normalizedLanes` to keep `revisionMode` accurate in `useAnalyticsMemoryStream`.

## 2. Instrument & Gate Lane Helpers
- Add progress/ready events inside `run_analysis_refresh` and other revision helpers so the stream shows `web_refresh` and similar events.
- Skip schema clarifier, slot collection, and other planner accessories whenever `ctx.is_revision_follow_up` and SQL/analysis aren’t requested.

## 3. Smarter Narrative Refresh Options
- Offer a light/quick analysis refresh that reuses cached SQL and only fetches targeted web snippets when tone tweaks are requested.
  - Update `SessionStateSnapshot` analytics cache to store per-lane timestamps (e.g., `lane_timestamps`).
  - Surface TTL-configurable refresh requirements in `analytics_memory_workflow`, populating `ctx.lane_refresh_required`.
  - Extend `PlannerPhaseContext` (`planner_executor.py`) with `analysis_refresh_mode` and use it inside `run_analysis_refresh`.
  - In `single_agent_tools.py` / `multi_agent.py`, branch `run_analysis_refresh` based on mode: reuse cached SQL/web when TTL is fresh; emit a progress event indicating light mode; update lane timestamps afterward.
  - Add pipeline helpers (e.g., `_compose_analysis_from_cache`) so light mode reuses artifacts without rerunning SQL/web unless TTL demands it.
  - Forward mode metadata in final events so the frontend can display “Narrative updated (cached SQL reused)” copy.
- Introduce lane TTL/freshness flags so back-to-back revisions can skip redundant web calls.

## 4. Front-End Visibility Filters
- Freeze analysis cards (or show a “chart unchanged” badge) when only the chart lane runs; prevent UI flicker.
- Dim or annotate the chart area during analysis-only revisions to signal that visuals aren’t being updated.

## 5. Dedicated Revision Pipeline (Major Refactor)
- Split `PlannerExecutorFlow` into a lightweight `RevisionFlow` that only hydrates chart/analysis/market helpers.
- Remove classification + clarification from fast-path execution entirely; emit clean lane-specific events the UI can trust.

## October 30, 2025 Implementation Notes
- Added per-lane timestamps to `SessionStateSnapshot` plus TTL helpers so revisions can decide when cached SQL/web context is still fresh.
- `analytics_memory_workflow` now computes lane freshness, pushes `lane_refresh_required` + `analysis_refresh_mode` into `PlannerPhaseContext`, and every flow respects the metadata.
- Planner pipeline emits a new light analysis path that reuses cached artifacts, stamps `analysis_complete` events with `refresh_mode`, and leaves lane timestamps untouched on cache hits.
- Single- and multi-agent controllers honour the new mode/TTL flags, falling back to full analysis when artifacts are missing.
- Front-end stream handling recognises `refresh_mode: 'light'`, keeps the revision lane in analysis, refreshes banner copy, and surfaces a "Quick narrative refresh" badge in the header.
