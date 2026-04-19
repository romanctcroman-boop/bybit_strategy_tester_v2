"""
Test script comparing MAE/MFE results with and without Bar Magnifier
using REAL data from the database.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection

DB_PATH = str(Path(__file__).resolve().parents[1] / "data.sqlite3")


def load_real_data(symbol: str = "BTCUSDT", interval_1h: str = "60", limit: int = 500):
    """Load real OHLC data from database."""
    conn = sqlite3.connect(DB_PATH)

    # Load 1H data from bybit_kline_audit
    query_1h = """
        SELECT open_time as timestamp, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = ? AND interval = ?
        ORDER BY open_time DESC
        LIMIT ?
    """
    df_1h = pd.read_sql_query(query_1h, conn, params=(symbol, interval_1h, limit))
    df_1h = df_1h.sort_values("timestamp").reset_index(drop=True)
    df_1h["timestamp"] = pd.to_datetime(df_1h["timestamp"], unit="ms")

    if df_1h.empty:
        print(f"❌ No 1H data found for {symbol}")
        return None, None

    print(f"   First candle: {df_1h['timestamp'].min()}")
    print(f"   Last candle:  {df_1h['timestamp'].max()}")

    # Get time range for 1m data
    start_ts = int(df_1h["timestamp"].min().timestamp() * 1000)
    end_ts = int(df_1h["timestamp"].max().timestamp() * 1000) + 3600 * 1000

    # Load 1M data for the same period
    query_1m = """
        SELECT open_time as timestamp, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = ? AND interval = '1'
        AND open_time >= ? AND open_time <= ?
        ORDER BY open_time
    """
    df_1m = pd.read_sql_query(query_1m, conn, params=(symbol, start_ts, end_ts))
    df_1m["timestamp"] = pd.to_datetime(df_1m["timestamp"], unit="ms")

    conn.close()

    return df_1h, df_1m


def generate_rsi_signals(df: pd.DataFrame, rsi_period: int = 14, oversold: int = 30, overbought: int = 70):
    """Generate simple RSI signals."""
    # Calculate RSI (Wilder's smoothing)
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)

    avg_gain = gain.ewm(alpha=1 / rsi_period, min_periods=rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / rsi_period, min_periods=rsi_period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Generate signals
    rsi_prev = rsi.shift(1)

    long_entries = (rsi_prev <= oversold) & (rsi > oversold)
    long_exits = (rsi_prev >= overbought) & (rsi < overbought)

    short_entries = (rsi_prev >= overbought) & (rsi < overbought)
    short_exits = (rsi_prev <= oversold) & (rsi > oversold)

    return (
        long_entries.fillna(False).values.astype(bool),
        long_exits.fillna(False).values.astype(bool),
        short_entries.fillna(False).values.astype(bool),
        short_exits.fillna(False).values.astype(bool),
    )


def run_comparison():
    """Run backtest with and without Bar Magnifier using real data on multiple timeframes."""
    print("=" * 70)
    print("BAR MAGNIFIER COMPARISON TEST (3 MONTHS, Multiple Timeframes)")
    print("=" * 70)

    # Test configuration
    timeframes = [
        ("15", 3 * 30 * 24 * 4, "15m"),  # 3 months of 15-minute candles
        ("30", 3 * 30 * 24 * 2, "30m"),  # 3 months of 30-minute candles
        ("60", 3 * 30 * 24, "1h"),  # 3 months of 1-hour candles
    ]

    results_summary = []

    for interval, limit, label in timeframes:
        print(f"\n{'=' * 70}")
        print(f"TESTING {label.upper()} TIMEFRAME")
        print("=" * 70)

        # Load data
        print(f"\n📊 Loading {label} data from database...")
        df_htf, df_1m = load_real_data("BTCUSDT", interval, min(limit, 8000))  # Cap at 8000 for performance

        if df_htf is None or df_htf.empty:
            print(f"❌ No {label} data found!")
            continue

        print(f"   {label} candles: {len(df_htf)}")
        print(f"   1M candles: {len(df_1m) if df_1m is not None else 0}")
        print(f"   Period: {df_htf['timestamp'].min()} to {df_htf['timestamp'].max()}")

        if df_1m is None or df_1m.empty:
            print(f"⚠️ No 1M data available for {label}")
            continue

        # Generate RSI signals
        long_entries, long_exits, short_entries, short_exits = generate_rsi_signals(df_htf)
        signal_count = np.sum(long_entries) + np.sum(short_entries)
        print(f"   Entry signals: {signal_count}")

        engine = FallbackEngineV2()

        # Run WITHOUT Bar Magnifier
        input_no_bm = BacktestInput(
            candles=df_htf,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            initial_capital=10000.0,
            leverage=10,
            position_size=0.1,
            stop_loss=0.02,
            take_profit=0.03,
            taker_fee=0.0006,
            slippage=0.0001,
            direction=TradeDirection.BOTH,
            use_bar_magnifier=False,
            candles_1m=None,
        )
        result_no_bm = engine.run(input_no_bm)

        # Run WITH Bar Magnifier
        input_with_bm = BacktestInput(
            candles=df_htf,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            initial_capital=10000.0,
            leverage=10,
            position_size=0.1,
            stop_loss=0.02,
            take_profit=0.03,
            taker_fee=0.0006,
            slippage=0.0001,
            direction=TradeDirection.BOTH,
            use_bar_magnifier=True,
            candles_1m=df_1m,
        )
        result_with_bm = engine.run(input_with_bm)

        # Calculate stats
        trades_no_bm = result_no_bm.trades
        trades_with_bm = result_with_bm.trades

        mfe_no_bm = [t.mfe for t in trades_no_bm if t.mfe and t.mfe > 0]
        mfe_with_bm = [t.mfe for t in trades_with_bm if t.mfe and t.mfe > 0]
        mae_no_bm = [t.mae for t in trades_no_bm if t.mae and t.mae > 0]
        mae_with_bm = [t.mae for t in trades_with_bm if t.mae and t.mae > 0]

        avg_mfe_no_bm = np.mean(mfe_no_bm) if mfe_no_bm else 0
        avg_mfe_with_bm = np.mean(mfe_with_bm) if mfe_with_bm else 0
        avg_mae_no_bm = np.mean(mae_no_bm) if mae_no_bm else 0
        avg_mae_with_bm = np.mean(mae_with_bm) if mae_with_bm else 0

        mfe_diff = ((avg_mfe_with_bm - avg_mfe_no_bm) / avg_mfe_no_bm * 100) if avg_mfe_no_bm > 0 else 0
        mae_diff = ((avg_mae_with_bm - avg_mae_no_bm) / avg_mae_no_bm * 100) if avg_mae_no_bm > 0 else 0

        # Store results
        results_summary.append(
            {
                "timeframe": label,
                "trades_no_bm": len(trades_no_bm),
                "trades_with_bm": len(trades_with_bm),
                "pnl_no_bm": result_no_bm.metrics.net_profit,
                "pnl_with_bm": result_with_bm.metrics.net_profit,
                "avg_mfe_no_bm": avg_mfe_no_bm,
                "avg_mfe_with_bm": avg_mfe_with_bm,
                "mfe_diff": mfe_diff,
                "avg_mae_no_bm": avg_mae_no_bm,
                "avg_mae_with_bm": avg_mae_with_bm,
                "mae_diff": mae_diff,
            }
        )

        # Print detailed results
        print(f"\n📈 Trades: {len(trades_no_bm)} (no BM) vs {len(trades_with_bm)} (with BM)")
        print(f"📊 Net Profit: ${result_no_bm.metrics.net_profit:,.2f} vs ${result_with_bm.metrics.net_profit:,.2f}")
        print(f"   MFE: ${avg_mfe_no_bm:,.2f} vs ${avg_mfe_with_bm:,.2f} ({mfe_diff:+.1f}%)")
        print(f"   MAE: ${avg_mae_no_bm:,.2f} vs ${avg_mae_with_bm:,.2f} ({mae_diff:+.1f}%)")

    # Print summary table
    print("\n" + "=" * 70)
    print("SUMMARY TABLE")
    print("=" * 70)
    print(f"{'TF':<6} {'Trades':<10} {'PnL Diff':<12} {'MFE Diff':<12} {'MAE Diff':<12}")
    print("-" * 52)

    for r in results_summary:
        trade_match = "✓" if r["trades_no_bm"] == r["trades_with_bm"] else "✗"
        pnl_diff = r["pnl_with_bm"] - r["pnl_no_bm"]
        print(
            f"{r['timeframe']:<6} {r['trades_no_bm']:>3}/{r['trades_with_bm']:<3} {trade_match}  "
            f"${pnl_diff:>+8.2f}   {r['mfe_diff']:>+8.1f}%   {r['mae_diff']:>+8.1f}%"
        )

    print("\n✅ Test complete!")


if __name__ == "__main__":
    run_comparison()
