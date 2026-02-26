---
name: Documentation
description: "Generate comprehensive documentation including docstrings, README files, and API documentation."
---

# Documentation Skill for Qwen

## Overview

Create clear, comprehensive documentation that helps developers understand and use the codebase effectively.

## Documentation Types

### 1. Code Docstrings

#### Function Docstrings (Google Style)

```python
def calculate_portfolio_metrics(
    trades: list[Trade],
    initial_capital: float,
    risk_free_rate: float = 0.02
) -> PortfolioMetrics:
    """
    Calculate comprehensive portfolio performance metrics.
    
    Args:
        trades: List of executed trades with entry/exit prices
        initial_capital: Starting capital amount (e.g., 10000.0)
        risk_free_rate: Annual risk-free rate for Sharpe calculation (default: 2%)
    
    Returns:
        PortfolioMetrics object containing:
        - total_return: Overall return percentage
        - sharpe_ratio: Risk-adjusted return metric
        - max_drawdown: Maximum peak-to-trough decline
        - win_rate: Percentage of winning trades
    
    Raises:
        ValueError: If trades list is empty or capital <= 0
        ZeroDivisionError: If no trades executed
    
    Example:
        >>> trades = [Trade(...), Trade(...)]
        >>> metrics = calculate_portfolio_metrics(trades, 10000.0)
        >>> print(f"Sharpe: {metrics.sharpe_ratio:.2f}")
        Sharpe: 1.45
    
    Note:
        Uses MONTHLY returns for Sharpe ratio calculation (TradingView compatible).
        Commission is already deducted from trade PnL.
    
    See Also:
        calculate_sharpe_ratio: Detailed Sharpe calculation
        calculate_sortino_ratio: Downside risk-adjusted metric
    """
    # Implementation
```

#### Class Docstrings

```python
class BacktestEngine:
    """
    High-performance backtesting engine for trading strategy evaluation.
    
    This engine executes trading strategies on historical OHLCV data,
    simulating real-world trading conditions including:
    - Commission fees (default: 0.07% per trade)
    - Slippage modeling
    - Position sizing and leverage
    - Stop-loss and take-profit orders
    - Pyramiding (multiple concurrent positions)
    
    Attributes:
        commission_rate: Commission per trade (default: 0.0007 = 0.07%)
        initial_capital: Starting capital for backtest
        leverage: Position leverage (1.0-125.0)
        direction: Trading direction ('long', 'short', or 'both')
    
    Methods:
        run: Execute backtest on given data with strategy signals
        reset: Clear engine state for new backtest
        get_trades: Retrieve list of executed trades
    
    Example:
        >>> engine = BacktestEngine(commission_rate=0.0007)
        >>> result = engine.run(
        ...     data=ohlcv_df,
        ...     signals=signals_df,
        ...     initial_capital=10000.0
        ... )
        >>> print(f"Net profit: {result.net_profit:.2f}")
    
    Note:
        This is the gold standard engine (FallbackEngineV4).
        All other engines must maintain 100% parity with this implementation.
    
    See Also:
        NumbaEngineV2: JIT-compiled version for optimization (20-40x faster)
        MetricsCalculator: Centralized metric calculations
    """
    
    def __init__(self, config: BacktestConfig):
        """
        Initialize backtest engine with configuration.
        
        Args:
            config: Complete backtest configuration including:
                - symbol: Trading pair (e.g., 'BTCUSDT')
                - interval: Candle timeframe (e.g., '15', '1h', 'D')
                - commission_rate: Fee per trade (0.0007 = 0.07%)
                - initial_capital: Starting capital
        """
```

#### Module Docstrings

```python
"""
Backtesting Engine Module

Provides high-performance backtesting engines for trading strategy evaluation.

Engines:
    FallbackEngineV4: Gold standard, pure Python implementation
    NumbaEngineV2: JIT-compiled for 20-40x speedup (optimization)
    DCAEngine: Dollar-cost averaging strategy support
    GPUEngineV2: CUDA-accelerated (deprecated, use Numba)

Example:
    from backend.backtesting.engine import BacktestEngine
    from backend.backtesting.models import BacktestConfig
    
    config = BacktestConfig(
        symbol='BTCUSDT',
        interval='15',
        initial_capital=10000.0,
        commission_rate=0.0007
    )
    
    engine = BacktestEngine(config)
    result = engine.run(data, signals)

Architecture:
    OHLCV Data → Strategy Signals → Engine Execution → Metrics Calculation
    
    All engines maintain 100% bit-level parity for comparable results.

See Also:
    backend.core.metrics_calculator: Metric calculations
    backend.backtesting.strategies: Strategy implementations
"""
```

### 2. README Documentation

#### Module README

```markdown
# Backtesting Module

High-performance backtesting system for cryptocurrency trading strategies.

## Overview

The backtesting module provides:

- **Multiple engines**: Fallback (accuracy), Numba (speed), DCA (strategies)
- **TradingView parity**: 166 metrics matching TradingView calculations
- **Strategy support**: Built-in strategies + custom strategy builder
- **Risk management**: SL/TP, trailing stops, position sizing

## Quick Start

```python
from backend.backtesting import BacktestEngine, BacktestConfig

config = BacktestConfig(
    symbol='BTCUSDT',
    interval='15',
    start_date='2025-01-01',
    end_date='2025-02-01',
    initial_capital=10000.0,
    commission_rate=0.0007  # 0.07% - DO NOT CHANGE
)

engine = BacktestEngine(config)
result = engine.run(data, signals)
print(f"Net profit: {result.net_profit:.2f}")
```

## Architecture

```
┌─────────────────┐
│  OHLCV Data     │
│  (DataService)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Strategy      │
│  (generate_signals) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Engine       │
│ (Fallback/Numba)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Metrics       │
│ (Calculator)    │
└─────────────────┘
```

## Engines

| Engine | Speed | Use Case | Parity |
|--------|-------|----------|--------|
| FallbackEngineV4 | 1x | Single backtests | 100% (gold standard) |
| NumbaEngineV2 | 20-40x | Optimization | 100% |
| DCAEngine | 1x | DCA strategies | 100% |

## Critical Constants

```python
# NEVER change without approval
COMMISSION_RATE = 0.0007  # 0.07% TradingView parity
DATA_START_DATE = datetime(2025, 1, 1)
MAX_BACKTEST_DAYS = 730  # 2 years
```

## Testing

```bash
# Run backtest tests
pytest tests/backend/backtesting/test_engine.py -v

# Parity tests
pytest tests/backend/backtesting/test_strategy_builder_parity.py -v

# With coverage
pytest tests/backend/backtesting/ --cov=backend/backtesting
```

## See Also

- [Strategy Builder](../strategy_builder/README.md)
- [Metrics Calculator](../../core/metrics_calculator/README.md)
- [API Documentation](../../api/README.md)
```

### 3. API Documentation

#### Endpoint Documentation

```markdown
## POST /api/v1/backtests/

Run a strategy backtest on historical data.

### Request

```json
{
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
}
```

### Response

```json
{
  "id": "uuid-string",
  "status": "completed",
  "metrics": {
    "net_profit": 1234.56,
    "total_return": 12.35,
    "sharpe_ratio": 1.45,
    "max_drawdown": -5.67,
    "win_rate": 62.5,
    "total_trades": 42
  },
  "trades": [...],
  "equity_curve": [...]
}
```

### Error Codes

| Code | Meaning |
|------|---------|
| 400 | Invalid parameters (check date range, strategy params) |
| 404 | Strategy type not found |
| 500 | Internal error (check logs) |

### Example (curl)

```bash
curl -X POST http://localhost:8000/api/v1/backtests/ \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "interval": "15",
    "start_date": "2025-01-01",
    "end_date": "2025-02-01",
    "strategy_type": "rsi",
    "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
    "initial_capital": 10000.0
  }'
```
```

### 4. CHANGELOG Entry

```markdown
## [Unreleased]

### Added

- New feature: [description] ([#issue](link))
- New endpoint: `POST /api/v1/[endpoint]` for [purpose]
- New strategy: [Strategy Name] - [brief description]

### Changed

- [Component] now [what changed] for [reason]
- Updated [dependency] to version X.Y.Z

### Fixed

- Bug: [description of bug] - [fix summary]
- Issue with [component] causing [symptom]

### Deprecated

- [Feature] is deprecated, use [replacement] instead
- Will be removed in version X.Y.Z

### Removed

- [Feature] removed (use [alternative])
- Support for [old version/feature]

### Security

- Fixed vulnerability: [description]
- Added [security measure]
```

## Documentation Standards

### Writing Style

- ✅ Use clear, concise language
- ✅ Include code examples
- ✅ Explain WHY, not just WHAT
- ✅ Link related documents
- ✅ Use consistent terminology

### Formatting

- Use `code` formatting for:
  - Function names: `calculate_metrics()`
  - Variables: `commission_rate`
  - Files: `backend/backtesting/engine.py`
  - Values: `0.0007`

- Use **bold** for:
  - Important concepts
  - Section headers
  - Emphasis on critical points

- Use *italics* for:
  - Terminology introductions
  - Subtle emphasis

### Code Examples

```python
# ✅ GOOD: Complete, runnable example
from backend.backtesting import BacktestEngine

engine = BacktestEngine(commission_rate=0.0007)
result = engine.run(data, signals)
print(f"Profit: {result.net_profit:.2f}")

# ❌ BAD: Incomplete, unclear
engine = Engine()  # What engine? What config?
result = engine.run(data)  # What data?
```

## Documentation Checklist

Before committing documentation:

- [ ] Code examples are complete and runnable
- [ ] All public functions have docstrings
- [ ] Parameters and return values documented
- [ ] Edge cases mentioned
- [ ] Links to related docs included
- [ ] CHANGELOG.md updated
- [ ] No typos or grammatical errors
- [ ] Consistent formatting throughout

## Post-Documentation

After writing documentation:

1. **Verify examples work:**
   ```bash
   python -c "from backend.api.app import app; print('OK')"
   ```

2. **Check links:**
   - All internal links resolve
   - External links are valid

3. **Update index:**
   - Add to table of contents
   - Update navigation if needed

4. **Commit:**
   ```bash
   git commit -m "docs: add documentation for [feature]"
   ```
