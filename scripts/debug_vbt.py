"""Debug state in actual vectorbt_sltp flow."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import sqlite3

import pandas as pd

# Load data
db_path = ROOT / "data.sqlite3"
conn = sqlite3.connect(str(db_path))
df = pd.read_sql(
    """SELECT open_time, open_price as open, high_price as high,
       low_price as low, close_price as close, volume
    FROM bybit_kline_audit WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time DESC LIMIT 200""", conn)
conn.close()
df = df.sort_values("open_time").reset_index(drop=True)
df["datetime"] = pd.to_datetime(df["open_time"], unit="ms")
df = df.set_index("datetime")

# Mock config
class MockConfig:
    initial_capital = 10000.0
    position_size = 1.0
    leverage = 10.0
    stop_loss = 0.02
    take_profit = 0.04
    taker_fee = 0.0004
    slippage = 0.0005
    direction = 'short'

# Get signals
from backend.backtesting.strategies import get_strategy

strategy = get_strategy('rsi')
strategy.params = {'period': 14, 'overbought': 70, 'oversold': 30}
strategy.direction = 'short'
signals = strategy.generate_signals(df)

# Run
from backend.backtesting.vectorbt_sltp import run_vectorbt_with_sltp

config = MockConfig()
pf = run_vectorbt_with_sltp(df, signals, config)

print(f"Trades: {len(pf.trades.records)}")

# Print first few trades
trades_df = pf.trades.records_readable
print(trades_df[['Entry Timestamp', 'Avg Entry Price', 'Avg Exit Price', 'Size', 'PnL']].head())
