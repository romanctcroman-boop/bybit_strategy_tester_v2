---
mode: "agent"
description: "Thorough code review with security, performance, and quality checks"
---

# Code Review Prompt

Review code changes for quality, security, performance, and correctness.

## Instructions

### Review Checklist

#### 1. Correctness

- [ ] Logic is correct for all edge cases
- [ ] Error handling covers failure modes
- [ ] Return types match declared types
- [ ] No off-by-one errors
- [ ] Null/None/empty checks present

#### 2. Security

- [ ] No hardcoded secrets or API keys
- [ ] User input is validated and sanitized
- [ ] SQL queries use parameterized statements
- [ ] No path traversal vulnerabilities
- [ ] No exposed debug endpoints in production

#### 3. Performance

- [ ] No unnecessary loops over DataFrames (use vectorized ops)
- [ ] No N+1 database queries
- [ ] No memory leaks (unclosed resources)
- [ ] Caching used where appropriate
- [ ] No blocking I/O in async context

#### 4. Code Quality

- [ ] Functions are < 50 lines
- [ ] Classes have single responsibility
- [ ] Variable names are descriptive
- [ ] No magic numbers (use constants)
- [ ] DRY — no duplicated logic
- [ ] Type hints on all function signatures

#### 5. Project-Specific

- [ ] commission_rate = 0.0007 (unchanged)
- [ ] Uses FallbackEngineV4 (not deprecated V2)
- [ ] DATA_START_DATE imported from database_policy.py
- [ ] Timeframes from ALL_TIMEFRAMES only
- [ ] Async DB operations use asyncio.to_thread()

#### 6. Testing

- [ ] Tests exist for new/changed code
- [ ] Tests cover happy path + edge cases
- [ ] No real API calls in tests
- [ ] Tests use conftest.py fixtures

### Output Format

```markdown
## Code Review Summary

**Files Reviewed**: [list]
**Verdict**: ✅ Approve / ⚠️ Approve with comments / ❌ Request changes

### Issues Found

| #   | Severity | File:Line  | Issue | Suggestion |
| --- | -------- | ---------- | ----- | ---------- |
| 1   | 🔴 High  | file.py:42 | ...   | ...        |
| 2   | 🟡 Med   | file.py:88 | ...   | ...        |
| 3   | 🟢 Low   | file.py:15 | ...   | ...        |

### Positive Observations

- [Good patterns observed]
```
