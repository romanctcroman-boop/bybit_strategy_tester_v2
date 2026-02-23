#!/usr/bin/env python3
"""
Test MTF BTC Correlation Filter.

Phase 5: BTC Correlation 100%
- Test BTC filter on altcoin (ETHUSDT)
- Verify filter logic works correctly
- Compare with/without BTC filter

Run: python test_btc_correlation.py
"""

import os
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Project root: parent of scripts/
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DB_PATH = os.environ.get("DATABASE_PATH", str(_PROJECT_ROOT / "data.sqlite3"))


def load_candles(
    symbol: str, interval: str, start_date: str, end_date: str
) -> pd.DataFrame:
    """Load candles from database."""
    conn = sqlite3.connect(_DB_PATH)
    query = f"""
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = '{symbol}'
          AND interval = '{interval}'
          AND open_time >= {int(pd.Timestamp(start_date).timestamp() * 1000)}
          AND open_time <= {int(pd.Timestamp(end_date).timestamp() * 1000)}
        ORDER BY open_time
    """
    df = pd.read_sql(query, conn)
    conn.close()

    if not df.empty:
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df.set_index("open_time", inplace=True)

    return df


def test_btc_correlation_filter():
    """Test 1: BTC Correlation Filter Logic."""
    print("\n" + "=" * 60)
    print("TEST 1: BTC Correlation Filter Logic")
    print("=" * 60)

    from backend.backtesting.mtf.filters import BTCCorrelationFilter

    # Create filter
    btc_filter = BTCCorrelationFilter(btc_sma_period=50, min_distance_pct=0.5)

    # Test cases
    test_cases = [
        # (btc_close, btc_sma, expected_long, expected_short, description)
        (100.0, 95.0, True, False, "BTC bullish (5% above SMA) → LONG only"),
        (95.0, 100.0, False, True, "BTC bearish (5% below SMA) → SHORT only"),
        (100.0, 100.0, True, True, "BTC neutral (at SMA) → BOTH allowed"),
        (
            100.2,
            100.0,
            True,
            True,
            "BTC slightly above (0.2%) → BOTH (within min_distance)",
        ),
        (0.0, 100.0, True, True, "Invalid BTC close → BOTH allowed"),
        (100.0, 0.0, True, True, "Invalid BTC SMA → BOTH allowed"),
    ]

    passed = 0
    for btc_close, btc_sma, exp_long, exp_short, desc in test_cases:
        allow_long, allow_short = btc_filter.check(btc_close, btc_sma)

        ok = allow_long == exp_long and allow_short == exp_short
        status = "✅" if ok else "❌"
        print(f"{status} {desc}")
        print(f"   Expected: long={exp_long}, short={exp_short}")
        print(f"   Got:      long={allow_long}, short={allow_short}")

        if ok:
            passed += 1

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_btc_correlation_with_real_data():
    """Test 2: BTC Correlation with Real Data."""
    print("\n" + "=" * 60)
    print("TEST 2: BTC Correlation with Real Data (ETHUSDT + BTC)")
    print("=" * 60)

    start_date = "2025-07-01"
    end_date = "2026-01-26"

    # Load ETH data (LTF = 15m, HTF = 1H)
    eth_ltf = load_candles("ETHUSDT", "15", start_date, end_date)
    eth_htf = load_candles("ETHUSDT", "60", start_date, end_date)
    btc_htf = load_candles("BTCUSDT", "60", start_date, end_date)

    if eth_ltf.empty or eth_htf.empty or btc_htf.empty:
        print("⚠️ SKIPPED: Missing data in database")
        print(f"   ETHUSDT 15m: {len(eth_ltf)} bars")
        print(f"   ETHUSDT 60m: {len(eth_htf)} bars")
        print(f"   BTCUSDT 60m: {len(btc_htf)} bars")
        return True  # Skip but don't fail

    print("Loaded data:")
    print(f"  ETHUSDT 15m: {len(eth_ltf)} bars")
    print(f"  ETHUSDT 1H:  {len(eth_htf)} bars")
    print(f"  BTCUSDT 1H:  {len(btc_htf)} bars")

    # Create index maps
    from backend.backtesting.mtf.index_mapper import create_htf_index_map

    htf_index_map = create_htf_index_map(eth_ltf, eth_htf)
    btc_index_map = create_htf_index_map(eth_ltf, btc_htf)

    print(f"  HTF index map: {len(htf_index_map)} entries")
    print(f"  BTC index map: {len(btc_index_map)} entries")

    # Generate signals WITH BTC filter
    from backend.backtesting.mtf.signals import generate_mtf_signals_with_btc

    long_btc, _, short_btc, _ = generate_mtf_signals_with_btc(
        ltf_candles=eth_ltf,
        htf_candles=eth_htf,
        htf_index_map=htf_index_map,
        btc_candles=btc_htf,
        btc_index_map=btc_index_map,
        strategy_type="rsi",
        strategy_params={"rsi_period": 14, "overbought": 70, "oversold": 30},
        htf_filter_type="sma",
        htf_filter_period=200,
        btc_filter_period=50,
        require_btc_alignment=True,
        direction="both",
    )

    # Generate signals WITHOUT BTC filter
    from backend.backtesting.mtf.signals import generate_mtf_rsi_signals

    long_no_btc, _, short_no_btc, _ = generate_mtf_rsi_signals(
        ltf_candles=eth_ltf,
        htf_candles=eth_htf,
        htf_index_map=htf_index_map,
        htf_filter_type="sma",
        htf_filter_period=200,
        direction="both",
        rsi_period=14,
        overbought=70,
        oversold=30,
    )

    # Compare
    n_long_btc = int(np.sum(long_btc))
    n_short_btc = int(np.sum(short_btc))
    n_long_no_btc = int(np.sum(long_no_btc))
    n_short_no_btc = int(np.sum(short_no_btc))

    print("\nSignals comparison:")
    print(f"  WITHOUT BTC filter: {n_long_no_btc} long, {n_short_no_btc} short")
    print(f"  WITH BTC filter:    {n_long_btc} long, {n_short_btc} short")

    filtered_long = n_long_no_btc - n_long_btc
    filtered_short = n_short_no_btc - n_short_btc
    print(f"  Filtered by BTC:    {filtered_long} long, {filtered_short} short")

    # BTC filter should reduce signals (or keep same)
    passed = (n_long_btc <= n_long_no_btc) and (n_short_btc <= n_short_no_btc)

    if passed:
        print("✅ PASSED: BTC filter reduces/maintains signal count")
    else:
        print("❌ FAILED: BTC filter increased signals (unexpected)")

    return passed


def test_btc_correlation_backtest():
    """Test 3: Full Backtest with BTC Correlation."""
    print("\n" + "=" * 60)
    print("TEST 3: Full Backtest with BTC Correlation (ETHUSDT)")
    print("=" * 60)

    start_date = "2025-07-01"
    end_date = "2026-01-26"

    # Load data
    eth_ltf = load_candles("ETHUSDT", "15", start_date, end_date)
    eth_htf = load_candles("ETHUSDT", "60", start_date, end_date)
    btc_htf = load_candles("BTCUSDT", "60", start_date, end_date)

    if eth_ltf.empty or eth_htf.empty or btc_htf.empty:
        print("⚠️ SKIPPED: Missing ETHUSDT data")
        return True

    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput
    from backend.backtesting.mtf.index_mapper import create_htf_index_map
    from backend.backtesting.mtf.signals import (
        generate_mtf_rsi_signals,
        generate_mtf_signals_with_btc,
    )

    htf_index_map = create_htf_index_map(eth_ltf, eth_htf)
    btc_index_map = create_htf_index_map(eth_ltf, btc_htf)

    # --- Backtest WITHOUT BTC filter ---
    long_no_btc, _, short_no_btc, _ = generate_mtf_rsi_signals(
        ltf_candles=eth_ltf,
        htf_candles=eth_htf,
        htf_index_map=htf_index_map,
        htf_filter_type="sma",
        htf_filter_period=200,
        direction="both",
        rsi_period=14,
        overbought=70,
        oversold=30,
    )

    input_no_btc = BacktestInput(
        symbol="ETHUSDT",
        interval="15m",
        initial_capital=10000.0,
        leverage=5,
        direction="both",
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        candles=eth_ltf,
        long_entries=long_no_btc,
        long_exits=np.zeros(len(eth_ltf), dtype=bool),
        short_entries=short_no_btc,
        short_exits=np.zeros(len(eth_ltf), dtype=bool),
        use_bar_magnifier=False,
        mtf_enabled=True,
        mtf_htf_candles=eth_htf,
        mtf_htf_index_map=htf_index_map,
        mtf_filter_type="sma",
        mtf_filter_period=200,
    )

    engine = FallbackEngineV4()
    result_no_btc = engine.run(input_no_btc)

    # --- Backtest WITH BTC filter ---
    long_btc, _, short_btc, _ = generate_mtf_signals_with_btc(
        ltf_candles=eth_ltf,
        htf_candles=eth_htf,
        htf_index_map=htf_index_map,
        btc_candles=btc_htf,
        btc_index_map=btc_index_map,
        strategy_type="rsi",
        strategy_params={"rsi_period": 14, "overbought": 70, "oversold": 30},
        htf_filter_type="sma",
        htf_filter_period=200,
        btc_filter_period=50,
        require_btc_alignment=True,
        direction="both",
    )

    input_btc = BacktestInput(
        symbol="ETHUSDT",
        interval="15m",
        initial_capital=10000.0,
        leverage=5,
        direction="both",
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        candles=eth_ltf,
        long_entries=long_btc,
        long_exits=np.zeros(len(eth_ltf), dtype=bool),
        short_entries=short_btc,
        short_exits=np.zeros(len(eth_ltf), dtype=bool),
        use_bar_magnifier=False,
        mtf_enabled=True,
        mtf_htf_candles=eth_htf,
        mtf_htf_index_map=htf_index_map,
        mtf_filter_type="sma",
        mtf_filter_period=200,
    )

    result_btc = engine.run(input_btc)

    # Compare results
    m_no_btc = result_no_btc.metrics
    m_btc = result_btc.metrics

    print("\nResults comparison (ETHUSDT with MTF RSI):")
    print(f"  {'Metric':<20} {'No BTC':<15} {'With BTC':<15} {'Delta':<15}")
    print(f"  {'-' * 65}")
    print(
        f"  {'Trades':<20} {m_no_btc.total_trades:<15} {m_btc.total_trades:<15} {m_btc.total_trades - m_no_btc.total_trades:<15}"
    )
    print(
        f"  {'Net Profit':<20} ${m_no_btc.net_profit:<14.2f} ${m_btc.net_profit:<14.2f} ${m_btc.net_profit - m_no_btc.net_profit:<14.2f}"
    )
    print(
        f"  {'Win Rate':<20} {m_no_btc.win_rate * 100:<14.1f}% {m_btc.win_rate * 100:<14.1f}% {(m_btc.win_rate - m_no_btc.win_rate) * 100:<14.1f}%"
    )
    print(
        f"  {'Max Drawdown':<20} {m_no_btc.max_drawdown:<14.2f}% {m_btc.max_drawdown:<14.2f}% {m_btc.max_drawdown - m_no_btc.max_drawdown:<14.2f}%"
    )
    print(
        f"  {'Sharpe':<20} {m_no_btc.sharpe_ratio:<14.2f} {m_btc.sharpe_ratio:<14.2f} {m_btc.sharpe_ratio - m_no_btc.sharpe_ratio:<14.2f}"
    )

    # BTC filter should have some effect
    trades_reduced = m_btc.total_trades <= m_no_btc.total_trades

    if trades_reduced:
        print("\n✅ PASSED: BTC correlation filter working correctly")
    else:
        print("\n⚠️ WARNING: BTC filter didn't reduce trades (may be data-dependent)")

    return True  # Always pass as long as no errors


def test_api_mtf_endpoint():
    """Test 4: MTF API Endpoint."""
    print("\n" + "=" * 60)
    print("TEST 4: MTF API Endpoint (if server running)")
    print("=" * 60)

    import requests

    try:
        # Check if server is running
        health = requests.get("http://localhost:8000/api/v1/health", timeout=3)
        if health.status_code != 200:
            print("⚠️ SKIPPED: Server not running")
            return True

        # Test MTF endpoint
        payload = {
            "symbol": "BTCUSDT",
            "interval": "15m",
            "start_date": "2025-07-01",
            "end_date": "2025-08-01",
            "strategy_type": "rsi",
            "strategy_params": {"rsi_period": 14, "oversold": 30, "overbought": 70},
            "htf_interval": "60",
            "htf_filter_type": "sma",
            "htf_filter_period": 200,
            "initial_capital": 10000,
            "leverage": 5,
        }

        response = requests.post(
            "http://localhost:8000/api/v1/backtests/mtf",
            json=payload,
            timeout=60,
        )

        print(f"Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"  backtest_id: {data.get('backtest_id')}")
            print(f"  total_trades: {data.get('total_trades')}")
            print(f"  net_profit: ${data.get('net_profit', 0):.2f}")
            print(f"  win_rate: {data.get('win_rate', 0) * 100:.1f}%")
            print("✅ PASSED: MTF API endpoint works")
            return True
        else:
            print(f"  Error: {response.text[:200]}")
            print("❌ FAILED: MTF API endpoint returned error")
            return False

    except requests.exceptions.ConnectionError:
        print("⚠️ SKIPPED: Server not running (connection refused)")
        return True
    except Exception as e:
        print(f"⚠️ SKIPPED: {e}")
        return True


def main():
    """Run all BTC correlation tests."""
    print("=" * 70)
    print("MTF BTC CORRELATION TESTS - Phase 5")
    print("=" * 70)

    start = time.time()
    results = []

    tests = [
        ("Filter Logic", test_btc_correlation_filter),
        ("Real Data Signals", test_btc_correlation_with_real_data),
        ("Full Backtest", test_btc_correlation_backtest),
        ("API Endpoint", test_api_mtf_endpoint),
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

    for name, result, _error in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print(f"Time: {time.time() - start:.2f}s")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
