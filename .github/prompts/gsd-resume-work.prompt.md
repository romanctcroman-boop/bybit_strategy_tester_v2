---
description: "Resume paused GSD work. Reads CONTINUE-HERE.md and picks up exactly where we left off."
tools: ["search/readFile", "edit/editFiles", "search/listDirectory", "search/textSearch", "runCommands/runInTerminal"]
---

<objective>
Resume GSD work from where it was paused. Read CONTINUE-HERE.md and continue.

Use when: Starting a new session and `.gsd/CONTINUE-HERE.md` exists.
</objective>

<context>
@.gsd/CONTINUE-HERE.md
@.gsd/STATE.md
@.gsd/PROJECT.md
</context>

<process>

<step name="read_context">
1. Read CONTINUE-HERE.md for exact state
2. Read STATE.md for position
3. Read relevant phase files
</step>

<step name="resume">
1. Execute the "Next Action" from CONTINUE-HERE.md
2. Delete CONTINUE-HERE.md (it's temporary)
3. Update STATE.md status back to "In progress"
4. Continue with the GSD workflow from where we left off
</step>

</process>

<success_criteria>

- [ ] CONTINUE-HERE.md read and understood
- [ ] Work resumed from exact point
- [ ] CONTINUE-HERE.md deleted
- [ ] STATE.md updated
      </success_criteria>
