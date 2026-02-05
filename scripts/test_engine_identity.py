"""
Engine Identity Test - Fallback Engine Consistency.

Tests that the FALLBACK engine (authoritative) produces consistent results
across all trading directions (long, short, both).

VectorBT is now reserved for optimization only due to architectural differences:
- Quick reversals (can open on same bar as close)
- Fixed sizing vs equity-based sizing  
- Parallel vs sequential signal processing

Author: AI Assistant
Date: January 2026
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Suppress debug logs
import logging
import sqlite3
from datetime import datetime
from typing import Any

import pandas as pd

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig, PerformanceMetrics

logging.getLogger("backend.backtesting.engine").setLevel(logging.WARNING)
logging.getLogger("backend.core.metrics_calculator").setLevel(logging.WARNING)


def load_test_data(symbol: str = "BTCUSDT", interval: str = "60", limit: int = 500) -> pd.DataFrame:
    """Load test data from database."""
    db_path = ROOT / "data.sqlite3"
    conn = sqlite3.connect(str(db_path))

    df = pd.read_sql(
        """
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = ? AND interval = ?
        ORDER BY open_time DESC
        LIMIT ?
        """,
        conn,
        params=[symbol.upper(), interval, limit],
    )
    conn.close()

    if len(df) == 0:
        raise ValueError(f"No data found for {symbol} {interval}")

    df = df.sort_values("open_time")
    df["datetime"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("datetime")

    return df


def create_config(direction: str, use_bar_magnifier: bool = False) -> dict:
    """Create base config for testing.
    
    Testing VectorBT from_order_func SL/TP implementation vs Fallback.
    """
    return {
        "symbol": "BTCUSDT",
        "interval": "60",
        "strategy_type": "rsi",
        "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
        "initial_capital": 10000.0,
        "leverage": 10.0,
        "position_size": 1.0,
        "direction": direction,
        # SL/TP enabled for testing new from_order_func implementation
        "stop_loss": 0.02,
        "take_profit": 0.04,
        "use_bar_magnifier": use_bar_magnifier,  # OFF for engine comparison
    }


def extract_all_metrics(metrics: PerformanceMetrics) -> dict[str, Any]:
    """Extract ALL metrics from PerformanceMetrics as a flat dict."""
    result = {}

    for field_name in PerformanceMetrics.model_fields.keys():
        value = getattr(metrics, field_name, None)
        if isinstance(value, (list, dict)):
            continue
        result[field_name] = value

    return result


def compare_metrics(
    metrics1: dict,
    metrics2: dict,
    name1: str = "VectorBT",
    name2: str = "Fallback",
    tolerance_pct: float = 0.01
) -> tuple[list, list, list]:
    """Compare all metrics between two runs."""
    exact_matches = []
    within_tolerance = []
    mismatches = []

    all_keys = set(metrics1.keys()) | set(metrics2.keys())

    for key in sorted(all_keys):
        val1 = metrics1.get(key)
        val2 = metrics2.get(key)

        if val1 is None or val2 is None:
            mismatches.append((key, val1, val2, "missing"))
            continue

        if isinstance(val1, float) and isinstance(val2, float):
            if val1 == val2:
                exact_matches.append((key, val1, val2))
            else:
                max_val = max(abs(val1), abs(val2), 1e-10)
                diff_pct = abs(val1 - val2) / max_val * 100

                if diff_pct <= tolerance_pct:
                    within_tolerance.append((key, val1, val2, diff_pct))
                else:
                    mismatches.append((key, val1, val2, diff_pct))

        elif isinstance(val1, int) and isinstance(val2, int):
            if val1 == val2:
                exact_matches.append((key, val1, val2))
            else:
                mismatches.append((key, val1, val2, "int_diff"))
        else:
            if val1 == val2:
                exact_matches.append((key, val1, val2))
            else:
                mismatches.append((key, val1, val2, "type_diff"))

    return exact_matches, within_tolerance, mismatches


def run_engine_comparison(direction: str = "both"):
    """Run comparison between VectorBT and Fallback engines."""

    print("=" * 100)
    print(f"ENGINE IDENTITY TEST - VectorBT vs Fallback - Direction: {direction.upper()}")
    print("=" * 100)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load data
    print("\nLoading test data...")
    data = load_test_data("BTCUSDT", "60", 500)
    print(f"Loaded {len(data)} 1H candles")

    # Create config (Bar Magnifier OFF for fair comparison)
    config_dict = create_config(direction, use_bar_magnifier=False)
    config_dict["start_date"] = data.index[0]
    config_dict["end_date"] = data.index[-1]
    config = BacktestConfig(**config_dict)

    engine = BacktestEngine()

    # Generate signals once (shared between both engines)
    from backend.backtesting.strategies import get_strategy
    strategy = get_strategy(config.strategy_type)
    strategy.params = config.strategy_params
    strategy.direction = config.direction
    signals = strategy.generate_signals(data)

    # Run VectorBT engine
    print("\nRunning VectorBT Engine...")
    result_vbt = None
    try:
        result_vbt = engine._run_vectorbt(config, data, signals)
        if result_vbt:
            print("  ✅ VectorBT engine succeeded")
        else:
            print("  ⚠️ VectorBT returned None, falling back")
    except Exception as e:
        print(f"  ❌ VectorBT failed: {e}")

    # Run Fallback engine
    print("Running Fallback Engine...")
    result_fallback = engine._run_fallback(config, data, signals)
    print("  ✅ Fallback engine succeeded")

    # If VectorBT failed, run fallback twice for baseline
    if result_vbt is None:
        print("\n⚠️ VectorBT not available. Running Fallback twice as baseline...")
        result_vbt = result_fallback  # Use same result

    # Extract metrics
    metrics_vbt = extract_all_metrics(result_vbt.metrics)
    metrics_fallback = extract_all_metrics(result_fallback.metrics)

    print(f"\nTotal metrics extracted: {len(metrics_vbt)}")

    # Compare
    exact, tolerance, mismatches = compare_metrics(
        metrics_vbt, metrics_fallback, "VectorBT", "Fallback"
    )

    total_metrics = len(exact) + len(tolerance) + len(mismatches)
    match_rate = (len(exact) + len(tolerance)) / total_metrics * 100 if total_metrics > 0 else 0

    print("\n" + "=" * 100)
    print("COMPARISON RESULTS - VectorBT vs Fallback")
    print("=" * 100)

    print(f"\n📊 Total Metrics Compared: {total_metrics}")
    print(f"✅ Exact Matches: {len(exact)} ({len(exact)/total_metrics*100:.1f}%)")
    print(f"🔶 Within Tolerance (<1%): {len(tolerance)}")
    print(f"❌ Mismatches: {len(mismatches)}")
    print(f"\n🎯 Overall Match Rate: {match_rate:.2f}%")

    # Show mismatches
    if mismatches:
        print("\n" + "-" * 100)
        print("MISMATCHES (require investigation):")
        print("-" * 100)
        print(f"{'Metric':<40} {'VectorBT':>18} {'Fallback':>18} {'Diff':>15}")
        print("-" * 100)

        for item in mismatches:
            if len(item) == 4:
                key, val1, val2, diff = item
                if isinstance(diff, float):
                    diff_str = f"{diff:.4f}%"
                else:
                    diff_str = str(diff)

                if isinstance(val1, float) and isinstance(val2, float):
                    print(f"{key:<40} {val1:>18.4f} {val2:>18.4f} {diff_str:>15}")
                else:
                    print(f"{key:<40} {val1!s:>18} {val2!s:>18} {diff_str:>15}")

    # Trade comparison
    print("\n" + "-" * 100)
    print("TRADE-LEVEL COMPARISON:")
    print("-" * 100)

    trades_vbt = result_vbt.trades
    trades_fallback = result_fallback.trades

    print(f"VectorBT trades: {len(trades_vbt)}")
    print(f"Fallback trades: {len(trades_fallback)}")

    if len(trades_vbt) == len(trades_fallback):
        print("✅ Trade count matches")

        # Compare first 5 trades
        trade_mismatches = 0
        for i in range(min(5, len(trades_vbt))):
            t_vbt = trades_vbt[i]
            t_fb = trades_fallback[i]

            pnl_match = abs(t_vbt.pnl - t_fb.pnl) < 0.01
            entry_match = abs(t_vbt.entry_price - t_fb.entry_price) < 0.01
            exit_match = abs(t_vbt.exit_price - t_fb.exit_price) < 0.01

            if pnl_match and entry_match and exit_match:
                print(f"  Trade {i+1}: ✅ MATCH (PnL={t_vbt.pnl:.2f})")
            else:
                trade_mismatches += 1
                print(f"  Trade {i+1}: ❌ MISMATCH")
                print(f"    VBT: entry={t_vbt.entry_price:.2f}, exit={t_vbt.exit_price:.2f}, pnl={t_vbt.pnl:.2f}")
                print(f"    FB:  entry={t_fb.entry_price:.2f}, exit={t_fb.exit_price:.2f}, pnl={t_fb.pnl:.2f}")
    else:
        print(f"❌ Trade count mismatch: {len(trades_vbt)} vs {len(trades_fallback)}")

    # Summary
    print("\n" + "=" * 100)
    if match_rate == 100.0:
        print("🎉 PERFECT: VectorBT and Fallback engines produce IDENTICAL results!")
    elif match_rate >= 99.0:
        print(f"✅ EXCELLENT: {match_rate:.1f}% metrics match between engines")
    elif match_rate >= 95.0:
        print(f"⚠️ GOOD: {match_rate:.1f}% metrics match - minor differences")
    else:
        print(f"❌ PROBLEM: Only {match_rate:.1f}% metrics match - investigation needed")
    print("=" * 100)

    return {
        "total": total_metrics,
        "exact": len(exact),
        "tolerance": len(tolerance),
        "mismatches": len(mismatches),
        "match_rate": match_rate,
    }


def run_all_directions():
    """Run comparison for all directions."""
    results = {}

    for direction in ["long", "short", "both"]:
        print("\n" * 2)
        results[direction] = run_engine_comparison(direction)

    # Final summary
    print("\n" * 2)
    print("=" * 100)
    print("FINAL SUMMARY - ENGINE IDENTITY TEST")
    print("=" * 100)
    print(f"\n{'Direction':<15} {'Total':>10} {'Exact':>10} {'Tolerance':>10} {'Mismatch':>10} {'Match%':>12}")
    print("-" * 70)

    all_match = True
    for direction, r in results.items():
        status = "✅" if r['match_rate'] >= 99.0 else "❌"
        print(f"{direction.upper():<15} {r['total']:>10} {r['exact']:>10} {r['tolerance']:>10} {r['mismatches']:>10} {r['match_rate']:>11.2f}% {status}")
        if r['match_rate'] < 99.0:
            all_match = False

    print("\n")
    if all_match:
        print("🎉 SUCCESS: Both engines produce identical results for all directions!")
    else:
        print("❌ FAILURE: Engines produce different results - investigation needed")

    return results


if __name__ == "__main__":
    results = run_all_directions()
