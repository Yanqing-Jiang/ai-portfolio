---
name: nextgen-project-showcase
description: |
  Explains the Next Gen Analytics Agent project architecture and provides a demo walkthrough.
  Use when the user asks about project tour, showcase, demo, walkthrough, how does this work,
  system overview, architecture, explain agents, single-agent, multi-agent, supervisor, what
  is a skill, or how skills work. DO NOT USE for actual financial data queries - this skill
  is informational only.
---

# Skill: Project Showcase / Architecture Demo

## Intent
Explain the Next Gen Analytics (Agent) project, how single- and multi-agent modes run, and how `skill.md` files steer the experience. Provide an interactive showcase link plus a narrated walkthrough.

## Guardrails
- Do **not** query databases, run news sentiment, generate charts, or call TradingView. Stay informational only.
- Call the `open_showcase_page` tool **once** to surface the showcase link, then include the link in the reply.
- Use concise Markdown with `##`/`###` headings and bullet lists. Keep tone crisp and demo-friendly.
- Avoid speculating about live data, credentials, or external APIs.

## Workflow (follow this order)
1) Call `open_showcase_page` and share the returned link + one-line description.
2) Present the overview and flows below. Keep sections tight and scannable.
3) Close with 3–4 sample prompts the user can try.

## Output Sections (exact order)
1) Overview — what the project is and what it powers.
2) Single-Agent Flow — linear path: request → skill detection → Claude + tools → response.
3) Multi-Agent Flow — supervisor + specialist lanes; how handoffs work.
4) Skills Lifecycle — detection → prompt injection → slot resolution/HITL → visualization.
5) Frontend Surfacing — ProcessPanel + Skill accordion + SkillModal role.
6) Try It — sample prompts for the user to copy.

## Content Notes (use in the narrative)
- Agents: Single agent uses SQL/ECharts/TradingView/News tools. Multi-agent mode adds a supervisor routing to specialists (database admin, chart builder, news).
- ProcessPanel: shows process nodes, edges, active skill, and skill.md details.
- SkillModal: optional UI that can display the current skill and a "What is a Skill?" explainer.
- Skills live in `backend/conversational_analytics/skills/*.md`; routes expose download links at `/api/conv-analytics/skills/{id}`.
- Static showcase HTML is served from `/api/conv-analytics/showcase` and embeds the demo GIF.

## Tooling
- Allowed: `open_showcase_page` (returns showcase URL + description).
- Disallowed: database, news, charting, web search, or any other tool.

## Example Prompt Snippet
"Use the Project Showcase skill. Call `open_showcase_page` once to surface the showcase link. Then deliver the ordered sections (Overview, Single-Agent Flow, Multi-Agent Flow, Skills Lifecycle, Frontend Surfacing, Try It) using Markdown headings and bullets. Do **not** call database/chart/news tools."
