# Chat History Stream Unification

## Summary
- render streaming artifacts directly inside the assistant result bubble so ranked cards update in place
- removed the separate `LiveArtifacts` mount from the memory page and routed all chart/analysis/stock/web cards through `ChatHistory`
- added progressive analysis/text fields to the analytics stream hook so interim drafts surface without duplicate cards and preserve ordering

## Testing
- `npx vitest run components/analytics/memory/ChatHistory.test.tsx`
