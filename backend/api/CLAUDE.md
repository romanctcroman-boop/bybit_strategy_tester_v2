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

---

## Warning codes в API response

The `warnings[]` field in backtest responses may contain:

| Tag                         | Meaning                                                                                      |
| --------------------------- | -------------------------------------------------------------------------------------------- |
| `[DIRECTION_MISMATCH]`      | Direction filter dropped all signals (e.g., `direction="long"` but only short entries exist) |
| `[NO_TRADES]`               | Strategy generated signals but no trades were executed (SL/TP/filters eliminated all)        |
| `[INVALID_OHLC]`            | Bars with invalid OHLC data were removed before backtest                                     |
| `[UNIVERSAL_BAR_MAGNIFIER]` | Bar magnifier initialization failed; falling back to standard mode. STUB — intrabar SL/TP loop does not exist; `use_bar_magnifier=True` silently has no effect. |

## `direction` default — API vs Engine

| Model                         | Default  | File                                      |
| ----------------------------- | -------- | ----------------------------------------- |
| `BacktestConfig` (engine)     | `"both"` | `backend/backtesting/models.py`           |
| `BacktestCreateRequest` (API) | `"long"` | `backend/backtesting/models.py:1269`      |
| Strategy Builder API          | `"both"` | `backend/api/routers/strategy_builder.py` |

**Trap:** `POST /api/backtests/` без `direction` → дефолт `"long"` → short signals silently dropped.

## `market_type`: spot vs linear

| Value                | Data source       | Purpose                                                        |
| -------------------- | ----------------- | -------------------------------------------------------------- |
| `"spot"`             | Bybit spot market | Matches TradingView candles exactly — use for **parity tests** |
| `"linear"` (default) | Perpetual futures | For live trading and real strategy development                 |

---

## Cross-cutting parameters (dependency graph)

These parameters are used in **3+ subsystems**. Changing any of them requires updating every listed location.

| Parameter                              | Subsystems                                                        | Default                     | Risk     |
| -------------------------------------- | ----------------------------------------------------------------- | --------------------------- | -------- |
| `commission_rate` / `commission_value` | Engine, BacktestConfig, Bridges×2, Optimization, MCP, RL env, MLflow, Frontend, Live | 0.0007 | HIGHEST |
| `initial_capital`                      | Engine (30+ refs), MetricsCalculator, Optimization, Frontend tests | 10000.0 | HIGH    |
| `position_size`                        | Engine, API routers×2, Optimization, Optuna, Live trading         | 1.0                         | HIGH     |
| `leverage`                             | Engine, Optimization×2, Frontend (leverageManager), Live trading×3 | 10 (optim/UI) vs 1.0 (live) | MODERATE |
| `pyramiding`                           | Engine, Engine selector, BacktestConfig, Optimization             | 1                           | MODERATE |
| `direction`                            | API (default `"long"`), Engine (default `"both"`), Frontend       | varies!                     | MODERATE |
| `strategy_params`                      | API → Router → Strategy → Engine (all layers)                     | n/a                         | LOW      |

**Ключевые файлы для commission_rate:**
`engine.py`, `models.py:318`, `backtest_bridge.py:50`, `walk_forward_bridge.py:54`,
`optimization/models.py:32+189`, `ml/rl/trading_env.py:58`, `api/routers/agents.py:902`,
`metrics_calculator.py`, `strategy_builder.js:912`, `live_trading.py:263`

### Known inconsistencies (as of 2026-02-21)

1. **commission_rate 0.001 (legacy):** Два оставшихся дефолта 0.001 в `backend/tasks/optimize_tasks.py:309,470` (fallback для отсутствующего ключа — приемлемо) и `backend/ml/ai_backtest_executor.py:170` (ML experimental, не core).
2. **position_size: fraction vs percent** — Engine/Optimization = fraction (0.0–1.0); `live_trading/strategy_runner.py:72` = percent. ADR-006.
3. **leverage default: 10 vs 1.0** — Optimization и Frontend = 10; live trading = 1.0.
4. **pyramiding был hardcoded=1 — FIXED (commit d5d0eb2):** `optimization/utils.py:84` теперь читает из `request_params`.

> **Rule:** Before changing any parameter, run: `grep -rn commission backend/ | grep -v 0.0007 | grep -v .pyc | grep -v __pycache__ | grep -v "0.001.*tolerance\|0.001.*qty\|optimize_tasks\|ai_backtest_executor.*0.001\|_commission.*0.001"`
