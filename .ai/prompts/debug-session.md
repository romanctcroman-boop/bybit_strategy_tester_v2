# Debug Session Prompt

Structured approach for debugging issues in the backtesting system.

## Issue Classification

### 1. Identify Issue Type

| Type                  | Symptoms                    | Common Causes                  |
| --------------------- | --------------------------- | ------------------------------ |
| **Calculation Error** | Wrong PnL, metrics mismatch | Commission, slippage, formula  |
| **Signal Error**      | No trades, wrong direction  | Indicator params, signal logic |
| **Data Error**        | NaN values, missing data    | Data loading, time zones       |
| **API Error**         | 500 errors, timeouts        | Rate limits, auth, validation  |
| **Performance**       | Slow execution              | Loops, memory, caching         |

### 2. Gather Context

```
@workspace "[error message]"
@workspace "[function name]"
```

## Debug Workflow

### Step 1: Reproduce

Create minimal reproduction:

```python
# Minimal test case
def test_reproduce_issue():
    # Setup
    data = load_test_data()
    params = {'param': value}

    # Execute
    result = function_under_test(data, params)

    # Verify
    assert result == expected  # This fails
```

### Step 2: Isolate

Add logging to narrow down:

```python
from loguru import logger

def suspicious_function(data):
    logger.debug(f"Input shape: {data.shape}")
    logger.debug(f"Input columns: {data.columns.tolist()}")

    result = calculation(data)

    logger.debug(f"Result: {result}")
    logger.debug(f"Result type: {type(result)}")

    return result
```

### Step 3: Identify Root Cause

Common checks:

```python
# Check for NaN
assert not data['close'].isna().any(), "NaN in close prices"

# Check commission
assert commission_rate == 0.0007, f"Wrong commission: {commission_rate}"

# Check signal values
assert set(signals['signal'].unique()).issubset({-1, 0, 1}), "Invalid signals"

# Check data alignment
assert len(prices) == len(signals), "Data length mismatch"
```

### Step 4: Fix and Verify

1. Make minimal fix
2. Run original test case
3. Run full test suite
4. Check for regressions

## Common Issues & Solutions

### PnL Mismatch with TradingView

```python
# Check commission calculation
expected_commission = entry_price * quantity * 0.0007 * 2  # Entry + exit
assert abs(trade.commission - expected_commission) < 0.01

# Check direction calculation
if direction == 1:  # Long
    pnl = (exit_price - entry_price) * quantity
else:  # Short
    pnl = (entry_price - exit_price) * quantity
```

### No Trades Generated

```python
# Check indicator warmup
warmup_period = max(rsi_period, ema_period)
valid_signals = signals[warmup_period:]

# Check signal thresholds
logger.debug(f"RSI range: {data['rsi'].min():.2f} - {data['rsi'].max():.2f}")
logger.debug(f"Overbought: {overbought}, Oversold: {oversold}")

# Check signal counts
logger.debug(f"Long signals: {(signals['signal'] == 1).sum()}")
logger.debug(f"Short signals: {(signals['signal'] == -1).sum()}")
```

### Memory Issues

```python
# Check DataFrame memory
logger.debug(f"Memory usage: {data.memory_usage(deep=True).sum() / 1e6:.2f} MB")

# Use chunking for large datasets
for chunk in pd.read_csv(file, chunksize=10000):
    process(chunk)

# Clear unused data
del large_dataframe
gc.collect()
```

### API Rate Limits

```python
# Add rate limit logging
logger.warning(f"Rate limited, waiting {wait_time}s")

# Check request count
logger.debug(f"Requests this minute: {len(rate_limiter.requests)}")

# Implement backoff
await asyncio.sleep(2 ** attempt)
```

## Debug Tools

```bash
# Run single test with output
pytest tests/test_file.py::test_function -v -s

# Run with debugger
pytest tests/test_file.py::test_function --pdb

# Check coverage for specific file
pytest tests/ --cov=backend/module --cov-report=term-missing

# Profile performance
python -m cProfile -s cumtime script.py
```

## Resolution Checklist

- [ ] Issue reproduced in test
- [ ] Root cause identified
- [ ] Fix implemented
- [ ] Original test passes
- [ ] Full test suite passes
- [ ] No performance regression
- [ ] Documentation updated if needed
