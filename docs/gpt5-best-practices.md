# GPT-5 Best Practices for Analytics Agents

## Why GPT-5
- GPT-5 introduces controllable reasoning effort, letting you trade accuracy for latency on a per-call basis and reach stronger factuality than earlier reasoning models when you dial effort up selectively. citeturn0search0turn0search5
- Benchmark evaluations across 220 real-world GDPval tasks show GPT-5 delivers accuracy gains while maintaining competitive cost and turnaround time versus human experts and competing LLMs—use it for analyst-facing flows that demand precision. citeturn0search8

## Model Configuration
- Prefer the latest dated GPT-5 variant (e.g., `gpt-5-mini-2025-08-07`) for production analytics agents; dated SKUs guarantee parameter stability for reproducible telemetry and auditability. citeturn0search9
- Use `model_settings.reasoning.effort` to right-size thinking time: `minimal`/`low` for routing, cached revisions, and timeline updates; `medium` or higher only when plans span multiple tools or require novel synthesis. citeturn0search0
- Pair reasoning controls with the new `verbosity` parameter—keep it `low` when streaming to tightly scoped cards, and promote to `medium/high` only for narrative drafts that must include supporting detail. citeturn0search0

## Safety & Compliance
- Align prompts and review pipelines with GPT-5’s safe-completion training: encourage the model to offer partial guidance plus policy reminders for dual-use prompts instead of hard refusals, and log those responses for audit trails. citeturn0search2
- Reference the GPT-5 System Card when documenting deployment risks; it outlines routing behaviors between fast and thinking modes, plus the smaller “mini” fallbacks your service might trigger under quota pressure. citeturn0search9

## Agent Workflow Guidance
- When orchestrating specialists (SQL, web, market, analysis), treat GPT-5 as the reasoning controller but keep per-lane tools deterministic; Consensus’ multi-agent deployment shows the pattern of GPT-5 planning, reading, and synthesizing evidence before emitting final summaries. citeturn0search4
- Avoid redundant agent handoffs that reissue high-effort reasoning unless a lane truly requires fresh synthesis—overthinking is a known failure mode, and trimming effort plus clarifying “definition of done” keeps turnaround tight. citeturn0search6

## Troubleshooting Checklist
- If responses stall on simple prompts, lower `reasoning.effort` and tighten instructions; this reduces the chance of GPT-5 exploring unnecessary branches (“overthinking”). citeturn0search6
- Monitor API errors for unsupported parameters—older GPT models reject `reasoning.effort`, so ensure all manifests reference GPT-5 SKUs before rolling out shared configs. citeturn0search6

## Additional Resources
- Internal references: review the materials under `docs/references/` for Agents SDK patterns, orchestration diagrams, and prior migration notes.
- External documentation: Introducing GPT-5 for developers, GPT-5 System Card, Safe-Completions paper, GPT-5 Troubleshooting Guide, and GDPval evaluation report (citations above).
