# AI Context - Bybit Strategy Tester v2

**Last Updated:** 2026-01-30 18:30 MSK
**Current Phase:** Development - Strategy Builder & Backtesting
**Project Version:** 2.x

---

## Current Project State

### Active Development

**Current Focus:** Strategy Builder frontend/backend integration
**Status:** Active development
**Key Components:**

- `frontend/js/pages/strategy_builder.js` - Visual strategy constructor
- `backend/services/strategy_builder/` - Strategy builder backend
- `backend/backtesting/engines/fallback_engine_v2.py` - Gold standard backtest engine

### Recent Completions

- ✅ FallbackEngineV2 with TradingView parity (commission 0.07%)
- ✅ 166-metric calculation suite
- ✅ MFE/MAE analysis for trades
- ✅ Walk-forward optimization
- ✅ Bybit API v5 integration

---

## Critical Variables Tracking

### Backtesting Engine (backend/backtesting/engines/)

| Variable        | Location              | Type  | Notes                                   |
| --------------- | --------------------- | ----- | --------------------------------------- |
| commission_rate | fallback_engine_v2.py | float | **0.0007 (0.07%)** - TradingView parity |
| initial_capital | engine.py             | float | Default 10000.0                         |
| strategy_params | engine.py             | Dict  | Passed to strategies                    |
| leverage        | engine.py             | int   | Default 1                               |

### Strategy Builder

| Variable        | Location            | Type  | Notes                  |
| --------------- | ------------------- | ----- | ---------------------- |
| blocks          | strategy_builder.js | Array | Visual strategy blocks |
| connections     | strategy_builder.js | Array | Block connections      |
| strategy_config | strategy_builder.py | Dict  | Compiled strategy      |

### API Configuration

| Variable         | Location | Type   | Notes         |
| ---------------- | -------- | ------ | ------------- |
| BYBIT_API_KEY    | .env     | string | Never commit! |
| BYBIT_API_SECRET | .env     | string | Never commit! |
| DATABASE_URL     | .env     | string | SQLite path   |

---

## Component Status

### Production Ready ✅

- ✅ FallbackEngineV2 (gold standard)
- ✅ MetricsCalculator (166 metrics)
- ✅ DataService (SQLite + Bybit)
- ✅ RSI Strategy
- ✅ EMA Crossover Strategy
- ✅ Bollinger Bands Strategy
- ✅ FastAPI application

### In Development 🚧

- 🚧 Strategy Builder UI
- 🚧 Walk-Forward Optimization UI
- 🚧 Real-time WebSocket feeds
- 🚧 AI Strategy Generator

### Planned 📋

- 📋 Multi-timeframe analysis
- 📋 Portfolio backtesting
- 📋 Live trading execution
- 📋 Telegram notifications

---

## Architecture Overview

### Data Flow

```
Bybit API (REST + WebSocket)
    ↓
DataService (caches in SQLite: bybit_klines_15m.db)
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

### Key Files

- `backend/api/app.py` - FastAPI application
- `backend/backtesting/engines/fallback_engine_v2.py` - Backtest engine
- `backend/core/metrics_calculator.py` - Metrics calculation
- `backend/services/data_service.py` - Data loading
- `backend/services/adapters/bybit.py` - Bybit API
- `frontend/js/pages/strategy_builder.js` - Strategy builder UI

---

## Recent Decisions

### 2026-01-30: Commission Rate

**Decision:** Fixed commission at 0.07% (0.0007)
**Rationale:** Match TradingView strategy tester for result parity
**Impact:** All backtest results now comparable to TradingView

### Database Choice

**Decision:** SQLite with SQLAlchemy
**Rationale:** Simple deployment, sufficient performance for single-user
**Files:** `app.sqlite3` (app data), `backend/bybit_klines_15m.db` (market data)

---

## Known Issues & Workarounds

### Issue: WebSocket Disconnects

**Status:** WORKAROUND IMPLEMENTED
**Workaround:** Auto-reconnect with exponential backoff
**Location:** `backend/services/adapters/bybit.py`

### Issue: Large Dataset Performance

**Status:** OPTIMIZED
**Solution:** Vectorized calculations, LRU caching for indicators
**Benchmark:** 100K candles backtest < 10 seconds

---

## TODOs for Next Session

### High Priority 🔴

1. Complete Strategy Builder block connections
2. Add validation for strategy compilation
3. Fix frontend error handling

### Medium Priority 🟡

4. Add more strategy templates
5. Improve optimization speed
6. Add export functionality

### Low Priority 🟢

7. UI polish
8. Documentation updates
9. Additional test coverage

---

## Quick Reference

### Run Commands

```powershell
# Start server
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=term-missing

# Lint check
ruff check .

# Format code
ruff format .
```

### Key Endpoints

- `POST /api/v1/backtests/` - Run backtest
- `GET /api/v1/backtests/{id}` - Get backtest result
- `POST /api/v1/strategies/` - Create strategy
- `GET /api/v1/symbols/` - List available symbols

### Database Commands

```powershell
# Check database
sqlite3 app.sqlite3 ".tables"

# Check klines
sqlite3 backend/bybit_klines_15m.db "SELECT COUNT(*) FROM klines WHERE symbol='BTCUSDT'"
```

---

## Session Log Template

When starting a session, copy this:

```markdown
## Session [DATE] [TIME]

### Goals

- [ ] Goal 1
- [ ] Goal 2

### Progress

- [TIME] Started: [task]
- [TIME] Completed: [task]

### Changes Made

- file1.py: [what changed]
- file2.py: [what changed]

### Issues Encountered

- [Issue and resolution]

### For Next Session

- [ ] TODO 1
- [ ] TODO 2
```
