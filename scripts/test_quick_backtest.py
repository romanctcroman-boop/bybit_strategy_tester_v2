"""Quick test: Verify fallback engine works correctly."""
import sqlite3

import pandas as pd

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig

# Load data
conn = sqlite3.connect('data.sqlite3')
df = pd.read_sql('''
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume 
    FROM bybit_kline_audit 
    WHERE symbol='BTCUSDT' AND interval='60' 
    ORDER BY open_time DESC LIMIT 100
''', conn)
conn.close()

df = df.sort_values('open_time')
df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
df = df.set_index('datetime')

# Create config
config = BacktestConfig(
    symbol='BTCUSDT',
    interval='60',
    strategy_type='rsi',
    strategy_params={'period': 14, 'overbought': 70, 'oversold': 30},
    initial_capital=10000,
    leverage=10,
    position_size=1.0,
    direction='both',
    stop_loss=0.02,
    take_profit=0.04,
    start_date=df.index[0],
    end_date=df.index[-1]
)

# Run backtest
engine = BacktestEngine()
result = engine.run(config, df, silent=True)

print("✅ Backtest completed successfully!")
print(f"   Trades: {result.metrics.total_trades}")
print(f"   Net Profit: ${result.metrics.net_profit:.2f}")
print(f"   Win Rate: {result.metrics.win_rate:.1f}%")
print("   Engine: Fallback (authoritative)")
