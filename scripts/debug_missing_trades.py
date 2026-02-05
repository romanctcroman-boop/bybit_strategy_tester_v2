"""Debug which trades V3 is skipping."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
from backend.backtesting.interfaces import BacktestInput, TradeDirection

# Load and filter data
ohlc = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
ohlc['timestamp'] = pd.to_datetime(ohlc['timestamp'], utc=True).dt.tz_localize(None)
start_date = pd.Timestamp('2025-12-21 15:00:00')
verified_ohlc = ohlc[ohlc['timestamp'] >= start_date].reset_index(drop=True)

# RSI signals
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

print(f"V2: {len(r2.trades)} trades")
print(f"V3: {len(r3.trades)} trades")

# Find missing trades by matching entry prices
v2_entries = [(t.entry_price, t.direction) for t in r2.trades]
v3_entries = [(t.entry_price, t.direction) for t in r3.trades]

print("\n=== V2 trades NOT in V3 ===")
for i, t in enumerate(r2.trades):
    found = False
    for t3 in r3.trades:
        if abs(t.entry_price - t3.entry_price) < 1 and t.direction == t3.direction:
            found = True
            break
    if not found:
        print(f"Trade {i+1}: {t.direction} entry={t.entry_price:.2f} exit={t.exit_price:.2f} pnl={t.pnl:.2f}")

print("\n=== V3 trades NOT in V2 ===")
for i, t in enumerate(r3.trades):
    found = False
    for t2 in r2.trades:
        if abs(t.entry_price - t2.entry_price) < 1 and t.direction == t2.direction:
            found = True
            break
    if not found:
        print(f"Trade {i+1}: {t.direction} entry={t.entry_price:.2f} exit={t.exit_price:.2f} pnl={t.pnl:.2f}")
