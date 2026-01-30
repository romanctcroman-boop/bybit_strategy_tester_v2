"""Debug Numba equity structure"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import sqlite3

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

from backend.backtesting.strategies import RSIStrategy
from backend.backtesting.numba_engine import simulate_trades_numba

# Generate signals
strategy = RSIStrategy(params={"period": 14, "overbought": 70, "oversold": 30})
signals = strategy.generate_signals(df)

close = df['close'].values.astype(np.float64)
high = df['high'].values.astype(np.float64)
low = df['low'].values.astype(np.float64)

long_entries = signals.entries.values.astype(np.bool_)
long_exits = signals.exits.values.astype(np.bool_)
short_entries = signals.short_entries.values.astype(np.bool_)
short_exits = signals.short_exits.values.astype(np.bool_)

trades, equity, _, n_trades = simulate_trades_numba(
    close, high, low,
    long_entries, long_exits,
    short_entries, short_exits,
    10000.0, 1.0, 0.0004, 0.0001,
    0.03, 0.06, 1.0, 2
)

print(f"Total bars: {len(equity)}")
print(f"Total trades: {n_trades}")
print(f"\nFirst 20 equity values:")
print(equity[:20])
print(f"\nLast 20 equity values:")
print(equity[-20:])
print(f"\nZeros in equity: {np.sum(equity == 0)}")
print(f"Non-zero count: {np.sum(equity > 0)}")
print(f"\nEquity stats:")
print(f"  Min: {np.min(equity):.2f}")
print(f"  Max: {np.max(equity):.2f}")
print(f"  Mean: {np.mean(equity):.2f}")

# Calculate returns
equity_fixed = equity.copy()
equity_fixed[equity_fixed <= 0] = 10000.0

returns = np.diff(equity_fixed) / equity_fixed[:-1]
returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)

print(f"\nReturns stats:")
print(f"  Non-zero returns: {np.sum(returns != 0)}")
print(f"  Mean return: {np.mean(returns)*100:.6f}%")
print(f"  Std return: {np.std(returns)*100:.6f}%")

# Sharpe
mean_ret = np.mean(returns)
std_ret = np.std(returns, ddof=1)
periods_per_year = 8760
risk_free_rate = 0.02
period_rfr = risk_free_rate / periods_per_year

sharpe = (mean_ret - period_rfr) / std_ret * np.sqrt(periods_per_year) if std_ret > 1e-10 else 0
print(f"\nNumba Sharpe: {sharpe:.3f}")
