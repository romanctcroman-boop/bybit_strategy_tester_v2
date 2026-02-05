"""
DCA Grid Strategy Test on REAL DATA from Database
Tests LONG and SHORT with all configurable parameters
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from backend.backtesting.engine_selector import get_engine
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.strategies import get_strategy

print("=" * 70)
print("DCA GRID STRATEGY - REAL DATA TEST (BTCUSDT 15m)")
print("=" * 70)

# Load real OHLC data
ohlc = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
ohlc['timestamp'] = pd.to_datetime(ohlc['timestamp'], utc=True).dt.tz_localize(None)

# Use last 2000 bars (~20 days of 15m data)
candles = ohlc.tail(2000).reset_index(drop=True)
n = len(candles)

print(f"\nData: {n} bars (15m timeframe)")
print(f"Period: {candles['timestamp'].iloc[0]} to {candles['timestamp'].iloc[-1]}")
print(f"Price range: ${candles['low'].min():.0f} - ${candles['high'].max():.0f}")

# ============================================
# DCA PARAMETERS (3commas/WunderTrading style)
# ============================================
DCA_PARAMS = {
    # Deal start
    "_direction": "long",
    "cooldown_between_deals": 4,  # Min bars between deals
    "rsi_period": 14,
    "rsi_trigger": 30,  # RSI < 30 for long entry

    # Base order
    "base_order_size": 10.0,  # 10% of capital

    # Safety orders (averaging)
    "max_safety_orders": 5,  # 5 SOs = 6 total orders
    "safety_order_size": 10.0,  # 10% of capital
    "safety_order_volume_scale": 1.05,  # +5% per SO (martingale)
    "price_deviation": 1.0,  # 1% drop triggers SO1
    "step_scale": 1.4,  # SO2 at 1.4%, SO3 at 1.96%, etc.

    # Take profit
    "target_profit": 2.5,  # 2.5% from average price
    "trailing_deviation": 0.4,  # 0.4% trailing

    # Stop loss
    "stop_loss": 4.0,  # 4% SL
    "stop_loss_type": "last_order",  # 'average' or 'last_order'
}

# Backtest parameters
INITIAL_CAPITAL = 10000.0
POSITION_SIZE = DCA_PARAMS["base_order_size"] / 100  # From params
LEVERAGE = 10
PYRAMIDING = 1 + DCA_PARAMS["max_safety_orders"]  # Base + SOs

print(f"\n{'=' * 70}")
print("DCA 3COMMAS-STYLE PARAMETERS:")
print(f"{'=' * 70}")
print("\n  [Deal Start]")
print(f"    Direction: {DCA_PARAMS['_direction']}")
print(f"    Cooldown: {DCA_PARAMS['cooldown_between_deals']} bars")
print(f"    RSI Period: {DCA_PARAMS['rsi_period']}")
print(f"    RSI Trigger: {DCA_PARAMS['rsi_trigger']}")
print("\n  [Base Order]")
print(f"    Size: {DCA_PARAMS['base_order_size']}% of capital")
print("\n  [Safety Orders]")
print(f"    Max SOs: {DCA_PARAMS['max_safety_orders']}")
print(f"    SO Size: {DCA_PARAMS['safety_order_size']}%")
print(f"    Volume Scale: x{DCA_PARAMS['safety_order_volume_scale']}")
print(f"    Price Deviation: {DCA_PARAMS['price_deviation']}%")
print(f"    Step Scale: x{DCA_PARAMS['step_scale']}")
print("\n  [Take Profit]")
print(f"    Target Profit: {DCA_PARAMS['target_profit']}%")
print(f"    Trailing: {DCA_PARAMS['trailing_deviation']}%")
print("\n  [Stop Loss]")
print(f"    Stop Loss: {DCA_PARAMS['stop_loss']}%")
print(f"    Type: {DCA_PARAMS['stop_loss_type']}")
print("\n  [Backtest]")
print(f"    Leverage: {LEVERAGE}x")
print(f"    Pyramiding: {PYRAMIDING}")

# ============================================
# TEST 1: DCA LONG
# ============================================
print(f"\n{'=' * 70}")
print("TEST 1: DCA LONG Strategy")
print(f"{'=' * 70}")

dca_long = get_strategy('dca', {**DCA_PARAMS, '_direction': 'long'})
signals_long = dca_long.generate_signals(candles)

entry_count = signals_long.entries.sum()
exit_count = signals_long.exits.sum()

print("\nSignal Analysis:")
print(f"  Entry signals (RSI < {DCA_PARAMS['rsi_trigger']}): {entry_count}")
print(f"  Exit signals (TP/SL): {exit_count}")

# Get engine with pyramiding support
engine = get_engine(
    strategy_type='dca',
    pyramiding=PYRAMIDING,
    max_entries=PYRAMIDING
)
print(f"\nEngine: {engine.name}")

# Prepare BacktestInput
input_data = BacktestInput(
    candles=candles,
    long_entries=signals_long.entries.values,
    long_exits=signals_long.exits.values,
    short_entries=np.zeros(n, dtype=bool),
    short_exits=np.zeros(n, dtype=bool),
    initial_capital=INITIAL_CAPITAL,
    position_size=POSITION_SIZE,
    leverage=LEVERAGE,
    stop_loss=0.0,      # Handled by strategy signals
    take_profit=0.0,    # Handled by strategy signals
    taker_fee=0.0007,
    direction=TradeDirection.LONG,
    pyramiding=PYRAMIDING,
    close_entries_rule='ALL',
    use_bar_magnifier=False,
)

result_long = engine.run(input_data)

print("\n--- LONG Results ---")
print(f"  Trades: {len(result_long.trades)}")
print(f"  Net Profit: ${result_long.metrics.net_profit:.2f}")
print(f"  Total Return: {result_long.metrics.total_return:.2f}%")
print(f"  Win Rate: {result_long.metrics.win_rate * 100:.1f}%")
print(f"  Max Drawdown: {result_long.metrics.max_drawdown:.2f}%")

if result_long.trades:
    print("\n  First 5 trades:")
    for i, t in enumerate(result_long.trades[:5], 1):
        print(f"    #{i}: Entry ${t.entry_price:.0f} → Exit ${t.exit_price:.0f}, PnL ${t.pnl:.2f} ({t.pnl_pct*100:.2f}%)")

# ============================================
# TEST 2: DCA SHORT
# ============================================
print(f"\n{'=' * 70}")
print("TEST 2: DCA SHORT Strategy")
print(f"{'=' * 70}")

dca_short = get_strategy('dca', {**DCA_PARAMS, '_direction': 'short'})
signals_short = dca_short.generate_signals(candles)

entry_count_short = signals_short.short_entries.sum()
exit_count_short = signals_short.short_exits.sum()

print("\nSignal Analysis:")
print(f"  Entry signals (RSI trigger): {entry_count_short}")
print(f"  Exit signals (TP/SL): {exit_count_short}")

# Prepare BacktestInput for SHORT
input_data_short = BacktestInput(
    candles=candles,
    long_entries=np.zeros(n, dtype=bool),
    long_exits=np.zeros(n, dtype=bool),
    short_entries=signals_short.short_entries.values,
    short_exits=signals_short.short_exits.values,
    initial_capital=INITIAL_CAPITAL,
    position_size=POSITION_SIZE,
    leverage=LEVERAGE,
    stop_loss=0.0,
    take_profit=0.0,
    taker_fee=0.0007,
    direction=TradeDirection.SHORT,
    pyramiding=PYRAMIDING,
    close_entries_rule='ALL',
    use_bar_magnifier=False,
)

result_short = engine.run(input_data_short)

print("\n--- SHORT Results ---")
print(f"  Trades: {len(result_short.trades)}")
print(f"  Net Profit: ${result_short.metrics.net_profit:.2f}")
print(f"  Total Return: {result_short.metrics.total_return:.2f}%")
print(f"  Win Rate: {result_short.metrics.win_rate * 100:.1f}%")
print(f"  Max Drawdown: {result_short.metrics.max_drawdown:.2f}%")

if result_short.trades:
    print("\n  First 5 trades:")
    for i, t in enumerate(result_short.trades[:5], 1):
        print(f"    #{i}: Entry ${t.entry_price:.0f} → Exit ${t.exit_price:.0f}, PnL ${t.pnl:.2f} ({t.pnl_pct*100:.2f}%)")

# ============================================
# SUMMARY
# ============================================
print(f"\n{'=' * 70}")
print("SUMMARY")
print(f"{'=' * 70}")
print(f"\n{'Strategy':<15} {'Trades':<10} {'Net Profit':<15} {'Return':<10} {'Win Rate':<10}")
print(f"{'-'*60}")
print(f"{'DCA LONG':<15} {len(result_long.trades):<10} ${result_long.metrics.net_profit:<14.2f} {result_long.metrics.total_return:<9.2f}% {result_long.metrics.win_rate*100:<9.1f}%")
print(f"{'DCA SHORT':<15} {len(result_short.trades):<10} ${result_short.metrics.net_profit:<14.2f} {result_short.metrics.total_return:<9.2f}% {result_short.metrics.win_rate*100:<9.1f}%")

combined_profit = result_long.metrics.net_profit + result_short.metrics.net_profit
combined_return = (combined_profit / INITIAL_CAPITAL) * 100
print(f"\n{'COMBINED':<15} {len(result_long.trades) + len(result_short.trades):<10} ${combined_profit:<14.2f} {combined_return:<9.2f}%")

print(f"\n{'=' * 70}")
print("✅ DCA REAL DATA TEST COMPLETED!")
print(f"{'=' * 70}")
