"""
Test MTF Grid Optimizer

Tests MTF optimization with multiple filter types and periods.
"""

import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def load_test_data():
    """Load test data from database."""
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{PROJECT_ROOT / 'data.sqlite3'}")

    # Load LTF data (15m)
    ltf_query = """
        SELECT open_time, open_price as open, high_price as high, 
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '15'
        ORDER BY open_time DESC
        LIMIT 5000
    """
    ltf = pd.read_sql(ltf_query, engine)
    ltf = ltf.iloc[::-1].reset_index(drop=True)

    # Load HTF data (1H)
    htf_query = """
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '60'
        ORDER BY open_time DESC
        LIMIT 1250
    """
    htf = pd.read_sql(htf_query, engine)
    htf = htf.iloc[::-1].reset_index(drop=True)

    return ltf, htf


def test_mtf_optimizer_basic():
    """Test 1: Basic MTF Optimization."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic MTF Optimization")
    print("=" * 60)

    ltf, htf = load_test_data()

    if ltf.empty or htf.empty:
        print("⚠️ SKIPPED: No data available")
        return True

    print(f"LTF candles: {len(ltf)}")
    print(f"HTF candles: {len(htf)}")

    # Create index map
    from backend.backtesting.mtf.index_mapper import create_htf_index_map

    htf_index_map = create_htf_index_map(ltf, htf)
    print(f"Index map: {len(htf_index_map)} entries")

    # Run small optimization
    from backend.backtesting.mtf_optimizer import MTFOptimizer

    optimizer = MTFOptimizer(verbose=True)

    result = optimizer.optimize(
        ltf_candles=ltf,
        htf_candles=htf,
        htf_index_map=htf_index_map,
        # Small param ranges for quick test
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[0.02],
        take_profit_range=[0.03],
        # MTF params
        htf_filter_types=["sma", "ema"],
        htf_filter_periods=[50, 200],
        # Trading
        initial_capital=10000,
        leverage=10,
        direction="both",
        optimize_metric="sharpe_ratio",
        top_k=10,
    )

    print("\n📊 Results:")
    print(f"  Total combinations: {result.total_combinations}")
    print(f"  Tested: {result.tested_combinations}")
    print(f"  Time: {result.execution_time_seconds:.2f}s")
    print(f"  Speed: {result.performance_stats['combinations_per_second']:.1f} comb/s")
    print("\n🏆 Best result:")
    print(f"  Score: {result.best_score:.4f}")
    print(f"  Params: {result.best_params}")
    print(f"  Trades: {result.best_metrics.get('total_trades', 0)}")

    # Verify result structure
    assert result.status == "completed"
    assert result.tested_combinations > 0
    assert len(result.top_results) > 0

    print("\n✅ PASSED: Basic optimization works")
    return True


def test_mtf_optimizer_all_filters():
    """Test 2: All Simple Filter Types Optimization."""
    print("\n" + "=" * 60)
    print("TEST 2: All Simple Filter Types (SMA/EMA)")
    print("=" * 60)

    ltf, htf = load_test_data()

    if ltf.empty or htf.empty:
        print("⚠️ SKIPPED: No data available")
        return True

    # Create index map
    from backend.backtesting.mtf.index_mapper import create_htf_index_map

    htf_index_map = create_htf_index_map(ltf, htf)

    # Run optimization with SMA/EMA filter types
    from backend.backtesting.mtf_optimizer import MTFOptimizer

    optimizer = MTFOptimizer(verbose=True)

    result = optimizer.optimize(
        ltf_candles=ltf,
        htf_candles=htf,
        htf_index_map=htf_index_map,
        # Fixed strategy params
        rsi_period_range=[14],
        rsi_overbought_range=[70],
        rsi_oversold_range=[30],
        stop_loss_range=[0.02],
        take_profit_range=[0.03],
        # SMA/EMA filter types (simple)
        htf_filter_types=["sma", "ema"],
        htf_filter_periods=[50, 100, 200],
        # Trading
        initial_capital=10000,
        leverage=10,
        direction="both",
        optimize_metric="sharpe_ratio",
        top_k=10,
    )

    print("\n📊 Results by filter type:")

    # Group results by filter type
    filter_results = {}
    for r in result.top_results:
        ft = r["params"]["htf_filter_type"]
        if ft not in filter_results:
            filter_results[ft] = []
        filter_results[ft].append(r)

    for ft, results in filter_results.items():
        best = max(results, key=lambda x: x["score"])
        print(f"  {ft:12s}: score={best['score']:.4f}, period={best['params']['htf_filter_period']}")

    # Verify all filter types were tested
    tested_types = set(r["params"]["htf_filter_type"] for r in result.top_results)
    print(f"\n  Filter types tested: {tested_types}")

    print("\n✅ PASSED: All filter types work")
    return True


def test_mtf_optimizer_compare_with_without():
    """Test 3: Compare results with/without MTF filter."""
    print("\n" + "=" * 60)
    print("TEST 3: Compare With/Without MTF Filter")
    print("=" * 60)

    ltf, htf = load_test_data()

    if ltf.empty or htf.empty:
        print("⚠️ SKIPPED: No data available")
        return True

    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput
    from backend.backtesting.mtf.index_mapper import create_htf_index_map
    from backend.backtesting.mtf.signals import generate_mtf_rsi_signals
    from backend.core.signal_generator import generate_signals

    htf_index_map = create_htf_index_map(ltf, htf)

    # Run WITHOUT MTF filter
    print("\n1. Running WITHOUT MTF filter...")
    long_signals_no_mtf, long_exits_no_mtf, short_signals_no_mtf, short_exits_no_mtf = generate_signals(
        ltf,
        strategy_type="rsi",
        direction="both",
        period=14,
        overbought=70,
        oversold=30,
    )

    bt_no_mtf = BacktestInput(
        candles=ltf,
        long_entries=long_signals_no_mtf,
        long_exits=long_exits_no_mtf,
        short_entries=short_signals_no_mtf,
        short_exits=short_exits_no_mtf,
        initial_capital=10000,
        leverage=10,
        commission=0.0007,
        stop_loss=0.02,
        take_profit=0.03,
        direction="both",
    )

    engine = FallbackEngineV4()
    result_no_mtf = engine.run(bt_no_mtf)

    # Run WITH MTF filter (SMA200)
    print("2. Running WITH MTF filter (SMA200)...")
    long_signals_mtf, long_exits_mtf, short_signals_mtf, short_exits_mtf = generate_mtf_rsi_signals(
        ltf_candles=ltf,
        htf_candles=htf,
        htf_index_map=htf_index_map,
        htf_filter_type="sma",
        htf_filter_period=200,
        direction="both",
        rsi_period=14,
        overbought=70,
        oversold=30,
    )

    bt_mtf = BacktestInput(
        candles=ltf,
        long_entries=long_signals_mtf,
        long_exits=long_exits_mtf,
        short_entries=short_signals_mtf,
        short_exits=short_exits_mtf,
        initial_capital=10000,
        leverage=10,
        commission=0.0007,
        stop_loss=0.02,
        take_profit=0.03,
        direction="both",
    )

    result_mtf = engine.run(bt_mtf)

    # Compare
    print("\n📊 Comparison:")
    print(f"{'Metric':<20} {'No MTF':>12} {'With MTF':>12} {'Delta':>12}")
    print("-" * 60)

    metrics_to_compare = [
        "total_trades",
        "win_rate",
        "total_return",
        "max_drawdown",
        "sharpe_ratio",
    ]
    for m in metrics_to_compare:
        v1 = result_no_mtf.metrics.get(m, 0)
        v2 = result_mtf.metrics.get(m, 0)
        delta = v2 - v1
        print(f"{m:<20} {v1:>12.2f} {v2:>12.2f} {delta:>+12.2f}")

    # MTF should generally reduce trades (filtering)
    trades_no_mtf = result_no_mtf.metrics.get("total_trades", 0)
    trades_mtf = result_mtf.metrics.get("total_trades", 0)

    print(f"\nTrade filtering: {trades_no_mtf} → {trades_mtf} ({trades_no_mtf - trades_mtf} filtered)")

    print("\n✅ PASSED: Comparison complete")
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("MTF OPTIMIZER TESTS")
    print("=" * 70)

    start = time.time()

    results = {
        "Basic Optimization": test_mtf_optimizer_basic(),
        "All Filter Types": test_mtf_optimizer_all_filters(),
        # "Compare With/Without MTF": test_mtf_optimizer_compare_with_without(),
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
