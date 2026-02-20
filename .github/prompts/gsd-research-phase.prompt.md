---
description: "Research implementation approaches for a phase before planning. Investigates libraries, patterns, and trade-offs."
tools: ["search/readFile", "search/listDirectory", "search/textSearch", "search/codebase", "usages", "fetch"]
---

<objective>
Research implementation approaches for a specific phase.
Creates RESEARCH.md to inform the planner.

Use when: Phase involves unfamiliar territory, new libraries, or multiple viable approaches.
</objective>

<execution_context>
@.github/agents/gsd-phase-researcher.agent.md
</execution_context>

<context>
@.gsd/ROADMAP.md
@.gsd/STATE.md

Phase to research: ${input}
</context>

<process>

<step name="research">
Hand off to @gsd-phase-researcher agent.
Agent creates `.gsd/phases/XX-name/{phase}-RESEARCH.md` with:
1. Investigation results with confidence levels
2. Recommended approach with rationale
3. Alternatives considered with trade-offs
4. Verified code examples
</step>

</process>

<success_criteria>

- [ ] Research document created in phase directory
- [ ] Clear recommendation with rationale
- [ ] All claims have evidence/source
- [ ] Alternatives documented with trade-offs
      </success_criteria>
