"""
Check if Fallback opens a position after trade 20
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

import pandas as pd

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

strategy = RSIStrategy(params={"period": 14, "overbought": 70, "oversold": 30})
signals = strategy.generate_signals(df)

engine = get_engine()

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

result = engine._run_fallback(config, df, signals)

print(f"Fallback trades: {len(result.trades)}")
print(f"Final equity from equity_curve: {result.equity_curve.equity[-1]:.2f}")
print(f"Net PnL: {result.metrics.net_profit:.2f}")
print(f"Expected (10000 + pnl): {10000 + result.metrics.net_profit:.2f}")

# Last trades
print("\nLast 3 trades:")
for i, t in enumerate(result.trades[-3:]):
    print(f"  Trade {len(result.trades)-2+i}: entry_bar={t.entry_bar_index}, exit_bar={t.exit_bar_index}, side={t.side}, pnl={t.pnl:.2f}")
