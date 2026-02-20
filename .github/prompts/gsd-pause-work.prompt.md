---
description: "Save current work context for later resumption. Creates CONTINUE-HERE.md with exact state."
tools: ["search/readFile", "edit/editFiles", "edit/createFile"]
---

<objective>
Pause current GSD work and save complete context for seamless resumption.
Creates `.gsd/CONTINUE-HERE.md` that lets any fresh session pick up exactly where we left off.

Use when: Ending a work session, switching to another task, or before a long break.
</objective>

<context>
@.gsd/STATE.md
</context>

<process>

<step name="capture_state">
Create `.gsd/CONTINUE-HERE.md`:

```markdown
---
phase: [current phase]
task: [current task number]
total_tasks: [how many in phase]
status: in_progress | blocked | almost_done
last_updated: [ISO timestamp]
---

## What's Done

[Completed tasks and their outcomes]

## What's In Progress

[Current task, what's been done so far, what remains]

## Decisions Made

[Key decisions and WHY — so next session doesn't re-debate]

## Blockers

[Anything stuck or waiting on external factors]

## Context

[Mental state, what were you thinking about, what was the plan]

## Next Action

Start with: [specific first action when resuming]
```

</step>

<step name="update_state">
Update STATE.md status to "Paused"
</step>

</process>

<success_criteria>

- [ ] CONTINUE-HERE.md exists with actionable resume instructions
- [ ] STATE.md updated
- [ ] Next action is specific enough for a fresh session
      </success_criteria>
