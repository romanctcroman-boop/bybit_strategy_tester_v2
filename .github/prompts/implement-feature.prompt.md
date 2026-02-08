---
mode: "agent"
description: "Implement a new feature end-to-end with tests and docs"
---

# Implement Feature Prompt

Implement a new feature from specification to deployment-ready code.

## Instructions

### Phase 1: Understand & Plan

1. **Restate** the feature in your own words
2. **Identify affected layers**:
    - [ ] Database models (`backend/models/`)
    - [ ] API schemas (`backend/api/schemas/`)
    - [ ] API routers (`backend/api/routers/`)
    - [ ] Services (`backend/services/`)
    - [ ] Backtesting engine (`backend/backtesting/`)
    - [ ] Strategies (`backend/strategies/`)
    - [ ] Frontend (`frontend/js/`)
    - [ ] Tests (`tests/`)
3. **Map dependencies** — What existing code will be affected?
4. **Check for conflicts** — Does this break existing behavior?

### Phase 2: Implement (Bottom-Up)

5. **Models first** — Create/update database models
6. **Services** — Implement business logic
7. **API** — Create endpoints with proper validation
8. **Frontend** — Update UI if needed
9. **Tests** — Write tests for each layer

### Phase 3: Verify

10. **Run full test suite**: `pytest tests/ -v`
11. **Lint**: `ruff check . --fix && ruff format .`
12. **Manual test** via API/UI
13. **Update docs**: CHANGELOG.md, API.md if needed

### Implementation Checklist

```markdown
- [ ] Feature code implemented
- [ ] Input validation added (Pydantic)
- [ ] Error handling with proper HTTP codes
- [ ] Logging with loguru
- [ ] Unit tests (>90% coverage for new code)
- [ ] Integration test
- [ ] Documentation updated
- [ ] No hardcoded values
- [ ] commission_rate still 0.0007
- [ ] All existing tests still pass
```

### Code Style Requirements

```python
# Use type hints everywhere
async def create_backtest(request: BacktestRequest) -> BacktestResponse:

# Use loguru for logging
from loguru import logger
logger.info(f"Starting backtest for {symbol}")

# Use proper error handling
try:
    result = await service.process(request)
except ValidationError as e:
    raise HTTPException(status_code=422, detail=str(e))
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise HTTPException(status_code=500, detail="Internal server error")
```
