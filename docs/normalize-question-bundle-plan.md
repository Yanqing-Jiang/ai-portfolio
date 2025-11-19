# Normalizing `normalizeQuestionBundle` Hook Usage (November 19, 2025)

## Problem Statement
`components/analytics/hooks/useAnalyticsMemoryStream.ts` defines a helper named `normalizeQuestionBundle`. The helper calls `useEffect` even though it is neither a React component nor a hook. Whenever tests (especially concentrated Vitest runs) invoke the helper outside of the main hook render cycle, React detects that hook order changed and raises “Invalid hook call” / “Do not call Hooks inside …” errors. The regression plan previously noted this as a pre-existing issue; we need a dedicated cleanup to restore deterministic hook ordering.

## Proposed Fix Plan
1. **Move buffering effect into the main hook body.**  
   - Extract the `useEffect` that flushes `pendingAnalysisBufferRef` from inside `normalizeQuestionBundle`.  
   - Re-create the effect near the other topic-progress watchers so it observes `topicProgress.total/pending` at the top level of `useAnalyticsMemoryStream`.

2. **Convert `normalizeQuestionBundle` into a pure helper.**  
   - Keep it as a pure function that returns `{keywordFocus,user,industry}` without any side effects or hook usage.  
   - Re-run TypeScript checks to ensure no other helper calls include hook-only constructs.

3. **Add regression coverage.**  
   - Extend `useAnalyticsMemoryStream.test.tsx` with a minimal test that stubs topic events but never hydrates React state; the test should assert that no “invalid hook call” warnings are emitted.  
   - Optionally, add a unit test that exercises `normalizeQuestionBundle` independently to prove it remains pure.

4. **Verify full Vitest and React warning-free runs.**  
   - `npm test -- useAnalyticsMemoryStream.test.tsx --runInBand` must complete without the React hook-order warning banner.  
   - Run the targeted `vitest -t "buffers analysis updates until topic branches finish"` command to ensure the newly added buffering effect still fires.

## Risks / Open Questions
- If other helpers also call hooks, we should audit them while touching this area.  
- Moving the effect could affect batching behavior; we’ll need to confirm the analysis buffer flushes only once per topic batch.

Document authored November 19, 2025 to complement the Immediate Fix Plan entry in `docs/revision-card-handoff.md`.
