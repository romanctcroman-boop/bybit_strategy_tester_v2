---
name: Backtest Execution
description: "Run, compare, and analyze cryptocurrency trading backtests with TradingView parity verification."
---

# Backtest Execution Skill for Qwen

## Overview

Execute backtests via API or directly through engines, analyze results, and verify TradingView metric parity.

## 🚀 Quick Start

### Via API

```bash
curl -X POST http://localhost:8000/api/v1/backtests/ \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "interval": "15",
    "start_date": "2025-01-01",
    "end_date": "2025-02-01",
    "strategy_type": "rsi",
    "strategy_params": {
      "period": 14,
      "overbought": 70,
      "oversold": 30
    },
    "initial_capital": 10000.0,
    "leverage": 1.0,
    "direction": "both",
    "commission_rate": 0.0007
  }'
```

### Direct Engine Usage

```python
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.models import BacktestConfig

config = BacktestConfig(
    symbol='BTCUSDT',
    interval='15',
    start_date='2025-01-01',
    end_date='2025-02-01',
    initial_capital=10000.0,
    commission_rate=0.0007  # NEVER change
)

engine = FallbackEngineV4(config)
result = engine.run(data=ohlcv_df, signals=signals_df)
print(f"Net profit: {result.net_profit:.2f}")
```

## ⚠️ Critical Rules

| Rule | Value | Reason |
|------|-------|--------|
| Commission | `0.0007` (0.07%) | TradingView parity |
| Engine | `FallbackEngineV4` | Gold standard |
| Data start | `2025-01-01` | Retention policy |
| Timeframes | `1,5,15,30,60,240,D,W,M` | Bybit supported |
| Max duration | `730 days` (2 years) | API limit |

## 📊 Supported Strategies

| Strategy | Params | File |
|----------|--------|------|
| RSI | `period`, `overbought`, `oversold` | `backend/backtesting/strategies/rsi.py` |
| MACD | `fast`, `slow`, `signal` | `backend/backtesting/strategies/macd.py` |
| Bollinger Bands | `period`, `std_dev` | `backend/backtesting/strategies/bollinger.py` |
| EMA Cross | `fast_period`, `slow_period` | `backend/backtesting/strategies/ema_cross.py` |
| SMA Cross | `fast_period`, `slow_period` | `backend/backtesting/strategies/sma_cross.py` |
| Grid | `grid_levels`, `grid_spacing` | `backend/backtesting/strategies/grid.py` |
| DCA | `dca_order_count`, `grid_size_percent` | `backend/backtesting/strategies/dca.py` |

## 📈 Metrics Reference

### Primary Metrics

| Metric | Description | TradingView Parity |
|--------|-------------|-------------------|
| `net_profit` | Total profit in capital currency | ✅ |
| `total_return` | Return percentage | ✅ |
| `sharpe_ratio` | Risk-adjusted return (monthly) | ✅ |
| `sortino_ratio` | Downside risk-adjusted return | ✅ |
| `max_drawdown` | Peak-to-trough decline (%) | ✅ |
| `win_rate` | Winning trades / total trades | ✅ |
| `profit_factor` | Gross profit / gross loss | ✅ |

### Verification

```bash
# Run parity calibration
py -3.14 scripts/calibrate_166_metrics.py

# Compare with TradingView
# Export TV results → Compare with backtest output
```

## 🔍 Debugging Backtests

### No Trades Generated

**Check:**
1. Strategy signals are generated (`signal` column has 1/-1 values)
2. Date range has sufficient data
3. Direction filter matches signals (`long`/`short`/`both`)
4. SL/TP not too tight

### Metrics Don't Match TradingView

**Check:**
1. Commission is exactly `0.0007`
2. Same initial capital
3. Same leverage
4. Same SL/TP values
5. Data range matches exactly

### Performance Issues

**Solutions:**
- Use `NumbaEngineV2` for optimization (20-40x faster)
- Reduce date range
- Use higher timeframe
- Enable caching

## 📋 Backtest Checklist

Before running:

- [ ] Commission = `0.0007`
- [ ] Engine = `FallbackEngineV4` (or `NumbaEngineV2` for optimization)
- [ ] Date range ≤ 730 days
- [ ] Timeframe in supported list
- [ ] Strategy params validated

After running:

- [ ] Metrics calculated
- [ ] Equity curve generated
- [ ] Trades list populated
- [ ] No warnings in response

## 🧪 Testing Backtests

```python
import pytest
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4


def test_backtest_generates_positive_profit(sample_ohlcv, sample_signals):
    """Verify backtest produces expected profit."""
    engine = FallbackEngineV4(commission_rate=0.0007)
    result = engine.run(sample_ohlcv, sample_signals, initial_capital=10000.0)
    
    assert result.net_profit > 0
    assert result.total_trades > 0
    assert result.sharpe_ratio > 0


def test_backtest_commission_parity(sample_ohlcv, sample_signals):
    """Verify commission calculation matches TradingView."""
    engine = FallbackEngineV4(commission_rate=0.0007)
    result = engine.run(sample_ohlcv, sample_signals)
    
    # Commission should be ~0.07% per trade
    expected_commission_per_trade = result.trade_value * 0.0007
    actual_commission = result.commission_paid / result.total_trades
    
    assert abs(actual_commission - expected_commission_per_trade) < 0.0001
```

## 📝 Response Structure

```json
{
  "id": "uuid-string",
  "status": "completed",
  "metrics": {
    "net_profit": 1234.56,
    "total_return": 12.35,
    "sharpe_ratio": 1.45,
    "sortino_ratio": 1.82,
    "max_drawdown": -5.67,
    "win_rate": 62.5,
    "profit_factor": 1.85,
    "total_trades": 42,
    "winning_trades": 26,
    "losing_trades": 16
  },
  "trades": [
    {
      "id": 1,
      "entry_time": "2025-01-15T10:30:00Z",
      "exit_time": "2025-01-15T14:45:00Z",
      "side": "long",
      "entry_price": 42500.0,
      "exit_price": 42800.0,
      "pnl": 300.0,
      "fees": 5.95
    }
  ],
  "equity_curve": [
    {"timestamp": "...", "equity": 10000.0},
    {"timestamp": "...", "equity": 10150.0},
    ...
  ],
  "warnings": []
}
```

## 🔗 Related

- [Strategy Development](../strategy-development/) — Create strategies
- [Metrics Calculator](../metrics-calculator/) — Metric calculations
- [API Endpoint](../../api/routers/backtests.py) — Backtest API
