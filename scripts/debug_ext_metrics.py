"""
Quick debug - check extended metrics values
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import sqlite3

# Load data
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df_1h = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
    LIMIT 500
""", conn)
df_1h['open_time'] = pd.to_datetime(df_1h['open_time'], unit='ms')
df_1h.set_index('open_time', inplace=True)
conn.close()

# RSI
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(df_1h['close'], 14)
long_entries = (rsi < 30).values
long_exits = (rsi > 70).values
short_entries = (rsi > 70).values
short_exits = (rsi < 30).values

from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.core.extended_metrics import ExtendedMetricsCalculator

input_data = BacktestInput(
    candles=df_1h,
    candles_1m=None,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    symbol="BTCUSDT",
    interval="60",
    initial_capital=10000.0,
    position_size=0.10,
    leverage=10,
    stop_loss=0.03,
    take_profit=0.02,
    direction=TradeDirection.BOTH,
    taker_fee=0.001,
    slippage=0.0005,
    use_bar_magnifier=False,
)

fb = FallbackEngineV2().run(input_data)
nb = NumbaEngineV2().run(input_data)

calc = ExtendedMetricsCalculator()
fb_ext = calc.calculate_all(fb.equity_curve, fb.trades)
nb_ext = calc.calculate_all(nb.equity_curve, nb.trades)

print("=" * 80)
print("EXTENDED METRICS COMPARISON")
print("=" * 80)

metrics = ["sortino_ratio", "calmar_ratio", "omega_ratio", "recovery_factor", 
           "ulcer_index", "tail_ratio", "downside_deviation", "upside_potential_ratio", 
           "gain_to_pain_ratio", "profit_factor"]

print(f"\n{'Metric':<25} {'Fallback':>15} {'Numba':>15} {'Match':>10}")
print("-" * 65)

for m in metrics:
    fb_val = getattr(fb_ext, m, 0.0)
    nb_val = getattr(nb_ext, m, 0.0)
    match = "✅" if abs(fb_val - nb_val) < 0.0001 else "❌"
    print(f"{m:<25} {fb_val:>15.4f} {nb_val:>15.4f} {match:>10}")

print("\n" + "=" * 80)
print("TRADES INFO")
print("=" * 80)
print(f"Fallback trades: {len(fb.trades)}")
print(f"Numba trades:    {len(nb.trades)}")

if fb.trades:
    print(f"\nFallback trade[0]: {fb.trades[0]}")
if nb.trades:
    print(f"Numba trade[0]:    {nb.trades[0]}")
