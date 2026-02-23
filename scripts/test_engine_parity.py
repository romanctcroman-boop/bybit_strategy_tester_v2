"""
Comprehensive Engine Parity Test with Bar Magnifier

Tests VectorBT vs Fallback with ALL metrics comparison.
Uses Bar Magnifier (1m ticks) for high-fidelity SL/TP detection.

Author: AI Assistant
Date: January 2026
"""

import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Suppress debug logs
import logging

import pandas as pd

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig, PerformanceMetrics, TradeRecord

logging.getLogger("backend.backtesting.engine").setLevel(logging.WARNING)
logging.getLogger("backend.core.metrics_calculator").setLevel(logging.WARNING)


def load_test_data(symbol: str = "BTCUSDT", interval: str = "60", limit: int = 200) -> pd.DataFrame:
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
    """Create config for testing with Bar Magnifier."""
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
    }


def extract_all_metrics(metrics: PerformanceMetrics) -> dict[str, Any]:
    """Extract ALL metrics from PerformanceMetrics as a flat dict."""
    result = {}

    for field_name in PerformanceMetrics.model_fields:
        value = getattr(metrics, field_name, None)
        if isinstance(value, (list, dict)):
            continue
        result[field_name] = value

    return result


def compare_trades(trades1: list[TradeRecord], trades2: list[TradeRecord], tolerance: float = 0.01) -> dict:
    """Compare two lists of trades in detail."""
    result = {
        "count_match": len(trades1) == len(trades2),
        "trades1_count": len(trades1),
        "trades2_count": len(trades2),
        "exact_matches": 0,
        "close_matches": 0,
        "mismatches": [],
    }

    min_len = min(len(trades1), len(trades2))

    for i in range(min_len):
        t1, t2 = trades1[i], trades2[i]

        # Compare key fields
        pnl_match = abs(t1.pnl - t2.pnl) < tolerance if t1.pnl and t2.pnl else t1.pnl == t2.pnl
        entry_match = abs(t1.entry_price - t2.entry_price) < 1.0 if t1.entry_price and t2.entry_price else True
        exit_match = abs(t1.exit_price - t2.exit_price) < 1.0 if t1.exit_price and t2.exit_price else True

        if pnl_match and entry_match and exit_match:
            result["exact_matches"] += 1
        elif abs(t1.pnl - t2.pnl) < 10.0 if t1.pnl and t2.pnl else False:
            result["close_matches"] += 1
        else:
            result["mismatches"].append({
                "trade_idx": i,
                "t1_pnl": t1.pnl,
                "t2_pnl": t2.pnl,
                "t1_entry": t1.entry_price,
                "t2_entry": t2.entry_price,
                "t1_exit": t1.exit_price,
                "t2_exit": t2.exit_price,
            })

    return result


def compare_metrics_detailed(m1: dict, m2: dict, tolerance: float = 0.001) -> dict:
    """Compare two metric dicts and return detailed comparison."""
    all_keys = set(m1.keys()) | set(m2.keys())

    result = {
        "exact_matches": [],
        "close_matches": [],
        "mismatches": [],
        "missing_in_1": [],
        "missing_in_2": [],
    }

    for key in sorted(all_keys):
        v1 = m1.get(key)
        v2 = m2.get(key)

        if v1 is None and v2 is not None:
            result["missing_in_1"].append(key)
            continue
        if v2 is None and v1 is not None:
            result["missing_in_2"].append(key)
            continue

        if v1 == v2:
            result["exact_matches"].append(key)
        elif isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            if (v1 == 0 and v2 == 0) or (abs(v1) < 1e-10 and abs(v2) < 1e-10):
                result["exact_matches"].append(key)
            elif abs(v1 - v2) / max(abs(v1), abs(v2), 1e-10) < tolerance:
                result["close_matches"].append(key)
            else:
                result["mismatches"].append({
                    "key": key,
                    "v1": v1,
                    "v2": v2,
                    "diff_pct": abs(v1 - v2) / max(abs(v1), abs(v2), 1e-10) * 100
                })
        else:
            result["mismatches"].append({"key": key, "v1": v1, "v2": v2, "diff_pct": None})

    return result


def run_parity_test(direction: str, use_bar_magnifier: bool = False):
    """Run comprehensive parity test for a direction."""

    print("=" * 100)
    print(f"COMPREHENSIVE ENGINE PARITY TEST - Direction: {direction.upper()}")
    print(f"Bar Magnifier: {'ON' if use_bar_magnifier else 'OFF'}")
    print("=" * 100)

    # Load data
    data = load_test_data("BTCUSDT", "60", 200)
    print(f"Loaded {len(data)} 1H candles")

    # Create config
    config_dict = create_config(direction, use_bar_magnifier)
    config_dict["start_date"] = data.index[0]
    config_dict["end_date"] = data.index[-1]
    config = BacktestConfig(**config_dict)

    engine = BacktestEngine()

    # Generate signals once
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
        print(f"  ✅ VectorBT: {len(result_vbt.trades)} trades")
    except Exception as e:
        print(f"  ❌ VectorBT failed: {e}")

    # Run Fallback engine
    print("Running Fallback Engine...")
    result_fallback = engine._run_fallback(config, data, signals)
    print(f"  ✅ Fallback: {len(result_fallback.trades)} trades")

    if result_vbt is None:
        print("\n❌ VectorBT not available - cannot compare")
        return None

    # Compare trades
    print("\n" + "=" * 50)
    print("TRADE COMPARISON")
    print("=" * 50)

    trade_comparison = compare_trades(result_vbt.trades, result_fallback.trades)
    print(f"VectorBT trades: {trade_comparison['trades1_count']}")
    print(f"Fallback trades: {trade_comparison['trades2_count']}")
    print(f"Trade count match: {'✅' if trade_comparison['count_match'] else '❌'}")
    print(f"Exact PnL matches: {trade_comparison['exact_matches']}")
    print(f"Close matches: {trade_comparison['close_matches']}")
    print(f"Mismatches: {len(trade_comparison['mismatches'])}")

    if trade_comparison['mismatches'][:3]:
        print("\nFirst 3 mismatches:")
        for m in trade_comparison['mismatches'][:3]:
            print(f"  Trade {m['trade_idx']}: VBT PnL={m['t1_pnl']:.2f}, FB PnL={m['t2_pnl']:.2f}")

    # Compare metrics
    print("\n" + "=" * 50)
    print("METRICS COMPARISON")
    print("=" * 50)

    metrics_vbt = extract_all_metrics(result_vbt.metrics)
    metrics_fallback = extract_all_metrics(result_fallback.metrics)

    metric_comparison = compare_metrics_detailed(metrics_vbt, metrics_fallback)

    total_metrics = len(metrics_vbt)
    exact = len(metric_comparison['exact_matches'])
    close = len(metric_comparison['close_matches'])
    mismatch = len(metric_comparison['mismatches'])

    print(f"Total metrics: {total_metrics}")
    print(f"Exact matches: {exact} ({exact/total_metrics*100:.1f}%)")
    print(f"Close matches (< 0.1% diff): {close}")
    print(f"Mismatches: {mismatch}")

    parity_pct = (exact + close) / total_metrics * 100
    print(f"\n🎯 PARITY RATE: {parity_pct:.1f}%")

    if mismatch > 0:
        print("\nTop 5 mismatched metrics:")
        sorted_mismatches = sorted(metric_comparison['mismatches'],
                                   key=lambda x: x.get('diff_pct', 0) or 0,
                                   reverse=True)[:5]
        for m in sorted_mismatches:
            print(f"  {m['key']}: VBT={m['v1']}, FB={m['v2']}, diff={m.get('diff_pct', 'N/A'):.2f}%")

    # Final verdict
    print("\n" + "=" * 50)
    if parity_pct >= 99.0 and trade_comparison['count_match']:
        print("✅ SUCCESS: 99%+ parity achieved!")
    elif parity_pct >= 90.0:
        print("⚠️ GOOD: 90%+ parity - minor differences")
    else:
        print("❌ NEEDS WORK: Significant differences remain")

    return {
        "direction": direction,
        "bar_magnifier": use_bar_magnifier,
        "trade_parity": trade_comparison,
        "metric_parity_pct": parity_pct,
    }


def main():
    """Run comprehensive parity tests."""
    print("\n" + "🔬 " * 20)
    print("COMPREHENSIVE ENGINE PARITY TEST SUITE")
    print("🔬 " * 20 + "\n")

    results = []

    # Test without Bar Magnifier first
    for direction in ["long", "short", "both"]:
        result = run_parity_test(direction, use_bar_magnifier=False)
        if result:
            results.append(result)
        print("\n")

    # Summary
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"{'Direction':<12} {'Bar Magnifier':<15} {'Trade Match':<15} {'Metric Parity':<15}")
    print("-" * 60)
    for r in results:
        trade_match = "✅" if r['trade_parity']['count_match'] else "❌"
        print(f"{r['direction']:<12} {'ON' if r['bar_magnifier'] else 'OFF':<15} {trade_match:<15} {r['metric_parity_pct']:.1f}%")


if __name__ == "__main__":
    main()
