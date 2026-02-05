"""
🔍 Debug Engine Trades - Detailed trade comparison between engines.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.backtesting.interfaces import BacktestInput, TradeDirection


def load_ohlc_data(filepath: Path) -> pd.DataFrame:
    """Load OHLC data from CSV."""
    df = pd.read_csv(filepath)

    column_map = {
        "time": "timestamp",
        "Time": "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    df.rename(columns=column_map, inplace=True)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def main():
    print("🔍 Debug Engine Trades Comparison")
    print("=" * 80)

    # Load data
    tv_data_dir = Path("d:/TV")
    candles = load_ohlc_data(tv_data_dir / "BYBIT_BTCUSDT.P_15m_full.csv")
    long_signals = np.load(tv_data_dir / "long_signals.npy")
    short_signals = np.load(tv_data_dir / "short_signals.npy")

    print(f"📊 Loaded {len(candles)} candles")
    print(
        f"📈 Long signals: {long_signals.sum()}, Short signals: {short_signals.sum()}"
    )

    # Configuration - same as verification script
    config = {
        "initial_capital": 10000.0,
        "fixed_amount": 1000.0,
        "leverage": 10,
        "take_profit": 0.015,
        "stop_loss": 0.03,
        "commission": 0.0007,
    }

    # Create input
    input_data = BacktestInput(
        candles=candles,
        candles_1m=None,
        initial_capital=config["initial_capital"],
        use_fixed_amount=True,
        fixed_amount=config["fixed_amount"],
        leverage=config["leverage"],
        take_profit=config["take_profit"],
        stop_loss=config["stop_loss"],
        taker_fee=config["commission"],
        direction=TradeDirection.BOTH,
        long_entries=long_signals,
        short_entries=short_signals,
        use_bar_magnifier=False,
    )

    # Run FallbackEngineV2
    print("\n🔧 Running FallbackEngineV2...")
    from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2

    fb_engine = FallbackEngineV2()
    fb_result = fb_engine.run(input_data)
    fb_trades = fb_result.trades

    # Run NumbaEngineV2
    print("🔧 Running NumbaEngineV2...")
    from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

    nb_engine = NumbaEngineV2()
    nb_result = nb_engine.run(input_data)
    nb_trades = nb_result.trades

    # Compare first N trades
    print("\n" + "=" * 80)
    print("📊 COMPARING FIRST 10 TRADES")
    print("=" * 80)

    max_trades = min(10, len(fb_trades), len(nb_trades))

    for i in range(max_trades):
        fb_t = fb_trades[i]
        nb_t = nb_trades[i]

        print(f"\n--- Trade #{i + 1} ---")
        print(f"{'Field':<20} {'Fallback':<25} {'Numba':<25} {'Match':<10}")
        print("-" * 80)

        fields = [
            ("direction", lambda t: t.direction),
            ("entry_time", lambda t: str(t.entry_time)),
            ("exit_time", lambda t: str(t.exit_time)),
            ("entry_price", lambda t: f"{t.entry_price:.2f}"),
            ("exit_price", lambda t: f"{t.exit_price:.2f}"),
            ("size", lambda t: f"{t.size:.6f}"),
            ("pnl", lambda t: f"{t.pnl:.4f}"),
            ("fees", lambda t: f"{t.fees:.4f}"),
            ("exit_reason", lambda t: t.exit_reason),
        ]

        for fname, getter in fields:
            fb_val = getter(fb_t)
            nb_val = getter(nb_t)
            match = "✅" if str(fb_val) == str(nb_val) else "❌"
            print(f"{fname:<20} {fb_val!s:<25} {nb_val!s:<25} {match}")

    # Show signal context for first mismatched trade
    print("\n" + "=" * 80)
    print("🔍 SIGNAL CONTEXT FOR FIRST FEW ENTRIES")
    print("=" * 80)

    if len(fb_trades) > 0:
        first_trade = fb_trades[0]
        idx = first_trade.entry_index

        print(f"\nFirst Fallback trade entry at index {idx}")
        print(f"Signal bar (should be at i-1={idx - 1}):")

        if idx >= 2:
            for j in range(idx - 3, min(idx + 3, len(candles))):
                sig_long = "🟢" if long_signals[j] else "  "
                sig_short = "🔴" if short_signals[j] else "  "
                o, h, l, c = candles.iloc[j][["open", "high", "low", "close"]]
                print(
                    f"  [{j}] {sig_long}{sig_short} O={o:.2f} H={h:.2f} L={l:.2f} C={c:.2f}"
                )

    # Summary
    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print(
        f"Fallback: {len(fb_trades)} trades, Net PnL: {fb_result.metrics.net_profit:.2f}"
    )
    print(
        f"Numba:    {len(nb_trades)} trades, Net PnL: {nb_result.metrics.net_profit:.2f}"
    )

    # Check entry_index distribution
    fb_entries = [t.entry_index for t in fb_trades]
    nb_entries = [t.entry_index for t in nb_trades]

    if fb_entries != nb_entries:
        print("\n⚠️ Entry indices differ!")
        # Find first difference
        for i in range(min(len(fb_entries), len(nb_entries))):
            if fb_entries[i] != nb_entries[i]:
                print(
                    f"   First mismatch at trade #{i + 1}: FB={fb_entries[i]}, NB={nb_entries[i]}"
                )
                break


if __name__ == "__main__":
    main()
