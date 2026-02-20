---
description: "Verify that completed work actually achieves the stated goal. Runs tests, checks parity, generates verification report."
tools: ["search/readFile", "search/listDirectory", "search/textSearch", "runCommands/runInTerminal", "runTests", "search/codebase", "usages"]
---

<objective>
Verify that the current phase/plan work achieves its goal.
Produce a verification report with evidence.

Use when: After executing a phase or plan. Before marking work as done.
</objective>

<execution_context>
@.github/agents/gsd-verifier.agent.md
</execution_context>

<context>
@.gsd/STATE.md
@.gsd/PROJECT.md

Current phase plans and summaries:
@.gsd/phases/ (current phase directory)
</context>

<process>

<step name="gather_must_haves">
1. Read PLAN.md frontmatter for `must_haves`
2. If no must_haves, derive from ROADMAP.md phase goal
</step>

<step name="automated_verification">
Run automated checks:
1. `pytest tests/ -v` — all tests pass
2. `ruff check .` — no linting errors
3. `ruff format . --check` — code formatted
4. Check commission_rate: `grep -r "0.0007" backend/` — still consistent
5. Check engine: `grep -r "FallbackEngineV4\|fallback_engine_v4" backend/` — still gold standard
</step>

<step name="goal_verification">
Hand off to @gsd-verifier agent with must_haves.
Agent checks truths, artifacts, key_links, and anti-patterns.
</step>

<step name="report">
Create verification report:
- Status: passed | gaps_found | human_needed
- Evidence for each check
- If gaps: recommended fix plans
</step>

</process>

<success_criteria>

- [ ] All must_haves verified with evidence
- [ ] Tests passing
- [ ] No anti-patterns in modified files
- [ ] Verification report created
      </success_criteria>
