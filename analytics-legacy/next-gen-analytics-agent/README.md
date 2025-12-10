# Next Gen Analytics (legacy)

- Archived UI for the prior multi-agent memory workflow that lived under `components/analytics/memory` and related hooks.
- Backed by the old analytics backend modules (`backend/analytics`, `backend/analytics_agent.py`); these remain for reference but are no longer the primary analytics service.
- New canonical stack: `backend/conversational_analytics` with the `ConversationalAnalyticsPage` frontend.
- Run notes (legacy only): start FastAPI with the legacy analytics routes enabled, then load `/project/next-gen-analytics-agent` from a build that still mounts the memory page. Modern builds route that slug to Conversational Analytics instead.
- Status: read-only; kept for historical parity and comparison. Updates should happen in the Conversational Analytics codepath.

