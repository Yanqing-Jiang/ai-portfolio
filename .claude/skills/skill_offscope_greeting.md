---
name: offscope_greeting
description: |
  Handle greetings, chit-chat, or non-financial/off-scope requests with a polite redirect.
  
  USE THIS SKILL WHEN the user:
  - Says hello, hi, hey, or other greetings
  - Asks personal questions unrelated to financials
  - Requests something outside semiconductor financial analysis
  - Engages in casual conversation
  
  DO NOT USE for:
  - Any financial data requests (use appropriate financial skill)
  - Revenue, margin, or market share questions
tools: []
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

