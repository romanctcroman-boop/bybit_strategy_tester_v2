---
description: "Execute all plans in the current phase. Runs plans by wave, creates summaries, verifies results."
tools: ["search/readFile", "edit/editFiles", "edit/createFile", "search/listDirectory", "search/textSearch", "runCommands/runInTerminal", "runTests", "search/codebase", "usages"]
---

<objective>
Execute all PLAN.md files for the current phase, grouped by wave number.

Use when: Plans exist and STATE.md shows "Ready to execute".
</objective>

<execution_context>
@.github/skills/execute-plan/SKILL.md
@.github/agents/implementer.agent.md
</execution_context>

<context>
@.gsd/PROJECT.md
@.gsd/STATE.md

Phase plans:
@.gsd/phases/ (current phase directory)
</context>

<process>

<step name="load_plans">
1. Read STATE.md for current phase
2. Find all PLAN.md files in phase directory
3. Group by `wave` number from frontmatter
4. Sort waves ascending
</step>

<step name="execute_waves">
For each wave (1, 2, 3...):
1. Read all plans in this wave
2. For each plan:
   a. Execute tasks in order
   b. Run verify command after each task
   c. If checkpoint: pause and report to user
   d. After all tasks: run verification checks
3. Create `{phase}-{plan}-SUMMARY.md` for each completed plan
4. Wave N+1 only starts after all wave N plans complete
</step>

<step name="verify_phase">
After all waves complete:
1. Hand off to @gsd-verifier to check must_haves
2. If gaps_found: create fix plans and re-execute
3. If passed: mark phase complete
</step>

<step name="update_state">
Update `.gsd/STATE.md`:
- Advance to next phase
- Record decisions made during execution
- Update progress percentage
</step>

<step name="quality_gate">
Before marking phase complete:
- [ ] `pytest tests/ -v -m "not slow"` passes
- [ ] `ruff check .` — no errors
- [ ] `ruff format . --check` — formatted
- [ ] CHANGELOG.md updated
- [ ] All PLAN.md must_haves verified
</step>

</process>

<success_criteria>

- [ ] All plans in all waves executed
- [ ] SUMMARY.md created for each plan
- [ ] Verification passed (all must_haves met)
- [ ] Tests pass, linting clean
- [ ] STATE.md updated with new position
      </success_criteria>
