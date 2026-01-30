# Analyze Task Prompt

Use this prompt when starting any non-trivial task.

## Workflow

### 1. Understand

- Rephrase the task in your own words
- Ask clarifying questions if needed
- Identify the scope and boundaries

### 2. Search

Use `@workspace` to find:

- Affected files and modules
- Related patterns in codebase
- Existing implementations to reference

### 3. Map Dependencies

Create dependency graph:

```
Component A
    ↓ uses
Component B
    ↓ imports
Component C
```

### 4. Identify Variables

List all variables that will be touched:

| Variable | Type  | File:Line    | Action |
| -------- | ----- | ------------ | ------ |
| `var1`   | `str` | `file.py:42` | Modify |
| `var2`   | `int` | `file.py:50` | Add    |

### 5. Create Plan

```markdown
## Execution Plan

**Task:** [Task description]
**Files:** [List of files]
**Risk Level:** Low/Medium/High

### Steps

1. Step 1 - [description]
2. Step 2 - [description]
3. Step 3 - [description]

### Validation

- [ ] Tests pass
- [ ] No lint errors
- [ ] Variables verified
```

## STOP for Approval

**Do not proceed with execution until plan is approved.**
