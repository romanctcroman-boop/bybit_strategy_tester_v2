# API Reference

Complete API documentation for Bybit Strategy Tester v2.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently, the API does not require authentication for local development.
For production, configure API keys via environment variables.

---

## Endpoints

### Backtests

#### Run Backtest

```http
POST /backtests/
```

Run a new backtest with the specified configuration.

**Request Body:**

| Field             | Type   | Required | Description                                              |
| ----------------- | ------ | -------- | -------------------------------------------------------- |
| `symbol`          | string | Yes      | Trading pair (e.g., "BTCUSDT")                           |
| `interval`        | string | Yes      | Timeframe ("1m", "5m", "15m", "1h", "4h", "1d")          |
| `start_date`      | string | Yes      | Start date (ISO format: "2025-01-01")                    |
| `end_date`        | string | Yes      | End date (ISO format: "2025-01-15")                      |
| `initial_capital` | number | Yes      | Starting capital in USDT                                 |
| `leverage`        | number | No       | Leverage (default: 1)                                    |
| `strategy_type`   | string | Yes      | Strategy type ("rsi", "macd", "sma", "ema", "bollinger") |
| `strategy_params` | object | Yes      | Strategy-specific parameters                             |
| `stop_loss`       | number | No       | Stop loss percentage (0.02 = 2%)                         |
| `take_profit`     | number | No       | Take profit percentage (0.04 = 4%)                       |
| `direction`       | string | No       | Trade direction ("long", "short", "both")                |
| `taker_fee`       | number | No       | Taker fee (default: 0.0007)                              |
| `maker_fee`       | number | No       | Maker fee (default: 0.0002)                              |

**Example Request:**

```json
{
    "symbol": "BTCUSDT",
    "interval": "15m",
    "start_date": "2025-01-01",
    "end_date": "2025-01-15",
    "initial_capital": 10000,
    "leverage": 10,
    "strategy_type": "rsi",
    "strategy_params": {
        "period": 14,
        "overbought": 70,
        "oversold": 30
    },
    "stop_loss": 0.02,
    "take_profit": 0.04,
    "direction": "both"
}
```

**Response:**

```json
{
    "id": "bt_abc123",
    "status": "completed",
    "created_at": "2025-01-26T12:00:00Z",
    "completed_at": "2025-01-26T12:00:05Z",
    "metrics": {
        "net_profit": 1234.56,
        "net_profit_pct": 12.35,
        "total_trades": 45,
        "winning_trades": 28,
        "losing_trades": 17,
        "win_rate": 62.22,
        "profit_factor": 1.85,
        "sharpe_ratio": 1.42,
        "sortino_ratio": 2.15,
        "max_drawdown": 8.5,
        "max_drawdown_value": 850.0,
        "calmar_ratio": 1.45
    },
    "trades": [
        {
            "id": "1",
            "entry_time": "2025-01-02T10:30:00Z",
            "exit_time": "2025-01-02T14:45:00Z",
            "side": "buy",
            "entry_price": 42500.0,
            "exit_price": 43200.0,
            "size": 0.5,
            "pnl": 350.0,
            "pnl_pct": 1.65,
            "fees": 12.5,
            "mfe": 2.1,
            "mae": 0.5
        }
    ],
    "equity_curve": [10000, 10150, 10050, ...]
}
```

---

#### Get Backtest

```http
GET /backtests/{backtest_id}
```

Retrieve a specific backtest result.

**Path Parameters:**

| Parameter     | Type   | Description |
| ------------- | ------ | ----------- |
| `backtest_id` | string | Backtest ID |

**Response:** Same as Run Backtest response.

---

#### List Backtests

```http
GET /backtests/
```

List all backtests with optional filtering.

**Query Parameters:**

| Parameter       | Type    | Description               |
| --------------- | ------- | ------------------------- |
| `limit`         | integer | Max results (default: 50) |
| `offset`        | integer | Pagination offset         |
| `symbol`        | string  | Filter by symbol          |
| `strategy_type` | string  | Filter by strategy        |
| `status`        | string  | Filter by status          |

**Response:**

```json
{
    "total": 125,
    "items": [
        {
            "id": "bt_abc123",
            "symbol": "BTCUSDT",
            "strategy_type": "rsi",
            "status": "completed",
            "created_at": "2025-01-26T12:00:00Z",
            "net_profit": 1234.56,
            "win_rate": 62.22
        }
    ]
}
```

---

#### Delete Backtest

```http
DELETE /backtests/{backtest_id}
```

Delete a specific backtest.

**Response:**

```json
{
    "success": true,
    "message": "Backtest deleted successfully"
}
```

---

### Optimization

#### Run Optimization

```http
POST /optimize/
```

Run parameter optimization for a strategy.

**Request Body:**

| Field             | Type    | Required | Description                                  |
| ----------------- | ------- | -------- | -------------------------------------------- |
| `symbol`          | string  | Yes      | Trading pair                                 |
| `interval`        | string  | Yes      | Timeframe                                    |
| `start_date`      | string  | Yes      | Start date                                   |
| `end_date`        | string  | Yes      | End date                                     |
| `strategy_type`   | string  | Yes      | Strategy type                                |
| `param_ranges`    | object  | Yes      | Parameter ranges to optimize                 |
| `optimize_metric` | string  | No       | Metric to optimize (default: "sharpe_ratio") |
| `use_gpu`         | boolean | No       | Use GPU acceleration (default: true)         |

**Example Request:**

```json
{
    "symbol": "BTCUSDT",
    "interval": "15m",
    "start_date": "2025-01-01",
    "end_date": "2025-01-15",
    "strategy_type": "rsi",
    "param_ranges": {
        "period": { "min": 10, "max": 21, "step": 1 },
        "overbought": { "min": 65, "max": 80, "step": 5 },
        "oversold": { "min": 20, "max": 35, "step": 5 }
    },
    "optimize_metric": "sharpe_ratio"
}
```

**Response:**

```json
{
    "id": "opt_xyz789",
    "status": "completed",
    "best_params": {
        "period": 14,
        "overbought": 75,
        "oversold": 25
    },
    "best_score": 2.15,
    "total_combinations": 192,
    "duration_seconds": 12.5,
    "top_results": [
        {
            "params": { "period": 14, "overbought": 75, "oversold": 25 },
            "sharpe_ratio": 2.15,
            "net_profit": 1856.32,
            "win_rate": 65.4
        }
    ]
}
```

---

### Market Data

#### Get Klines

```http
GET /data/klines
```

Fetch historical kline (candlestick) data.

**Query Parameters:**

| Parameter    | Type    | Required | Description                |
| ------------ | ------- | -------- | -------------------------- |
| `symbol`     | string  | Yes      | Trading pair               |
| `interval`   | string  | Yes      | Timeframe                  |
| `start_time` | integer | No       | Start timestamp (ms)       |
| `end_time`   | integer | No       | End timestamp (ms)         |
| `limit`      | integer | No       | Max candles (default: 200) |

**Response:**

```json
{
    "symbol": "BTCUSDT",
    "interval": "15m",
    "data": [
        {
            "open_time": 1706270400000,
            "open": 42500.0,
            "high": 42650.0,
            "low": 42400.0,
            "close": 42600.0,
            "volume": 1250.5,
            "turnover": 53125000.0
        }
    ]
}
```

---

#### Get Available Symbols

```http
GET /data/symbols
```

List available trading symbols.

**Response:**

```json
{
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "base_currency": "BTC",
            "quote_currency": "USDT",
            "status": "Trading"
        }
    ]
}
```

---

### Strategies

#### List Strategies

```http
GET /strategies/
```

List all available strategies.

**Response:**

```json
{
    "strategies": [
        {
            "type": "rsi",
            "name": "RSI (Relative Strength Index)",
            "description": "Momentum oscillator measuring speed and change of price movements",
            "params": {
                "period": { "type": "int", "default": 14, "min": 2, "max": 100 },
                "overbought": { "type": "int", "default": 70, "min": 50, "max": 95 },
                "oversold": { "type": "int", "default": 30, "min": 5, "max": 50 }
            }
        }
    ]
}
```

---

### Health

#### Health Check

```http
GET /health
```

Check system health status.

**Response:**

```json
{
    "status": "healthy",
    "version": "2.3.13",
    "uptime_seconds": 3600,
    "database": "connected",
    "redis": "connected",
    "gpu_available": true,
    "gpu_memory_free": "3.2GB"
}
```

---

## Error Responses

All errors follow this format:

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid parameter: interval must be one of ['1m', '5m', '15m', '1h', '4h', '1d']",
        "details": {
            "field": "interval",
            "value": "2m"
        }
    }
}
```

### Error Codes

| Code               | HTTP Status | Description                |
| ------------------ | ----------- | -------------------------- |
| `VALIDATION_ERROR` | 400         | Invalid request parameters |
| `NOT_FOUND`        | 404         | Resource not found         |
| `RATE_LIMITED`     | 429         | Too many requests          |
| `INTERNAL_ERROR`   | 500         | Server error               |
| `DATA_UNAVAILABLE` | 503         | Market data unavailable    |

---

## Rate Limits

| Endpoint           | Limit      |
| ------------------ | ---------- |
| `/backtests/` POST | 10/minute  |
| `/optimize/` POST  | 5/minute   |
| `/data/klines` GET | 100/minute |
| Other endpoints    | 200/minute |

---

## WebSocket API

### Real-Time Price Updates

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/prices");

ws.onopen = () => {
    ws.send(
        JSON.stringify({
            action: "subscribe",
            symbols: ["BTCUSDT", "ETHUSDT"],
        }),
    );
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data);
    // { symbol: 'BTCUSDT', price: 42500.0, timestamp: 1706270400000 }
};
```

---

## SDK Examples

### Python

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Run backtest
response = requests.post(f"{BASE_URL}/backtests/", json={
    "symbol": "BTCUSDT",
    "interval": "15m",
    "start_date": "2025-01-01",
    "end_date": "2025-01-15",
    "initial_capital": 10000,
    "strategy_type": "rsi",
    "strategy_params": {"period": 14, "overbought": 70, "oversold": 30}
})

result = response.json()
print(f"Net Profit: ${result['metrics']['net_profit']:.2f}")
```

### JavaScript

```javascript
const response = await fetch("http://localhost:8000/api/v1/backtests/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        symbol: "BTCUSDT",
        interval: "15m",
        start_date: "2025-01-01",
        end_date: "2025-01-15",
        initial_capital: 10000,
        strategy_type: "rsi",
        strategy_params: { period: 14, overbought: 70, oversold: 30 },
    }),
});

const result = await response.json();
console.log(`Net Profit: $${result.metrics.net_profit.toFixed(2)}`);
```

---

_Last Updated: 2026-01-26_
