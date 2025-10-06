# Agent‑Driven Chart Revisions (Design Notes)

Goal: treat the chart as a first‑class “tool” an agent can revise without re‑querying the database. A typical flow:

1) User asks a question → SQL pipeline runs → initial ECharts option renders.
2) User follow‑up: “change to bar chart” → agent emits a chart patch → UI updates the same chart and dataset in place.

This document proposes the wire format, frontend reducer, and minimal backend plumbing to enable that.

---

## Principles

- Keep data stable, mutate only presentation.
- Make operations idempotent and composable (sequence of small ops → final spec).
- Keep the presentational component (`ChartCard`) dumb; put mutations in a controller/reducer layer.
- Prefer high‑level ops (set_chart_type) over raw JSON patches; translate to ECharts changes in one place.

---

## Wire Format (Tool I/O)

Define a single tool the agent can call: `chart_tool.edit`.

Input JSON (emitted over SSE or tool‑call):

```
{
  "event": "chart_patch",
  "data": {
    "chart_id": "active",              
    "reason": "Switch to bar chart",
    "ops": [
      { "op": "set_chart_type", "value": "bar" }
    ]
  }
}
```

Recommended ops (extensible):

- set_chart_type: `line | bar | area | candlestick | stacked_area | stacked_bar`
- set_grouping: `{ grouping: "ticker" | "metric" }`
- set_stack: `{ stack: boolean, mode?: "normal" | "percent" }`
- select_metrics: `{ include?: string[] | "ALL", exclude?: string[] }`
- filter_companies: `{ tickers: string[] }`
- set_x_axis: `{ field: "calendar_year" | "calendar_quarter" | "date" }`
- set_y_axis_format: `{ valueType: "percent" | "currency", percentFormat?: "decimal" | "pre_multiplied" }`
- set_palette: `{ palette: string[] }`
- set_axis_scale: `{ axis: "x" | "y" | 0 | 1, scale: "linear" | "log" }`
- toggle_series: `{ names: string[], visible: boolean }`

Why high‑level ops?
- They’re easy for LLMs to choose and safer for the UI to apply.
- We retain authority in the client to translate ops into valid ECharts.

---

## Frontend Shape

### 1) Controller + Reducer (reuse existing utils)

Put the reducer in the existing `components/analytics/utils/chartOptions.ts` (do not add new files). It will own the working `option` and apply ops deterministically.

```
// components/analytics/utils/chartOptions.ts
export type ChartOp =
  | { op: 'set_chart_type'; value: 'line'|'bar'|'area'|'candlestick'|'stacked_area'|'stacked_bar' }
  | { op: 'set_grouping'; grouping: 'ticker'|'metric' }
  | { op: 'set_stack'; stack: boolean; mode?: 'normal'|'percent' }
  | { op: 'select_metrics'; include?: string[]|'ALL'; exclude?: string[] }
  | { op: 'filter_companies'; tickers: string[] }
  | { op: 'set_x_axis'; field: 'calendar_year'|'calendar_quarter'|'date' }
  | { op: 'set_y_axis_format'; valueType: 'percent'|'currency'; percentFormat?: 'decimal'|'pre_multiplied' }
  | { op: 'set_palette'; palette: string[] }
  | { op: 'set_axis_scale'; axis: 'x'|'y'|0|1; scale: 'linear'|'log' }
  | { op: 'toggle_series'; names: string[]; visible: boolean };

export interface ChartPatch { ops: ChartOp[]; reason?: string; chart_id?: string; }

export function applyChartOps(base: any, patch: ChartPatch): any {
  let option = JSON.parse(JSON.stringify(base));
  for (const p of patch.ops) {
    switch (p.op) {
      case 'set_chart_type': {
        const isStacked = p.value === 'stacked_area' || p.value === 'stacked_bar';
        const type = p.value.includes('bar') ? 'bar' : p.value.includes('area') ? 'line' : p.value; // area= line+areaStyle
        option.series = (option.series || []).map((s: any) => ({
          ...s,
          type,
          areaStyle: p.value === 'area' || p.value === 'stacked_area' ? ({ opacity: 0.2 }) : undefined,
          stack: isStacked ? 'total' : undefined,
        }));
        option.legend = option.legend || {};
        option.meta = option.meta || {};
        option.meta.chartDesign = { ...(option.meta.chartDesign||{}), chart_type: p.value };
        break;
      }
      case 'set_stack': {
        const stack = p.stack ? 'total' : undefined;
        option.series = (option.series || []).map((s: any) => ({ ...s, stack }));
        if (p.mode === 'percent') {
          // Hint to formatter/UI
          option.meta = option.meta || {};
          option.meta.chartValueType = 'percent';
        }
        break;
      }
      case 'toggle_series': {
        const selected = { ...((option.legend||{}).selected || {}) };
        for (const n of p.names) selected[n] = p.visible;
        option.legend = { ...(option.legend||{}), selected };
        break;
      }
      case 'set_y_axis_format': {
        option.meta = option.meta || {};
        option.meta.chartValueType = p.valueType;
        option.meta.seriesPercentFormat = option.meta.seriesPercentFormat || {};
        // Leave per-series overrides to existing meta; `withLightTheme` will pick these up.
        break;
      }
      case 'set_x_axis': {
        const arr = Array.isArray(option.xAxis) ? option.xAxis : option.xAxis ? [option.xAxis] : [];
        option.xAxis = arr.map((ax: any) => ({ ...ax, name: p.field }));
        option.meta = option.meta || {};
        option.meta.chartDesign = { ...(option.meta.chartDesign||{}), x_field: p.field };
        break;
      }
      case 'filter_companies': {
        // Soft filter by toggling series visibility based on company prefix (e.g., "AMD - Revenue")
        const selected = { ...((option.legend||{}).selected || {}) };
        const whitelist = new Set(p.tickers.map(t => t.toUpperCase()));
        for (const s of (option.series||[])) {
          const name: string = s.name || '';
          const prefix = name.includes(' - ') ? name.split(' - ', 1)[0].toUpperCase() : name.toUpperCase();
          selected[name] = whitelist.has(prefix);
        }
        option.legend = { ...(option.legend||{}), selected };
        break;
      }
      // Other ops map similarly…
    }
  }
  return option;
}
```

### 2) ChartCard stays presentational

- Accepts a finalized `option` and renders it.
- Keep `replaceMerge: ['series','xAxis','yAxis']` to avoid stale series when switching chart types.

### 3) Page integration (reuse hooks + pages)

- Keep a `chartSpec` in state (the last committed option).
- In both hooks, add a `case 'chart_patch'` that computes `next = applyChartOps(chartSpec, patch)` and sets it.
  - `components/analytics/hooks/useAnalyticsSqlStream.ts`
  - `components/analytics/hooks/useAnalyticsMemoryStream.ts`
- Pages stay as-is; they already render `<ChartCard>` (SQL) and, after we add a page-level chart, Memory too.

---

## Backend Plumbing (Minimal / no schema change)

If the agent runs server‑side, add a pass‑through event in the streaming endpoints:

- Analytics SQL endpoint already streams JSON; permit it to emit `{ event: 'chart_patch', data: { ops: [...] } }`.
- Analytics Memory flow can do the same inside `analytics_memory_workflow(...)`.

No database work is needed—this is purely presentational.

---

## Example: “Switch to bar chart”

Agent decides one high‑level op:

```
{
  "event": "chart_patch",
  "data": {
    "reason": "User requested bar chart",
    "ops": [{ "op": "set_chart_type", "value": "bar" }]
  }
}
```

UI reaction (in either hook):

```
const onChartPatch = (patch: ChartPatch) => {
  setChartSpec(prev => applyChartOps(prev, patch));
  streamHook.setCurrentStatus?.('Updated chart: bar');
};
```

If the current data is OHLC (candlestick), pick a safe fallback (e.g., close price) automatically or return a validation nudge (see Edge Cases).

---

## Edge Cases & Conventions

- Candlestick → Bar/Line: if OHLC columns are present, default to `close` series when switching away from candlestick.
- Percent vs currency: carry `meta.seriesValueType`/`seriesPercentFormat` and allow `set_y_axis_format` to force display if the user asks “show in %”.
- Grouping switches: changing `grouping` from `ticker` to `metric` affects legend semantics. Keep legend.selected intact where possible (name‑based matching).
- Undo: keep a ring buffer of the last N patches so you can support undo/redo.
- chart_id: if you support multiple charts on screen, use `chart_id` to target the right one.

---

## Test Plan (targeted)

- Reducer unit tests
  - set_chart_type converts all series to expected types and adjusts `areaStyle/stack` as needed.
  - toggle_series updates legend.selected only, not data.
  - set_y_axis_format updates meta and `withLightTheme` formats values accordingly.

- Hook/page tests
  - Receiving `chart_patch` updates the rendered chart without refetching.

(If CI cannot install deps locally, keep tests small and colocated; run later in dev.)

---

## Rollout Steps

1) Add `chartOps.ts` and unit tests.
2) Wire `chart_patch` handling in both streams (SQL + Memory).
3) Keep `ChartCard` as is; just pass the updated option and use `replaceMerge`.
4) Optional: add UI affordances to show “Chart updated by agent: <reason>”.

---

## Prompting Hints for the Agent

- Prefer high‑level ops over rebuilding full specs.
- Use minimal patches: one or two ops per follow‑up.
- If changing visualization would make values misleading (e.g., switching to percent requires normalization), include a companion op `set_y_axis_format` with `valueType: 'percent'`.

```
{
  "event": "chart_patch",
  "data": {
    "reason": "Compare % instead of $",
    "ops": [
      { "op": "set_chart_type", "value": "stacked_bar" },
      { "op": "set_stack", "stack": true, "mode": "percent" },
      { "op": "set_y_axis_format", "valueType": "percent" }
    ]
  }
}
```

This keeps the dataset intact while telling the UI exactly how to redraw.

---

## Files to Touch (when implementing)

- Reuse: `components/analytics/utils/chartOptions.ts` (add types + reducer `applyChartOps`)
- Hooks: handle `chart_patch` in
  - `components/analytics/hooks/useAnalyticsSqlStream.ts`
  - `components/analytics/hooks/useAnalyticsMemoryStream.ts`
- Optional: tweak `components/analytics/common/ChartCard.tsx` to use `replaceMerge` inside `onChartReady`/updates.
