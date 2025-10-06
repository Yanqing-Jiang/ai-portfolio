# Next‑Gen Analytics ECharts: Memory vs SQL

This note documents how ECharts options are produced and rendered in the two analytics experiences and why the Memory flow often shows no chart. It ends with concrete, low‑risk improvements and test ideas.

## TL;DR

- SQL flow renders a top‑level chart immediately after receiving `chart_generated` from the backend.
- Memory flow only injects charts into a chat “result” bubble after the workflow completes. If the run pauses (clarification) or exits early, users see no chart.
- Fix: render a page‑level chart in Memory as soon as the spec arrives (mirror SQL), optionally show a preview result message, and preload the chart component.

---

## Where Charts Render

- SQL page
  - Renders a page‑level `<ChartCard>` when `chartSpec` is set.
  - Files:
    - `components/analytics/sql/Page.tsx` (conditional render of `<ChartCard>`)
    - `components/analytics/hooks/useAnalyticsSqlStream.ts` (sets `chartSpec` on `chart_generated`)

- Memory page
  - Does not render a top‑level `<ChartCard>`.
  - Charts appear only inside chat history after a final “result” message is appended.
  - Files:
    - `components/analytics/memory/Page.tsx` (no page‑level chart render)
    - `components/analytics/memory/ChatHistory.tsx` (lazy‑loads `<ChartCard>` inside a message bubble)
    - `components/analytics/hooks/useAnalyticsMemoryStream.ts` (receives `echarts_complete`/`chart_generated`, but defers rendering to the final message)

## Event Timing & Data Flow

- Backend emits early chart events in both flows:
  - SQL: `backend/analytics_agent.py` yields `{ event: "chart_generated", data: { chart_spec } }` before analysis streaming.
  - Memory (planner‑executor): `backend/analytics/flows/planner_executor.py` yields `chart_planned` then `chart_generated` with `chart_spec`.

- Frontend handling:
  - SQL hook (`useAnalyticsSqlStream`) sets `chartSpec` on `chart_generated` and the page renders `<ChartCard>` immediately.
  - Memory hook (`useAnalyticsMemoryStream`) captures the same events but only surfaces a chart in chat after `workflow_complete` triggers `emitResultOnce()`. If the flow pauses on clarification or errors, there is no chart visible.

## Why Memory Often Shows No Chart

1. UX gating by conversation: Chart rendering is tied to a final “result” bubble. Until `emitResultOnce()` fires, the chart isn’t shown.
2. Lazy component: `ChartCard` is lazy‑loaded inside `ChatHistory`, so even when the result is ready there’s a small extra delay.
3. Streaming sequence: The backend sends `chart_generated` early, but the UI hides it while analysis and other steps continue.

---

## Improvements (Concrete, Low‑Risk)

1) Render page‑level chart in Memory (mirror SQL)

Add a top‑level `<ChartCard>` to `components/analytics/memory/Page.tsx` so charts appear as soon as `chartSpec` is available.

```tsx
// components/analytics/memory/Page.tsx
import { ChartCard } from '../common'; // add near other imports
import { isValidChartSpec } from '../utils';

// Inside the main content area (where results go)
{chartSpec && isValidChartSpec(chartSpec) && (
  <ChartCard
    chartSpec={chartSpec}
    dataSample={dataSample}
    enableDropdown
    enableCsvDownload
  />
)}
```

Result: Memory page behaves like SQL—users see the chart immediately after `chart_generated`, independent of chat timing.

2) Optional: Preview chart inside chat early

Augment the Memory hook to append/update a “Preview” result message when `chart_generated` arrives, then enrich it at `workflow_complete`:

```ts
// components/analytics/hooks/useAnalyticsMemoryStream.ts
const previewIdRef = useRef<string | null>(null);
const addOrUpdatePreviewResult = (payload: { chartSpec?: any; dataSample?: any[] }) => {
  if (!previewIdRef.current) {
    previewIdRef.current = addChatMessage({
      type: 'result',
      content: 'Preview chart ready — analysis in progress…',
      chartSpec: payload.chartSpec,
      dataSample: payload.dataSample,
    });
  } else {
    updateChatMessage(previewIdRef.current, payload);
  }
};

// On chart events
case 'chart_generated': {
  const normalized = resolveChartSpecOption(eventData) ?? resolveChartSpecOption(data);
  if (normalized) {
    scheduleProgressiveUpdate({ chartSpec: normalized });
    streamHook.setCurrentStatus('Chart ready — analysis in progress');
    addOrUpdatePreviewResult({ chartSpec: normalized, dataSample: workflowDataRef.current.dataSample });
  }
  break;
}
```

3) Preload the chart component on first chart event

```ts
// On first chart event (Memory hook)
void import('../common/ChartCard');
```

This removes the Suspense delay when the chart is shown for the first time.

4) Use deterministic ECharts updates under streaming

When options arrive incrementally, prefer replace‑merge semantics to avoid stale series lingering:

```ts
// components/analytics/common/ChartCard.tsx (idea)
onChartReady={(instance) => {
  chartRef.current = instance;
  setTimeout(() => {
    try {
      instance.setOption(withLightTheme(chartSpec), { replaceMerge: ['series','xAxis','yAxis'] });
    } catch {}
  }, 100);
}}
```

If you keep using the `option` prop only, expose a prop to toggle this behavior or perform the call inside an effect when `chartSpec` changes.

5) Keep spec metadata aligned with formatting logic

Memory already emits `meta.seriesValueType` and `seriesPercentFormat`. Ensure these match `withLightTheme(...)` expectations so tooltips/labels format currency vs percent correctly. If all included columns are percent‑like, set `meta.chartValueType = 'percent'` as a chart‑level hint (SQL already follows this pattern).

6) UX hint

Upon `chart_generated` set status to “Chart ready — analysis in progress” to reassure users that visualization is available.

---

## Verification Plan

- Frontend (vitest + jsdom)
  - Memory Page renders `<ChartCard>` when `chartSpec` is set.
  - Memory hook: `chart_generated` → `chartSpec` is populated and optional preview message is added.
  - `utils/chartOptions.ts` tests remain green (existing unit tests).

- Backend (manual)
  - Confirm `chart_generated` precedes analysis in both flows:
    - SQL: `backend/analytics_agent.py`
    - Memory: `backend/analytics/flows/planner_executor.py`

---

## Appendix: Example Events

SQL event (early):

```json
{ "event": "chart_generated", "data": { "chart_spec": { /* ECharts option */ } } }
``;

Memory (planner‑executor) events:

```json
{ "event": "chart_planned", "data": { "chart_type": "line_multi", "series_count": 6 } }
{ "event": "chart_generated", "data": { "chart_spec": { /* ECharts option */ } } }
```

---

## References

- Frontend files
  - `components/analytics/sql/Page.tsx`
  - `components/analytics/memory/Page.tsx`
  - `components/analytics/memory/ChatHistory.tsx`
  - `components/analytics/hooks/useAnalyticsSqlStream.ts`
  - `components/analytics/hooks/useAnalyticsMemoryStream.ts`
  - `components/analytics/common/ChartCard.tsx`

- Backend files
  - `backend/analytics_agent.py` (SQL flow)
  - `backend/analytics/flows/planner_executor.py` (Memory flow)
  - `backend/analytics/core/charting.py` (spec builder)

