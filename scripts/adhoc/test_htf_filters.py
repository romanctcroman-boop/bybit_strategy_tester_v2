"""
Test HTF Filters: SuperTrend, Ichimoku, MACD

Tests Phase 2-4: Additional HTF filter implementations
"""

import sys
import time
from pathlib import Path

import numpy as np

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_supertrend_filter():
    """Test 1: SuperTrend Filter."""
    print("\n" + "=" * 60)
    print("TEST 1: SuperTrend Filter")
    print("=" * 60)

    from backend.backtesting.mtf.filters import (
        SuperTrendFilter,
        calculate_supertrend,
    )

    # Create synthetic price data
    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)

    # Calculate SuperTrend
    st_values, trend = calculate_supertrend(high, low, close, period=10, multiplier=3.0)

    print(f"Data points: {n}")
    print(f"SuperTrend calculated: {np.sum(~np.isnan(st_values))} valid values")
    print(f"Bullish periods: {np.sum(trend == 1)}")
    print(f"Bearish periods: {np.sum(trend == -1)}")

    # Test filter
    filter = SuperTrendFilter(period=10, multiplier=3.0)

    test_cases = [
        (1, "BULLISH trend", True, False),
        (-1, "BEARISH trend", False, True),
        (0, "NEUTRAL (no trend)", True, True),
    ]

    passed = 0
    for trend_val, desc, exp_long, exp_short in test_cases:
        allow_long, allow_short = filter.check(100.0, 95.0, trend=trend_val)
        ok = allow_long == exp_long and allow_short == exp_short
        status = "✅" if ok else "❌"
        print(f"{status} {desc}: long={allow_long}, short={allow_short}")
        if ok:
            passed += 1

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_ichimoku_filter():
    """Test 2: Ichimoku Cloud Filter."""
    print("\n" + "=" * 60)
    print("TEST 2: Ichimoku Cloud Filter")
    print("=" * 60)

    from backend.backtesting.mtf.filters import (
        IchimokuFilter,
        calculate_ichimoku,
    )

    # Create synthetic price data
    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)

    # Calculate Ichimoku
    ichimoku = calculate_ichimoku(high, low, tenkan_period=9, kijun_period=26, senkou_b_period=52)

    print(f"Data points: {n}")
    print(f"Tenkan valid: {np.sum(~np.isnan(ichimoku['tenkan']))}")
    print(f"Kijun valid: {np.sum(~np.isnan(ichimoku['kijun']))}")
    print(f"Senkou A valid: {np.sum(~np.isnan(ichimoku['senkou_a']))}")
    print(f"Senkou B valid: {np.sum(~np.isnan(ichimoku['senkou_b']))}")

    # Test filter
    filter = IchimokuFilter()

    test_cases = [
        # (close, senkou_a, senkou_b, expected_long, expected_short, desc)
        (110.0, 100.0, 95.0, True, False, "Above cloud"),
        (90.0, 100.0, 95.0, False, True, "Below cloud"),
        (97.0, 100.0, 95.0, True, True, "Inside cloud (allow_in_cloud=True)"),
        (100.0, np.nan, np.nan, True, True, "No valid cloud data"),
    ]

    passed = 0
    for close_val, sa, sb, exp_long, exp_short, desc in test_cases:
        allow_long, allow_short = filter.check(close_val, 0, senkou_a=sa, senkou_b=sb)
        ok = allow_long == exp_long and allow_short == exp_short
        status = "✅" if ok else "❌"
        print(f"{status} {desc}: long={allow_long}, short={allow_short}")
        if ok:
            passed += 1

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_macd_filter():
    """Test 3: MACD Filter."""
    print("\n" + "=" * 60)
    print("TEST 3: MACD Filter")
    print("=" * 60)

    from backend.backtesting.mtf.filters import (
        MACDFilter,
        calculate_macd,
    )

    # Create synthetic price data
    np.random.seed(42)
    n = 50
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)

    # Calculate MACD
    macd_line, signal_line, histogram = calculate_macd(close, fast_period=12, slow_period=26, signal_period=9)

    print(f"Data points: {n}")
    print(f"MACD valid: {np.sum(~np.isnan(macd_line))}")
    print(f"Signal valid: {np.sum(~np.isnan(signal_line))}")
    print(f"Histogram valid: {np.sum(~np.isnan(histogram))}")

    # Test filter
    filter = MACDFilter()

    test_cases = [
        # (macd, signal, expected_long, expected_short, desc)
        (0.5, 0.3, True, False, "MACD above signal (bullish)"),
        (0.3, 0.5, False, True, "MACD below signal (bearish)"),
        (0.5, 0.5, True, True, "MACD equals signal (neutral)"),
        (np.nan, np.nan, True, True, "No valid MACD data"),
    ]

    passed = 0
    for macd_val, signal_val, exp_long, exp_short, desc in test_cases:
        allow_long, allow_short = filter.check(0, 0, macd=macd_val, signal=signal_val)
        ok = allow_long == exp_long and allow_short == exp_short
        status = "✅" if ok else "❌"
        print(f"{status} {desc}: long={allow_long}, short={allow_short}")
        if ok:
            passed += 1

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_filters_with_real_data():
    """Test 4: All Filters with Real Data."""
    print("\n" + "=" * 60)
    print("TEST 4: All Filters with Real Data (BTCUSDT)")
    print("=" * 60)

    import pandas as pd
    from sqlalchemy import create_engine, text

    # Load real data
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    engine = create_engine(f"sqlite:///{PROJECT_ROOT / 'data.sqlite3'}")
    query = """
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '60'
        ORDER BY open_time DESC
        LIMIT 500
    """
    df = pd.read_sql(query, engine)
    df = df.iloc[::-1].reset_index(drop=True)  # Reverse to chronological order

    if df.empty:
        print("⚠️ SKIPPED: No BTCUSDT 1H data")
        return True

    print(f"Loaded {len(df)} candles")

    high = df["high_price"].values.astype(float)
    low = df["low_price"].values.astype(float)
    close = df["close_price"].values.astype(float)

    # Test all filter calculations
    from backend.backtesting.mtf.filters import (
        IchimokuFilter,
        MACDFilter,
        SuperTrendFilter,
        calculate_ichimoku,
        calculate_macd,
        calculate_supertrend,
    )

    # 1. SuperTrend
    st_values, st_trend = calculate_supertrend(high, low, close, period=10, multiplier=3.0)
    st_bullish = np.sum(st_trend == 1)
    st_bearish = np.sum(st_trend == -1)
    print(f"\n📈 SuperTrend: {st_bullish} bullish, {st_bearish} bearish periods")

    # 2. Ichimoku
    ichimoku = calculate_ichimoku(high, low, tenkan_period=9, kijun_period=26, senkou_b_period=52)
    valid_clouds = np.sum(~np.isnan(ichimoku["senkou_a"]) & ~np.isnan(ichimoku["senkou_b"]))
    print(f"🌩️ Ichimoku: {valid_clouds} valid cloud data points")

    # 3. MACD
    macd_line, signal_line, histogram = calculate_macd(close)
    macd_bullish = np.sum(macd_line > signal_line)
    macd_bearish = np.sum(macd_line < signal_line)
    print(f"📊 MACD: {macd_bullish} bullish, {macd_bearish} bearish periods")

    # Test filter decisions on last 10 bars
    print("\nLast 10 bars filter decisions:")
    st_filter = SuperTrendFilter(period=10, multiplier=3.0)
    ich_filter = IchimokuFilter()
    macd_filter = MACDFilter()

    for i in range(-10, 0):
        idx = len(df) + i
        c = close[idx]

        # SuperTrend
        st_long, st_short = st_filter.check(c, st_values[idx], trend=st_trend[idx])
        st_dir = "LONG" if st_long and not st_short else ("SHORT" if st_short and not st_long else "BOTH")

        # Ichimoku
        ich_long, ich_short = ich_filter.check(
            c, 0, senkou_a=ichimoku["senkou_a"][idx], senkou_b=ichimoku["senkou_b"][idx]
        )
        ich_dir = "LONG" if ich_long and not ich_short else ("SHORT" if ich_short and not ich_long else "BOTH")

        # MACD
        macd_long, macd_short = macd_filter.check(0, 0, macd=macd_line[idx], signal=signal_line[idx])
        macd_dir = "LONG" if macd_long and not macd_short else ("SHORT" if macd_short and not macd_long else "BOTH")

        print(f"  Bar {i}: ST={st_dir:5s}, ICH={ich_dir:5s}, MACD={macd_dir:5s}")

    print("\n✅ PASSED: All filters calculated successfully")
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("HTF FILTERS TESTS - SuperTrend, Ichimoku, MACD")
    print("=" * 70)

    start = time.time()

    results = {
        "SuperTrend Filter": test_supertrend_filter(),
        "Ichimoku Filter": test_ichimoku_filter(),
        "MACD Filter": test_macd_filter(),
        "Real Data Integration": test_filters_with_real_data(),
    }

    elapsed = time.time() - start

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    all_passed = True
    for name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    total_passed = sum(results.values())
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")
    print(f"Time: {elapsed:.2f}s")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
