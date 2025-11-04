# OpenAI Agents Patterns Research — November 4, 2025

## Manager-as-Tool Orchestration
- OpenAI’s CLI orchestration guide highlights that a “manager” agent can call specialist tools directly, allowing the manager to keep execution state while delegating focused work. This mirrors our supervisor needing to plan tasks, track retries, and hand off to SQL/web/market specialists without releasing control. citeturn0search0turn0search3
- Cookbook examples frame the manager pattern as a blend of deterministic workflows and LLM reasoning: code decides when to invoke specialists, while the manager agent stabilises tool choice and context sharing. citeturn0search3turn0search10

## Handoff vs. Tool Delegation
- Handoffs remain useful for clean role switches, but the manager-as-tool approach offers tighter feedback loops—especially when the supervisor must record retries and continue even after tool failure. This aligns with our requirement to keep the card stack flowing despite specialist errors. citeturn0search3turn0search11
- Stack Overflow discussions comparing multi-agent patterns emphasise that handoff-heavy flows risk extra latency and state divergence; they recommend centralised supervisors when consistency and audit trails are priority—which matches our cache + telemetry guardrails. citeturn0search5turn0search8

## Evaluation & Observability
- OpenAI’s manager tutorial and tracing docs suggest capturing tool call spans, retry counts, and guardrail verdicts to debug complex workflows—exactly what we need when integrating the Agents SDK with existing telemetry. citeturn0search0turn0search10
