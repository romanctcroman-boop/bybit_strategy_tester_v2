---
description: "Bootstrap GSD into an existing project. Maps codebase, captures current state, creates PROJECT/ROADMAP/STATE from what already exists."
tools: ["search/readFile", "edit/editFiles", "edit/createFile", "search/listDirectory", "search/textSearch", "search/codebase", "usages", "runCommands/runInTerminal"]
mode: "agent"
---

<objective>
Bootstrap GSD workflow into an EXISTING project.

Unlike /gsd-new-project (for greenfield), this captures what already exists:

- Maps the codebase structure and architecture
- Identifies current state (what works, what's in progress, what's broken)
- Creates GSD project files from existing reality
- Sets up the first actionable phase

Use when: Project already has code, tests, infrastructure. You want GSD's structured workflow going forward.
</objective>

<execution_context>
@.github/copilot-instructions.md
@AGENTS.MD
@.github/agents/gsd-codebase-mapper.agent.md
</execution_context>

<context>
User's goal for GSD adoption: ${input}

Existing project docs:
@.github/copilot-instructions.md
@AGENTS.MD
@CHANGELOG.md
</context>

<process>

<step name="assess_existing" priority="first">
**Assess what already exists. DO NOT recreate what's already there.**

1. Check for existing `.gsd/` directory — if exists, read STATE.md and resume
2. Read `.github/copilot-instructions.md` — project context is already documented
3. Read `AGENTS.MD` — autonomy rules already defined
4. Read `CHANGELOG.md` — recent changes and current state
5. Read `docs/DECISIONS.md` (if exists) — architecture decisions already made
6. Scan key directories:
    - `backend/` — how many routers, engines, strategies, services
    - `frontend/` — pages, components
    - `tests/` — test coverage
7. Run `pytest tests/ -v --co -q` — list existing tests (don't run them)
8. Run `ruff check . --statistics` — current code quality
   </step>

<step name="map_codebase">
**Create codebase analysis from existing code.**

Hand off to @gsd-codebase-mapper or do inline:
Create `.gsd/codebase/` with:

- `STRUCTURE.md` — directory layout (from actual scan, not template)
- `STACK.md` — actual tech stack (from pyproject.toml, requirements, imports)
- `ARCHITECTURE.md` — real data flow (from import chain analysis)
- `PATTERNS.md` — actual conventions (from reading existing code)
- `CONCERNS.md` — real issues (from test failures, TODOs, known bugs)

**Critical:** Populate from ACTUAL code, not assumptions.
</step>

<step name="create_project">
**Create `.gsd/PROJECT.md` from existing project reality.**

NOT a wishlist — a snapshot of what this project IS:

- Core value: extracted from README/copilot-instructions, not invented
- Technical constraints: extracted from actual config (commission_rate, engine, etc.)
- Current capabilities: what already works
- Known limitations: what doesn't work yet
- Success criteria: derived from user's stated goal
  </step>

<step name="identify_current_state">
**Capture where the project actually is right now.**

1. What features are complete and working?
2. What's partially implemented?
3. What's planned but not started?
4. What's broken or has known issues?
5. What's the test coverage situation?
6. What are the biggest pain points?

Source this from:

- Test results
- CHANGELOG.md entries
- TODO/FIXME grep across codebase
- User input about their priorities
  </step>

<step name="ask_user_goal">
**Ask the user what they want to work on NEXT.**

GSD needs a direction. Ask:

1. "What's the ONE thing you want to accomplish next?"
2. "Are there any blockers or debt you want to fix first?"
3. "What's your timeline / how many sessions do you want this to take?"

Do NOT create a roadmap for the entire project — only for the user's stated goal.
</step>

<step name="create_roadmap">
**Create focused ROADMAP.md for the user's goal.**

NOT a roadmap for the whole project. A roadmap for THIS initiative:

- 3-6 phases maximum
- Each phase achievable in 1-3 plans
- First phase should be the smallest possible valuable increment
- Include a "Phase 0: Stabilize" if there are blockers

Example for "add walk-forward optimization":

```
Phase 1: Walk-Forward Engine (2 plans)
Phase 2: Walk-Forward API endpoints (1 plan)
Phase 3: Walk-Forward UI integration (2 plans)
Phase 4: Validation against TradingView (1 plan)
```

</step>

<step name="create_state">
**Create STATE.md reflecting actual project position.**

```markdown
# Project State

## Project Reference

See: .gsd/PROJECT.md (updated YYYY-MM-DD)
Core value: [from PROJECT.md]
Current focus: [user's stated goal]

## Current Position

Phase: [1] of [N] ([Phase name])
Plan: [0] of [M] in current phase
Status: Ready to plan
Last activity: YYYY-MM-DD — GSD bootstrapped into existing project

Progress: [░░░░░░░░░░] 0%

## Existing Codebase Context

- Backend: ~X files, Y routers, Z strategies
- Tests: N test files, ~M tests
- Code quality: ruff reports X issues
- Last test run: [pass/fail summary]

## Accumulated Context

### Key Decisions (pre-GSD)

[Decisions from DECISIONS.md / CHANGELOG.md that matter]

### Known Issues (pre-GSD)

[From CONCERNS.md / grep TODO / user input]

### Patterns Established (pre-GSD)

[From PATTERNS.md — existing conventions to follow]
```

</step>

<step name="first_action">
**Tell the user exactly what to do next.**

Output:

```
✅ GSD bootstrapped into existing project.

📊 Codebase: X files analyzed, Y patterns documented
📋 Roadmap: N phases for "[user's goal]"
📍 Position: Phase 1, ready to plan

▶️ Next step: Type /gsd-plan-phase to plan Phase 1: [name]
   Or select the Planner agent and describe what you want first.
```

</step>

</process>

<anti_patterns>
NEVER:

- Recreate files that already exist (read them instead)
- Invent requirements the user didn't state
- Create a roadmap for the entire project lifetime
- Ignore existing tests, docs, decisions
- Assume the codebase is broken (verify first)
- Create generic templates — fill with ACTUAL data

ALWAYS:

- Read before writing
- Use real numbers (file counts, test counts, line counts)
- Quote from existing docs when creating PROJECT.md
- Ask the user before committing to a direction
- Keep Phase 1 small and achievable
  </anti_patterns>

<success_criteria>

- [ ] Codebase mapped with REAL data (not templates)
- [ ] PROJECT.md reflects actual project, not aspirational
- [ ] STATE.md has real metrics (test count, file count, etc.)
- [ ] ROADMAP.md focused on user's stated goal (not everything)
- [ ] User confirmed the plan makes sense
- [ ] Next action is clear: /gsd-plan-phase for Phase 1
      </success_criteria>
