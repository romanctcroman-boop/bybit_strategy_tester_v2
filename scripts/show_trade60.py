"""Show trade #60 from Numba"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import sqlite3

conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df_1h = pd.read_sql("""SELECT open_time, open_price as open, high_price as high, low_price as low, close_price as close 
FROM bybit_kline_audit WHERE symbol='BTCUSDT' AND interval='60' ORDER BY open_time ASC LIMIT 500""", conn)
df_1h['open_time'] = pd.to_datetime(df_1h['open_time'], unit='ms')
df_1h.set_index('open_time', inplace=True)

df_1m = pd.read_sql("""SELECT open_time, open_price as open, high_price as high, low_price as low, close_price as close 
FROM bybit_kline_audit WHERE symbol='BTCUSDT' AND interval='1' ORDER BY open_time ASC""", conn)
df_1m['open_time'] = pd.to_datetime(df_1m['open_time'], unit='ms')
df_1m.set_index('open_time', inplace=True)
df_1m = df_1m[(df_1m.index >= df_1h.index[0]) & (df_1m.index <= df_1h.index[-1])]
conn.close()

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(df_1h['close'], period=14)
long_entries = (rsi < 30).values
long_exits = (rsi > 70).values
short_entries = (rsi > 70).values
short_exits = (rsi < 30).values

from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

input_data = BacktestInput(
    candles=df_1h, candles_1m=df_1m,
    long_entries=long_entries, long_exits=long_exits,
    short_entries=short_entries, short_exits=short_exits,
    symbol='BTCUSDT', interval='60',
    initial_capital=5000, position_size=0.25, leverage=50,
    stop_loss=0.01, take_profit=0.02,
    direction=TradeDirection.BOTH,
    taker_fee=0.001, slippage=0.001,
    use_bar_magnifier=True,
)

nb = NumbaEngineV2()
nb_result = nb.run(input_data)

print(f"Numba total trades: {len(nb_result.trades)}")
print(f"\nTrade #59: {nb_result.trades[58]}")
print(f"\nTrade #60: {nb_result.trades[59]}")
