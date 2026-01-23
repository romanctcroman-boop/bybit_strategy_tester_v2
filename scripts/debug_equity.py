"""Debug equity calculation."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import sqlite3
import pandas as pd
import numpy as np
from numba import njit
import vectorbt as vbt
from vectorbt.portfolio.nb import order_nb, order_nothing_nb
from vectorbt.portfolio.enums import Direction

@njit
def debug_flex_order_nb(c, entries, sl_pct, tp_pct, leverage, fees, slippage):
    """Debug order func to print equity."""
    col = c.from_col
    i = c.i
    
    if c.call_idx >= 2:
        return -1, order_nothing_nb()
    
    position_now = c.last_position[col]
    cash_now = c.last_cash[col]
    value_now = c.last_value[col]
    close_now = c.close[i, col]
    
    # Entry
    if c.call_idx == 0 and position_now == 0 and entries[i, 0]:
        entry_px = close_now * (1.0 + slippage)
        # Use value (equity) for sizing
        size = value_now * 1.0 * leverage / entry_px
        print("Entry at bar", i, ": cash=", cash_now, "value=", value_now, "size=", size)
        return col, order_nb(size=size, price=entry_px, fees=fees, direction=Direction.ShortOnly)
    
    # Exit (simplified - just on SL)  
    if c.call_idx == 0 and position_now != 0:
        last_oidx = c.last_oidx[col]
        if last_oidx >= 0:
            entry_order = c.order_records[last_oidx]
            entry_price = entry_order[4]
            # For short: entry * 1.002 = SL (0.2% adverse move)
            sl_price = entry_price * (1.0 + sl_pct / leverage)
            high_now = c.close[i, col] * 1.01  # Approximate
            if high_now >= sl_price:
                print("Exit SL at bar", i, ": position=", position_now)
                return col, order_nb(size=-position_now, price=sl_price, fees=fees)
    
    return -1, order_nothing_nb()


# Load data  
db_path = ROOT / "data.sqlite3"
conn = sqlite3.connect(str(db_path))
df = pd.read_sql(
    """SELECT open_time, open_price as open, high_price as high,
       low_price as low, close_price as close, volume
    FROM bybit_kline_audit WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time DESC LIMIT 100""", conn)
conn.close()
df = df.sort_values("open_time").reset_index(drop=True)
df["datetime"] = pd.to_datetime(df["open_time"], unit="ms")
df = df.set_index("datetime")

# Get signals for short
from backend.backtesting.strategies import get_strategy
strategy = get_strategy('rsi')
strategy.params = {'period': 14, 'overbought': 70, 'oversold': 30}
strategy.direction = 'short'
signals = strategy.generate_signals(df)

entries_2d = signals.short_entries.values.reshape(-1, 1).astype(np.bool_) if signals.short_entries is not None else signals.entries.values.reshape(-1, 1).astype(np.bool_)

close_df = pd.DataFrame({'close': df['close'].values}, index=df.index)

print("Short entries at:", np.where(entries_2d.flatten())[0][:5])

pf = vbt.Portfolio.from_order_func(
    close_df,
    debug_flex_order_nb,
    entries_2d,
    0.02,  # sl
    0.04,  # tp
    10.0,  # leverage
    0.0004,
    0.0005,
    flexible=True,
    init_cash=10000.0,
    max_orders=200,
)

print("\nTrades:", len(pf.trades.records))
