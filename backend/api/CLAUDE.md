# backend/api/ — Контекст модуля

## Структура
```
api/
  app.py              — FastAPI app factory, монтирует все роутеры
  lifespan.py         — startup/shutdown (DB, Redis, warmup)
  schemas.py          — Shared Pydantic schemas
  routers/            — 55+ FastAPI route handlers
    backtests.py      — POST/GET /api/backtests/ — ГЛАВНЫЙ роутер
    strategy_builder/ — POST /api/strategy-builder/run
    optimizations.py  — POST /api/optimizations/
    marketdata.py     — GET /api/marketdata/ohlcv
    agents.py         — AI agents
```

## Главные эндпоинты
| Эндпоинт | Роутер | Действие |
|----------|--------|---------|
| `POST /api/backtests/` | `backtests.py` | Одиночный бэктест |
| `POST /api/strategy-builder/run` | `strategy_builder/router.py` | Builder-стратегия |
| `POST /api/optimizations/` | `optimizations.py` | Запуск оптимизации |
| `GET /api/marketdata/ohlcv` | `marketdata.py` | OHLCV данные |

## Критические ловушки

### Direction default (ГЛАВНАЯ ЛОВУШКА)
```python
# BacktestCreateRequest (API): default = "long"
# BacktestConfig (движок): default = "both"
# Strategy Builder API: default = "both"
# → POST /api/backtests/ без direction → ТОЛЬКО long сигналы!
```

### Роутеры должны быть тонкими
- Логика в сервисах/движке, не в роутере
- Async: все роутеры `async def`
- SQLite blocking → `asyncio.to_thread()`

### Паттерн роутера
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

### Bybit API responses
```python
response = await adapter.get_historical_klines(...)
if response.get('retCode') != 0:
    raise APIError(response.get('retMsg'))
```

## Response format (backtests)
```json
{
  "metrics": {...},
  "trades": [...],
  "warnings": ["[DIRECTION_MISMATCH] ...", "[NO_TRADES] ..."]
}
```

## Безопасность
- ORM only — никаких raw string queries (SQL injection)
- Нет subprocess с user input (command injection)
- Rate limiting: 120 req/min для Bybit API, backoff на 429

## Тесты
```bash
pytest tests/backend/api/ -v
pytest tests/backend/api/test_backtests.py -v
```
