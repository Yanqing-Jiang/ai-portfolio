---
description: Parallel call Opus, Codex, and Gemini agents on same task, then compare results for better decision making
allowed-tools: Task, Read, Write, Bash, TaskCreate, TaskUpdate, TaskList, AskUserQuestion
argument-hint: <task-type> <description> (e.g., "plan implement auth system" or "debug login failure")
---

# Parallel Agent Comparison (3 Agents)

Runs three agents in parallel on the same task, then synthesizes the best approach from all perspectives.

## Usage

```
/parallel <task-type> <task description>
```

**Task types**: plan, debug, brainstorm, analyze, architect, review, research, design

**Examples**:
- `/parallel plan implement user authentication with OAuth`
- `/parallel debug API returning 500 errors on POST requests`
- `/parallel brainstorm ways to improve app performance`
- `/parallel architect microservices for payment system`
- `/parallel research best practices for caching`
- `/parallel design dashboard layout`

---

## Workflow

### Step 1: Parse Initial Input

Extract from `$ARGUMENTS`:
- **task_type**: First word (plan/debug/brainstorm/analyze/architect/review/research/design)
- **task_description**: Everything after first word

If no arguments or unclear, proceed to clarifying questions.

---

### Step 2: Clarifying Questions (REQUIRED)

**CRITICAL**: Before distributing to agents, gather comprehensive context. Use `AskUserQuestion` tool to collect details. Ask questions based on task type:

#### For `plan` / `architect`:
1. **Scope**: "What's the scope? (New feature / Enhancement / Refactor)"
2. **Constraints**: "Any tech constraints? (Framework, dependencies, existing patterns)"
3. **Priority**: "What matters most? (Speed / Maintainability / Scalability / Security)"

#### For `debug`:
1. **Symptoms**: "What exactly happens? (Error message, unexpected behavior)"
2. **Reproduction**: "Steps to reproduce? (Always / Sometimes / Random)"
3. **Recent changes**: "Any recent changes before this started?"

#### For `brainstorm` / `analyze`:
1. **Goal**: "What problem are we solving?"
2. **Constraints**: "Any limitations? (Budget, time, tech stack)"
3. **Preferences**: "Favor innovation or proven approaches?"

#### For `research`:
1. **Depth**: "Quick overview or deep dive?"
2. **Focus**: "Any specific aspects to prioritize?"
3. **Use case**: "How will this be applied?"

#### For `design`:
1. **Component type**: "What kind of component/layout?"
2. **Constraints**: "Design system, existing patterns to follow?"
3. **Priority**: "Accessibility / Performance / Aesthetics?"

**Compile the enriched context** into a detailed brief for all agents.

---

### Step 3: Create Tasks for Tracking

Use `TaskCreate` to set up tracking:

```
Task 1: "Gather requirements for parallel analysis"
  - status: completed (after Step 2)

Task 2: "Run Opus agent analysis"
  - status: pending → in_progress → completed

Task 3: "Run Codex agent analysis"
  - status: pending → in_progress → completed

Task 4: "Run Gemini agent analysis"
  - status: pending → in_progress → completed

Task 5: "Compare and synthesize results"
  - status: pending → in_progress → completed
```

---

### Step 4: Launch All Three Agents in Parallel

**CRITICAL**: Use a SINGLE message with THREE Task tool calls to run truly in parallel.

Update Tasks 2, 3, 4 to `in_progress`.

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

    Output to: docs/{task_type_folder}/parallel-codex-{topic}.md
```

**Agent C - Gemini**:
```
Task tool call:
- subagent_type: "gemini-agent"
- description: "{task_type} via Gemini CLI"
- prompt: |
    Task type: {task_type}

    Context: {enriched_context_from_clarifying_questions}

    Task: {task_description}

    Output to: docs/{task_type_folder}/parallel-gemini-{topic}.md
```

**Task type to folder mapping**:
- plan/architect → `docs/planning/`
- debug → `docs/bugs/`
- brainstorm/analyze/review → `docs/analysis/`
- research/design → `docs/research/` or `docs/designs/`

---

### Step 5: Collect Results

Wait for all three agents to complete.

Update Tasks 2, 3, 4 to `completed`.

Read outputs:
- Agent A (Opus): Returns inline result
- Agent B (Codex): Writes to markdown file → read that file
- Agent C (Gemini): Writes to markdown file → read that file

Update Task 5 to `in_progress`.

---

### Step 6: Compare and Synthesize

Create structured comparison:

```markdown
## Parallel Agent Comparison Results

### Task: {task_description}
### Type: {task_type}
### Context: {summary of clarifying answers}

---

## Agent A (Opus) Analysis

### Summary
{condensed key points - 3-5 sentences}

### Strengths
- {strength 1}
- {strength 2}

### Key Recommendations
1. {rec 1}
2. {rec 2}

---

## Agent B (Codex) Analysis

### Summary
{condensed key points - 3-5 sentences}

### Strengths
- {strength 1}
- {strength 2}

### Key Recommendations
1. {rec 1}
2. {rec 2}

---

## Agent C (Gemini) Analysis

### Summary
{condensed key points - 3-5 sentences}

### Strengths
- {strength 1}
- {strength 2}

### Key Recommendations
1. {rec 1}
2. {rec 2}

---

## Comparison Matrix

| Aspect | Opus | Codex | Gemini | Notes |
|--------|------|-------|--------|-------|
| Completeness | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | {note} |
| Practicality | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | {note} |
| Innovation | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | {note} |
| Risk Awareness | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | {note} |
| Alignment | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | {note} |

**Legend**: ⭐ = Low, ⭐⭐ = Medium, ⭐⭐⭐ = High

---

## Areas of Agreement
- {point all/most agents agree on}
- {another agreement}

## Areas of Divergence
- {where they differ and why}
- {another difference}

---

## Synthesis: Recommended Approach

Based on all three agents' analysis:

{synthesized recommendation combining best elements}

### Key Decisions
1. {decision 1 - which agent's approach and why}
2. {decision 2}
3. {decision 3}

### Action Items
- [ ] {next step 1}
- [ ] {next step 2}
- [ ] {next step 3}

### Risks to Monitor
- {risk 1}
- {risk 2}
```

Update Task 5 to `completed`.

---

### Step 7: Save and Present

**Save comparison report** to: `docs/{task_type_folder}/parallel-comparison-{topic}.md`

**Present to user** with options:
- "Would you like me to proceed with the recommended approach?"
- "Want to explore any agent's approach in more detail?"
- "Should I implement the action items?"

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
| research | docs/research/ |
| design | docs/designs/ |

---

## Why Three Agents?

1. **Diverse perspectives**: Claude (Opus), OpenAI (Codex), Google (Gemini) have different strengths
2. **Reduced blind spots**: Three perspectives catch more edge cases
3. **Confidence boost**: Agreement across all three = high confidence
4. **Better synthesis**: More data points for main agent to evaluate
5. **Model diversity**: Different training, different insights

---

## Notes

- **Clarifying questions are mandatory** - don't skip
- All three agents work on the EXACT same enriched task
- Parallel execution (single message with 3 Task calls)
- Main agent acts as judge/synthesizer
- Full outputs preserved in docs/ for reference
- Tasks track progress for complex analyses
