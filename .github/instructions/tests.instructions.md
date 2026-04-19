---
applyTo: "**/tests/**/*.py"
---

# Testing Rules for Bybit Strategy Tester

## Structure

```
tests/
├── conftest.py              # Root fixtures
├── backend/
│   ├── backtesting/         # Engine, MTF, strategy builder parity
│   ├── api/                 # API router tests
│   ├── agents/              # 40+ agent system tests
│   ├── services/            # Service layer tests
│   └── core/                # MetricsCalculator, indicators
├── ai_agents/               # 56+ divergence + AI agent tests
├── backtesting/             # GPU, market regime tests
├── integration/             # Multi-component / DB / Redis tests
├── e2e/                     # End-to-end tests
├── chaos/                   # Chaos engineering tests
├── frontend/                # Frontend smoke tests
└── test_*.py                # Root-level tests
```

## Naming Convention

- File: `test_[module_name].py`
- Function: `test_[function_name]_[scenario]`
- Example: `test_rsi_calculation_with_valid_data`
- Class (optional): `TestClassName`

## Fixtures

```python
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Sample OHLCV data for testing (100 candles)"""
    np.random.seed(42)
    n = 100
    base_price = 50000.0

    timestamps = pd.date_range(
        start='2025-01-01',
        periods=n,
        freq='15min',
        tz='UTC'
    )

    # Generate realistic price movement
    returns = np.random.randn(n) * 0.002  # 0.2% std
    prices = base_price * np.cumprod(1 + returns)

    return pd.DataFrame({
        'timestamp': timestamps,
        'open': prices * (1 + np.random.randn(n) * 0.001),
        'high': prices * (1 + abs(np.random.randn(n)) * 0.002),
        'low': prices * (1 - abs(np.random.randn(n)) * 0.002),
        'close': prices,
        'volume': np.random.uniform(100, 1000, n)
    })

@pytest.fixture
def sample_strategy_params() -> dict:
    """Default strategy parameters for testing"""
    return {
        'rsi_period': 14,
        'rsi_overbought': 70,
        'rsi_oversold': 30,
        'stop_loss': 0.02,
        'take_profit': 0.04
    }

@pytest.fixture
def backtest_config() -> dict:
    """Standard backtest configuration"""
    return {
        'initial_capital': 10000.0,
        'commission_rate': 0.0007,  # 0.07% - TradingView parity
        'leverage': 1,
        'position_size': 1.0
    }
```

## Test Coverage Requirements

| Module Category    | Minimum Coverage                                                                             |
| ------------------ | -------------------------------------------------------------------------------------------- |
| **Critical (95%)** | `backend/backtesting/engines/`, `backend/core/metrics_calculator.py`, `backend/api/routers/` |
| **Medium (85%)**   | `backend/services/`, `backend/backtesting/strategies.py`                                     |
| **Standard (80%)** | Everything else                                                                              |

## Test Patterns

### Unit Test

```python
import pytest
from backend.backtesting.strategies import RSIStrategy, SignalResult

class TestRSIStrategy:
    """Unit tests for RSI strategy"""

    def test_init_with_valid_params(self):
        """Test strategy initialization"""
        strategy = RSIStrategy({"period": 14, "oversold": 30, "overbought": 70})
        assert strategy.params['period'] == 14

    def test_init_missing_params_raises_error(self):
        """Test that missing params raises ValueError"""
        with pytest.raises(ValueError):
            RSIStrategy({})

    def test_generate_signals_returns_signal_result(self, sample_ohlcv):
        """Test signal generation output type — must be SignalResult, NOT DataFrame"""
        strategy = RSIStrategy({"period": 14, "oversold": 30, "overbought": 70})
        result = strategy.generate_signals(sample_ohlcv)

        # ✅ Correct: check for SignalResult
        assert isinstance(result, SignalResult)
        assert hasattr(result, "entries")
        assert hasattr(result, "exits")
        assert result.entries.dtype == bool
        # ✅ len(result.entries), NOT len(result) — SignalResult has no __len__
        assert len(result.entries) == len(sample_ohlcv)
        assert not result.entries.isna().any()

    # ❌ WRONG pattern — do NOT use:
    # assert 'signal' in result.columns       ← old DataFrame API, no longer valid
    # assert set(result['signal'].unique())... ← old API
```

### Integration Test

```python
import pytest
from httpx import AsyncClient
from backend.api.app import app

class TestBacktestAPI:
    """Integration tests for backtest API"""

    @pytest.mark.asyncio
    async def test_run_backtest_success(self):
        """Test successful backtest execution"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/backtests/", json={
                "symbol": "BTCUSDT",
                "interval": "15",
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "strategy_type": "rsi",
                "strategy_params": {"period": 14}
            })

        assert response.status_code == 200
        data = response.json()
        assert "backtest_id" in data
        assert "metrics" in data
```

### Parametrized Tests

```python
import pytest

@pytest.mark.parametrize("period,overbought,oversold,expected_valid", [
    (14, 70, 30, True),
    (5, 80, 20, True),
    (0, 70, 30, False),   # Invalid period
    (14, 30, 70, False),  # Overbought < oversold
])
def test_rsi_params_validation(period, overbought, oversold, expected_valid):
    """Test RSI parameter validation"""
    params = {'rsi_period': period, 'rsi_overbought': overbought, 'rsi_oversold': oversold}

    if expected_valid:
        strategy = RSIStrategy(params)
        assert strategy is not None
    else:
        with pytest.raises(ValueError):
            RSIStrategy(params)
```

### Mock External Services

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_fetch_klines_with_mock():
    """Test kline fetching with mocked Bybit API"""
    mock_response = {
        "retCode": 0,
        "result": {"list": [[1704067200000, "42000", "42100", "41900", "42050", "100"]]}
    }

    with patch("backend.adapters.bybit.BybitClient.fetch_klines", new_callable=AsyncMock) as mock:
        mock.return_value = mock_response
        # Test code here
```

## Running Tests

```bash
# Full suite
pytest tests/ -v

# With coverage
pytest tests/ --cov=backend --cov-report=term-missing

# Specific module
pytest tests/backend/backtesting/ -v

# Run only fast tests
pytest tests/ -m "not slow"

# Parallel execution
pytest tests/ -n auto
```

## TradingView Parity Tests

```python
def test_tradingview_parity():
    """Verify indicator values match TradingView"""
    # Load reference data exported from TradingView
    # Note: create this file manually; tests/fixtures/ does not exist by default
    tv_data = pd.read_csv("tv_rsi_reference.csv")  # adjust path as needed

    # Calculate using our implementation
    our_rsi = ta.rsi(tv_data['close'], length=14)

    # Compare first 100 values (after warmup)
    np.testing.assert_array_almost_equal(
        our_rsi[14:114].values,
        tv_data['rsi'][14:114].values,
        decimal=2  # 2 decimal places tolerance
    )
```

## DO NOT

- Skip fixtures - use them for consistency
- Write tests without assertions
- Use hardcoded paths (use fixtures)
- Forget to test edge cases
- Skip async tests for async code
- Use real API calls in unit tests
