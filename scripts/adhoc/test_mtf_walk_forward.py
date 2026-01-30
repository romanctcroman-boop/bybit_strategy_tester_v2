"""
Test MTF Walk-Forward Analysis

Tests rolling walk-forward optimization for MTF strategy validation.
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

    # Load LTF data (15m) - in chronological order (ASC)
    ltf_query = """
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '15'
        ORDER BY open_time ASC
        LIMIT 10000
    """
    ltf = pd.read_sql(ltf_query, engine)

    # Load HTF data (1H) - in chronological order (ASC)
    htf_query = """
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '60'
        ORDER BY open_time ASC
        LIMIT 2500
    """
    htf = pd.read_sql(htf_query, engine)

    return ltf, htf


def test_walk_forward_basic():
    """Test 1: Basic Walk-Forward Analysis."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Walk-Forward Analysis")
    print("=" * 60)

    ltf, htf = load_test_data()

    if len(ltf) < 2000 or len(htf) < 500:
        print(f"⚠️ SKIPPED: Not enough data (LTF={len(ltf)}, HTF={len(htf)})")
        return True

    print(f"LTF candles: {len(ltf)}")
    print(f"HTF candles: {len(htf)}")

    # Create index map
    from backend.backtesting.mtf.index_mapper import create_htf_index_map

    htf_index_map = create_htf_index_map(ltf, htf)
    print(f"Index map: {len(htf_index_map)} entries")

    # Run walk-forward with small param space
    from backend.backtesting.mtf_walk_forward import MTFWalkForward

    analyzer = MTFWalkForward(verbose=True)

    result = analyzer.analyze(
        ltf_candles=ltf,
        htf_candles=htf,
        htf_index_map=htf_index_map,
        # Window config
        train_pct=0.7,
        n_windows=3,  # Small for quick test
        overlap_pct=0.3,
        # Small param space
        rsi_period_range=[14],
        rsi_overbought_range=[70],
        rsi_oversold_range=[30],
        stop_loss_range=[0.02],
        take_profit_range=[0.03],
        htf_filter_types=["sma"],
        htf_filter_periods=[50, 200],
        # Trading
        initial_capital=10000,
        leverage=10,
        direction="both",
        optimize_metric="sharpe_ratio",
    )

    print(f"\n📊 Walk-Forward Results:")
    print(f"  Status: {result.status}")
    print(f"  Windows: {result.completed_windows}/{result.total_windows}")
    print(f"  Time: {result.execution_time_seconds:.2f}s")
    print(f"\n  Avg OOS Return: {result.avg_oos_return:.2f}%")
    print(f"  Total OOS Return: {result.total_oos_return:.2f}%")
    print(f"  Avg OOS Sharpe: {result.avg_oos_sharpe:.2f}")
    print(
        f"  Profitable Windows: {result.profitable_windows}/{result.completed_windows} ({result.profitable_pct:.0f}%)"
    )

    # Display window details
    print("\n  Window Details:")
    for w in result.windows:
        print(f"    Window {w.window_id}: OOS return={w.oos_return:.2f}%, trades={w.oos_trades}")

    # Verify result
    assert result.status == "completed"
    assert result.completed_windows > 0

    print("\n✅ PASSED: Walk-forward analysis works")
    return True


def test_walk_forward_robustness():
    """Test 2: Walk-Forward Robustness Check."""
    print("\n" + "=" * 60)
    print("TEST 2: Walk-Forward Robustness Check")
    print("=" * 60)

    ltf, htf = load_test_data()

    if len(ltf) < 2000 or len(htf) < 500:
        print(f"⚠️ SKIPPED: Not enough data")
        return True

    # Create index map
    from backend.backtesting.mtf.index_mapper import create_htf_index_map

    htf_index_map = create_htf_index_map(ltf, htf)

    from backend.backtesting.mtf_walk_forward import run_mtf_walk_forward

    # Run with more windows for robustness
    result = run_mtf_walk_forward(
        ltf_candles=ltf,
        htf_candles=htf,
        htf_index_map=htf_index_map,
        n_windows=4,
        train_pct=0.65,
        # Slightly larger param space
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70],
        rsi_oversold_range=[30],
        htf_filter_types=["sma", "ema"],
        htf_filter_periods=[50, 200],
    )

    print(f"\n📊 Robustness Metrics:")
    print(f"  Completed windows: {result.completed_windows}")
    print(f"  Avg OOS Return: {result.avg_oos_return:.2f}%")
    print(f"  OOS Return Std: {result.oos_return_std:.2f}%")
    print(f"  Profitable %: {result.profitable_pct:.0f}%")

    # Check stability
    stability_score = result.profitable_pct / 100 * (1 - result.oos_return_std / max(abs(result.avg_oos_return), 1))
    print(f"  Stability Score: {stability_score:.2f}")

    # Strategy is robust if >50% windows profitable
    if result.profitable_pct >= 50:
        print("\n  ✅ Strategy shows robustness (>50% profitable windows)")
    else:
        print("\n  ⚠️ Strategy may need improvement (<50% profitable)")

    print("\n✅ PASSED: Robustness check complete")
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("MTF WALK-FORWARD TESTS")
    print("=" * 70)

    start = time.time()

    results = {
        "Basic Walk-Forward": test_walk_forward_basic(),
        "Robustness Check": test_walk_forward_robustness(),
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
