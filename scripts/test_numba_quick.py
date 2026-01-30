"""Quick test for NumbaEngineV2 changes"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import sqlite3

conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC LIMIT 200
""", conn)
df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df.set_index('open_time', inplace=True)
conn.close()

# RSI
def rsi(close, p=14):
    d = close.diff()
    g = d.where(d > 0, 0)
    l = -d.where(d < 0, 0)
    ag = g.rolling(p).mean()
    al = l.rolling(p).mean()
    return 100 - (100 / (1 + ag / al))

r = rsi(df['close'], 7)
le = (r < 30).values
lx = (r > 70).values
se = (r > 70).values
sx = (r < 30).values

from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

inp = BacktestInput(
    candles=df, long_entries=le, long_exits=lx, short_entries=se, short_exits=sx,
    symbol='BTCUSDT', interval='60', initial_capital=10000.0, position_size=0.1, 
    leverage=10, stop_loss=0.02, take_profit=0.04, direction=TradeDirection.BOTH, 
    taker_fee=0.001, slippage=0.0005, use_bar_magnifier=False
)

print("Running Fallback...")
fb = FallbackEngineV2().run(inp)
print("Running Numba...")
nb = NumbaEngineV2().run(inp)

print(f"\nFB: {len(fb.trades)} trades, Net: ${fb.metrics.net_profit:.2f}")
print(f"NB: {len(nb.trades)} trades, Net: ${nb.metrics.net_profit:.2f}")
print(f"Match: {'YES' if abs(fb.metrics.net_profit - nb.metrics.net_profit) < 0.01 else 'NO'}")

# Check trade details
if fb.trades and nb.trades:
    print(f"\nFirst trade comparison:")
    print(f"  FB: size={fb.trades[0].size:.6f}, fees={fb.trades[0].fees:.4f}, pnl_pct={fb.trades[0].pnl_pct:.4f}")
    print(f"  NB: size={nb.trades[0].size:.6f}, fees={nb.trades[0].fees:.4f}, pnl_pct={nb.trades[0].pnl_pct:.4f}")
