---
description: "Analyze and document the entire codebase structure, architecture, patterns, and concerns."
tools: ["search/readFile", "search/listDirectory", "search/textSearch", "search/codebase", "usages"]
---

<objective>
Create comprehensive codebase documentation in `.gsd/codebase/`.

Use when: First time using GSD in this project, or after major architectural changes.
</objective>

<execution_context>
@.github/agents/gsd-codebase-mapper.agent.md
</execution_context>

<context>
@.github/copilot-instructions.md
@AGENTS.MD
</context>

<process>

<step name="scan">
Hand off to @gsd-codebase-mapper agent.
Agent will create:
1. `.gsd/codebase/STRUCTURE.md` — Directory layout and file purposes
2. `.gsd/codebase/STACK.md` — Technology stack and versions
3. `.gsd/codebase/ARCHITECTURE.md` — Component architecture and data flows
4. `.gsd/codebase/PATTERNS.md` — Code conventions and patterns
5. `.gsd/codebase/INTEGRATIONS.md` — External services (Bybit API, etc.)
6. `.gsd/codebase/CONCERNS.md` — Tech debt and known issues
</step>

</process>

<success_criteria>

- [ ] All 6 codebase analysis files created
- [ ] Architecture accurately reflects actual code
- [ ] Patterns match existing conventions
- [ ] Concerns identified with severity levels
      </success_criteria>
