"""Debug state persistence in VBT - simple version."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import vectorbt as vbt
from numba import njit
from vectorbt.portfolio.enums import Direction
from vectorbt.portfolio.nb import order_nb, order_nothing_nb


@njit
def simple_order_func_nb(c, entries, fees, slippage, leverage, state_arr):
    """Simple order func to test state persistence."""
    col = c.from_col
    i = c.i

    if c.call_idx >= 1:
        return -1, order_nothing_nb()

    position_now = c.last_position[col]
    tracked_cash = state_arr[0]  # Read from mutable array

    close_now = c.close[i, col]

    # Entry
    if position_now == 0 and entries[i, 0]:
        entry_px = close_now * (1.0 - slippage)
        size = (tracked_cash * 1.0) / (entry_px * (1.0 + fees))

        # Update state
        position_value = size * entry_px
        entry_fees = position_value * fees
        new_cash = tracked_cash - position_value - entry_fees
        state_arr[0] = new_cash
        state_arr[1] = entry_px  # entry price
        state_arr[2] = size

        print("Bar", i, "Entry: cash before=", tracked_cash, "size=", size, "cash after=", new_cash)

        return col, order_nb(
            size=size,
            price=entry_px,
            fees=fees,
            direction=Direction.ShortOnly
        )

    # Exit at fixed bar offset (simulate SL)
    if position_now < 0:
        entry_price = state_arr[1]
        if entry_price > 0:
            # Simple exit after 2 bars
            last_oidx = c.last_oidx[col]
            if last_oidx >= 0:
                entry_bar = c.order_records[last_oidx][2]
                if i >= entry_bar + 2:  # Exit 2 bars after entry
                    exit_px = close_now
                    position_value = abs(position_now) * exit_px
                    exit_fees = position_value * fees
                    pnl = (entry_price - exit_px) * abs(position_now) * leverage - exit_fees

                    new_cash = state_arr[0] + position_value + pnl
                    state_arr[0] = new_cash
                    state_arr[1] = 0.0
                    state_arr[2] = 0.0

                    print("Bar", i, "Exit: pnl=", pnl, "cash after=", new_cash)

                    return col, order_nb(
                        size=-position_now,
                        price=exit_px,
                        fees=fees,
                    )

    return -1, order_nothing_nb()


# Load data
import sqlite3

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

# Create simple short entry signals
entries = np.zeros(len(df), dtype=np.bool_)
entries[10] = True  # Trade 1
entries[20] = True  # Trade 2

entries_2d = entries.reshape(-1, 1)
close_df = pd.DataFrame({'close': df['close'].values}, index=df.index)

# State array - will it persist?
state_arr = np.array([10000.0, 0.0, 0.0, 1.0], dtype=np.float64)

print("Initial state:", state_arr)

pf = vbt.Portfolio.from_order_func(
    close_df,
    simple_order_func_nb,
    entries_2d,
    0.0004,  # fees
    0.0005,  # slippage
    10.0,    # leverage
    state_arr,  # Mutable state
    flexible=True,
    init_cash=10000.0,
    max_orders=100,
)

print("\nFinal state:", state_arr)
print("Trades:", len(pf.trades.records))
if len(pf.trades.records) > 0:
    for t in pf.trades.records:
        print(f"  Trade: entry_price={t[4]:.2f}, exit_price={t[7]:.2f}, pnl={t[9]:.2f}")
