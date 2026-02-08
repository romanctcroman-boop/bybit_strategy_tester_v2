---
mode: "agent"
description: "Systematic full-stack debugging from frontend to database"
---

# Full-Stack Debug Protocol

Debug an issue across the entire stack: Frontend → API → Service → Engine → Database.

## Instructions

You are debugging an issue in the Bybit Strategy Tester v2 platform.

### Phase 1: Reproduce & Localize

1. **Identify the symptom** — What exactly fails? (UI error, wrong data, 500 error, etc.)
2. **Determine the layer** — Where does the error originate?
    - Frontend JS console errors → `frontend/js/`
    - API 4xx/5xx → `backend/api/routers/`
    - Service logic errors → `backend/services/`
    - Engine calculation errors → `backend/backtesting/engines/`
    - Data issues → SQLite / `backend/services/data_service.py`

### Phase 2: Trace the Data Flow

```
Frontend (JS fetch) → API Router → Service Layer → Engine/DB → Response → Frontend render
```

3. **Read the relevant API router** to understand the endpoint
4. **Check request validation** — Pydantic schemas in `backend/api/schemas/`
5. **Follow the service call** — What function processes the request?
6. **Check the engine/DB call** — Is data loaded correctly?

### Phase 3: Fix & Verify

7. **Apply the minimal fix** — Change as little as possible
8. **Add a test** for this specific bug
9. **Run the test suite**: `pytest tests/ -v --tb=short`
10. **Verify via API**: Test the endpoint manually

### Variables to Check (always)

- `commission_rate` — Must be `0.0007`
- `DATA_START_DATE` — Must be `2025-01-01`
- `ALL_TIMEFRAMES` — Only 9 valid values
- Signal column — Must be `1`, `-1`, or `0`

### Output Format

```markdown
## Debug Report

**Symptom**: [description]
**Root Cause**: [file:line — explanation]
**Fix Applied**: [description of change]
**Tests Added**: [test name]
**Verification**: [pass/fail]
```
