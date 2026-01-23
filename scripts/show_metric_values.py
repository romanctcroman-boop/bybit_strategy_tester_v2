"""Check non-zero values for 46 core metrics"""
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')
import numpy as np
import pandas as pd
import sqlite3
from dataclasses import fields

conn = sqlite3.connect('d:/bybit_strategy_tester_v2/data.sqlite3')
df = pd.read_sql("""SELECT open_time, open_price as open, high_price as high, 
    low_price as low, close_price as close, volume 
    FROM bybit_kline_audit WHERE symbol='BTCUSDT' AND interval='60' 
    ORDER BY open_time ASC LIMIT 1000""", conn)
df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df.set_index('open_time', inplace=True)
conn.close()

# RSI + EMA strategy 
close = df['close']
delta = close.diff()
gain = delta.where(delta > 0, 0).rolling(7).mean()
loss = -delta.where(delta < 0, 0).rolling(7).mean()
rsi = 100 - (100 / (1 + gain / loss))
ema20 = close.ewm(span=20).mean()

long_entries = ((rsi < 25) & (close > ema20)).values
long_exits = (rsi > 75).values
short_entries = ((rsi > 75) & (close < ema20)).values
short_exits = (rsi < 25).values

from backend.backtesting.interfaces import BacktestInput, TradeDirection, BacktestMetrics
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.core.extended_metrics import ExtendedMetricsCalculator, ExtendedMetricsResult

input_data = BacktestInput(
    candles=df, long_entries=long_entries, long_exits=long_exits,
    short_entries=short_entries, short_exits=short_exits,
    symbol='BTCUSDT', interval='60', initial_capital=10000,
    position_size=0.15, leverage=10, stop_loss=0.03, take_profit=0.06,
    direction=TradeDirection.BOTH, taker_fee=0.001, slippage=0.0005)

result = FallbackEngineV2().run(input_data)
ext = ExtendedMetricsCalculator().calculate_all(result.equity_curve, result.trades)

print(f'Trades: {len(result.trades)}, Net Profit: ${result.metrics.net_profit:.2f}')
print(f'Final Equity: ${result.equity_curve[-1]:.2f}')

# Show all metrics
print('\n=== BacktestMetrics (32) ===')
non_zero = 0
for f in fields(BacktestMetrics):
    if not f.name.startswith('_'):
        v = getattr(result.metrics, f.name)
        if isinstance(v, (int, np.integer)):
            print(f'  {f.name}: {v}')
            if v != 0: non_zero += 1
        elif v is not None:
            print(f'  {f.name}: {v:.6f}')
            if abs(v) > 1e-10: non_zero += 1
        else:
            print(f'  {f.name}: None')

print(f'\n=== ExtendedMetrics (14) ===')
for f in fields(ExtendedMetricsResult):
    if not f.name.startswith('_'):
        v = getattr(ext, f.name)
        if v is not None:
            print(f'  {f.name}: {v:.6f}')
            if abs(v) > 1e-10: non_zero += 1
        else:
            print(f'  {f.name}: None')

print(f'\n=== ИТОГО ===')
print(f'Ненулевых метрик: {non_zero}/46')
