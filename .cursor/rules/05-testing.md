# Testing Standards

## Structure

```
tests/
├── unit/           # Fast, isolated tests
├── integration/    # Multi-component tests
├── e2e/            # End-to-end tests
└── conftest.py     # Shared fixtures
```

## Coverage Requirements

- **Minimum overall:** 80%
- **Critical modules (95%):**
    - `backend/backtesting/engines/`
    - `backend/core/metrics_calculator.py`
    - `backend/api/routers/`

## Running Tests

```bash
# Full suite
pytest tests/ -v

# With coverage
pytest tests/ --cov=backend --cov-report=term-missing

# Specific module
pytest tests/test_backtesting.py -v

# Skip slow tests
pytest tests/ -v -m "not slow"
```

## Test Naming

- File: `test_[module_name].py`
- Function: `test_[function_name]_[scenario]`
- Example: `test_rsi_calculation_with_valid_data`

## Fixtures Pattern

```python
import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Sample OHLCV data for testing"""
    n = 100
    np.random.seed(42)
    return pd.DataFrame({
        'timestamp': pd.date_range('2025-01-01', periods=n, freq='15min'),
        'open': 50000 + np.random.randn(n).cumsum() * 100,
        'high': 50000 + np.random.randn(n).cumsum() * 100 + 50,
        'low': 50000 + np.random.randn(n).cumsum() * 100 - 50,
        'close': 50000 + np.random.randn(n).cumsum() * 100,
        'volume': np.random.uniform(100, 1000, n)
    })
```

## Mock External APIs

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_bybit_fetch_with_network_error():
    with patch('backend.services.adapters.bybit.aiohttp.ClientSession') as mock:
        mock.return_value.__aenter__.return_value.get.side_effect = NetworkError

        with pytest.raises(NetworkError):
            await connector.fetch_ohlcv('BTCUSDT', '1h')
```

## Pre-Commit Checklist

- ✅ All tests pass: `pytest tests/ -v`
- ✅ Linting clean: `ruff check .`
- ✅ Format code: `ruff format .`
- ✅ No secrets in code: `git diff | grep -i "api_key\|secret"`
