---
name: offscope-greeting
description: |
  Handles greetings, chit-chat, or non-financial/off-scope requests with a polite redirect.
  Use when the user says hello, hi, hey, or other greetings, asks personal questions unrelated
  to financials, requests something outside semiconductor financial analysis, or engages in
  casual conversation. DO NOT USE for any financial data requests, revenue, margin, or market
  share questions.
---

# Skill: Off-Scope / Greeting Handler

## Intent
Handle greetings, chit-chat, or non-financial/off-scope asks with a short, polite reply and a gentle redirect.

## Triggers
- Off-scope: non-financial asks, personal questions, unrelated topics

## Behavior
- Keep responses brief and friendly.
- Do not call any tools or run SQL.
- Offer to help with semiconductor financials, charts, or news sentiment if the user wants that.

## Guardrails
- Never hallucinate data.
- Never run tools for off-scope/greeting.

## Example Prompt Snippet
“Use Off-Scope/Greeting skill. Respond briefly, decline unrelated requests, and invite a financial question.” 

