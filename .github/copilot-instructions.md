# Bybit Strategy Tester v2 - Copilot Instructions

> **Last updated:** 2026-03-28
> **Stack:** Python 3.11-3.14, FastAPI, SQLAlchemy, SQLite, Pandas, NumPy, Bybit API v5
> **Purpose:** Backtesting system for Bybit trading strategies with TradingView metric parity

---

## 🏗️ Architecture Overview

```
Bybit API (REST + WebSocket)
    ↓
DataService → SQLite (data.sqlite3, bybit_klines_15m.db)
    ↓
Strategy.generate_signals(ohlcv) → SignalResult (entries/exits bool Series)
    ↓
BacktestEngine → FallbackEngineV4 (gold standard), commission=0.0007
    ↓
MetricsCalculator → 166 TradingView-parity metrics
    ↓
FastAPI → 753+ routes at /api/v1/
    ↓
Frontend → Static HTML/JS/CSS at /frontend/
```

### Key Directories

| Path                                            | Purpose                                          |
| ----------------------------------------------- | ------------------------------------------------ |
| `backend/backtesting/engines/fallback_engine_v4.py` | Gold standard engine (3204 lines)            |
| `backend/backtesting/strategies.py`             | ALL strategies + BaseStrategy + SignalResult     |
| `backend/core/metrics_calculator.py`            | 166 TV-parity metrics                            |
| `backend/api/routers/`                          | 70+ API router files                             |
| `backend/services/adapters/bybit.py`            | Bybit API integration (1710 lines)               |
| `backend/config/constants.py`                   | COMMISSION_TV, ALL_TIMEFRAMES, DEFAULT_CAPITAL   |
| `backend/config/database_policy.py`             | DATA_START_DATE=2025-01-01                       |
| `frontend/js/pages/strategy_builder.js`         | Main UI logic (13378 lines)                      |

---

## ⚠️ Critical Rules (NEVER VIOLATE)

### 1. Commission Rate = 0.0007 (0.07%)

```python
# NEVER change without explicit approval - breaks TradingView parity
commission_rate = 0.0007  # Must match TradingView for metric validation
```

### 2. Use FallbackEngineV4 as Gold Standard

```python
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngine
# V2 is deprecated but kept for parity tests - do not use for new code
```

### 3. Data Retention Policy

```python
# From backend/config/database_policy.py - import from here, don't hardcode
DATA_START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)
RETENTION_YEARS = 2
# No data before 2025-01-01 is stored
```

### 4. Supported Timeframes (ONLY these 9)

```python
ALL_TIMEFRAMES = ["1", "5", "15", "30", "60", "240", "D", "W", "M"]
# Legacy TF mapping on load: 3→5, 120→60, 360→240, 720→D
```

### 5. High-Risk Variables (NEVER DELETE without tracking all usages)

- `commission_rate` (10+ files) - TradingView parity
- `strategy_params` (all strategies, optimizer, UI)
- `initial_capital` (engine, metrics, UI)

---

## 🔧 Development Commands

```powershell
# Start server (pick one)
.\dev.ps1 run                        # Recommended
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000  # Direct

# Tests
pytest tests/ -v                     # All tests
pytest tests/ -v -m "not slow"       # Fast tests only
pytest tests/ --cov=backend          # With coverage (80% minimum)

# Linting (ALWAYS run before commit)
ruff check . --fix
ruff format .
```

### Database

- **SQLite** at `data.sqlite3` (main) and `bybit_klines_15m.db` (klines)
- **Do NOT set DATABASE_URL** for local dev - uses SQLite by default
- Migrations: `alembic upgrade head`

### Key URLs

| URL                                                  | Description                   |
| ---------------------------------------------------- | ----------------------------- |
| http://localhost:8000/frontend/strategy-builder.html | Strategy Builder UI           |
| http://localhost:8000/frontend/dashboard.html        | Dashboard                     |
| http://localhost:8000/docs                           | Swagger API docs (753 routes) |
| http://localhost:8000/api/v1/health                  | Health check                  |

---

## 📝 Code Patterns

### Strategy Class (CORRECT API — returns SignalResult, NOT DataFrame)

```python
# ALL strategies are in backend/backtesting/strategies.py (single file)
from backend.backtesting.strategies import BaseStrategy, SignalResult
import pandas as pd
import pandas_ta as ta
from typing import Any

class MyStrategy(BaseStrategy):
    name: str = "my_strategy"
    description: str = "Brief description"

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)  # calls _validate_params() internally

    def _validate_params(self) -> None:
        if 'period' not in self.params:
            raise ValueError("Missing required param: period")

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        rsi = ta.rsi(ohlcv['close'], length=self.params['period'])
        return SignalResult(
            entries=(rsi < 30).fillna(False),
            exits=(rsi > 70).fillna(False),
            short_entries=(rsi > 70).fillna(False),
            short_exits=(rsi < 30).fillna(False),
        )

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {'period': 14}

# Register in STRATEGY_REGISTRY dict (near end of strategies.py):
# STRATEGY_REGISTRY["my_strategy"] = MyStrategy
```

### FastAPI Endpoint

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

### Bybit API (ALWAYS check retCode)

```python
response = await adapter.get_historical_klines(symbol, interval, start, end)
if response.get('retCode') != 0:
    raise APIError(response.get('retMsg'))
# Rate limit: 120 req/min - use exponential backoff on 429
```

### Async DB Operations (for routers)

```python
# Use thread pool for blocking SQLite operations in async context
rows = await asyncio.to_thread(db.query(Model).filter(...).all)
```

---

## 🧪 Testing

- **Coverage:** 80% overall, 95% for `backend/backtesting/engines/`
- **Naming:** `test_[function]_[scenario]` (e.g., `test_rsi_with_valid_data`)
- **Mock Bybit:** Never call real API in unit tests
- **Fixtures:** Use `conftest.py` for `sample_ohlcv`, `mock_adapter`

---

## 🚫 VS Code Errors to IGNORE

False positives from extensions (NOT real errors):

- `$ref '/contributes...pgsql...' can not be resolved`
- `Matches multiple schemas when only one must validate`
- Any `vscode://schemas` resolution errors

---

## ✅ Pre-Commit Checklist

1. `pytest tests/ -v` — all pass
2. `ruff check .` — no errors
3. `ruff format .` — formatted
4. No hardcoded paths (`d:\...`) or secrets in code
5. Update `CHANGELOG.md` for notable changes

---

## 📚 Key Documentation

| File                        | Purpose                                                |
| --------------------------- | ------------------------------------------------------ |
| `docs/DECISIONS.md`         | Architecture decision records (ADR)                    |
| `docs/architecture/`        | Component docs (ENGINE_PARITY, STRATEGY_BUILDER, etc.) |
| `CHANGELOG.md`              | Detailed change history                                |
| `AGENTS.MD`                 | Full agent autonomy rules + **VS Code Agent Mode**     |
| `.github/instructions/*.md` | Path-specific rules (apply automatically)              |

---

## 🤖 Agent Mode (VS Code)

For maximum autonomy, add to VS Code `settings.json`:

```json
{
    "github.copilot.chat.agent.enabled": true,
    "chat.agent.maxRequests": 25,
    "chat.agent.runTasks": true
}
```

See `AGENTS.MD` section "VS Code Agent Mode Configuration" for full details.

---

## 🔒 CLAUDE_CODE.md — Mandatory Context for Risky Changes

> **Full project map:** `CLAUDE_CODE.md` in repository root (31 sections, 2279 lines, 100% coverage).
> Copilot MUST read relevant sections before modifying core subsystems.

### Before ANY change to these areas, read `CLAUDE_CODE.md` sections:

| Area                                               | Sections to read                                          |
| -------------------------------------------------- | --------------------------------------------------------- |
| `BacktestConfig`, engine, `MetricsCalculator`      | §5 (Cross-cutting vars), §13 (Engines), §14 (Metrics)     |
| Strategy Builder adapter, strategies               | §6 (Builder blocks), §10 (Data transform pipeline)        |
| Optimization, scoring                              | §28 (Optimization deep dive)                              |
| Risk management, position sizing                   | §20 (Risk Management)                                     |
| Live trading                                       | §19 (Live Trading subsystem)                              |
| Frontend (strategy_builder.js, leverageManager.js) | §29 (Frontend Architecture)                               |
| AI agent system                                    | §15, §21-§25, §30 (Memory, Consensus, Security, Services) |

### High-risk parameters — NEVER change without explicit plan

These parameters are used in **3+ subsystems** (see `CLAUDE.md` §7 "Cross-cutting parameters" table):

- `commission_value` / `commission_rate` (0.0007) — 12+ files, TradingView parity
- `initial_capital` — engine, metrics, optimization, frontend
- `position_size` — engine, routers, optimization, live trading (⚠️ unit mismatch: fraction vs percent)
- `leverage` — engine, optimization, frontend, live trading (⚠️ default mismatch: 10 vs 1.0)
- `pyramiding` — engine, engine_selector, optimization (⚠️ hardcoded to 1 in optimizer)
- `direction` — API, engine, frontend (⚠️ default mismatch: "long" vs "both")
- `strategy_params` — passes through all layers

**Rule:** Before changing any parameter above → `grep -rn <param> backend/ frontend/` and update ALL locations.

### Commission parity check (run before any commit touching commission)

```bash
grep -rn commission backend/ | grep -v 0.0007 | grep -v .pyc | grep -v __pycache__
```
