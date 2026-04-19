---
name: innovation-mode
description: Enable proactive improvements, experimentation, and autonomous innovation
activation: always
priority: HIGH
---

# Innovation Mode Rules

## Proactive Analysis

### When Starting New Work

1. Scan related code for improvement opportunities
2. Check for deprecated patterns
3. Identify performance bottlenecks
4. Note security concerns

### Report Improvements

```markdown
## Improvement Opportunity

**Location**: path/to/file.py
**Issue**: Description of the problem
**Suggestion**: Proposed improvement
**Impact**: Expected benefit (performance, security, maintainability)
**Effort**: Low/Medium/High
```

---

## Experimentation Rights

### You Are Permitted To:

- Create experimental branches without asking
- Run performance benchmarks
- Prototype alternative implementations
- Test new libraries in isolation
- Profile code paths

### Experimental Workflow

```bash
# 1. Create branch
git checkout -b experiment/feature-name

# 2. Implement
# ... code changes ...

# 3. Benchmark
py -3.14 -m cProfile -s cumtime script.py

# 4. Test
pytest tests/ -v

# 5. Document
# Save to .agent/experiments/

# 6. Report or rollback
git checkout main  # if failed
# or propose merge if successful
```

---

## Documentation of Experiments

### Experiment Report Template

```markdown
# Experiment: [Name]

**Date**: YYYY-MM-DD
**Branch**: experiment/name
**Status**: In Progress | Successful | Failed

## Hypothesis

What we expected to achieve.

## Implementation

What was changed and how.

## Results

Actual outcomes with data.

## Conclusion

What we learned and next steps.

## Artifacts

- Benchmarks: [link]
- Code: [branch]
- Tests: [results]
```

---

## Performance Optimization Rights

### Auto-Execute Profiling

```python
# cProfile for CPU
py -3.14 -m cProfile -s cumtime script.py > .agent/reports/profile.txt

# memory_profiler for memory
py -3.14 -m memory_profiler script.py

# line_profiler for line-by-line
kernprof -l -v script.py
```

### Optimization Workflow

1. Profile current implementation
2. Identify top 3 bottlenecks
3. Research optimization approaches
4. Implement improvements
5. Re-profile and compare
6. Document results

---

## Security Auditing Rights

### Autonomous Security Checks

- Review authentication flows
- Check for SQL injection
- Validate input sanitization
- Audit dependency vulnerabilities

### Report Security Issues

```markdown
## Security Finding

**Severity**: Critical | High | Medium | Low
**Location**: path/to/file.py:line
**Issue**: Description
**Risk**: What could happen
**Fix**: Recommended solution
**Verified**: How it was tested
```

---

## Library & Framework Upgrades

### Propose Upgrades When

- Security vulnerability in current version
- Significant performance improvement available
- Deprecated API usage detected
- Better alternative exists

### Upgrade Proposal Format

```markdown
## Upgrade Proposal: [library]

**Current Version**: x.y.z
**Proposed Version**: a.b.c

### Benefits

- List of improvements

### Breaking Changes

- What needs to change

### Migration Steps

1. Step by step guide

### Risk Assessment

Low/Medium/High with justification
```

---

## Refactoring Rights

### Autonomous Refactoring Allowed For

- Extract method/class
- Rename for clarity
- Remove dead code
- Simplify conditionals
- Apply DRY principle

### Require Confirmation For

- Architecture changes
- Public API changes
- Database schema changes
- Breaking interface changes

---

## Innovation Artifacts

### Output Locations

- `.agent/experiments/` - Experiment reports
- `.agent/reports/` - Performance reports
- `.agent/docs/IMPROVEMENTS.md` - Improvement log
