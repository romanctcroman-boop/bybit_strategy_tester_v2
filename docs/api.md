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

GET /backtests/{id}/trades
- Query params: side?=buy|sell|LONG|SHORT, limit?, offset?
- Response: Trade[] (normalized fields: price=entry_price, qty=quantity, side=buy/sell)

---

## Optimizations

GET /optimizations
GET /optimizations/{id}
POST /optimizations
GET /optimizations/{id}/results

---

## Market data

GET /marketdata/bybit/klines
- Query: symbol, limit?, start_time?
- Response: normalized rows read from audit table (most recent first)

GET /marketdata/bybit/klines/fetch
- Query: symbol, interval ('1','3','60','D'...), limit (<=1000), persist (0|1)
- Response: normalized rows [{ open_time(ms), open, high, low, close, volume, turnover }]

---

Data shapes (summary)
_All time-related fields below are expressed in ISO 8601 UTC._
- Strategy: { id, name, description, strategy_type, config, is_active, created_at, updated_at }
- Backtest: { id, strategy_id, symbol, timeframe, start_date, end_date, initial_capital, leverage, commission, config, status, created_at, started_at, completed_at, final_capital, metrics... }
- Trade: { id, backtest_id, entry_time, exit_time, price, qty, side, pnl, created_at }
- Optimization: { id, strategy_id, params, created_at, status }
- MarketDataPoint: { id, symbol, timestamp, open, high, low, close, volume }

---

Notes
- These API endpoints are a thin HTTP layer on top of `DataService` and the Celery tasks. Implementations should validate input, return consistent error shapes, and use timezone-aware ISO8601 datetimes.

---

## Timezones

- Standard: UTC across storage and API. All datetime fields are returned as ISO 8601 in UTC (with trailing "Z" or explicit +00:00 offset).
- Exchanges: Bybit timestamps are UTC; TradingView charting assumes UTC and aligns candle buckets to UTC boundaries. This API follows the same rule for kline alignment and time-based calculations.
- Database: Timestamp columns are stored as timestamptz (UTC). Any naive datetimes from legacy data are treated as UTC on read.
- Clients: Convert to a local timezone only for display purposes; avoid sending local-time values without timezone info.

---

## Live market stream (WebSocket)

Endpoint: `GET /api/v1/live` (WebSocket)

Purpose
- Relays real-time messages from Redis Pub/Sub to connected WebSocket clients.
- When the optional Bybit WS manager is enabled, normalized trade and kline events are published to Redis channels and will appear on this stream.

Query params
- `channel`: Redis channel to subscribe to. Default: `bybit:ticks`
- `pattern`: `1` to use pattern subscription (psubscribe). Default: `0`

Behavior
- On connect, the server immediately sends a JSON message confirming the subscription:
	- `{ "status": "subscribed", "channel": "bybit:ticks", "url": "redis://..." }`
- Subsequent messages are forwarded as text frames; if the Redis payload is JSON, clients should `JSON.parse` it.

Example messages (normalized schema v=1)
- Trade (ticks channel: `bybit:ticks`):
	- `{ "v":1, "type":"trade", "source":"bybit", "symbol":"BTCUSDT", "ts_ms": 1712345678901, "price": 65000.5, "qty": 0.001, "side": "buy" }`
- Kline (klines channel: `bybit:klines`):
	- `{ "v":1, "type":"kline", "source":"bybit", "symbol":"BTCUSDT", "interval":"1", "open_time":1712345678000, "open":64990.0, "high":65050.0, "low":64900.0, "close":65010.0, "volume":12.34, "turnover":803210.12 }`

Configuration
- Redis location defaults to `REDIS_URL` (e.g. `redis://127.0.0.1:6379/0`).
- Optional overrides for channels and streams:
	- `REDIS_CHANNEL_TICKS`, `REDIS_CHANNEL_KLINES`, `REDIS_STREAM_TICKS`, `REDIS_STREAM_KLINES`

Bybit WS background manager (optional)
- Enable to auto-connect to Bybit public WS and publish normalized events into Redis:
	- `BYBIT_WS_ENABLED=1`
	- `BYBIT_WS_SYMBOLS=BTCUSDT,ETHUSDT`
	- `BYBIT_WS_INTERVALS=1,5`
- Reconnect backoff tunables:
	- `WS_RECONNECT_DELAY_SEC` (default 1.5), `WS_RECONNECT_DELAY_MAX_SEC` (default 15)

Notes
- The WebSocket sends the initial subscription confirmation as JSON; subsequent frames are text and may contain JSON strings.
- When `pattern=1`, the server uses Redis `psubscribe` with the given pattern and forwards matching messages.

---

## Bots (mock)

GET /bots
- Query params: limit?: number (default 50, <=500), offset?: number (default 0)
- Response: { items: Bot[], total: number }

GET /bots/{id}
- Response: Bot

POST /bots/{id}/start
- Response: { ok: boolean, status: BotStatus, message?: string }

POST /bots/{id}/stop
- Response: { ok: boolean, status: BotStatus, message?: string }

POST /bots/{id}/delete
- Response: { ok: boolean, message?: string }

Bot shape (mock):
```json
{
	"id": "bot_1",
	"name": "BTC Scalper",
	"strategy": "scalper_v1",
	"symbols": ["BTCUSDT"],
	"capital_allocated": 1000.0,
	"status": "running|stopped|awaiting_start|awaiting_stop|error",
	"created_at": "2025-10-22T12:00:00Z"
}
```

---

## Active deals (mock)

GET /active-deals
- Query params: limit?: number (default 50, <=500), offset?: number (default 0)
- Response: { items: ActiveDeal[], total: number }

POST /active-deals/{id}/close
POST /active-deals/{id}/average
POST /active-deals/{id}/cancel
- Response: { ok: boolean, action: string, message?: string }

ActiveDeal shape (mock):
```json
{
	"id": "deal_1",
	"bot_id": "bot_1",
	"symbol": "BTCUSDT",
	"entry_price": 60000.0,
	"quantity": 0.02,
	"next_open_price": 60350.0,
	"current_price": 60200.0,
	"pnl_abs": 4.0,
	"pnl_pct": 0.33,
	"opened_at": "2025-10-22T12:00:00Z"
}
```
