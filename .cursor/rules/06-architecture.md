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
