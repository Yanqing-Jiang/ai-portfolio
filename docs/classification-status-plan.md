# Classification & Status Fix Plan

Progress log: October 20, 2025 @ 3:40 PM PDT

## Issue Recap
- **Ledger (90)** – Classification flow returns `Final Answer Ready` with a decline message, but the chat UI only surfaces a green “Output ready” status bubble. No assistant bubble renders with the banner copy.
- **Ledger (92)** – Follow-up after “how are you” detects a financial query, but the planner aborts with `TimeframeModel.granularity` extra field errors, blocking the SQL/stock/web fan-out and leaving the status bubble blank.
- **Ledgers (93) & (94)** – Clarification responses hit the same `granularity` validation error, producing backend/front-end failures mid-run.
- **Live status positioning** – Screenshot in `docs/Untitled2.png` shows the desired placement: when no assistant cards exist yet, the live status bubble should appear on the **right** beneath the latest user turn; once cards start streaming, the bubble should merge onto the top of the assistant card stack.

## Step-by-Step Plan
1. **Patch Timeframe Schema & Normalizers**  
   - Extend `TimeframeModel` to accept an optional `granularity` enum so planner/clarifier payloads like the one in ledger (92) validate.  
   - Strip or remap `granularity` when serializing to prevent double sources (ensure `intent_to_sql_criteria` still forces quarterly when needed).  
   - Example: ledger (92) should advance past intent detection with `timeframe.granularity: "annual"` instead of raising `extra_forbidden`.
   - *Update:* `TimeframeModel` now includes an optional `granularity` field and clarification updates persist that value on the plan, eliminating the validation fault.

2. **Resume Full Pipeline After Small Talk → Finance Pivot**  
   - Once schema accepts `granularity`, confirm the workflow re-enters the three-lane execution (SQL + stock + web).  
   - Verify the live status bubble reappears during classification (`Classifying query`) and continues updating through planner/tool stages.  
   - Example: replay ledger (92) scenario – expect the next status to read “Clarifying timeframe…” while cards begin to trickle in.

3. **Render Classification Finalization Message**  
   - Update `useAnalyticsMemoryStream` so a `finalization` event with `details.banner.message` produces a visible assistant bubble (when no `final_answer` arrives).  
   - Ensure the follow-up banner still surfaces so the user can relaunch a full pipeline run.  
   - Example: ledger (90) should render “I can’t help with casual chat…” as the assistant response instead of “Output ready.”
   - *Update:* A dedicated `finalization` handler now emits/refreshes the result bubble and banner when only the decline turn is streamed.

4. **Reposition Standalone Status Bubble**  
   - Adjust `ChatHistory` layout so, prior to any assistant cards, the standalone status bubble anchors to the right/aligned beneath the latest user turn (matching screenshot).  
   - Keep the inline merge behavior once assistant artifacts exist so the bubble sits above the card stack.  
   - Example: immediate response after “how are you” should show “Analyzing query intent” on the right until the first card renders.
   - *Update:* Standalone status rows now mirror the user column (right-aligned with a trailing spacer) while inline bubbles remain attached to the assistant card stack.

5. **Regression Notes & Follow-Up**  
   - After code changes, re-run focused pytest/vitest suites covering planner validation and chat history rendering (deferred until explicitly allowed).  
   - Append verification outcomes back into this document once testing/manual checks occur.

Status Legend: ✅ done · 🚧 in progress · ⏱️ queued
- Step 1: ✅ done
- Step 2: 🚧 in progress (pending end-to-end replay)
- Step 3: ✅ done
- Step 4: ✅ done
- Step 5: ⏱️ queued
