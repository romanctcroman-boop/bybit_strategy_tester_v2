# API Contract (Level-2) — bybit_strategy_tester_v2

This document describes the planned HTTP API surface for frontend Level‑2. It is derived from `backend.services.DataService` methods and is intended to be a stable contract for the frontend team.

Base URL: /api/v1

Authentication: TBD (JWT / API key). Endpoints assume an authenticated context where needed.

Content types: application/json for requests/responses.

---

## Strategies

GET /strategies
- Query params: is_active?: boolean, strategy_type?: string, limit?: number, offset?: number
- Response: { items: Strategy[], total?: number }

GET /strategies/{id}
- Response: Strategy

POST /strategies
- Body: { name, description, strategy_type, config, is_active }
- Response: Strategy (201)

PUT /strategies/{id}
- Body: partial strategy fields
- Response: Strategy

DELETE /strategies/{id}
- Response: { success: boolean }

---

## Backtests

GET /backtests
- Query params: strategy_id?, symbol?, status?, limit?, offset?, order_by?, order_dir?
- Response: { items: Backtest[], total?: number }

GET /backtests/{id}
- Response: Backtest

POST /backtests
- Body: { strategy_id, symbol, timeframe, start_date, end_date, initial_capital, leverage?, commission?, config? }
- Response: Backtest

PUT /backtests/{id}
- Body: partial backtest fields
- Response: Backtest

POST /backtests/{id}/claim
- Body: { now: ISO8601 string }
- Response: { status: 'claimed'|'running'|'completed'|'not_found'|'error', backtest?: Backtest, message?: string }

POST /backtests/{id}/results
- Body: { final_capital, total_return, total_trades, winning_trades, losing_trades, win_rate, sharpe_ratio, max_drawdown, ... }
- Response: Backtest

---

## Trades

GET /trades?backtest_id={id}
- Response: { items: Trade[] }

GET /trades/{id}
- Response: Trade

---

## Optimizations

GET /optimizations
GET /optimizations/{id}
POST /optimizations
GET /optimizations/{id}/results

---

## Market data

GET /market_data?symbol={symbol}&from={iso}&to={iso}&limit={n}
- Response: { items: MarketDataPoint[] }

GET /market_data/{id}/latest_candle

---

Data shapes (summary)
- Strategy: { id, name, description, strategy_type, config, is_active, created_at, updated_at }
- Backtest: { id, strategy_id, symbol, timeframe, start_date, end_date, initial_capital, leverage, commission, config, status, created_at, started_at, completed_at, final_capital, metrics... }
- Trade: { id, backtest_id, entry_time, exit_time, price, qty, side, pnl, created_at }
- Optimization: { id, strategy_id, params, created_at, status }
- MarketDataPoint: { id, symbol, timestamp, open, high, low, close, volume }

---

Notes
- These API endpoints are a thin HTTP layer on top of `DataService` and the Celery tasks. Implementations should validate input, return consistent error shapes, and use timezone-aware ISO8601 datetimes (UTC).
