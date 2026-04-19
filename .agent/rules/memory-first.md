---
name: memory-first
description: Always check memory and existing knowledge before starting new work
activation: always
priority: CRITICAL
---

# Memory-First Rule

## Mandatory First Steps

Before starting ANY work:

### 1. Check Knowledge Items

```
IF request involves known topic THEN
  → Read relevant KI artifacts
  → Build upon existing knowledge
  → Don't reinvent the wheel
```

### 2. Check Local Documentation

```
Read in order:
1. .agent/docs/ARCHITECTURE.md → System overview
2. .agent/docs/DECISIONS.md → Design rationale
3. .agent/docs/CHANGELOG.md → Recent changes
```

### 3. Check Skills

```
IF request matches existing skill THEN
  → Use the skill
  → Don't implement from scratch
```

## Memory Persistence

After completing work:

### 1. Update Documentation

- Add CHANGELOG entry
- Update ARCHITECTURE if structural change
- Add DECISIONS entry if design choice

### 2. Consider KI Creation

If discovery is significant and reusable:

- Suggest creating new Knowledge Item
- Include artifacts with implementation details

### 3. Leave Context

Document enough for next session to understand:

- What was done
- Why it was done
- What remains to do
