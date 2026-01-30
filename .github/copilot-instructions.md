# Bybit Strategy Tester v2 - Copilot Instructions

> **Auto-generated from .ai/rules/ on 2026-01-30 17:38**
> Edit source files in .ai/rules/, then run `python scripts/sync-ai-rules.py`

# Core Principles

> These rules apply to ALL AI interactions in this workspace.

## Project Overview

- **Project:** Bybit Strategy Tester v2
- **Stack:** Python 3.14+, FastAPI, SQLAlchemy, Pandas, NumPy, Bybit API v5
- **Purpose:** Backtesting system for Bybit trading strategies with TradingView parity

## Core Workflow: ANALYZE → PLAN → APPROVE → EXECUTE → VALIDATE

### ANALYZE Phase

For ANY non-trivial task:

1. **Understand:** Rephrase task, ask clarifying questions
2. **Search:** Find affected files and similar patterns in codebase
3. **Map:** Build dependency graph of affected components
4. **Identify:** List all variables that will be touched

### PLAN Phase

Create detailed execution plan:

```markdown
## Task: [name]

**Files affected:** [list with full paths]
**Variables tracked:** [name, type, file:line]
**Dependencies:** [component → dependencies]
**Execution order:** [step-by-step]
**Validation:** [how to verify success]
```

**STOP and REQUEST APPROVAL before proceeding**

### VALIDATE Phase

After changes:

- Run: `pytest tests/` (all tests must pass)
- Check: `ruff check .` (no lint errors)
- Verify: All tracked variables still exist
- Test: Manual verification if needed

## Autonomy Guidelines

### Auto-Execute (Safe)

- File reads, directory listings
- `git status`, `git log`, `git diff`
- `pytest`, `ruff check`, `ruff format`
- Creating/editing code files

### Ask Before

- `git push` (especially to main)
- Database migrations
- Installing new dependencies
- Modifying security-critical code

### Never Auto-Execute

- Destructive database operations
- Commands with sudo/admin
- External API calls without explicit permission

---

# Variable Tracking Rules

## Variable Safety - CRITICAL

Before modifying ANY code:

1. **Search first:** Find ALL usages of variables you'll touch
2. **Track in plan:** Document every variable (name, type, file:line)
3. **After changes:** Verify no variables lost
4. **Update imports:** Immediately after any refactoring

## Variable Tracking Format

```markdown
| Variable        | File                  | Line | Type  | Status      | Notes       |
| --------------- | --------------------- | ---- | ----- | ----------- | ----------- |
| strategy_params | engine.py             | 45   | Dict  | ✅ Active   | Core config |
| commission_rate | fallback_engine_v2.py | 50   | float | ⚠️ CRITICAL | 0.0007      |
```

## High-Risk Variables (NEVER DELETE)

These are used in 10+ files. Extra caution required:

### `commission_rate`

- **Value:** 0.0007 (0.07%)
- **Location:** `backend/backtesting/engines/fallback_engine_v2.py`
- **Impact:** ALL backtest results, TradingView parity
- **Rule:** NEVER change without approval

### `strategy_params`

- **Type:** Dict[str, Any]
- **Location:** `backend/backtesting/engine.py`
- **Impact:** All strategy classes, optimizer, UI
- **Rule:** Update ALL strategy classes when modified

### `initial_capital`

- **Type:** float
- **Default:** 10000.0
- **Location:** `backend/backtesting/engine.py`
- **Impact:** Engine, metrics calculator, UI

## Naming Conventions

```python
# Strategy Parameters: [indicator]_[param_type]
rsi_period: int = 14
ema_fast: int = 12

# Configuration: [component]_[setting]
backtest_initial_capital: float
api_rate_limit: int

# Data Containers: [content]_[container_type]
trade_log: List[Trade]
signal_series: pd.Series
results_df: pd.DataFrame
```

---

# TradingView Parity Rules

## CRITICAL: Commission Rate

```python
# Commission MUST be 0.07% for TradingView parity
commission_rate = 0.0007  # 0.07%

# Use FallbackEngineV2 as gold standard
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
```

## Indicator Parity

- Preserve EXACT indicator behavior (periods, multipliers)
- Match TradingView output (compare first 100 values)
- Document conversions:

```python
# Pine: ta.rsi(close, 14) → Python: ta.rsi(df['close'], length=14)
# Pine: ta.ema(close, 12) → Python: ta.ema(df['close'], length=12)
```

## Backtester Data Flow

```
DataService (loads OHLCV from SQLite/Bybit)
    ↓
Strategy (generates signals from indicators)
    ↓ (depends on: strategy_params dict)
BacktestEngine/FallbackEngineV2 (executes trades)
    ↓ (depends on: initial_capital, commission=0.0007)
MetricsCalculator (calculates 166 metrics)
```

**NEVER lose:** `strategy_params`, `initial_capital`, `commission_rate`

## Validation Requirements

After ANY change to backtesting:

1. Run benchmark: `python benchmarks/backtest_speed.py`
2. Compare results: must match previous version within 0.01%
3. Check memory usage on 1M+ candles
4. Compare with TradingView on same dataset

---

# Code Patterns

## Strategy Template

```python
from backend.backtesting.strategies.base import BaseStrategy
from typing import Dict, Optional
import pandas as pd
import pandas_ta as ta

class NewStrategy(BaseStrategy):
    """Strategy description"""

    def __init__(self, params: Dict[str, float]):
        super().__init__(params)
        self.required_params = ['param1', 'param2']
        self._validate_params()

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate entry/exit signals"""
        signals = data.copy()
        # Implementation
        return signals
```

## FastAPI Endpoint

```python
from fastapi import APIRouter, Depends, HTTPException
from backend.api.schemas import RequestModel, ResponseModel
from loguru import logger

router = APIRouter(prefix="/api/v1", tags=["feature"])

@router.post("/endpoint", response_model=ResponseModel)
async def endpoint(request: RequestModel):
    """Endpoint description"""
    try:
        # Implementation
        return ResponseModel(...)
    except Exception as e:
        logger.error(f"Endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## Error Handling

```python
from loguru import logger
import asyncio

def robust_operation(func):
    """Decorator for operations with retry logic"""
    async def wrapper(*args, **kwargs):
        retries = 3
        for attempt in range(retries):
            try:
                return await func(*args, **kwargs)
            except RateLimitError:
                wait_time = 2 ** attempt
                logger.warning(f"Rate limited, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
            except NetworkError as e:
                if attempt == retries - 1:
                    raise
                logger.error(f"Network error (attempt {attempt+1}/{retries}): {e}")
        return None
    return wrapper
```

## Bybit API Pattern

```python
# ALWAYS use this pattern:
try:
    response = await bybit_client.fetch_data(symbol, timeframe)
    if response.get('retCode') != 0:
        raise APIError(response.get('retMsg'))
except (NetworkError, RateLimitError, Timeout) as e:
    logger.error(f"Bybit API error: {e}")
    # implement retry logic with exponential backoff
```

- Rate limit: 120 requests/min
- NEVER hardcode keys (use environment variables)
- Log ALL API calls (timestamp, endpoint, response code)

---

# Testing Standards

## Structure

```
tests/
├── unit/           # Fast, isolated tests
├── integration/    # Multi-component tests
├── e2e/            # End-to-end tests
└── conftest.py     # Shared fixtures
```

## Coverage Requirements

- **Minimum overall:** 80%
- **Critical modules (95%):**
    - `backend/backtesting/engines/`
    - `backend/core/metrics_calculator.py`
    - `backend/api/routers/`

## Running Tests

```bash
# Full suite
pytest tests/ -v

# With coverage
pytest tests/ --cov=backend --cov-report=term-missing

# Specific module
pytest tests/test_backtesting.py -v

# Skip slow tests
pytest tests/ -v -m "not slow"
```

## Test Naming

- File: `test_[module_name].py`
- Function: `test_[function_name]_[scenario]`
- Example: `test_rsi_calculation_with_valid_data`

## Fixtures Pattern

```python
import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Sample OHLCV data for testing"""
    n = 100
    np.random.seed(42)
    return pd.DataFrame({
        'timestamp': pd.date_range('2025-01-01', periods=n, freq='15min'),
        'open': 50000 + np.random.randn(n).cumsum() * 100,
        'high': 50000 + np.random.randn(n).cumsum() * 100 + 50,
        'low': 50000 + np.random.randn(n).cumsum() * 100 - 50,
        'close': 50000 + np.random.randn(n).cumsum() * 100,
        'volume': np.random.uniform(100, 1000, n)
    })
```

## Mock External APIs

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_bybit_fetch_with_network_error():
    with patch('backend.services.adapters.bybit.aiohttp.ClientSession') as mock:
        mock.return_value.__aenter__.return_value.get.side_effect = NetworkError

        with pytest.raises(NetworkError):
            await connector.fetch_ohlcv('BTCUSDT', '1h')
```

## Pre-Commit Checklist

- ✅ All tests pass: `pytest tests/ -v`
- ✅ Linting clean: `ruff check .`
- ✅ Format code: `ruff format .`
- ✅ No secrets in code: `git diff | grep -i "api_key\|secret"`

---

# Project Architecture

## Key Components

| Component        | Location                                            | Purpose                      |
| ---------------- | --------------------------------------------------- | ---------------------------- |
| FastAPI App      | `backend/api/app.py`                                | Main API application         |
| Backtesting      | `backend/backtesting/`                              | Strategy backtesting engines |
| FallbackEngineV2 | `backend/backtesting/engines/fallback_engine_v2.py` | Gold standard engine         |
| Metrics          | `backend/core/metrics_calculator.py`                | 166-metric calculation suite |
| Bybit Adapter    | `backend/services/adapters/bybit.py`                | Bybit API integration        |
| Strategy Builder | `backend/services/strategy_builder/`                | Visual strategy construction |
| Frontend         | `frontend/`                                         | Static HTML/JS/CSS           |

## Database

- **SQLite** with SQLAlchemy ORM
- Market data: `backend/bybit_klines_15m.db`
- App data: `app.sqlite3`
- Repository pattern for queries

## Configuration

- Environment: `.env` file (never commit!)
- Settings: `backend/config/settings.py`
- Logging: `loguru` format

## Data Flow

```
Bybit API (REST + WebSocket)
    ↓
DataService (caches in SQLite)
    ↓
Strategy (generates signals from indicators)
    ↓ uses: strategy_params dict
BacktestEngine/FallbackEngineV2 (executes trades)
    ↓ uses: initial_capital, commission_rate=0.0007
MetricsCalculator (calculates 166 metrics)
    ↓
FastAPI (REST API endpoints)
    ↓
Frontend (HTML/JS/CSS)
```

## Session Protocol

### START Session

1. Read `docs/DECISIONS.md` for key choices
2. Check `CHANGELOG.md` for recent changes
3. Review `.ai/context/ai-context.md`

### DURING Session

1. Update `.ai/context/ai-context.md` with progress
2. Track variable changes
3. Commit frequently with descriptive messages

### END Session

1. Update `CHANGELOG.md` with changes
2. Update `.ai/context/ai-context.md` with summary
3. Document decisions in `docs/DECISIONS.md`

---

