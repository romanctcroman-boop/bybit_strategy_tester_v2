---
description: "Initialize GSD workflow for a new feature or project. Creates PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md."
tools: ["search/readFile", "edit/editFiles", "edit/createFile", "search/listDirectory", "search/textSearch"]
---

<objective>
Initialize GSD for a NEW feature/initiative from scratch.

Use when: Greenfield feature with no existing code for it yet.
NOT for: Existing project with code already written — use /gsd-bootstrap instead.

Decision tree:

- Project exists, codebase exists → /gsd-bootstrap
- New feature in existing project → /gsd-new-project (this one)
- Bug investigation → /gsd-debug
- Quick one-off task → don't use GSD, just do it
  </objective>

<execution_context>
@.github/copilot-instructions.md
@AGENTS.MD
</execution_context>

<context>
User's goal: ${input}

Current project state:
@.gsd/STATE.md (if exists)
@.gsd/PROJECT.md (if exists)
</context>

<process>

<step name="discover">
Ask the user to clarify:
1. What is the high-level goal?
2. What are the constraints? (e.g., must maintain TradingView parity)
3. What is the definition of done?
4. Are there dependencies on existing features?
</step>

<step name="create_project">
Create `.gsd/PROJECT.md`:
- Project name and one-line description
- Core value (the ONE thing that matters)
- Technical constraints (commission=0.0007, FallbackEngineV4, etc.)
- Success criteria (measurable)
- Out of scope (explicit exclusions)
</step>

<step name="create_requirements">
Create `.gsd/REQUIREMENTS.md`:
- Categorized requirements with IDs (e.g., BT-01, API-02, UI-03)
- v1 (committed) vs v2 (deferred)
- Traceability table (empty, filled during roadmap)
</step>

<step name="create_roadmap">
Hand off to @gsd-roadmapper agent to create `.gsd/ROADMAP.md`
</step>

<step name="create_state">
Create `.gsd/STATE.md`:
- Current position: Phase 0 of N
- Status: Ready to plan
- Progress: 0%
</step>

</process>

<success_criteria>

- [ ] `.gsd/PROJECT.md` exists with clear goal and constraints
- [ ] `.gsd/REQUIREMENTS.md` exists with categorized requirements
- [ ] `.gsd/ROADMAP.md` exists with phased plan
- [ ] `.gsd/STATE.md` exists with initial state
- [ ] User confirmed the roadmap makes sense
      </success_criteria>
