---
name: enhanced-autonomy
description: Enhanced autonomy rules for proactive agent operation
activation: always
priority: HIGH
---

# Enhanced Autonomy Rules

## Proactive Task Execution

### Auto-Fix Common Issues

You are ENCOURAGED to automatically fix:

1. **Linting Errors**
   - Run `ruff check --fix .` automatically
   - Fix formatting issues with `black .`
   - Organize imports with `isort .`
   - Fix type hints with `mypy .`

2. **Test Failures**
   - Run tests after code changes
   - Fix failing tests automatically
   - Add missing test cases if obvious

3. **Import Errors**
   - Fix broken imports
   - Add missing imports
   - Remove unused imports

4. **Syntax Errors**
   - Fix obvious syntax mistakes
   - Correct indentation
   - Fix typos in code

5. **Documentation**
   - Update CHANGELOG.md after completing tasks
   - Add missing docstrings
   - Update outdated comments

## Autonomous Refactoring

### Safe Refactoring (Auto-Execute)

- Extract repeated code into functions/classes
- Rename variables/functions for clarity (non-public)
- Remove dead code and unused imports
- Simplify complex conditionals
- Break down large functions (>50 lines)
- Apply DRY (Don't Repeat Yourself) principle
- Improve variable names for readability

### Refactoring Workflow

```python
# Before refactoring:
1. Run tests to ensure baseline
2. Make refactoring changes
3. Run tests again to verify
4. Update documentation if needed
5. Commit with descriptive message
```

## Autonomous Bug Fixing

### Auto-Fix When:

- Error message clearly indicates the issue
- Fix is straightforward and low-risk
- Tests exist to verify the fix
- Change is isolated and doesn't affect other systems

### Bug Fix Workflow

```python
# 1. Reproduce the bug
# 2. Identify root cause
# 3. Implement fix
# 4. Add/update tests
# 5. Verify fix works
# 6. Document in CHANGELOG.md
```

## Proactive Improvements

### Code Quality Improvements

Automatically improve code when you notice:

- Performance bottlenecks (with profiling)
- Security vulnerabilities (low-risk fixes)
- Code smells (long functions, magic numbers)
- Missing error handling
- Inconsistent patterns
- Missing type hints

### Improvement Workflow

```markdown
1. Identify improvement opportunity
2. Assess risk (Low/Medium/High)
3. If Low risk → implement immediately
4. If Medium/High → document and ask
5. Test changes
6. Document in CHANGELOG.md
```

## Autonomous Testing

### Auto-Execute Testing

- Run relevant tests after code changes
- Add tests for new functionality
- Fix broken tests
- Generate coverage reports
- Run integration tests for affected areas

### Test-Driven Development

When implementing new features:

1. Write tests first (if TDD approach)
2. Implement feature
3. Ensure all tests pass
4. Refactor if needed
5. Document test coverage

## Documentation Autonomy

### Auto-Update Documentation

- CHANGELOG.md after every task
- Docstrings for new functions/classes
- README.md if structure changes
- ARCHITECTURE.md for structural changes
- DECISIONS.md for important choices
- API.md for endpoint changes

### Documentation Standards

```python
def function_name(param: Type) -> ReturnType:
    """
    Brief description.

    Extended explanation if needed.

    Args:
        param: Description

    Returns:
        Description

    Raises:
        ExceptionType: When this happens

    Example:
        >>> function_name(value)
        expected_result
    """
```

## Code Review & Quality Checks

### Automatic Quality Checks

Before completing any task:

1. ✅ Run linters (`ruff check .`)
2. ✅ Run type checker (`mypy .`)
3. ✅ Run formatters (`black .`, `isort .`)
4. ✅ Run tests (`pytest tests/ -v`)
5. ✅ Check for security issues (basic)
6. ✅ Verify no hardcoded secrets
7. ✅ Ensure proper error handling

## Branch Management

### Autonomous Branch Operations

- Create feature branches: `git checkout -b feature/name`
- Create fix branches: `git checkout -b fix/issue-name`
- Create refactor branches: `git checkout -b refactor/component`
- Merge feature branches to main (after tests pass)
- Delete merged branches: `git branch -d branch-name`

### Branch Naming Convention

- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `test/` - Test additions/changes
- `chore/` - Maintenance tasks

## Error Recovery

### Autonomous Error Handling

When encountering errors:

1. **Read error message carefully**
2. **Check if it's a known issue** (DECISIONS.md, CHANGELOG.md)
3. **Try obvious fixes first**
4. **Search codebase for similar patterns**
5. **Fix and test**
6. **Document if significant**

### Error Recovery Limits

- Maximum 3 self-fix attempts
- After 3 attempts, report to user with:
  - What failed
  - What was tried
  - Suggested solutions
  - Request for guidance

## Performance Optimization

### Autonomous Profiling

When performance is mentioned or suspected:

1. Profile the code (`cProfile`, `memory_profiler`)
2. Identify bottlenecks
3. Implement optimizations
4. Re-profile to verify improvement
5. Document results

### Optimization Rights

- Cache expensive computations
- Optimize database queries
- Reduce memory allocations
- Improve algorithm complexity
- Parallelize where appropriate

## Security Improvements

### Autonomous Security Fixes

Fix low-risk security issues automatically:

- Missing input validation
- Exposed debug endpoints (remove or protect)
- Hardcoded paths (use config)
- Missing error handling
- Insecure default values

### Security Audit Rights

- Review authentication flows
- Check for SQL injection risks
- Validate input sanitization
- Audit dependency vulnerabilities
- Check for exposed secrets

## Context Preservation

### Always Leave Context

After completing work:

1. Update CHANGELOG.md with what was done
2. Add comments for complex logic
3. Document decisions in DECISIONS.md if significant
4. Update relevant documentation
5. Leave clear commit messages

### Context for Next Session

```markdown
## What Was Done
- List of changes

## Why It Was Done
- Reasoning behind decisions

## What Remains
- Follow-up tasks if any

## Notes
- Important context or gotchas
```

## Decision Making Framework

### When to Act Autonomously

✅ **Proceed** if:
- Task is clear and well-defined
- Risk is low
- Reversible or testable
- Follows existing patterns
- Has tests to verify

⚠️ **Ask** if:
- Multiple valid approaches exist
- Risk is medium/high
- Irreversible action
- Security implications
- Architecture changes

🚫 **Stop** if:
- Missing critical information
- Conflicting requirements
- Security concerns
- Out of scope
- Requires user input

---

_Last Updated: 2026-01-27_
_Version: 2.0_
