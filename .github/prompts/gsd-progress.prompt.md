---
description: "Show current GSD project progress: phase, plan, completion percentage, recent activity."
tools: ["search/readFile", "search/listDirectory"]
---

<objective>
Display current project progress from GSD state files.

Use when: Want to know where we are in the project, what's done, what's next.
</objective>

<context>
@.gsd/STATE.md
@.gsd/ROADMAP.md
@.gsd/PROJECT.md
</context>

<process>

<step name="read_state">
1. Read STATE.md for current position
2. Read ROADMAP.md for full scope
3. Count completed vs total phases/plans
</step>

<step name="format_report">
Output:

```
📊 GSD Progress Report
═══════════════════════

📌 Project: [Name from PROJECT.md]
🎯 Core Value: [One-liner]

📍 Current Position:
   Phase [X] of [Y]: [Phase Name]
   Plan [A] of [B] in current phase
   Status: [Status]

📈 Overall Progress: [░░░░░░████] XX%

📋 Phase Breakdown:
   ✅ Phase 1: [Name] — Complete
   🔄 Phase 2: [Name] — In Progress (Plan 2/3)
   ⬜ Phase 3: [Name] — Not Started
   ⬜ Phase 4: [Name] — Not Started

🕐 Last Activity: [Date] — [Description]
⏭️ Next Action: [What to do next]
```

</step>

</process>

<success_criteria>

- [ ] Progress displayed with completion percentage
- [ ] Current position clear
- [ ] Next action identified
      </success_criteria>
