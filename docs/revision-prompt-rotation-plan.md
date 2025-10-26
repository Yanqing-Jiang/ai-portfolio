# Revision Prompt Rotation Plan

This plan documents how to surface precise follow-up prompts after the first analytics response so users can trigger the fast-path revision flows already wired into the memory project (`components/analytics/hooks/useAnalyticsMemoryStream.ts`). It assumes the initial query has completed (`emitResultOnce()` fired) and artifact metadata is available inside `workflowDataRef.current`.

## 1. Detect Revision Eligibility

1. When `chatHistory` gains its first `result` message, call `deriveRevisionContext()` (new helper) to extract:
   - `primarySymbols` – union of `analysisSources` symbols, `stockWidget.symbols`, and chart meta tickers.
   - `availableLanes` – derived from artifact presence:
     - `chart` if `chartSpec` exists.
     - `analysis` if `analysis` or `analysisOverview` are non-empty.
     - `market` if `stockWidget` or `webSearch` exist.
     - `sql` if `sqlQuery` or `dataSample` exist (enables SQL reformat prompts).
   - `timeContext` – most recent `analysisOverview?.evidence` date or `stockWidget.bars`.

2. Store this context in component state so the prompt bar can react without recomputing every render.

## 2. Prompt Rotation Rules

After the first answer, replace the “discovery” chips with **lane-specific prompts**. Always display three to four prompts, prioritising lanes that have cached artifacts.

| Lane | Trigger Logic | Prompt Copy Template | Example (NVDA focus) |
| --- | --- | --- | --- |
| Chart Revision | `availableLanes.chart` | `Change the chart to {chartStyle} and reuse the same dataset.` | “Change the SQL chart to a bar chart.” |
| Analysis Revision | `availableLanes.analysis` | `Rewrite the analysis but emphasise {analysisAngle}.` | “Rewrite the analysis but focus on industry background.” |
| Market Revision | `availableLanes.market` | `Refresh only the market data for {symbol}.` | “Refresh only the market data for NVDA.” |
| Mixed Revision | `availableLanes.chart && availableLanes.analysis` | `Keep the query but update both the chart and analysis to highlight {focus}.` | “Keep the query but update both chart and analysis to highlight margin recovery.” |
| SQL Format Revision | `availableLanes.sql` | `Reuse the SQL results and adjust the chart to compare {metric} by {group}.` | “Reuse the SQL results and chart revenue share by company as stacked columns.” |
| Stock Swap | `stockWidget.symbols.length > 0` | `Swap the stock widget to track {alternateSymbol}.` | “Change the stock chart to AVGO.” |
| Web Research Refresh | `webSearch` present | `Refresh the web research only and look for {topic}.` | “Refresh the web research only and look for AI data centre headlines.” |

> **Tip:** rotate `chartStyle`, `analysisAngle`, and `{focus}` from a small vocabulary so prompts feel fresh (e.g., `['bar chart', 'stacked column chart', 'heatmap']`).

## 3. Prompt Generation Algorithm

1. **Assemble Prompt Candidates**
   ```ts
   const CANDIDATES = buildPromptCandidates({
     symbols: primarySymbols,
     lanes: availableLanes,
     timeContext,
   });
   ```
   `buildPromptCandidates` yields objects `{ lane: 'chart', copy: 'Change the SQL chart to a bar chart.', intent: 'chart_revision' }`.

2. **Prioritise & Slice**
   - Always include at least one chart or analysis prompt if eligible.
   - Randomise within lane buckets, but keep deterministic order per session to avoid flicker.
   - Limit to four buttons to preserve layout.

3. **Render Buttons**
   Update the existing prompt strip in `components/analytics/memory/Page.tsx` around line `360`:
   ```tsx
   {!hasStartedChat && !isLoading ? renderDiscoveryPrompts() : renderRevisionPrompts()}
   ```
   `renderRevisionPrompts()` maps over the selected candidates and renders `onClick={() => setQuery(candidate.copy)}`.

4. **Refresh After Each Revision**
   - When `revisionMode !== 'none'` returns to `'none'` (revision completed), regenerate candidates.
   - Debounce to avoid churn while streaming – wait for `workflow_complete`.
   - Log user selection via telemetry hook (optional) to identify popular revisions.

## 4. Example Prompt Sets

### Example A – SQL + Chart + Analysis (NVDA vs AMD)
- “Change the SQL chart to a bar chart.”
- “Rewrite the analysis but focus on industry background.”
- “Refresh only the market data for NVDA.”
- “Keep the query but update both chart and analysis to highlight supply constraints.”

### Example B – Chart + Stock Widget (AVGO)
- “Change the chart to a stacked column view.”
- “Rewrite the analysis to speak to CFO-level priorities.”
- “Change the stock chart to AVGO.”
- “Refresh the web research only and surface semiconductor export headlines.”

### Example C – Analysis + Web Research
- “Rewrite the analysis but emphasise competitive positioning.”
- “Refresh only the market data for NVDA.”
- “Refresh the web research only and gather AI accelerator news.”
- “Change the chart to a heatmap comparing gross margin.”

## 5. Implementation Checklist

1. Add `deriveRevisionContext()` and `buildPromptCandidates()` helpers (co-locate in `components/analytics/memory/Page.tsx` or a new `hooks/prompts` file).
2. Replace the current post-query prompt rendering with the rotation logic described above.
3. Ensure `useAnalyticsMemoryStream` exposes the `revisionMode` and latest artifacts (already available via `workflowDataRef`).
4. Add Vitest coverage: simulate a run, call `renderRevisionPrompts()`, assert lane-specific copy appears.
5. QA: trigger each sample prompt in the dev server and verify:
   - `chart_patch` path (chart bubble stays single).
   - `analysis_revision` path (narrative updates without new SQL).
   - `stock_revision_ready` and `web_revision_ready` path (market badge displays).
   - Mixed prompts correctly flip `revisionMode` to `mixed`.

With this plan, users receive targeted, self-explanatory buttons that directly align with the existing revision infrastructure, making fast-path updates discoverable immediately after the first response.

## 6. Implementation Status (October 24, 2025)

- ✅ Added `deriveRevisionContext` and `buildPromptCandidates` in `components/analytics/memory/revisionPrompts.ts`, consolidating symbols, lane availability, and rotation vocab.
- ✅ Wired the prompt rotation logic into `components/analytics/memory/Page.tsx`, swapping discovery chips for revision prompts once the first `result` message lands and regenerating after revisions complete.
- ✅ Preserved the streaming analysis fallback card and kept pre-run discovery prompts intact.
- ✅ Created unit coverage in `components/analytics/memory/revisionPrompts.test.ts` to assert context extraction, lane prioritisation, and minimum prompt fallback behaviour.
- ✅ Verified helper behaviour via `npm test -- --run components/analytics/memory/revisionPrompts.test.ts`.

### Follow-up Notes
- Consider telemetry hooks for prompt selection popularity per rotation key.
- Plan future integration tests once prompt rotation connects to end-to-end revision triggers.*** End Patch
