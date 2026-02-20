Perform a code review of recent changes or specified files in Bybit Strategy Tester v2.

Usage: /review [file or description]

Example: /review   (reviews git diff HEAD)
Example: /review backend/backtesting/engine.py

Steps:
1. If no file specified, look at recently modified files (from git status context)
2. Read the target file(s)
3. Apply the full review checklist:

**Critical domain rules (any violation = FAIL):**
- commission_rate must be 0.0007
- FallbackEngineV4 used for new backtest code (not V2/V3)
- DATA_START_DATE imported from backend/config/database_policy.py
- Timeframes restricted to ["1","5","15","30","60","240","D","W","M"]
- Port aliases preserved: long↔bullish, short↔bearish, output↔value, result↔signal

**Code quality:**
- No Python loops where vectorized NumPy/Pandas operations would work
- async functions don't do blocking I/O without asyncio.to_thread()
- loguru logger used (not print)
- Type hints on new/changed functions
- No hardcoded secrets or absolute Windows paths

**Security:**
- No SQL injection (ORM only, no string-formatted queries)
- No command injection (no subprocess with user-controlled input)
- Bybit API responses check retCode before use

**Testing:**
- New logic has test coverage
- No real API calls in tests

**Housekeeping:**
- CHANGELOG.md updated for any notable change
- No debug print/console.log left in

Output the review in this format:
```
## Review: [files]
### ❌ Critical Issues  /  ⚠️ Warnings  /  ✅ Looks Good
[findings]
### Verdict: APPROVE / REQUEST CHANGES
```
