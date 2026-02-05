"""
Full Metrics Comparison Test - ALL 137+ Metrics.

Compares Standard vs Bar Magnifier modes across ALL PerformanceMetrics fields.
Reports exact matches, differences, and overall match percentage.

Author: AI Assistant
Date: January 2026
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Suppress debug logs for cleaner output
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


def create_config(direction: str, use_bar_magnifier: bool = True) -> dict:
    """Create base config for testing."""
    return {
        "symbol": "BTCUSDT",
        "interval": "60",
        "strategy_type": "rsi",
        "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
        "initial_capital": 10000.0,
        "leverage": 10.0,
        "position_size": 1.0,
        "direction": direction,
        "stop_loss": 0.02,
        "take_profit": 0.04,
        "use_bar_magnifier": use_bar_magnifier,
        "intrabar_ohlc_path": "O-HL-heuristic",
        "intrabar_subticks": 1,
    }


def extract_all_metrics(metrics: PerformanceMetrics) -> dict[str, Any]:
    """Extract ALL metrics from PerformanceMetrics as a flat dict."""
    result = {}

    # Get all fields from Pydantic model
    for field_name, field_info in metrics.model_fields.items():
        value = getattr(metrics, field_name, None)

        # Skip complex types (lists, dicts)
        if isinstance(value, (list, dict)):
            continue

        result[field_name] = value

    return result


def compare_all_metrics(
    metrics1: dict,
    metrics2: dict,
    name1: str = "Standard",
    name2: str = "Magnifier",
    tolerance_pct: float = 0.01  # 1% tolerance for floats
) -> tuple[list, list, list]:
    """
    Compare all metrics between two runs.
    
    Returns:
        (exact_matches, within_tolerance, mismatches)
    """
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

        # Handle different types
        if isinstance(val1, float) and isinstance(val2, float):
            # Exact match check
            if val1 == val2:
                exact_matches.append((key, val1, val2))
            else:
                # Tolerance check
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
            # String or other comparison
            if val1 == val2:
                exact_matches.append((key, val1, val2))
            else:
                mismatches.append((key, val1, val2, "type_diff"))

    return exact_matches, within_tolerance, mismatches


def run_full_comparison(direction: str = "both"):
    """Run full metrics comparison between Standard and Bar Magnifier."""

    print("=" * 100)
    print(f"FULL METRICS COMPARISON TEST - Direction: {direction.upper()}")
    print("=" * 100)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load data
    print("\nLoading test data...")
    data = load_test_data("BTCUSDT", "60", 500)
    print(f"Loaded {len(data)} 1H candles")

    # Create engine
    engine = BacktestEngine()

    # Run Standard mode
    print("\nRunning Standard mode (Bar Magnifier OFF)...")
    config_std = create_config(direction, use_bar_magnifier=False)
    config_std["start_date"] = data.index[0]
    config_std["end_date"] = data.index[-1]
    result_std = engine.run(BacktestConfig(**config_std), data, silent=True)

    # Run Bar Magnifier mode
    print("Running Bar Magnifier mode (ON)...")
    config_mag = create_config(direction, use_bar_magnifier=True)
    config_mag["start_date"] = data.index[0]
    config_mag["end_date"] = data.index[-1]
    result_mag = engine.run(BacktestConfig(**config_mag), data, silent=True)

    # Extract all metrics
    metrics_std = extract_all_metrics(result_std.metrics)
    metrics_mag = extract_all_metrics(result_mag.metrics)

    print(f"\nTotal metrics extracted: {len(metrics_std)}")

    # Compare
    exact, tolerance, mismatches = compare_all_metrics(
        metrics_std, metrics_mag, "Standard", "Magnifier"
    )

    total_metrics = len(exact) + len(tolerance) + len(mismatches)
    match_rate = (len(exact) + len(tolerance)) / total_metrics * 100 if total_metrics > 0 else 0

    print("\n" + "=" * 100)
    print("COMPARISON RESULTS")
    print("=" * 100)

    print(f"\n📊 Total Metrics Compared: {total_metrics}")
    print(f"✅ Exact Matches: {len(exact)} ({len(exact)/total_metrics*100:.1f}%)")
    print(f"🔶 Within Tolerance (<1%): {len(tolerance)}")
    print(f"❌ Mismatches: {len(mismatches)}")
    print(f"\n🎯 Overall Match Rate: {match_rate:.2f}%")

    # Show mismatches in detail
    if mismatches:
        print("\n" + "-" * 100)
        print("DETAILED MISMATCHES (metrics that differ between Standard and Bar Magnifier):")
        print("-" * 100)
        print(f"{'Metric':<40} {'Standard':>18} {'Magnifier':>18} {'Diff':>15}")
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

    # Show exact matches summary by category
    print("\n" + "-" * 100)
    print("EXACT MATCHES BY CATEGORY:")
    print("-" * 100)

    categories = {
        "Trade Counts": ["total_trades", "winning_trades", "losing_trades", "long_trades", "short_trades"],
        "Profit Metrics": ["net_profit", "gross_profit", "gross_loss", "profit_factor"],
        "Risk Metrics": ["max_drawdown", "sharpe_ratio", "sortino_ratio", "calmar_ratio"],
        "Win/Loss Stats": ["win_rate", "avg_win", "avg_loss", "largest_win", "largest_loss"],
        "Duration": ["avg_trade_duration_hours", "avg_bars_in_trade", "exposure_time"],
    }

    for cat_name, cat_keys in categories.items():
        matches_in_cat = sum(1 for m in exact if m[0] in cat_keys)
        total_in_cat = len(cat_keys)
        print(f"  {cat_name}: {matches_in_cat}/{total_in_cat} exact matches")

    # Key metrics summary
    print("\n" + "-" * 100)
    print("KEY METRICS COMPARISON:")
    print("-" * 100)

    key_metrics = [
        "total_trades", "winning_trades", "losing_trades",
        "net_profit", "gross_profit", "gross_loss",
        "win_rate", "profit_factor", "max_drawdown",
        "sharpe_ratio", "sortino_ratio",
        "avg_trade", "avg_win", "avg_loss",
        "long_trades", "short_trades",
        "long_pnl", "short_pnl",
    ]

    print(f"{'Metric':<30} {'Standard':>15} {'Magnifier':>15} {'Status':>12}")
    print("-" * 75)

    for key in key_metrics:
        val_std = metrics_std.get(key, "N/A")
        val_mag = metrics_mag.get(key, "N/A")

        if val_std == val_mag:
            status = "✅ MATCH"
        elif isinstance(val_std, float) and isinstance(val_mag, float):
            diff = abs(val_std - val_mag)
            if diff < 0.01:
                status = "🔶 ~MATCH"
            else:
                status = f"❌ diff={diff:.2f}"
        else:
            status = "❌ DIFF"

        if isinstance(val_std, float):
            print(f"{key:<30} {val_std:>15.4f} {val_mag:>15.4f} {status:>12}")
        else:
            print(f"{key:<30} {val_std!s:>15} {val_mag!s:>15} {status:>12}")

    # Summary
    print("\n" + "=" * 100)
    print("ANALYSIS SUMMARY")
    print("=" * 100)

    if match_rate == 100.0:
        print("\n🎉 PERFECT: All metrics match 100%!")
    elif match_rate >= 95.0:
        print(f"\n✅ EXCELLENT: {match_rate:.1f}% metrics match")
        print("   Minor differences are expected due to Bar Magnifier's more precise intrabar simulation.")
    elif match_rate >= 80.0:
        print(f"\n⚠️ GOOD: {match_rate:.1f}% metrics match")
        print("   Some differences due to Bar Magnifier detecting different SL/TP trigger order.")
    else:
        print(f"\n❌ SIGNIFICANT DIFFERENCES: Only {match_rate:.1f}% metrics match")
        print("   Investigation needed.")

    # Explain expected differences
    print("\n📌 EXPECTED DIFFERENCES:")
    print("   - net_profit, gross_profit, gross_loss: May differ if SL/TP order changes")
    print("   - win_rate: Changes when trades switch from SL to TP exits")
    print("   - MFE/MAE related: More precise with tick-level tracking")
    print("   - Streak metrics: May change if trade outcomes differ")

    return {
        "total": total_metrics,
        "exact": len(exact),
        "tolerance": len(tolerance),
        "mismatches": len(mismatches),
        "match_rate": match_rate,
        "mismatch_details": mismatches,
    }


def run_all_directions():
    """Run comparison for all directions."""
    results = {}

    for direction in ["long", "short", "both"]:
        print("\n" * 2)
        results[direction] = run_full_comparison(direction)

    # Final summary
    print("\n" * 2)
    print("=" * 100)
    print("FINAL SUMMARY - ALL DIRECTIONS")
    print("=" * 100)
    print(f"\n{'Direction':<15} {'Total':>10} {'Exact':>10} {'Tolerance':>10} {'Mismatch':>10} {'Match%':>12}")
    print("-" * 70)

    for direction, r in results.items():
        print(f"{direction.upper():<15} {r['total']:>10} {r['exact']:>10} {r['tolerance']:>10} {r['mismatches']:>10} {r['match_rate']:>11.2f}%")

    return results


if __name__ == "__main__":
    # Run for all directions
    results = run_all_directions()
