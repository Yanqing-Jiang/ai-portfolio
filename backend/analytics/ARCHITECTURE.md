# Analytics Architecture (Backend + Frontend) — Nov 26, 2025

Document purpose: capture the true current state of the analytics stack (frontend + FastAPI backend), the gaps in single-agent and multi-agent modes, and the target design that aligns with OpenAI Agent SDK multi-agent patterns and Claude Code single-agent/tool best practices. This replaces the prior function catalog and is meant to guide refactors, not auto-generated inventories.

## Scope at a Glance
- Frontend: Vite/React app at repo root; ProcessPanel, WorkflowCanvas, LiveArtifacts, and stream hooks under `components/analytics` consume SSE envelopes from the backend.
- Backend: FastAPI service in `backend/` with analytics flows (`flows/`), agent orchestrators (`agent_orchestrator/`, `agents_stream_bridge.py`), canonical tool layer (`tools/`), telemetry (`core/telemetry`, `validators/`), and session state (`core/session_state_snapshot.py`).
- Environments: Flow modes DIRECT (deterministic), SINGLE_AGENT (planner-style agent), MULTI_AGENT (supervisor + specialists), all sharing the same tool definitions and SSE schema.

## Current State (truthful snapshot)
- Fresh runs in SINGLE_AGENT still fall back to deterministic planner lanes; many ledgers lack `agent_turn_*` or `agent_tool_*`, so UI cannot render agent evidence or badges.
- Multi-agent coordination is unstable: supervisor often emits incomplete tool receipts, specialist ordering is ad-hoc, and lane reuse/guardrail metadata is missing or inconsistent.
- Tool registry parity is fragile: planner adapters, single-agent runtime, and supervisor sometimes diverge on schema versions and allowlists; receipts rarely carry `schema_version`, `guardrail`, or `from_cache` uniformly.
- Frontend coupling: hooks expect agent-style envelopes, but DIRECT-style planner events still appear in agent modes, forcing branchy UI logic and hiding reuse/guardrail badges.
- Revision runs: revision questions and lane decisions exist, but revision flows can bypass AgentRuntime or die on missing artifacts (`analysis_revision` NameError), leading to broken revision loops.

## Problems to Fix
1) **Single-agent “tool call + revision run” chaos** — agent loop not consistently used; tool allowlists ignore follow-up routes; retries and guardrails run outside AgentRuntime.  
2) **Multi-agent coordination** — no stable supervisor pattern; specialists act like parallel pipelines instead of tools; delegation metadata missing; workflow completes without matching `*_ready` events.  
3) **Receipts and cache semantics** — lane reuse badges rely on heuristics instead of signed receipts with TTL, guardrail verdicts, and `schema_version`.  
4) **Telemetry contract drift** — SSE stream mixes planner and agent envelopes; `agent_turn_id` / `tool_call_id` pairs not guaranteed; ProcessPanel cannot prove evidence.  
5) **Fresh vs revision split** — fresh should showcase all components; revision should selectively rerun with receipts/guardrails; today both paths intermix and skip required lanes.

## Design Principles (from current best practices)
- **Agent-as-tool supervisor**: run one supervisor/manager agent that calls specialists as tools (no nested AgentRuntime trees) and keeps the critical path inside a single Agent SDK run.  
- **Strict tool schemas + retries**: force structured arguments, validate before dispatch, and use retry/backoff on tool errors instead of silent planner fallbacks.  
- **Single-agent with deliberate tool choice**: one main agent loop, minimal sub-agents, and explicit allowlists; prefer blocking clarification and guardrail checks before tools.  
- **Least-privilege tools & policies**: scope tool access per role (e.g., analysis-only vs data-mutation), surface policy violations as guardrail metadata, and never auto-expand toolsets mid-run.  
- **Reusable skills/profiles**: factor recurring behaviors (e.g., “web researcher”, “chart fixer”) as reusable prompt + tool profiles rather than spawning new agents.  
- **Session-first caching**: `SessionStateSnapshot` is the source of truth; agent sessions are disposable. Receipts must carry TTL, cache age, and guardrail verdicts to justify reuse.

## Target Architecture
- **Fresh runs (show everything)**: supervisor (MULTI_AGENT) and planner agent (SINGLE_AGENT) must execute the full lane set (classification/clarification → SQL plan/execute → chart → web → market → analysis). Allowlists keep all lanes enabled; cache hits still emit receipts with `from_cache=true` so UI shows reused components instead of skipping them.
- **Revision runs (targeted + tool-first)**: run inside AgentRuntime (single or supervisor) with allowlists derived from follow-up route and revision directives. Agents must hydrate `SessionStateSnapshot`, decide rerun/reuse per lane, and emit lane decisions + receipts before analysis. Guardrail redirects emit `workflow_redirect: direct` when agent runtime is unhealthy.
- **Supervisor pattern**: one supervisor agent orchestrates specialists-as-tools (`sql`, `chart`, `web`, `market`, `analysis`, `revision_lane`). Delegation metadata (`specialist_id`, `role`, `lane`, retries, elapsed_ms, guardrail) flows through `AgentsStreamBridge` and into receipts.
- **Canonical tool plane**: single `TOOL_REGISTRY` feeds DIRECT, SINGLE_AGENT, MULTI_AGENT. Every tool returns a signed receipt `{schema_version, guardrail, elapsed_ms, retry_count, from_cache, ttl_seconds, output_hash}` persisted in `SessionStateSnapshot`.
- **Telemetry contract**: SSE emits `agent_turn_start/end`, `agent_tool_call`, `agent_tool_complete`, `*_ready`/`lane_reused`, `workflow_error/redirect`. IDs must pair (`agent_turn_id` ↔ `tool_call_id`) and include lane + specialist metadata so the frontend renders evidence without mode-specific branches.
- **Frontend alignment**: hooks consume only agent-style envelopes for non-DIRECT modes; DIRECT keeps deterministic planner cards. Reuse badges, guardrail badges, and specialist labels depend solely on receipt metadata, not heuristics.

## Concrete Refactor Moves (no future-dated promises)
- Enforce AgentRuntime on every SINGLE_AGENT run; fail fast when `agent_turn_*` evidence is missing and redirect to DIRECT with an explicit `workflow_error`.
- Collapse supervisor orchestration into “supervisor + tools” (no parallel planner pipeline); specialists exposed only as tools from the canonical registry with least-privilege manifests.
- Make receipts authoritative: every tool wrapper writes `schema_version`, `guardrail`, `from_cache`, `age_seconds`, `elapsed_ms`, and `retry_count` into `SessionStateSnapshot` and mirrors the same fields into SSE payloads.
- Block lanes on missing required slots: run clarification/guardrail preflight outside AgentRuntime, then start the agent run with hydrated slots and an allowlist derived from follow-up route.
- Require `*_ready` or `lane_reused` events for SQL, chart, web, market, and analysis before `workflow_complete`; treat omissions as errors surfaced to the UI.
- Frontend simplification: ProcessPanel/WorkflowCanvas render agent timelines only for non-DIRECT; deterministic-only events are hidden once agent evidence is present.

## Known Risks
- Tool/schema drift between DIRECT and agent flows until a parity test enforces byte-identical schemas.
- Supervisor latency may rise when forcing all lanes on fresh runs; need sensible parallelism + retries rather than serial execution.
- Clarification gating can block runs if timeout handling is weak; must surface actionable `workflow_error` instead of hanging streams.

## What “Good” Looks Like After Refactor
- Fresh SINGLE_AGENT and MULTI_AGENT ledgers always show agent turns + tool calls for every lane (fresh or reused) before analysis.
- Revisions reuse cached artifacts when TTL-valid, rerun only requested lanes, and show delegation/guardrail badges that match receipts.
- DIRECT stays deterministic and isolated; toggling to DIRECT remains the rollback without affecting agent manifests.
