---
name: a2ui-feature-showcase
description: |
  Demonstration skill that showcases the capabilities of the A2UI analytics platform.
  Use this skill when the user says "demo", "show me what you can do", "showcase features",
  "walk me through the capabilities", "what can you do", or when onboarding a new user.
  This skill provides an interactive tour, NOT a full analysis workflow.
  For actual analysis, route to topic-specific skills (explain-move, peer-compare, etc.).
tools:
  - query_database
  - generate_analysis
widgets:
  - KpiCard
  - MetricChart
  - DataTable
  - ExplainMovePanel
layout: feature_showcase
layout_variants:
  - tour
  - minimal
default_variant: tour
---

# Feature Showcase Skill

## Intent

Provide an interactive demonstration of the A2UI analytics platform capabilities.
This is for **showcasing features only**, NOT for comprehensive analysis.

## When to Invoke

This skill should be selected when the user:
- Says "Demo" or "Show me what you can do"
- Asks "What can you do?"
- Asks "Features" or "Capabilities"
- Says "Walk me through the features"
- Says "Help me get started"
- Asks "What is this?" or "How does this work?"
- Is explicitly onboarding

DO NOT use this skill for:
- Actual financial analysis (use explain-move, peer-compare, margin-analysis, revenue-trend)
- Specific questions about companies
- Any production analytical work

## Showcase Flow

### Step 1: Welcome & Quick Demo (5 seconds)

System displays welcome card:
```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🎯 Welcome to the A2UI Analytics Platform                                  │
│                                                                              │
│  I can help you analyze financial data through natural conversation.        │
│  Here's a quick demo using NVIDIA (NVDA) as an example...                  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

Action: Load sample NVDA data to populate widgets.

### Step 2: Show Core Capabilities

Brief explanation of what's on screen:

**KPI Cards**: "Key metrics at a glance - revenue, margins, growth rates"
**Charts**: "Visual trends powered by ECharts and TradingView"
**Tables**: "Detailed data you can sort and explore"
**Insights**: "AI-generated analysis explaining what you see"

### Step 3: Highlight Proactive Features

Draw attention to:
```
┌──────────────────────────────────────────────────────────────────────────────┐
│  💡 Notice how I automatically found something interesting:                  │
│     "NVDA's gross margin at 75.3% - highest in 5 years"                     │
│                                                                              │
│  I'll surface anomalies like this without you asking.                       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Step 4: Show Follow-Up Navigation

Point to "Continue your analysis" section:
```
These suggestions are context-aware based on what you're viewing.

[kpi] Margin analysis → Routes to margin-analysis skill
[peers] Compare peers → Routes to peer-compare skill
[trend] Revenue trend → Routes to revenue-trend skill

Or type your own question in natural language!
```

### Step 5: Demonstrate Conversational Refinement

Show examples of what users can say:
- "Compare to AMD" → Adds AMD to current view
- "Why is the margin so high?" → Drill-down explanation
- "Show me the 5-year trend" → Time range adjustment
- "Hide the news section" → Layout control

### Step 6: Call to Action

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🚀 Ready to try it yourself?                                               │
│                                                                              │
│  Try asking:                                                                 │
│  • "Why did NVDA rise this quarter?"                                        │
│  • "Compare AMD vs INTC revenue"                                            │
│  • "What are AMD's profit margins?"                                         │
│                                                                              │
│  Or click any of the suggestions below ↓                                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Output Contract

The showcase produces a minimal dashboard with demo content:

| Component | Type | Purpose |
|-----------|------|---------|
| Welcome Card | `Card` | Greet user, explain demo |
| Sample KPIs | `KpiCard` | Show metric display capability |
| Sample Chart | `MetricChart` | Show visualization capability |
| Feature Highlights | `ExplainMovePanel` | Explain capabilities |
| Try It Prompts | `FollowUpSuggestions` | Guide to first real query |

## Data Model Schema

```json
{
  "mode": "showcase",
  "sample_ticker": "NVDA",
  "features_highlighted": [
    "natural_language_queries",
    "proactive_insights", 
    "smart_follow_ups",
    "layout_controls",
    "conversational_refinement"
  ],
  "example_queries": [
    "Why did NVDA rise this quarter?",
    "Compare AMD vs INTC revenue",
    "What are AMD's profit margins?",
    "Show me the revenue trend for NVDA"
  ],
  "next_skill_suggestions": [
    {"skill_id": "a2ui-explain-move", "label": "Analyze price moves"},
    {"skill_id": "a2ui-peer-compare", "label": "Compare companies"},
    {"skill_id": "a2ui-margin-analysis", "label": "Profitability analysis"},
    {"skill_id": "a2ui-revenue-trend", "label": "Revenue trends"}
  ]
}
```

## Guardrails

- **This is NOT for production analysis** - always route actual queries to topic-specific skills
- Keep demo interactive and brief (< 30 seconds of auto-content)
- Always show clear "try it yourself" call to action
- Sample data only - do not pretend to have current real-time data
- Route follow-up queries to appropriate skills:
  - Price/movement questions → `a2ui-explain-move`
  - Comparison questions → `a2ui-peer-compare`  
  - Margin/profitability → `a2ui-margin-analysis`
  - Trend questions → `a2ui-revenue-trend`

## Example Triggers

- "Demo"
- "What can you do?"
- "Show me the features"
- "Help"
- "How does this work?"
- "Walk me through"
- "Getting started"
- "Tutorial"
