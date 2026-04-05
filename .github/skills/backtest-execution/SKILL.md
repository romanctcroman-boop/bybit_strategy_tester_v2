---
name: Backtest Execution
description: "Run, compare, and analyze cryptocurrency trading backtests on the Bybit Strategy Tester v2 platform."
---

# Backtest Execution Skill

## Overview

Execute backtests via the API or directly through the engine, analyze results, and verify TradingView metric parity.

## API Endpoint

**POST** `http://localhost:8000/api/v1/backtests/`

```json
{
    "symbol": "BTCUSDT",
    "interval": "15",
    "start_date": "2025-01-01",
    "end_date": "2025-02-01",
    "initial_capital": 10000.0,
    "leverage": 1,
    "direction": "both",
    "strategy_type": "rsi",
    "strategy_params": { "period": 14, "overbought": 70, "oversold": 30 },
    "stop_loss": null,
    "take_profit": null
}
```

## Direct Engine Usage

```python
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngine

engine = FallbackEngine(commission=0.0007)
result = engine.run(
    data=df,
    signals=signals_df,
    initial_capital=10000.0,
    leverage=1,
    direction="both"
)
```

## Critical Rules

- **Commission**: Always `0.0007` (0.07%)
- **Engine**: Always use `FallbackEngineV4` (gold standard)
- **Data**: No data before `2025-01-01` (retention policy)
- **Timeframes**: Only `1, 5, 15, 30, 60, 240, D, W, M`

## Metrics Verification

Run the calibration script to verify TradingView parity:

```powershell
py -3.14 scripts/calibrate_166_metrics.py
```

## Supported Strategies

All built-in strategies are defined in `backend/backtesting/strategies.py` (single file).
Register new strategies via `STRATEGY_REGISTRY["name"] = MyStrategy` in the same file.

| Strategy         | Key Params                   | Strategy type key   |
| ---------------- | ---------------------------- | ------------------- |
| SMA Crossover    | fast_period, slow_period     | `sma_crossover`     |
| RSI              | period, overbought, oversold | `rsi`               |
| MACD             | fast_period, slow_period, signal_period | `macd`  |
| Bollinger Bands  | period, std_dev              | `bollinger_bands`   |
| Grid             | grid_levels, grid_spacing    | `grid`              |
| DCA              | dca_order_count, dca_grid_size_percent | `dca`   |

## Response Structure

```json
{
    "id": "uuid",
    "metrics": {
        "net_profit": 1234.56,
        "total_trades": 42,
        "win_rate": 0.62,
        "profit_factor": 1.85,
        "max_drawdown": -0.12,
        "sharpe_ratio": 1.45
    },
    "trades": [...],
    "equity_curve": [...]
}
```
