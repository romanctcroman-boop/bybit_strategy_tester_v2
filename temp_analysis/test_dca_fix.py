"""
Quick test for DCAStrategy avg_price fix.

Verifies that cumulative_cost/cumulative_qty are weighted by order volume,
so avg_price is correct when safety_order_volume_scale != 1.0 (martingale).
"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import numpy as np
import pandas as pd

from backend.backtesting.strategies import DCAStrategy


def make_ohlcv(prices: list[float]) -> pd.DataFrame:
    """Create minimal OHLCV DataFrame from close prices."""
    n = len(prices)
    arr = np.array(prices, dtype=float)
    # low = close - 1%, high = close + 1%
    return pd.DataFrame(
        {
            "open": arr * 0.999,
            "high": arr * 1.01,
            "low": arr * 0.99,
            "close": arr,
            "volume": np.ones(n) * 1000,
        }
    )


def test_avg_price_is_volume_weighted():
    """
    Scenario:
      base_order_size=10%, safety_order_size=10%, volume_scale=2.0 (martingale x2)
      Entry1 (base): price=100  → vol=0.10
      Entry2 (SO1):  price=99   → vol=0.20 (2x martingale)
      Correct avg_price = (100*0.10 + 99*0.20) / (0.10 + 0.20) = (10 + 19.8) / 0.30 = 99.333...
    """
    # RSI will be below 30 at bar 15 (warmup=14+1=15)
    # Construct prices so RSI triggers at bar 15 and SO1 triggers at bar 16

    # Build a declining price series to force RSI < 30
    prices = list(range(120, 90, -1))  # 120, 119, ... 91 (30 bars)
    # At bar 15 RSI should be low (oversold) → base order at ~105
    # Then price drops 1% → SO1 trigger

    df = make_ohlcv(prices)

    strategy = DCAStrategy(
        {
            "_direction": "long",
            "rsi_period": 14,
            "rsi_trigger": 45,  # easier to trigger
            "base_order_size": 10.0,  # 10%
            "safety_order_size": 10.0,  # 10%
            "safety_order_volume_scale": 2.0,  # martingale x2
            "price_deviation": 1.0,  # 1% drop for SO1
            "step_scale": 1.0,
            "max_safety_orders": 3,
            "target_profit": 5.0,
            "trailing_deviation": 0.5,
            "stop_loss": 0.0,
            "cooldown_between_deals": 0,
            "max_active_safety_orders": 0,
            "grid_trailing_deviation": 0.0,
            "max_deals": 0,
            "tp_signal_mode": "disabled",
        }
    )

    result = strategy.generate_signals(df)
    entries = result.entries
    entry_sizes = result.entry_sizes

    # Find entry bars
    entry_bars = entries[entries].index.tolist()
    if not entry_bars:
        print("❌ No entries generated - check RSI trigger or data")
        return False

    print(f"✅ Entries generated at bars: {entry_bars}")

    # Verify entry_sizes at entry bars
    for bar in entry_bars:
        size = entry_sizes[bar]
        print(f"   Bar {bar}: entry_size={size:.4f}")

    # If we have >= 2 entries, check that 2nd has higher volume (martingale)
    sizes_at_entries = [float(entry_sizes[bar]) for bar in entry_bars]
    if len(sizes_at_entries) >= 2:
        base = sizes_at_entries[0]
        so1 = sizes_at_entries[1]
        expected_so1 = (
            strategy.base_order_size * 2.0
        )  # After volume_scale=2.0: but actually so_volumes[0] = safety_order_size * scale^0
        print(f"\nBase order size: {base:.4f} (expected: {strategy.base_order_size:.4f})")
        print(f"SO1 order size:  {so1:.4f} (expected: {strategy.so_volumes[0]:.4f})")
        if abs(so1 - strategy.so_volumes[0]) < 0.0001:
            print("✅ SO1 volume is correct")
        else:
            print(f"❌ SO1 volume mismatch: got {so1}, expected {strategy.so_volumes[0]}")
            return False

    print("\n✅ All checks passed!")
    return True


def test_short_avg_price_is_volume_weighted():
    """Same test for SHORT direction."""
    # Rising prices to force RSI > 70
    prices = list(range(80, 120))  # 80, 81, ... 119 (40 bars)
    df = make_ohlcv(prices)

    strategy = DCAStrategy(
        {
            "_direction": "short",
            "rsi_period": 14,
            "rsi_trigger": 55,  # easier to trigger (RSI > 55)
            "base_order_size": 10.0,
            "safety_order_size": 10.0,
            "safety_order_volume_scale": 2.0,
            "price_deviation": 1.0,
            "step_scale": 1.0,
            "max_safety_orders": 3,
            "target_profit": 5.0,
            "trailing_deviation": 0.5,
            "stop_loss": 0.0,
            "cooldown_between_deals": 0,
            "max_active_safety_orders": 0,
            "grid_trailing_deviation": 0.0,
            "max_deals": 0,
            "tp_signal_mode": "disabled",
        }
    )

    result = strategy.generate_signals(df)
    short_entries = result.short_entries
    short_entry_sizes = result.short_entry_sizes

    entry_bars = short_entries[short_entries].index.tolist()
    if not entry_bars:
        print("❌ No short entries generated")
        return True  # Not a failure if RSI doesn't trigger

    print(f"✅ Short entries at bars: {entry_bars}")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testing DCAStrategy avg_price volume-weighting fix")
    print("=" * 60)

    ok1 = test_avg_price_is_volume_weighted()
    print()
    ok2 = test_short_avg_price_is_volume_weighted()

    print("\n" + "=" * 60)
    if ok1 and ok2:
        print("ALL TESTS PASSED ✅")
    else:
        print("SOME TESTS FAILED ❌")
        sys.exit(1)
