---
name: Bybit API Integration
description: "Patterns for working with the Bybit API v5 adapter. Klines, rate limiting, circuit breaker, and error handling."
---

# Bybit API Integration Skill

## Overview

The project uses a custom `BybitAdapter` at `backend/services/adapters/bybit.py` (1701 lines) for Bybit API v5 integration. It supports both direct REST calls and optional `pybit` SDK.

## Adapter Usage

```python
from backend.services.adapters.bybit import BybitAdapter

# Public endpoints (no API key needed)
adapter = BybitAdapter()

# Authenticated endpoints
adapter = BybitAdapter(api_key="...", api_secret="...")
```

## Core Methods

### Get Klines (Candles)

```python
klines = adapter.get_klines(
    symbol="BTCUSDT",
    interval="15",   # Minutes: 1,5,15,30,60,240 or D,W,M
    limit=200        # Max 1000 per request
)
# Returns: List[dict] with keys: open_time, open, high, low, close, volume
```

### Get Historical Klines (Paginated)

```python
klines = adapter.get_historical_klines(
    symbol="BTCUSDT",
    interval="15",
    start=1704067200000,  # Unix timestamp ms
    end=1706745600000
)
```

### Get Tickers

```python
tickers = adapter.get_tickers(category="linear")
# Cached for 30 seconds in-memory to reduce API calls
```

## Interval Normalization

The adapter auto-normalizes intervals to Bybit v5 format:

| Input           | Normalized | Notes           |
| --------------- | ---------- | --------------- |
| `"15"`, `"15m"` | `"15"`     | Minutes         |
| `"1h"`, `"60"`  | `"60"`     | Hours → minutes |
| `"4h"`, `"240"` | `"240"`    | Hours → minutes |
| `"1d"`, `"D"`   | `"D"`      | Daily           |
| `"1w"`, `"W"`   | `"W"`      | Weekly          |
| `"1M"`, `"M"`   | `"M"`      | Monthly         |

## Rate Limiting

- **Bybit limit**: 120 requests/minute for public endpoints
- **Strategy**: Use exponential backoff on HTTP 429 responses
- **Caching**: Tickers cached 30s, instruments cached 5 minutes

## Circuit Breaker

```python
# Auto-enabled if backend.core.circuit_breaker is available
# Opens after consecutive failures, blocks calls temporarily
if not breaker.can_execute():
    raise ConnectionError("Circuit breaker OPEN")
```

## Error Handling (CRITICAL)

```python
response = adapter.get_klines("BTCUSDT", "15")

# For raw API responses, ALWAYS check retCode
raw = requests.get("https://api.bybit.com/v5/market/kline", params={...})
data = raw.json()
if data.get("retCode") != 0:
    raise APIError(f"Bybit API error: {data.get('retMsg')}")
```

## Symbol Discovery

The adapter auto-discovers symbols:

1. **Fast path**: If symbol ends with `USDT`, fetch directly
2. **Discovery**: Query `instruments-info` for available linear perpetuals
3. **Fallback**: Try common suffixes (`USDT`)
4. **Default**: `BTCUSDT` if nothing matches

## Testing Rules

- **NEVER** call real Bybit API in unit tests
- Use `unittest.mock.patch` to mock `requests.get`
- Use `conftest.py` fixtures: `mock_adapter`, `sample_klines`

```python
from unittest.mock import patch, MagicMock

@patch("backend.services.adapters.bybit.requests.get")
def test_get_klines(mock_get):
    mock_get.return_value.json.return_value = {
        "retCode": 0,
        "result": {"list": [
            [1704067200000, "42000", "42500", "41800", "42300", "1000"]
        ]}
    }
    adapter = BybitAdapter()
    klines = adapter.get_klines("BTCUSDT", "15")
    assert len(klines) == 1
```

## Data Retention

```python
from backend.config.database_policy import DATA_START_DATE, RETENTION_YEARS
# DATA_START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)
# No data before 2025-01-01 is stored
```

## Supported Timeframes (Project-wide)

```python
ALL_TIMEFRAMES = ["1", "5", "15", "30", "60", "240", "D", "W", "M"]
# Legacy mapping on load: 3→5, 120→60, 360→240, 720→D
```
