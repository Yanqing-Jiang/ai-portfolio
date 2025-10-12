# Next Gen Analytics (Agents) Refresh Plan

## Objective
Rebrand the `next-gen-analytics-memory` surfaces to "Next Gen Analytics (Agents)" while modernizing the landing hero and workflow descriptors so recruiters immediately understand the agentic workflow options.

## Steps
1. **Update Agent Workflow Metadata**  
   - Replace helper copy inside `components/analytics/memory/Page.tsx` so `FLOW_META['planner-executor'].helper` reads "Direct fixed workflow with RAG-backed SQL guidance" instead of "Deterministic direct workflow with YAML-backed SQL guidance".  
   - Change the same object for `single-agent` to "Claude-Code style single LLM agent with multipole tool calling capability" and `multi-agent` to "Supervisor agent collaboration across multiple specialists: financial analyst, charting specialist, stock watcher, web researcher, SQL analyst" (fix spelling).  
   - Update the `projectData.description` block to match the new bulleted narrative (e.g., "Human-in-the-loop: Compact widget for clarification on peers/metrics/range").

2. **Resync Portfolio Data Sources**  
   - In `constants.ts`, rename the project title to "Next Gen Analytics (Agents)" and swap the description paragraph for the new multi-line story ending with "Memory optimization: RAG optimized, Cached queries, vectorized prompts, stateful nodes".  
   - Update related SEO strings in `constants.ts` and `public/ai-projects.json` (e.g., change `seoTitle` to "Next Gen Analytics Agents | LangGraph + FastAPI Copilot").  
   - Verify `technologies` arrays keep parity with the landing badges after renaming.

3. **Rebuild Landing Hero Layout**  
   - Convert the hero container in `components/LandingPage.tsx` to a single-column mobile layout that becomes a 60/40 split (`lg:grid-cols-[3fr_2fr]` or equivalent) with 16px gap adjustments (name→subtitle 16px, subtitle→social 20px).  
   - Spotlight effect: replace current layered gradients with a single 360px radius circle at 20% opacity using `rgba(56,189,248,0.20)` anchored behind hero content.  
   - Typography adjustments:  
     - Hero title → `fontSize: clamp(44px, 4.5vw, 56px)`, `leading-[1.1]`, keep `font-extrabold tracking-[-0.01em]`.  
     - Subtitle credential → bold `text-sky-200` set inline (no pill) using `clamp(17px, 2vw, 22px)`.  
   - Hero heading accent: match the sidebar brand gradient (bg-gradient-to-r from-blue-400 to-purple-500), upgrade to `font-black`, reuse the hero's `fontSize: clamp(44px, 4.5vw, 56px)`, and layer `textShadow: '0 0 40px rgba(56, 189, 248, 0.3)'` for depth.  
   - Update body/project description copy to `text-gray-300`, `leading-[1.7]`, and cap width via `max-w-prose`; revisit truncation threshold to 180-200 chars or remove.  
   - Ensure contact icons breathe by enforcing the specified gap rhythm.

4. **Color System & Badge Semantics**  
   - Introduce a `getTechBadgeClass(tech)` helper inside `LandingPage.tsx` that maps technologies to semantic categories with accessible contrast (target ≥7:1):  
     - **AI / Agent Frameworks (Emerald):** `bg-emerald-600/20 text-emerald-300 border-emerald-500/30 hover:bg-emerald-600/30`.  
     - **Data / Backend (Green):** `bg-emerald-500/20 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/30`.  
     - **Frontend / UI (Purple):** `bg-purple-500/20 text-purple-300 border-purple-500/30 hover:bg-purple-500/30`.  
     - **Infrastructure / DevOps (Orange):** `bg-orange-500/20 text-orange-300 border-orange-500/30 hover:bg-orange-500/30`.  
     - **ML / Analytics (Pink):** `bg-pink-500/20 text-pink-300 border-pink-500/30 hover:bg-pink-500/30`.  
   - Update base text colors → `text-gray-300` on `bg-slate-950` (ratio ~11.9:1), subtitle retains `text-sky-200`.  
   - Remove remaining non-essential gradients so animated morphing text keeps the spotlight.

5. **Regression Checks**  
   - Run `npm run lint` (or `npm run test` if lint unavailable) to ensure TypeScript/React changes compile.  
   - Manually spot-check that the rebranded project still renders in the project gallery and the analytics page loads without runtime errors.

## Notes
- No backend changes required; edits stay inside the frontend Vite app.
- Verify there are no leftover "Memory" labels after the rename by running `rg "Memory Agent"` once edits complete.

## Current Status (as of 2025-10-12)
- ✅ Step 1 (Update Agent Workflow Metadata) — helper copy and `projectData.description` updated in `components/analytics/memory/Page.tsx`.
- ✅ Step 2 (Resync Portfolio Data Sources) — title/description/SEO strings refreshed for `next-gen-analytics-memory` entry in `constants.ts` and mirrored in `public/ai-projects.json`.
- ✅ Step 3 (Rebuild Landing Hero Layout) — hero grid, typography, divider accent, and spotlight simplified per spec with credential text inline.
- ✅ Step 4 (Color System & Badge Semantics) — semantic badge helper with WCAG-friendly palettes deployed in `components/LandingPage.tsx`.
- ✅ Step 5 (Regression Checks) — `npm run lint` unavailable; ran `npm run test` (vitest) successfully to validate the React build.
