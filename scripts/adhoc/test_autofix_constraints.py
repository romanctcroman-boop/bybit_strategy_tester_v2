#!/usr/bin/env python3
"""
Test __post_init__ auto-fixes for BacktestInput constraints.

Tests:
1. use_bar_magnifier auto-disabled when no 1m data
2. tp_mode auto-switched to MULTI when breakeven_enabled
3. candles auto-converted to DataFrame with datetime index
4. htf_index_map auto-converted to np.int32

Run: python test_autofix_constraints.py
"""

import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# Project root: parent of scripts/
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DB_PATH = os.environ.get("DATABASE_PATH", str(_PROJECT_ROOT / "data.sqlite3"))


def test_bar_magnifier_autofix():
    """Test 1: use_bar_magnifier auto-disabled when no 1m data."""
    print("\n" + "=" * 60)
    print("TEST 1: use_bar_magnifier auto-fix")
    print("=" * 60)

    from backend.backtesting.interfaces import BacktestInput

    # Create dummy candles
    df = pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.5] * 10,
            "volume": [1000.0] * 10,
        }
    )
    df.index = pd.date_range("2025-01-01", periods=10, freq="15T")

    # Create input with use_bar_magnifier=True but NO candles_1m
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        inp = BacktestInput(
            candles=df,
            candles_1m=None,  # No 1m data!
            use_bar_magnifier=True,  # Should be auto-disabled
        )

        # Check result
        assert inp.use_bar_magnifier is False, "use_bar_magnifier should be False"

        # Check warning was raised
        bar_mag_warnings = [x for x in w if "use_bar_magnifier" in str(x.message)]
        assert len(bar_mag_warnings) > 0, "Warning should be raised"

    print("✅ PASSED: use_bar_magnifier auto-disabled when no 1m data")
    return True


def test_breakeven_tp_mode_autofix():
    """Test 2: tp_mode auto-switched to MULTI when breakeven_enabled."""
    print("\n" + "=" * 60)
    print("TEST 2: breakeven + TpMode auto-fix")
    print("=" * 60)

    from backend.backtesting.interfaces import BacktestInput, TpMode

    # Create dummy candles
    df = pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.5] * 10,
            "volume": [1000.0] * 10,
        }
    )
    df.index = pd.date_range("2025-01-01", periods=10, freq="15T")

    # Create input with breakeven_enabled=True but tp_mode=FIXED (default)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        inp = BacktestInput(
            candles=df,
            use_bar_magnifier=False,
            tp_mode=TpMode.FIXED,  # Should be auto-switched to MULTI
            breakeven_enabled=True,
        )

        # Check result
        assert inp.tp_mode == TpMode.MULTI, (
            f"tp_mode should be MULTI, got {inp.tp_mode}"
        )

        # Check warning was raised
        tp_warnings = [x for x in w if "tp_mode" in str(x.message)]
        assert len(tp_warnings) > 0, "Warning should be raised"

    print("✅ PASSED: tp_mode auto-switched to MULTI when breakeven_enabled")
    return True


def test_candles_dataframe_autofix():
    """Test 3: candles auto-converted to DataFrame with datetime index."""
    print("\n" + "=" * 60)
    print("TEST 3: candles DataFrame auto-fix")
    print("=" * 60)

    from backend.backtesting.interfaces import BacktestInput

    # Create raw list of dicts (like from API)
    raw_candles = [
        {
            "open_time": 1704067200000,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000.0,
        },
        {
            "open_time": 1704070800000,
            "open": 100.5,
            "high": 102.0,
            "low": 100.0,
            "close": 101.0,
            "volume": 1100.0,
        },
        {
            "open_time": 1704074400000,
            "open": 101.0,
            "high": 103.0,
            "low": 100.5,
            "close": 102.0,
            "volume": 1200.0,
        },
    ]

    # Create DataFrame but with integer index (no datetime)
    df_no_index = pd.DataFrame(raw_candles)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        inp = BacktestInput(
            candles=df_no_index,
            use_bar_magnifier=False,
        )

        # Check result - should have DatetimeIndex
        assert isinstance(inp.candles.index, pd.DatetimeIndex), (
            f"candles.index should be DatetimeIndex, got {type(inp.candles.index)}"
        )

    print("✅ PASSED: candles auto-converted to DataFrame with datetime index")
    return True


def test_htf_index_map_dtype_autofix():
    """Test 4: htf_index_map auto-converted to np.int32."""
    print("\n" + "=" * 60)
    print("TEST 4: htf_index_map dtype auto-fix")
    print("=" * 60)

    from backend.backtesting.interfaces import BacktestInput

    # Create dummy candles
    df = pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.5] * 10,
            "volume": [1000.0] * 10,
        }
    )
    df.index = pd.date_range("2025-01-01", periods=10, freq="15T")

    htf_df = df.iloc[::4].copy()  # Every 4th bar as HTF

    # Create htf_index_map as list (wrong type)
    htf_index_map_list = [0, 0, 0, 0, 1, 1, 1, 1, 2, 2]

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        inp = BacktestInput(
            candles=df,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map_list,  # List, should be np.int32 array
        )

        # Check result
        assert isinstance(inp.mtf_htf_index_map, np.ndarray), (
            f"mtf_htf_index_map should be ndarray, got {type(inp.mtf_htf_index_map)}"
        )
        assert inp.mtf_htf_index_map.dtype == np.int32, (
            f"dtype should be int32, got {inp.mtf_htf_index_map.dtype}"
        )

    # Also test with wrong dtype (int64)
    htf_index_map_int64 = np.array([0, 0, 0, 0, 1, 1, 1, 1, 2, 2], dtype=np.int64)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        inp2 = BacktestInput(
            candles=df,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map_int64,  # int64, should be int32
        )

        assert inp2.mtf_htf_index_map.dtype == np.int32, (
            f"dtype should be int32, got {inp2.mtf_htf_index_map.dtype}"
        )

    print("✅ PASSED: htf_index_map auto-converted to np.int32")
    return True


def test_real_backtest_with_autofixes():
    """Test 5: Real backtest runs without errors with autofixes."""
    print("\n" + "=" * 60)
    print("TEST 5: Real backtest with auto-fixes")
    print("=" * 60)

    import sqlite3

    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput

    # Load real data
    conn = sqlite3.connect(_DB_PATH)
    query = """
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '15'
        ORDER BY open_time
        LIMIT 2000
    """
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        print("⚠️ SKIPPED: No data in database")
        return True

    # Convert open_time to datetime and set as index
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df.set_index("open_time", inplace=True)

    # Generate simple signals
    n = len(df)
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    # Simple entry every 100 bars
    for i in range(100, n, 100):
        if i % 200 == 0:
            long_entries[i] = True
        else:
            short_entries[i] = True

    # Test: breakeven without explicit MULTI mode
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")

        inp = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            candles=df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=True,  # Should be auto-disabled (no 1m data)
            candles_1m=None,
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            # NO tp_mode specified - but breakeven enabled
            breakeven_enabled=True,  # Should auto-switch to MULTI
            breakeven_mode="average",
        )

    # Verify auto-fixes applied
    assert inp.use_bar_magnifier is False, "use_bar_magnifier should be False"
    assert inp.tp_mode.value == "multi", (
        f"tp_mode should be 'multi', got {inp.tp_mode.value}"
    )

    # Run backtest
    engine = FallbackEngineV4()
    result = engine.run(inp)

    print(f"  Backtest completed: {result.metrics.total_trades} trades")
    print(f"  is_valid: {result.is_valid}")
    print(f"  use_bar_magnifier: {inp.use_bar_magnifier}")
    print(f"  tp_mode: {inp.tp_mode}")

    print("✅ PASSED: Real backtest works with auto-fixes")
    return True


def main():
    """Run all auto-fix tests."""
    print("=" * 70)
    print("BACKTEST INPUT AUTO-FIX CONSTRAINT TESTS")
    print("=" * 70)

    start = time.time()
    results = []

    tests = [
        ("Bar Magnifier Auto-fix", test_bar_magnifier_autofix),
        ("Breakeven TpMode Auto-fix", test_breakeven_tp_mode_autofix),
        ("Candles DataFrame Auto-fix", test_candles_dataframe_autofix),
        ("HTF Index Map Dtype Auto-fix", test_htf_index_map_dtype_autofix),
        ("Real Backtest with Auto-fixes", test_real_backtest_with_autofixes),
    ]

    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
        except Exception as e:
            import traceback

            results.append((name, False, traceback.format_exc()))
            print(f"❌ FAILED: {name}")
            print(f"   Error: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, r, _ in results if r)
    total = len(results)

    for name, result, error in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")
        if error:
            print(f"   {error[:200]}...")

    print(f"\nTotal: {passed}/{total} tests passed")
    print(f"Time: {time.time() - start:.2f}s")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
