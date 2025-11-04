# Revision Refresh Alternative Strategies

## Context Snapshot (2025-11-04)
- Latest single-agent and multi-agent revision runs (ledger timestamps 2025-11-04T02:03 and 2025-11-04T02:44) still enter the `analysis_only` route with the `Web Research Unavailable` banner, indicating that the web lane never emits a `web_ready` event.
- Telemetry shows the analysis lane completing quickly while web tooling is skipped; duplicate `analysis_revision` payloads suggest the frontend keeps replaying cached analysis without fresh web snippets.
- Backend changes now persist revision snapshots and tool receipts, but the live workflow still fails to trigger `refresh_web_lane`, so the root issue is likely higher in the orchestration layer (e.g., missing topics, disabled adapters, or gating logic that prevents the retriever from running).
- Given repeated failures and slipping timelines, the team requested broader architectural options instead of another incremental fix.

## Option 1 — Harden Existing Planner Pipeline (Incremental Fix)
**Effort:** Medium (1–2 weeks)  
**Goal:** Keep the current FastAPI + Vite stack but deeply instrument the revision pipeline to guarantee web fan-out.

### Key Activities
1. Add high-granularity tracing around `_reset_revision_accessories`, `run_web_refresh`, and `refresh_web_lane` to confirm adapter selection and queue states.  
2. Force-enable `web_retriever_live` during revisions with a feature flag to bypass cached-only execution and confirm whether the adapter itself fails.  
3. Extend regression tests with golden sessions that assert a `web_ready` event appears after rehydrate (single-agent and multi-agent flows).  
4. Frontend: de-duplicate revision cards by enforcing unique IDs and ignoring replayed analysis payloads when `web_ready` is missing.

### Trade-offs
- Least disruption to the codebase and existing tools.
- Continued custom-maintenance burden on planner orchestration logic.
- Does not address long-term desire for “true” agents that own their state.

## Option 2 — Adopt OpenAI Agents SDK for Supervisor + Specialists
**Effort:** High (4–6 weeks pilot; 8–10 weeks for production)**  
**Goal:** Replace bespoke planner executors with an OpenAI Agent orchestrator running a supervisor agent plus specialist tools for SQL, charting, and web research.

### Why Agents SDK
- The Agents SDK natively supports orchestrating multi-tool, multi-step workflows with shared memory/state, interchangeable tool adapters, and structured plans driven by OpenAI responses citeturn0search2.
- Combined with OpenAI’s AgentKit, the supervisor can call reusable tool functions (e.g., Supabase queries, search retrievers) without maintaining custom executor plumbing citeturn0search1.
- Recent Agent SDK updates focus on agents that “reason about when to call tools and how to orchestrate them,” aligning with the revision use case where the agent should decide whether web refresh is required citeturn0search3.

### Migration Outline
1. **Prototype** a supervisor agent with three tools: `run_sql`, `render_chart`, `fetch_web_briefs`. Use the SDK’s session memory to rehydrate previous plan artifacts.  
2. **State Reuse:** Persist revisions in the Agent SDK’s interaction store (or your own Redis) so the supervisor can reason about “previous analysis vs. requested revision” and issue new tool calls only when needed.  
3. **Specialist Agents:** Implement SQL/Chart/Web specialists as separate agents registered with the supervisor. Each specialist calls its respective service (existing Supabase, chart service, search API).  
4. **Streaming UI:** Swap current SSE endpoints with Agents SDK SSE/response streaming to surface supervisor notes, tool results, and final analysis in the frontend.

### Risks & Considerations
- Requires significant backend rewrite (FastAPI endpoints must proxy to the Agents SDK runtime).  
- Tool cost and latency may rise because each revision re-enters the LLM supervisor loop.  
- Needs robust guardrails/tests to ensure compliance and cost controls before production.

### Deliverables
- New `agent_orchestrator` backend module hosting supervisor & specialist definitions.  
- Migration scripts to seed legacy session data into the new agent memory store.  
- Frontend changes to render agent messages (supervisor reasoning, specialist outputs).  
- Observability dashboards to monitor tool-call rates and failure cases.

## Option 3 — Hybrid Orchestration with LangGraph or AutoGen Flow
**Effort:** Medium-High (3–5 weeks)  
**Goal:** Use a declarative multi-agent graph (LangGraph) or Microsoft AutoGen Flow to orchestrate deterministic revision paths with retries and guardrails, while retaining existing tools.

### Approach
- Define a graph where nodes represent planner stages (Intent, Plan, Web Refresh, Analysis). Branching logic ensures web refresh always runs before analysis revisions.  
- Integrate the same SQL/Web/Chart tools as Python callables; agents (LLMs) provide reasoning only where human-like judgment is required (e.g., rewriting analysis).  
- Adds built-in tracing/inspection to pinpoint exactly where the web lane skips.

### Pros/Cons
- Less vendor lock-in than fully adopting Agents SDK.
- Graphs are debuggable and can fall back to cached outputs when tools fail.
- Still a sizable refactor, and would coexist with the current planner only temporarily.

## Option 4 — Offline Refresh Job + On-demand Light Agent
**Effort:** Medium (2–3 weeks)  
**Goal:** Shift heavy revision recalculations to a scheduled worker that pre-generates refreshed analysis + web snippets, while the interactive agent only selects the right bundle.

### Outline
1. Background job replays the most recent conversations overnight, invoking web research and caching results.  
2. Frontend “revision” button only fetches the prebuilt bundle; if stale, triggers a single-agent refresh with minimal logic.  
3. Investigate JetStream (or similar) message bus to coordinate when a fresh web run is required.

### Trade-offs
- Reduces real-time tool churn but sacrifices immediacy (fresh data may lag).  
- Requires careful cache invalidation and storage of multiple revision snapshots.

## Option 5 — Full Rewrite: Dedicated Analytics Agent Backend
**Effort:** Very High (12+ weeks)  
**Goal:** Build a new service where revisions are first-class entities, leveraging vector memories, structured datasets, and guardrail engines.

### Components
- Graph-based planner that stores every tool invocation as a node with lineage.
- Vector store (e.g., pgvector) for prior analyses and web snippets.
- Agents (OpenAI or other) operate on top of a structured state machine; revisions become simple diff requests.

### Rationale
- Clean break from legacy complexity.
- Allows future expansion (e.g., user-tunable agents, cost-aware routing).
- High risk and timeline; should only be considered if incremental paths fail or a larger roadmap justifies it.

---

### Recommendation Snapshot
| Option | Effort | Near-term Reliability | Strategic Alignment |
|--------|--------|-----------------------|---------------------|
| Harden Existing Pipeline | Medium | ✅ Quick wins | ⚪️ Limited |
| Agents SDK Supervisor/Specialists | High | ⚪️ Requires rewrite | ✅ Strong |
| LangGraph/AutoGen Hybrid | Medium-High | ✅ Deterministic | ✅ Moderate |
| Offline Refresh Job | Medium | ⚪️ Depends on freshness | ⚪️ Limited |
| Full Rewrite | Very High | ✅ Long-term | ✅ Highest |

Next action: pick one path for a 2-week spike (suggest starting with an Agents SDK proof-of-concept vs. deeper instrumentation) and run a decision review with engineering + product once spike results are available.
