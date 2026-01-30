"""
Check data length in Fallback
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import sqlite3

from backend.backtesting.engine import get_engine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategies import RSIStrategy

# Load data
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    AND open_time >= 1735689600000
    AND open_time < 1737504000000
    ORDER BY open_time ASC
""", conn)
conn.close()

df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df.set_index('open_time', inplace=True)

print(f"DataFrame rows: {len(df)}")
print(f"First date: {df.index[0]}")
print(f"Last date: {df.index[-1]}")

# Check equity curve length
config = BacktestConfig(
    symbol="BTCUSDT",
    interval="60",
    start_date="2025-01-01",
    end_date="2025-01-22",
    initial_capital=10000.0,
    leverage=1,
    taker_fee=0.0004,
    slippage=0.0001,
    stop_loss=0.03,
    take_profit=0.06,
    direction="both",
    strategy_type="rsi",
    strategy_params={"period": 14, "overbought": 70, "oversold": 30},
    use_bar_magnifier=False,
)

strategy = RSIStrategy(params={"period": 14, "overbought": 70, "oversold": 30})
signals = strategy.generate_signals(df)

engine = get_engine()
result = engine._run_fallback(config, df, signals)

print(f"Equity curve length: {len(result.equity_curve.equity)}")
print(f"Last equity: {result.equity_curve.equity[-1]:.2f}")

# Check trade 20 details
t20 = result.trades[-1]
print(f"\nTrade 20:")
print(f"  entry_bar_index: {t20.entry_bar_index}")
print(f"  exit_bar_index: {t20.exit_bar_index}")
print(f"  exit_time: {t20.exit_time}")
