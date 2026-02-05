"""
Test script for Bar Magnifier functionality.

Tests:
1. Bar Magnifier initialization with 1m data
2. Intrabar path generation
3. SL/TP detection precision
4. Comparison with standard OHLC-based detection
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


import pandas as pd

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig


def test_bar_magnifier():
    """Test Bar Magnifier with real data."""
    print("=" * 80)
    print("BAR MAGNIFIER TEST")
    print("=" * 80)

    # Load test data using sqlite3 and pandas directly
    import sqlite3

    db_path = ROOT / "data.sqlite3"
    conn = sqlite3.connect(str(db_path))

    # Check if we have 1m data
    m1_count = pd.read_sql(
        """
        SELECT COUNT(*) as cnt FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '1'
        """,
        conn,
    )["cnt"].iloc[0]

    print(f"\n1m candles in DB: {m1_count:,}")

    if m1_count == 0:
        print("\n⚠️  No 1m data found! Bar Magnifier will use OHLC heuristic.")
        print("   Run data refresh to load 1m candles.\n")

    # Load 1h data for backtest
    h1_data = pd.read_sql(
        """
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '60'
        ORDER BY open_time DESC
        LIMIT 500
        """,
        conn,
    )
    conn.close()

    if len(h1_data) == 0:
        print("❌ No 1h data found for BTCUSDT!")
        return

    # Prepare OHLCV
    h1_data = h1_data.sort_values("open_time")
    h1_data["datetime"] = pd.to_datetime(h1_data["open_time"], unit="ms")
    h1_data = h1_data.set_index("datetime")

    print(f"1h candles loaded: {len(h1_data)}")
    print(f"Period: {h1_data.index[0]} to {h1_data.index[-1]}")

    # Create configs - one with Bar Magnifier, one without
    base_config = {
        "symbol": "BTCUSDT",
        "interval": "60",
        "start_date": h1_data.index[0],
        "end_date": h1_data.index[-1],
        "strategy_type": "rsi",
        "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
        "initial_capital": 10000.0,
        "leverage": 10.0,
        "position_size": 1.0,
        "direction": "both",
        "stop_loss": 0.02,  # 2% SL
        "take_profit": 0.04,  # 4% TP
    }

    # Test 1: Without Bar Magnifier (standard)
    print("\n" + "=" * 40)
    print("TEST 1: Standard Mode (no Bar Magnifier)")
    print("=" * 40)

    config_standard = BacktestConfig(**base_config, use_bar_magnifier=False)
    engine = BacktestEngine()

    result_standard = engine.run(config_standard, h1_data, silent=True)

    print(f"Total trades: {result_standard.metrics.total_trades}")
    print(f"Net profit: ${result_standard.metrics.net_profit:.2f}")
    print(f"Win rate: {result_standard.metrics.win_rate:.2f}%")

    # Count SL/TP exits (using exit_comment field from TradeRecord)
    sl_exits = sum(1 for t in result_standard.trades if getattr(t, "exit_comment", "") == "SL")
    tp_exits = sum(1 for t in result_standard.trades if getattr(t, "exit_comment", "") == "TP")
    signal_exits = sum(1 for t in result_standard.trades if getattr(t, "exit_comment", "") == "signal")

    print(f"SL exits: {sl_exits}, TP exits: {tp_exits}, Signal exits: {signal_exits}")

    # Test 2: With Bar Magnifier
    print("\n" + "=" * 40)
    print("TEST 2: Bar Magnifier Mode (1m intrabar)")
    print("=" * 40)

    config_magnifier = BacktestConfig(**base_config, use_bar_magnifier=True)

    result_magnifier = engine.run(config_magnifier, h1_data, silent=True)

    print(f"Total trades: {result_magnifier.metrics.total_trades}")
    print(f"Net profit: ${result_magnifier.metrics.net_profit:.2f}")
    print(f"Win rate: {result_magnifier.metrics.win_rate:.2f}%")

    # Count SL/TP exits (using exit_comment field from TradeRecord)
    sl_exits_mag = sum(1 for t in result_magnifier.trades if getattr(t, "exit_comment", "") == "SL")
    tp_exits_mag = sum(1 for t in result_magnifier.trades if getattr(t, "exit_comment", "") == "TP")
    signal_exits_mag = sum(1 for t in result_magnifier.trades if getattr(t, "exit_comment", "") == "signal")

    print(f"SL exits: {sl_exits_mag}, TP exits: {tp_exits_mag}, Signal exits: {signal_exits_mag}")

    # Comparison
    print("\n" + "=" * 40)
    print("COMPARISON")
    print("=" * 40)

    print(f"{'Metric':<25} {'Standard':>15} {'Bar Magnifier':>15} {'Diff':>10}")
    print("-" * 70)

    metrics = [
        ("Total Trades", result_standard.metrics.total_trades, result_magnifier.metrics.total_trades),
        ("Net Profit ($)", result_standard.metrics.net_profit, result_magnifier.metrics.net_profit),
        ("Win Rate (%)", result_standard.metrics.win_rate, result_magnifier.metrics.win_rate),
        ("Profit Factor", result_standard.metrics.profit_factor, result_magnifier.metrics.profit_factor),
        ("Max Drawdown (%)", result_standard.metrics.max_drawdown, result_magnifier.metrics.max_drawdown),
        ("SL Exits", sl_exits, sl_exits_mag),
        ("TP Exits", tp_exits, tp_exits_mag),
        ("Signal Exits", signal_exits, signal_exits_mag),
    ]

    for name, std, mag in metrics:
        diff = mag - std if isinstance(std, (int, float)) else "-"
        diff_str = f"{diff:+.2f}" if isinstance(diff, float) else str(diff) if diff != "-" else "-"
        std_str = f"{std:.2f}" if isinstance(std, float) else str(std)
        mag_str = f"{mag:.2f}" if isinstance(mag, float) else str(mag)
        print(f"{name:<25} {std_str:>15} {mag_str:>15} {diff_str:>10}")

    # Result interpretation
    print("\n" + "=" * 40)
    print("INTERPRETATION")
    print("=" * 40)

    if m1_count > 0:
        print("✅ Bar Magnifier used real 1m data for intrabar simulation")
        if sl_exits != sl_exits_mag or tp_exits != tp_exits_mag:
            print("   → SL/TP exit counts differ: Bar Magnifier detected different trigger order")
        else:
            print("   → SL/TP exit counts match: Similar behavior to standard mode")
    else:
        print("⚠️  Bar Magnifier used OHLC heuristic (no 1m data)")
        print("   Results may be similar to standard mode")

    print("\n✅ Bar Magnifier test completed!")


if __name__ == "__main__":
    test_bar_magnifier()
