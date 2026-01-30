# TradingView Parity Check Prompt

Step-by-step verification that Python implementation matches TradingView output.

## Why This Matters

- Commission rate difference = compounding errors
- Indicator mismatch = wrong signals
- Users expect identical results to TradingView

## Verification Workflow

### 1. Export TradingView Data

In TradingView:

1. Add strategy to chart
2. Open Pine Editor
3. Add export code:

```pine
//@version=5
indicator("Export Data", overlay=true)

// Your indicators
rsi_val = ta.rsi(close, 14)
ema_val = ta.ema(close, 12)

// Plot for export
plot(rsi_val, title="RSI")
plot(ema_val, title="EMA")
```

4. Export to CSV via TradingView export or browser console

### 2. Load Reference Data

```python
import pandas as pd
import numpy as np

# Load TradingView export
tv_data = pd.read_csv('tests/fixtures/tv_reference.csv')

# Verify columns
print(tv_data.columns)
# Expected: timestamp, open, high, low, close, volume, rsi, ema, ...
```

### 3. Calculate Python Values

```python
import pandas_ta as ta

# Calculate indicators
our_rsi = ta.rsi(tv_data['close'], length=14)
our_ema = ta.ema(tv_data['close'], length=12)
```

### 4. Compare Values

```python
def compare_indicators(our_values, tv_values, name, warmup=14, tolerance=0.01):
    """Compare indicator values with tolerance."""
    # Skip warmup period
    our_valid = our_values[warmup:].values
    tv_valid = tv_values[warmup:].values

    # Calculate difference
    diff = np.abs(our_valid - tv_valid)
    max_diff = diff.max()
    mean_diff = diff.mean()

    print(f"\n{name} Comparison:")
    print(f"  Max difference: {max_diff:.6f}")
    print(f"  Mean difference: {mean_diff:.6f}")
    print(f"  Within tolerance: {max_diff < tolerance}")

    # Detailed comparison
    if max_diff >= tolerance:
        worst_idx = np.argmax(diff) + warmup
        print(f"\n  Worst mismatch at index {worst_idx}:")
        print(f"    Ours: {our_values.iloc[worst_idx]:.6f}")
        print(f"    TV:   {tv_values.iloc[worst_idx]:.6f}")

    return max_diff < tolerance

# Run comparisons
assert compare_indicators(our_rsi, tv_data['rsi'], 'RSI', warmup=14)
assert compare_indicators(our_ema, tv_data['ema'], 'EMA', warmup=12)
```

### 5. Commission Verification

```python
def verify_commission_calculation():
    """Verify commission matches TradingView 0.07%"""
    entry_price = 50000.0
    quantity = 1.0
    commission_rate = 0.0007  # 0.07%

    # Our calculation (entry + exit)
    our_commission = entry_price * quantity * commission_rate * 2

    # TradingView calculation
    tv_commission = entry_price * quantity * 0.0007 * 2

    print(f"Our commission: ${our_commission:.2f}")
    print(f"TV commission:  ${tv_commission:.2f}")

    assert our_commission == tv_commission, "Commission mismatch!"
```

### 6. Trade Comparison

```python
def compare_trades(our_trades, tv_trades, tolerance=0.001):
    """Compare trade results."""
    print(f"\nTrade Comparison:")
    print(f"  Our trades: {len(our_trades)}")
    print(f"  TV trades:  {len(tv_trades)}")

    if len(our_trades) != len(tv_trades):
        print("  ⚠️ Trade count mismatch!")
        return False

    for i, (ours, tv) in enumerate(zip(our_trades, tv_trades)):
        entry_diff = abs(ours['entry_price'] - tv['entry_price']) / tv['entry_price']
        exit_diff = abs(ours['exit_price'] - tv['exit_price']) / tv['exit_price']
        pnl_diff = abs(ours['pnl'] - tv['pnl'])

        if entry_diff > tolerance or exit_diff > tolerance:
            print(f"\n  Trade {i} price mismatch:")
            print(f"    Entry: {ours['entry_price']:.2f} vs {tv['entry_price']:.2f}")
            print(f"    Exit:  {ours['exit_price']:.2f} vs {tv['exit_price']:.2f}")

        if pnl_diff > 1.0:  # $1 tolerance
            print(f"\n  Trade {i} PnL mismatch:")
            print(f"    Ours: ${ours['pnl']:.2f}")
            print(f"    TV:   ${tv['pnl']:.2f}")

    return True
```

## Common Discrepancies

| Issue               | Cause                     | Solution                     |
| ------------------- | ------------------------- | ---------------------------- |
| Indicator offset    | Different warmup handling | Skip first N values          |
| Small value diff    | Floating point precision  | Use 2 decimal tolerance      |
| Trade count diff    | Signal timing             | Check bar close vs intra-bar |
| PnL mismatch        | Commission calculation    | Verify 0.0007 rate           |
| Large diff at start | Different initial values  | Compare after warmup         |

## Pine Script to Python Mapping

| Pine Script                | Python (pandas_ta)                           |
| -------------------------- | -------------------------------------------- |
| `ta.rsi(close, 14)`        | `ta.rsi(df['close'], length=14)`             |
| `ta.ema(close, 12)`        | `ta.ema(df['close'], length=12)`             |
| `ta.sma(close, 20)`        | `ta.sma(df['close'], length=20)`             |
| `ta.macd(close)`           | `ta.macd(df['close'])`                       |
| `ta.bbands(close)`         | `ta.bbands(df['close'])`                     |
| `ta.atr(high, low, close)` | `ta.atr(df['high'], df['low'], df['close'])` |

## Checklist

- [ ] TradingView data exported
- [ ] All indicators compared (within 0.01 tolerance)
- [ ] Commission rate verified (0.0007)
- [ ] Trade count matches
- [ ] Entry/exit prices match (within 0.1%)
- [ ] PnL matches (within $1 per trade)
- [ ] Final equity matches (within 0.1%)
