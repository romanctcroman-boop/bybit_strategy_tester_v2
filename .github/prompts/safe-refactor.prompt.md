# Safe Refactor Prompt

Use this prompt for any code refactoring to prevent variable/functionality loss.

## Pre-Refactor Checklist

### 1. Variable Inventory

Before ANY changes, search and document:

```
@workspace "function_name"
@workspace "variable_name"
```

Fill tracker:

| Variable | Type  | Location     | Usages | Status |
| -------- | ----- | ------------ | ------ | ------ |
| `var1`   | `str` | `file.py:42` | 5      | ✅     |

### 2. Test Baseline

Run tests before changes:

```bash
pytest tests/ -v --tb=short
```

Record: `X passed, Y failed`

### 3. Create Backup Point

Mental note of git state:

```bash
git status
git log -1 --oneline
```

## During Refactor

### Rules

- Change ONE thing at a time
- Run tests after each change
- Keep variables in scope
- Update imports immediately

### Pattern: Rename Variable

```python
# 1. Find all usages first
# 2. Update definition
# 3. Update ALL usages in same commit
# 4. Run tests
```

### Pattern: Extract Function

```python
# 1. Identify code block
# 2. List all variables used
# 3. Create function with parameters
# 4. Replace original with call
# 5. Verify all variables passed
# 6. Run tests
```

### Pattern: Move Code

```python
# 1. Copy to new location
# 2. Update imports in new location
# 3. Verify functionality works
# 4. Remove from old location
# 5. Update all import statements
# 6. Run tests
```

## Post-Refactor Validation

### 1. Variable Check

Verify all tracked variables still exist:

```
@workspace "variable_name"
```

### 2. Test Suite

```bash
pytest tests/ -v
```

Must match or improve baseline.

### 3. Lint Check

```bash
ruff check .
```

No new errors.

### 4. Functionality Test

Manual verification if applicable.
