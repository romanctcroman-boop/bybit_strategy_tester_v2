"""Test V2/V3 parity on verified data period (Dec 21+)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
from backend.backtesting.interfaces import BacktestInput, TradeDirection

# Load full data
ohlc = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
ohlc['timestamp'] = pd.to_datetime(ohlc['timestamp'], utc=True).dt.tz_localize(None)

# Filter to verified period (Dec 21 15:00 UTC = Dec 21 18:00 Moscow)
start_date = pd.Timestamp('2025-12-21 15:00:00')
mask = ohlc['timestamp'] >= start_date
verified_ohlc = ohlc[mask].reset_index(drop=True)
print(f"Verified period: {verified_ohlc['timestamp'].iloc[0]} to {verified_ohlc['timestamp'].iloc[-1]}")
print(f"Bars: {len(verified_ohlc)}")

# Generate simple RSI signals for this period using numpy
def calc_rsi(close, period=14):
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=period, min_periods=1).mean().values
    avg_loss = pd.Series(loss).rolling(window=period, min_periods=1).mean().values
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))

rsi = calc_rsi(verified_ohlc['close'].values)
long_signals = rsi < 40
short_signals = rsi > 60
print(f"Signals: {sum(long_signals)} long, {sum(short_signals)} short")

# Run V2
candles = verified_ohlc.reset_index(drop=True)
input_data = BacktestInput(
    candles=candles, candles_1m=None, initial_capital=1_000_000.0,
    use_fixed_amount=True, fixed_amount=100.0, leverage=10,
    take_profit=0.015, stop_loss=0.03, taker_fee=0.0007,
    direction=TradeDirection.BOTH,
    long_entries=long_signals, short_entries=short_signals,
    use_bar_magnifier=False,
)

v2 = FallbackEngineV2()
r2 = v2.run(input_data)

v3 = FallbackEngineV3()
r3 = v3.run(input_data)

print("\n=== V2 ===")
print(f"Trades: {len(r2.trades)}, Net Profit: {r2.metrics.net_profit:.2f}")

print("\n=== V3 ===")
print(f"Trades: {len(r3.trades)}, Net Profit: {r3.metrics.net_profit:.2f}")

# Compare
if len(r2.trades) == len(r3.trades):
    all_match = True
    for i, (t2, t3) in enumerate(zip(r2.trades, r3.trades)):
        if abs(t2.entry_price - t3.entry_price) > 0.01 or abs(t2.pnl - t3.pnl) > 0.01:
            print(f"\nTrade {i+1} mismatch:")
            print(f"  V2: entry={t2.entry_price:.2f}, pnl={t2.pnl:.2f}")
            print(f"  V3: entry={t3.entry_price:.2f}, pnl={t3.pnl:.2f}")
            all_match = False
    if all_match:
        print("\n✅ ALL TRADES MATCH!")
else:
    print(f"\n❌ Trade count mismatch: V2={len(r2.trades)} vs V3={len(r3.trades)}")
