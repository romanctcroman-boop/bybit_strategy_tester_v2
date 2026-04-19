---
name: session-handoff
description: Ensure smooth context transfer between agent sessions
activation: on-session-end
priority: HIGH
---

# Session Handoff Protocol

## Before Ending Session

### 1. Update Context Summary

```
Location: .agent/memory/CONTEXT.md

Update:
- Recent Work section
- Next Session Hints
- Timestamp
```

### 2. Document Incomplete Work

```
Location: .agent/memory/TODO.md

Format:
## Incomplete Tasks
- [ ] Task description
  - What was done
  - What remains
  - How to continue
```

### 3. Update CHANGELOG

```
Add entry even for partial work:
## [YYYY-MM-DD] - Work in Progress
### In Progress
- What was started but not finished
```

### 4. Leave Clear Notes

If blocked or waiting:

```markdown
## Blocked: [Reason]

**Waiting for**: [external dependency]
**Resume with**: [specific command or action]
```

---

## On Session Start

### 1. Read Context

```
1. .agent/memory/CONTEXT.md
2. .agent/memory/TODO.md (if exists)
3. .agent/docs/CHANGELOG.md
```

### 2. Check Pending Items

```
Grep for:
- "TODO:"
- "FIXME:"
- "In Progress"
- "Blocked:"
```

### 3. Announce Session

```
"Resuming work on [project].
Last session: [summary].
Continuing with: [next task]."
```

---

## Context Persistence Checklist

| Item         | Location          | Updated? |
| ------------ | ----------------- | -------- |
| CONTEXT.md   | .agent/memory/    | □        |
| TODO.md      | .agent/memory/    | □        |
| CHANGELOG.md | .agent/docs/      | □        |
| Current task | artifacts/task.md | □        |
