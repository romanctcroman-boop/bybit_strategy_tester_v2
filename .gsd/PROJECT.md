# Bybit Strategy Tester v2

## Core Value

Production-grade backtesting platform with TradingView metric parity for Bybit cryptocurrency strategies.

## Description

Full-stack backtesting system: Bybit API data → Strategy signals → Backtest engine → 166 TradingView-parity metrics → FastAPI (753 routes) → Interactive frontend.

## Technical Constraints

| Constraint           | Value                                       | Reason                              |
| -------------------- | ------------------------------------------- | ----------------------------------- |
| Commission rate      | 0.0007 (0.07%)                              | TradingView parity — NEVER change   |
| Gold standard engine | FallbackEngineV4                            | Most accurate, TradingView-verified |
| Data start date      | 2025-01-01                                  | Database retention policy           |
| Supported timeframes | 1, 5, 15, 30, 60, 240, D, W, M              | Bybit API + legacy mapping          |
| Python version       | 3.11-3.14                                   | Project requirement                 |
| Database             | SQLite (data.sqlite3 + bybit_klines_15m.db) | Local development                   |
| Rate limit           | 120 req/min                                 | Bybit API v5                        |

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy, Pandas, NumPy, pandas_ta
- **Frontend**: Static HTML/JS/CSS
- **Database**: SQLite with Alembic migrations
- **External**: Bybit API v5 (REST + WebSocket)
- **Testing**: pytest (80% coverage, 95% for engines)
- **Linting**: ruff

## Architecture

```
Bybit API (REST + WebSocket)
    ↓
DataService → SQLite
    ↓
Strategy.generate_signals(df) → DataFrame with 'signal' column
    ↓
FallbackEngineV4 → commission=0.0007
    ↓
MetricsCalculator → 166 metrics
    ↓
FastAPI (753 routes) → /api/v1/
    ↓
Frontend → /frontend/
```

## Success Criteria

- All strategies produce metrics matching TradingView within tolerance
- Test coverage ≥80% overall, ≥95% for backtest engines
- All API endpoints documented in Swagger
- Frontend fully functional at http://localhost:8000/frontend/

## Out of Scope (Current Phase)

- Live trading execution
- Multi-exchange support (Bybit only)
- Machine learning model training
- Mobile application
