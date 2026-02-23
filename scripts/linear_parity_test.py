"""
LINEAR Parity Test: BTCUSDH2026
================================
Full parity comparison between our backtesting engine and TradingView
for quarterly futures (LINEAR) market.

Usage:
    python scripts/linear_parity_test.py
"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import sqlite3

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection


def get_btcusdh2026_candles() -> pd.DataFrame:
    """Load BTCUSDH2026 data from database as DataFrame."""
    db_path = project_root / "data.sqlite3"
    conn = sqlite3.connect(str(db_path))

    query = """
        SELECT
            open_time as timestamp,
            open_price as open,
            high_price as high,
            low_price as low,
            close_price as close,
            volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDH2026'
          AND interval = '15'
        ORDER BY open_time ASC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    return df


def generate_rsi_signals(candles: pd.DataFrame, period: int, overbought: int, oversold: int):
    """Generate RSI crossover signals matching TradingView logic."""
    closes = candles['close'].values

    # Calculate RSI using Wilder's smoothing (RMA)
    delta = np.diff(closes, prepend=closes[0])
    gains = np.where(delta > 0, delta, 0)
    losses = np.where(delta < 0, -delta, 0)

    # Wilder's smoothing (RMA)
    alpha = 1.0 / period
    avg_gain = np.zeros(len(closes))
    avg_loss = np.zeros(len(closes))

    # Initialize
    avg_gain[period] = np.mean(gains[1:period+1])
    avg_loss[period] = np.mean(losses[1:period+1])

    # Calculate using RMA
    for i in range(period + 1, len(closes)):
        avg_gain[i] = avg_gain[i-1] * (1 - alpha) + gains[i] * alpha
        avg_loss[i] = avg_loss[i-1] * (1 - alpha) + losses[i] * alpha

    # Calculate RSI
    rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
    rsi = 100 - (100 / (1 + rs))

    # Generate crossover signals (TradingView style)
    # ta.crossover: prev <= level AND curr > level
    # ta.crossunder: prev >= level AND curr < level

    long_entries = np.zeros(len(closes), dtype=bool)
    short_entries = np.zeros(len(closes), dtype=bool)

    warmup = period * 4  # RSI warmup period

    for i in range(warmup + 1, len(closes)):
        prev_rsi = rsi[i-1]
        curr_rsi = rsi[i]

        # Crossover: RSI crosses ABOVE oversold (Long entry)
        if prev_rsi <= oversold and curr_rsi > oversold:
            # Signal at i, but entry at i+1 (Next-Bar Entry)
            if i + 1 < len(closes):
                long_entries[i + 1] = True

        # Crossunder: RSI crosses BELOW overbought (Short entry)
        if prev_rsi >= overbought and curr_rsi < overbought and i + 1 < len(closes):
            short_entries[i + 1] = True

    return long_entries, short_entries


def run_parity_test():
    """Run full parity test on BTCUSDH2026 data."""

    print("=" * 70)
    print("🎯 LINEAR PARITY TEST: BTCUSDH2026")
    print("=" * 70)
    print()

    # Load data
    print("📊 Loading BTCUSDH2026 data from database...")
    candles = get_btcusdh2026_candles()
    print(f"   Loaded: {len(candles)} candles")

    if len(candles) == 0:
        print("❌ No data found! Run import_tv_btcusdh2026.py first.")
        return None

    # Date range
    start_ts = candles['timestamp'].iloc[0]
    end_ts = candles['timestamp'].iloc[-1]
    start_dt = datetime.utcfromtimestamp(start_ts / 1000)
    end_dt = datetime.utcfromtimestamp(end_ts / 1000)
    print(f"   Range: {start_dt.date()} to {end_dt.date()}")
    print()

    # Strategy parameters (matching TradingView)
    rsi_period = 14
    rsi_overbought = 70
    rsi_oversold = 25
    take_profit = 0.015  # 1.5%
    stop_loss = 0.03     # 3.0%
    leverage = 10
    initial_capital = 100.0

    print("⚙️ Strategy Configuration:")
    print(f"   RSI Period: {rsi_period}")
    print(f"   Overbought: {rsi_overbought}")
    print(f"   Oversold: {rsi_oversold}")
    print(f"   Take Profit: {take_profit*100}%")
    print(f"   Stop Loss: {stop_loss*100}%")
    print(f"   Leverage: {leverage}x")
    print()

    # Generate signals
    print("🔍 Generating RSI signals...")
    long_entries, short_entries = generate_rsi_signals(
        candles, rsi_period, rsi_overbought, rsi_oversold
    )
    long_signals = np.sum(long_entries)
    short_signals = np.sum(short_entries)
    print(f"   Long signals: {long_signals}")
    print(f"   Short signals: {short_signals}")
    print()

    # Create engine input
    bt_input = BacktestInput(
        candles=candles,
        candles_1m=None,  # No 1m data available
        long_entries=long_entries,
        long_exits=np.zeros(len(candles), dtype=bool),
        short_entries=short_entries,
        short_exits=np.zeros(len(candles), dtype=bool),
        symbol="BTCUSDH2026",
        interval="15",
        initial_capital=initial_capital,
        position_size=1.0,
        leverage=leverage,
        taker_fee=0.0007,  # 0.07%
        slippage=0.0,
        stop_loss=stop_loss,
        take_profit=take_profit,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,  # No 1m data
    )

    # Run backtest
    print("🚀 Running FallbackEngineV2...")
    engine = FallbackEngineV2()
    result = engine.run(bt_input)

    print()
    print("=" * 70)
    print("📈 BACKTEST RESULTS")
    print("=" * 70)

    metrics = result.metrics
    trades = result.trades

    print(f"\n   Total Trades:    {metrics.total_trades}")
    print(f"   Net Profit:      ${metrics.net_profit:.2f}")
    print(f"   Win Rate:        {metrics.win_rate*100:.1f}%")
    print(f"   Profit Factor:   {metrics.profit_factor:.2f}")
    print(f"   Max Drawdown:    {metrics.max_drawdown:.2f}%")

    # Analyze trades by type
    long_trades = [t for t in trades if t.direction == 'long']
    short_trades = [t for t in trades if t.direction == 'short']

    tp_long = [t for t in long_trades if 'take_profit' in str(t.exit_reason).lower()]
    sl_long = [t for t in long_trades if 'stop_loss' in str(t.exit_reason).lower()]
    tp_short = [t for t in short_trades if 'take_profit' in str(t.exit_reason).lower()]
    sl_short = [t for t in short_trades if 'stop_loss' in str(t.exit_reason).lower()]

    print(f"\n   Long Trades:     {len(long_trades)}")
    print(f"   Short Trades:    {len(short_trades)}")

    print()
    print("=" * 70)
    print("💰 PnL BY EXIT TYPE (Average per trade)")
    print("=" * 70)

    # Calculate average PnL by type
    if tp_long:
        avg_tp_long = sum(t.pnl for t in tp_long) / len(tp_long)
        print(f"\n   TP Long:  +${avg_tp_long:.2f}  ({len(tp_long)} trades)")
    else:
        avg_tp_long = None
        print("\n   TP Long:  N/A (0 trades)")

    if tp_short:
        avg_tp_short = sum(t.pnl for t in tp_short) / len(tp_short)
        print(f"   TP Short: +${avg_tp_short:.2f}  ({len(tp_short)} trades)")
    else:
        avg_tp_short = None
        print("   TP Short: N/A (0 trades)")

    if sl_long:
        avg_sl_long = sum(t.pnl for t in sl_long) / len(sl_long)
        print(f"   SL Long:  ${avg_sl_long:.2f}  ({len(sl_long)} trades)")
    else:
        avg_sl_long = None
        print("   SL Long:  N/A (0 trades)")

    if sl_short:
        avg_sl_short = sum(t.pnl for t in sl_short) / len(sl_short)
        print(f"   SL Short: ${avg_sl_short:.2f}  ({len(sl_short)} trades)")
    else:
        avg_sl_short = None
        print("   SL Short: N/A (0 trades)")

    # TradingView expected values
    print()
    print("=" * 70)
    print("✅ PARITY VERIFICATION (vs TradingView)")
    print("=" * 70)

    tv_expected = {
        "trades": 18,
        "tp_long": +13.59,
        "tp_short": +13.61,
        "sl_long": -31.38,
        "sl_short": -31.42,
    }

    print("\n   Metric          | TradingView | Our System | Status")
    print("   " + "-" * 55)

    # Trade count comparison
    parity_ratio = (metrics.total_trades / tv_expected["trades"]) * 100
    status = "✅" if abs(parity_ratio - 100) < 15 else "⚠️"
    print(f"   Total Trades    | {tv_expected['trades']:>11} | {metrics.total_trades:>10} | {status} {parity_ratio:.1f}%")

    # PnL type comparisons
    matches = []

    def check_pnl(name, expected, actual):
        if actual is not None:
            diff = abs(actual - expected)
            matched = diff < 0.50  # $0.50 tolerance
            status = "✅ MATCH" if matched else f"⚠️ Δ${diff:.2f}"
            print(f"   {name:<14} | {expected:>+11.2f} | {actual:>+10.2f} | {status}")
            return matched
        else:
            print(f"   {name:<14} | {expected:>+11.2f} | {'N/A':>10} | ⚠️ No trades")
            return False

    matches.append(check_pnl("TP Long", tv_expected["tp_long"], avg_tp_long))
    matches.append(check_pnl("TP Short", tv_expected["tp_short"], avg_tp_short))
    matches.append(check_pnl("SL Long", tv_expected["sl_long"], avg_sl_long))
    matches.append(check_pnl("SL Short", tv_expected["sl_short"], avg_sl_short))

    # Summary
    pnl_match_rate = sum(matches) / len(matches) * 100 if matches else 0

    print()
    print("=" * 70)
    print("🏆 FINAL CERTIFICATION")
    print("=" * 70)
    print(f"\n   Trade Parity:    {parity_ratio:.1f}%")
    print(f"   PnL Match Rate:  {pnl_match_rate:.0f}%")

    if pnl_match_rate == 100:
        print("\n   ✅ PnL FORMULAS: 100% IDENTICAL TO TRADINGVIEW!")
    elif pnl_match_rate >= 75:
        print("\n   ✅ PnL FORMULAS: HIGH FIDELITY MATCH!")

    overall_status = "CERTIFIED" if pnl_match_rate >= 75 else "PARTIAL"
    print(f"\n   Overall Status:  {overall_status}")

    # Show sample trades
    print()
    print("=" * 70)
    print("📋 SAMPLE TRADES (First 10)")
    print("=" * 70)
    print("\n   #  | Direction | Entry Time          | PnL      | Exit Reason")
    print("   " + "-" * 65)

    for i, trade in enumerate(trades[:10]):
        if isinstance(trade.entry_time, (int, float)):
            entry_dt = datetime.utcfromtimestamp(trade.entry_time / 1000)
        else:
            entry_dt = trade.entry_time
        direction = "LONG " if trade.direction == 'long' else "SHORT"
        reason = str(trade.exit_reason).split('.')[-1] if trade.exit_reason else "?"
        print(f"   {i+1:>2} | {direction} | {entry_dt.strftime('%Y-%m-%d %H:%M') if hasattr(entry_dt, 'strftime') else entry_dt} | {trade.pnl:>+8.2f} | {reason}")

    print()
    print("=" * 70)
    print("✅ LINEAR PARITY TEST COMPLETE!")
    print("=" * 70)

    return result


if __name__ == "__main__":
    run_parity_test()
