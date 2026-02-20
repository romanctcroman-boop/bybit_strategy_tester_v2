---
description: "Create executable plans for a roadmap phase. Breaks work into 2-3 task plans with dependencies, waves, and verification criteria."
tools: ["search/readFile", "edit/editFiles", "edit/createFile", "search/listDirectory", "search/textSearch", "search/codebase", "usages"]
---

<objective>
Plan the next phase from the roadmap. Creates PLAN.md files in `.gsd/phases/XX-name/`.

Use when: Ready to start a new phase. STATE.md shows "Ready to plan".
Prerequisite: `.gsd/ROADMAP.md` exists.
</objective>

<execution_context>
@.github/skills/execute-plan/SKILL.md (downstream consumer)
@.github/agents/planner.agent.md
</execution_context>

<context>
@.gsd/PROJECT.md
@.gsd/ROADMAP.md
@.gsd/STATE.md
@.gsd/REQUIREMENTS.md (if exists)

Phase to plan: ${input}
</context>

<process>

<step name="load_context">
1. Read STATE.md — what phase are we on?
2. Read ROADMAP.md — what's the phase goal?
3. Read prior phase SUMMARYs if they exist and are relevant
4. Scan codebase for files that will be affected
</step>

<step name="research">
If phase involves unfamiliar territory, hand off to @gsd-phase-researcher.
Otherwise, use `codebase` and `usages` tools to understand current implementation.
</step>

<step name="create_plans">
Create `.gsd/phases/XX-name/{phase}-{plan}-PLAN.md` files:

Each plan has:

```yaml
---
phase: XX-name
plan: NN
type: execute | tdd
wave: N
depends_on: []
files_modified: []
autonomous: true | false
must_haves:
    truths: []
    artifacts: []
    key_links: []
---
```

Rules:

- 2-3 tasks per plan maximum
- Vertical slices preferred (model + API + test, not all models then all APIs)
- Each task: name, files, action (specific!), verify, done criteria
- TDD candidates get separate plans with `type: tdd`
  </step>

<step name="update_state">
Update `.gsd/STATE.md`:
- Status: Ready to execute
- Plan count for current phase
</step>

</process>

<success_criteria>

- [ ] PLAN.md files created in phase directory
- [ ] Each plan has valid frontmatter (wave, depends_on, files_modified, autonomous)
- [ ] Tasks are specific and actionable (not vague)
- [ ] Dependencies correctly identified
- [ ] must_haves derived from phase goal
- [ ] STATE.md updated
      </success_criteria>
