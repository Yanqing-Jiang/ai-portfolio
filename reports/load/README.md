# Supervisor Load Test Artifacts

Store sanitized load-test outputs for the analytics supervisor rollout here. Each artifact should capture latency percentiles, retry counts, and failure metrics so incident reviews and dashboards can ingest consistent payloads.

## JSON Schema Outline

`
{
  "iteration": "agents-supervisor-iteration5",
  "generated_at": "2025-11-06T00:00:00Z",
  "duration_minutes": 30,
  "sessions": {
    "total": 50,
    "completed": 49,
    "failed": 1
  },
  "latency_ms": {
    "p50": 1800,
    "p95": 3800,
    "max": 6200
  },
  "lane_metrics": {
    "sql": { "p95": 3200, "retries": 4 },
    "web": { "p95": 2100, "retries": 2 },
    "market": { "p95": 1900, "retries": 1 },
    "analysis": { "p95": 2400, "retries": 0 }
  },
  "alerts": [
    { "key": "supervisor_backpressure", "count": 3 },
    { "key": "tool_failures", "count": 1 }
  ]
}
`

Copy this outline when capturing new artifacts (e.g., gents-supervisor-iteration5.json). Keep sensitive identifiers removed before committing.
