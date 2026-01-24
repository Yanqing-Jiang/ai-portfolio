---
description: Parallel call Opus and Codex agents on same task, then compare results for better decision making
allowed-tools: Task, Read, Write, Bash, TaskCreate, TaskUpdate, TaskList, AskUserQuestion
argument-hint: <task-type> <description> (e.g., "plan implement auth system" or "debug login failure")
---

# Parallel Agent Comparison

Runs two agents in parallel on the same task, then synthesizes the best approach from both perspectives.

## Usage

```
/parallel <task-type> <task description>
```

**Task types**: plan, debug, brainstorm, analyze, architect, review

**Examples**:
- `/parallel plan implement user authentication with OAuth`
- `/parallel debug API returning 500 errors on POST requests`
- `/parallel brainstorm ways to improve app performance`
- `/parallel architect microservices for payment system`

---

## Workflow

### Step 1: Parse Initial Input

Extract from `$ARGUMENTS`:
- **task_type**: First word (plan/debug/brainstorm/analyze/architect/review)
- **task_description**: Everything after first word

If no arguments or unclear, proceed to clarifying questions.

---

### Step 2: Clarifying Questions (REQUIRED)

**CRITICAL**: Before distributing to agents, gather comprehensive context. Use `AskUserQuestion` tool to collect details. Ask questions based on task type:

#### For `plan` / `architect`:
Ask about:
1. **Scope**: "What's the scope? (New feature / Enhancement / Refactor)"
2. **Constraints**: "Any tech constraints? (Framework, dependencies, existing patterns)"
3. **Priority**: "What matters most? (Speed / Maintainability / Scalability / Security)"
4. **Context**: "Any existing code/patterns to follow or avoid?"

#### For `debug`:
Ask about:
1. **Symptoms**: "What exactly happens? (Error message, unexpected behavior)"
2. **Reproduction**: "Steps to reproduce? (Always / Sometimes / Random)"
3. **Recent changes**: "Any recent changes before this started?"
4. **Environment**: "Where does it occur? (Dev / Prod / Specific browser)"

#### For `brainstorm`:
Ask about:
1. **Goal**: "What problem are we solving?"
2. **Constraints**: "Any limitations? (Budget, time, tech stack)"
3. **Preferences**: "Favor innovation or proven approaches?"
4. **Success criteria**: "How will we measure success?"

#### For `analyze` / `review`:
Ask about:
1. **Focus area**: "What to focus on? (Performance / Security / Code quality / Architecture)"
2. **Depth**: "Quick scan or deep dive?"
3. **Comparison**: "Compare against any standard or baseline?"
4. **Actionable**: "Need recommendations or just assessment?"

**Compile the enriched context** into a detailed brief for both agents.

---

### Step 3: Create Tasks for Tracking

Use `TaskCreate` to set up tracking:

```
Task 1: "Gather requirements for parallel analysis"
  - status: completed (after Step 2)
  - description: Collect context via clarifying questions

Task 2: "Run Opus agent analysis"
  - status: pending → in_progress → completed
  - description: Execute general-purpose agent with opus model

Task 3: "Run Codex agent analysis"
  - status: pending → in_progress → completed
  - description: Execute codex-agent via CLI

Task 4: "Compare and synthesize results"
  - status: pending → in_progress → completed
  - description: Evaluate both outputs, create comparison matrix, recommend approach
```

---

### Step 4: Launch Both Agents in Parallel

**CRITICAL**: Use a SINGLE message with TWO Task tool calls to run truly in parallel.

Update Task 2 and Task 3 to `in_progress`.

**Agent A - Opus (general-purpose)**:
```
Task tool call:
- subagent_type: "general-purpose"
- model: "opus"
- description: "{task_type} via Opus"
- prompt: |
    ## Task: {task_type}

    ## Context
    {enriched_context_from_clarifying_questions}

    ## Original Request
    {task_description}

    ## Instructions
    Provide your complete analysis/plan/solution. Be thorough and detailed.
    Structure your response clearly with sections.

    Focus on:
    - Clear reasoning and rationale
    - Practical implementation details
    - Edge cases and considerations
    - Trade-offs of your approach
    - Concrete next steps
```

**Agent B - Codex**:
```
Task tool call:
- subagent_type: "codex-agent"
- description: "{task_type} via Codex CLI"
- prompt: |
    Task type: {task_type}

    Context: {enriched_context_from_clarifying_questions}

    Task: {task_description}

    Provide your complete analysis/plan/solution.
    Output to: docs/{task_type_folder}/parallel-codex-{timestamp}.md
```

**Task type to folder mapping**:
- plan/architect → `docs/planning/`
- debug → `docs/bugs/`
- brainstorm/analyze/review → `docs/analysis/`

---

### Step 5: Collect Results

Wait for both agents to complete.

Update Task 2 and Task 3 to `completed`.

Read outputs:
- Agent A: Returns inline result
- Agent B: Writes to markdown file → read that file

Update Task 4 to `in_progress`.

---

### Step 6: Compare and Synthesize

Create structured comparison:

```markdown
## Parallel Agent Comparison Results

### Task: {task_description}
### Type: {task_type}
### Context Gathered: {summary of clarifying answers}

---

## Agent A (Opus) Analysis

### Summary
{condensed key points}

### Strengths
- {strength 1}
- {strength 2}

### Approach
{brief description of their approach}

### Key Recommendations
1. {rec 1}
2. {rec 2}

---

## Agent B (Codex) Analysis

### Summary
{condensed key points}

### Strengths
- {strength 1}
- {strength 2}

### Approach
{brief description of their approach}

### Key Recommendations
1. {rec 1}
2. {rec 2}

---

## Comparison Matrix

| Aspect | Opus | Codex | Notes |
|--------|------|-------|-------|
| Completeness | ⭐⭐⭐ | ⭐⭐⭐ | {note} |
| Practicality | ⭐⭐⭐ | ⭐⭐⭐ | {note} |
| Innovation | ⭐⭐⭐ | ⭐⭐⭐ | {note} |
| Risk Awareness | ⭐⭐⭐ | ⭐⭐⭐ | {note} |
| Alignment w/ Context | ⭐⭐⭐ | ⭐⭐⭐ | {note} |

**Legend**: ⭐ = Low, ⭐⭐ = Medium, ⭐⭐⭐ = High

---

## Areas of Agreement
- {point both agents agree on}
- {another agreement}

## Areas of Divergence
- {where they differ and why}
- {another difference}

---

## Synthesis: Recommended Approach

Based on both agents' analysis and the gathered context:

{synthesized recommendation combining best elements from both}

### Key Decisions
1. {decision 1 with rationale - which agent's approach and why}
2. {decision 2 with rationale}
3. {decision 3 with rationale}

### Action Items
- [ ] {concrete next step 1}
- [ ] {concrete next step 2}
- [ ] {concrete next step 3}
- [ ] {concrete next step 4}

### Risks to Monitor
- {risk 1}
- {risk 2}
```

Update Task 4 to `completed`.

---

### Step 7: Save and Present

**Save comparison report** to: `docs/{task_type_folder}/parallel-comparison-{timestamp}.md`

**Present to user** with options:
- "Would you like me to proceed with the recommended approach?"
- "Want to explore either agent's approach in more detail?"
- "Should I implement the action items?"
- "Need me to dig deeper on any specific aspect?"

---

## Clarifying Question Templates

### Quick Reference by Task Type

| Task Type | Must Ask | Optional |
|-----------|----------|----------|
| plan | Scope, Constraints, Priority | Timeline, Team size |
| architect | Scale, Patterns, Integration | Migration path |
| debug | Symptoms, Repro steps, Recent changes | Logs, Environment |
| brainstorm | Goal, Constraints | Wild ideas ok? |
| analyze | Focus area, Depth | Baseline comparison |
| review | Focus area, Standards | Blockers? |

### Example Clarifying Flow

**User**: `/parallel plan implement caching layer`

**Clarifying Questions**:
```
Before I dispatch this to both agents, a few quick questions:

1. **Scope**: Is this for API responses, database queries, or both?
   - [ ] API responses only
   - [ ] Database queries only
   - [ ] Both
   - [ ] Other: ___

2. **Tech constraints**: Any preferred caching solution?
   - [ ] Redis
   - [ ] Memcached
   - [ ] In-memory (Node cache)
   - [ ] No preference

3. **Priority**: What matters most?
   - [ ] Performance (lowest latency)
   - [ ] Simplicity (easy to maintain)
   - [ ] Cost (minimize infrastructure)
   - [ ] Flexibility (easy to change later)

4. **Context**: Any existing caching in the codebase I should know about?
   → [free text response]
```

**After answers**, compile into enriched context:
```
Task: Implement caching layer
Scope: API responses and database queries
Tech: Prefer Redis, open to alternatives
Priority: Performance first, then simplicity
Context: No existing caching, using Express + PostgreSQL
```

---

## Output Locations

| Task Type | Output Folder |
|-----------|---------------|
| plan | docs/planning/ |
| architect | docs/planning/ |
| debug | docs/bugs/ |
| brainstorm | docs/analysis/ |
| analyze | docs/analysis/ |
| review | docs/analysis/ |

---

## Why Parallel Agents?

1. **Diverse perspectives**: Different models have different strengths
2. **Reduced blind spots**: One agent may catch what another misses
3. **Confidence boost**: Agreement between agents increases confidence
4. **Better decisions**: Synthesis often better than either alone
5. **Context leverage**: Clarifying questions ensure both agents work with full picture

---

## Notes

- **Clarifying questions are mandatory** - don't skip to save time
- Both agents work on the EXACT same enriched task (no splitting)
- Parallel execution saves time despite extra question step
- Main agent acts as judge/synthesizer
- Full outputs preserved in docs/ for reference
- Tasks track progress for complex analyses
