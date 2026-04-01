---
paths:
  - "backend/api/**/*.py"
  - "tests/backend/api/**"
---

# API / Router Rules

## Критические ловушки

### Direction default — ГЛАВНАЯ ЛОВУШКА
| Модель | Default | Файл |
|--------|---------|------|
| `BacktestCreateRequest` (API) | `"long"` | `models.py:1269` |
| `BacktestConfig` (движок) | `"both"` | `models.py:~100` |
| Strategy Builder API | `"both"` | `routers/strategy_builder.py` |

Вызов `POST /api/backtests/` без `direction` → short-сигналы молча отбрасываются!

### Лимит 730 дней
`BacktestConfig.validate_dates()` бросает `ValueError` если период > 730 дней.

## Паттерны роутеров
```python
from fastapi import APIRouter, HTTPException
from loguru import logger

router = APIRouter(prefix="/api/v1/feature", tags=["Feature"])

@router.post("/action")
async def action(request: RequestModel) -> ResponseModel:
    try:
        return ResponseModel(...)
    except Exception as e:
        logger.error(f"Action failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## Async + SQLite
```python
# ПРАВИЛЬНО — не блокировать event loop
rows = await asyncio.to_thread(db.query(Model).filter(...).all)
```

## Bybit API (всегда проверять retCode)
```python
response = await adapter.get_historical_klines(symbol, interval, start, end)
if response.get('retCode') != 0:
    raise APIError(response.get('retMsg'))
```

## Порядок middleware (НЕ МЕНЯТЬ)
1. RequestIDMiddleware → 2. TimingMiddleware → 3. GZipMiddleware → 4. TrustedHostMiddleware
→ 5. HTTPSRedirectMiddleware (prod) → 6. CORSMiddleware → 7. RateLimitMiddleware
→ 8. CSRFMiddleware → 9. SecurityHeadersMiddleware → 10. ErrorHandlerMiddleware

## Тесты
```bash
pytest tests/backend/api/ -v
pytest tests/e2e/test_strategy_builder_full_flow.py -v
```
