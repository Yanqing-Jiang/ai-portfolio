# Support Macros - Analytics Agents Launch

## Macro 1: Agent Overview
```
Hi <Name>,

You are connected to our new Analytics Agent experience. Runs are now coordinated by an OpenAI-powered planner that can delegate to specialists (SQL, web, market, analysis). If you see "Agent is gathering more data," that means a specialist lane is still running. You will receive partial updates when cached results are reused.

Thanks for trying the refreshed workflow!
```

## Macro 2: Lane Error Follow-up
```
Hi <Name>,

Our agent hit an issue while refreshing <Lane>. We automatically retried twice and kept the latest cached insight so you are not blocked. If you need a fresh pull, click "Retry <Lane>" and we will attempt it again, or share any constraints (for example, symbols or date ranges) and we will pass them to the specialist.

Thank you!
```

## Macro 3: Supervisor Decisions
```
Hi <Name>,

Here is what the agent decided during the latest run:
- Planner intent: <Intent Summary>
- Delegated lanes: SQL, Market, Analysis
- Retries: <Count/Details>

If anything looks off, reply with guidance (for example, focus on Q3 earnings) and the supervisor will adjust the next cycle.

Best,
Support
```

_Keep this sheet in sync with analytics enablement updates._
