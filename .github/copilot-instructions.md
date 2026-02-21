# Bybit Strategy Tester v2 - Copilot Instructions

> **Last updated:** 2026-02-21  
> **Stack:** Python 3.11-3.14, FastAPI, SQLAlchemy, SQLite, Pandas, NumPy, Bybit API v5  
> **Purpose:** Backtesting system for Bybit trading strategies with TradingView metric parity

---

## 🏗️ Architecture Overview

```
Bybit API (REST + WebSocket)
    ↓
DataService → SQLite (data.sqlite3, bybit_klines_15m.db)
    ↓
Strategy → generate_signals(df) → pd.DataFrame with 'signal' column
    ↓
BacktestEngine → FallbackEngineV4 (gold standard), commission=0.0007
    ↓
MetricsCalculator → 166 TradingView-parity metrics
    ↓
FastAPI → 753 routes at /api/v1/
    ↓
Frontend → Static HTML/JS/CSS at /frontend/
```

### Key Directories

| Path                                    | Purpose                                                         |
| --------------------------------------- | --------------------------------------------------------------- |
| `backend/backtesting/engines/`          | Backtest engines: FallbackV2(deprecated)/V3/V4, GPU, Numba, DCA |
| `backend/api/routers/`                  | 70+ API router files                                            |
| `backend/services/adapters/bybit.py`    | Bybit API integration with rate limiting                        |
| `backend/config/database_policy.py`     | Data retention constants (DATA_START_DATE=2025-01-01)           |
| `frontend/js/pages/strategy_builder.js` | Main UI logic (~3000 lines)                                     |

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

### Strategy Class

```python
from backend.backtesting.strategies.base import BaseStrategy
import pandas_ta as ta

class MyStrategy(BaseStrategy):
    def __init__(self, params: dict):
        super().__init__(params)
        self.required_params = ['period', 'threshold']
        self._validate_params()

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = data.copy()
        # Add 'signal' column: 1=long, -1=short, 0=no action
        return signals
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

## 🔒 CLAUDE.md — Mandatory Context for Risky Changes

> **Full project map:** `CLAUDE.md` in repository root (15 sections, 780+ lines).
> Copilot MUST read relevant sections before modifying core subsystems.

### Before ANY change to these areas, read `CLAUDE.md` sections:

| Area                                               | Sections to read                                                                 |
| -------------------------------------------------- | -------------------------------------------------------------------------------- |
| `BacktestConfig`, engine, `MetricsCalculator`      | §5 (Critical Constants), §7 (Cross-cutting Parameters), §15 (Refactor Checklist) |
| Strategy Builder adapter, strategies               | §3 (Architecture), §6 (Strategy Parameters), §15                                 |
| Optimization, scoring                              | §7 (Key Optimization Metrics, Cross-cutting Parameters), §15                     |
| Risk management, position sizing                   | §7 (Global Parameters, MM Dependencies), §15                                     |
| Frontend (strategy_builder.js, leverageManager.js) | §3 (Direction Defaults), §7 (Cross-cutting Parameters), §15                      |

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
