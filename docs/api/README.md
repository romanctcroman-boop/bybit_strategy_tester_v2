# API Documentation

This directory contains API reference documentation for the Bybit Strategy Tester.

## Interactive Documentation

When the server is running, access interactive API documentation at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Overview

The API is organized into the following groups:

| Group         | Base Path               | Description                         |
| ------------- | ----------------------- | ----------------------------------- |
| Health        | `/api/v1/health`        | Service health and monitoring       |
| Backtests     | `/api/v1/backtests`     | Backtest execution and results      |
| Strategies    | `/api/v1/strategies`    | Strategy management                 |
| Market Data   | `/api/v1/marketdata`    | Historical and real-time data       |
| Optimizations | `/api/v1/optimizations` | Parameter optimization              |
| AI Agents     | `/api/v1/agents`        | DeepSeek and Perplexity integration |
| MCP           | `/mcp`                  | Model Context Protocol endpoints    |

## Authentication

Most endpoints are currently open. For production, configure authentication:

```ini
# .env
API_KEY_REQUIRED=true
API_KEY=your-secret-key
```

Then include the API key in requests:

```http
GET /api/v1/backtests
X-API-Key: your-secret-key
```

## Rate Limiting

API requests are rate-limited:

- Standard endpoints: 100 requests/minute
- Heavy operations: 10 requests/minute
- Health checks: Unlimited

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1706043600
```

## Common Endpoints

### Health Check

```http
GET /api/v1/health
```

Response:

```json
{
    "status": "healthy",
    "version": "2.0.0",
    "uptime": "2h 30m",
    "database": { "status": "ok" },
    "redis": { "status": "ok" }
}
```

### Run Backtest

```http
POST /api/v1/backtests
Content-Type: application/json

{
    "symbol": "BTCUSDT",
    "interval": "15",
    "strategy": "MACD",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 10000
}
```

Response:

```json
{
    "id": 123,
    "status": "completed",
    "metrics": {
        "total_return": 45.2,
        "sharpe_ratio": 1.85,
        "max_drawdown": -12.3,
        "win_rate": 58.5,
        "total_trades": 156
    }
}
```

### List Strategies

```http
GET /api/v1/strategies
```

### Get Market Data

```http
GET /api/v1/marketdata/klines?symbol=BTCUSDT&interval=15&limit=500
```

## Error Handling

All errors follow this format:

```json
{
    "error": "error_code",
    "message": "Human-readable message",
    "detail": "Additional details",
    "request_id": "abc-123"
}
```

Common error codes:

| Code                  | HTTP Status | Description                |
| --------------------- | ----------- | -------------------------- |
| `validation_error`    | 400         | Invalid request parameters |
| `not_found`           | 404         | Resource not found         |
| `rate_limit_exceeded` | 429         | Too many requests          |
| `internal_error`      | 500         | Server error               |

## See Also

- [Endpoint Reference](endpoints.md) — Detailed endpoint documentation
- [Examples](examples.md) — Usage examples
- [Architecture](../architecture/README.md) — System design
