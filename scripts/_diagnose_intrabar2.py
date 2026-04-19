"""
Diagnostic: compute intrabar drawdown/runup using equity-based OHLC approach
to understand TV's formula and get the correct values.
TV: Open -> High -> Low -> Close synthetic tick order for intrabar simulation.
For LONG: High = favorable (MFE), Low = adverse (MAE) within each bar.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DB = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
INITIAL_CAPITAL = 10000.0

conn = sqlite3.connect(DB)

# Get OHLCV data - backtest date range
START_MS = 1730419200 * 1000  # 2024-11-01 UTC
END_MS = 1740355199 * 1000  # 2026-02-23 UTC  (just beyond our range)
rows = conn.execute("""
    SELECT open_time, open_price, high_price, low_price, close_price
    FROM bybit_kline_audit
    WHERE symbol='BTCUSDT' AND interval='15'
    ORDER BY open_time ASC
""").fetchall()

# Get trades
trade_rows = conn.execute(
    """
    SELECT entry_time, exit_time, entry_price, exit_price, pnl, side, size,
           bars_in_trade, mae, mfe, is_open, entry_bar_index, exit_bar_index
    FROM trades
    WHERE strategy_id = ?
    ORDER BY entry_time ASC
""",
    (STRATEGY_ID,),
).fetchall()

conn.close()

print(f"OHLCV rows: {len(rows)}")
print(f"Trades: {len(trade_rows)}")

# Build arrays
ts_arr = np.array([r[0] for r in rows], dtype=np.int64)  # ms
open_arr = np.array([r[1] for r in rows], dtype=np.float64)
high_arr = np.array([r[2] for r in rows], dtype=np.float64)
low_arr = np.array([r[3] for r in rows], dtype=np.float64)
close_arr = np.array([r[4] for r in rows], dtype=np.float64)
total_bars = len(close_arr)

print(f"Total bars in DB: {total_bars}")

# Find trades with entry_bar_index set
valid_trades = [r for r in trade_rows if r[11] is not None and r[12] is not None]
closed_trades = [r for r in valid_trades if not r[10]]  # is_open=False
print(f"Closed trades with bar indices: {len(closed_trades)}")

if not closed_trades:
    print("ERROR: No closed trades with bar indices!")
    sys.exit(1)

# Verify bar indices are within range
entry_bars = [r[11] for r in closed_trades]
exit_bars = [r[12] for r in closed_trades]
print(f"Entry bar range: {min(entry_bars)} - {max(entry_bars)}")
print(f"Exit bar range:  {min(exit_bars)} - {max(exit_bars)}")
print(f"OHLCV array len: {total_bars}")

# =========================================================================
# APPROACH: Equity-based intrabar tracking using OHLC prices
# TV methodology: For each bar while in position:
#   - Synthetic tick sequence: Open -> High -> Low -> Close
#   - For LONG: High = max price (favorable), Low = min price (adverse)
#   - For SHORT: Low = favorable, High = adverse
#
# TV max_runup = peak equity (using intrabar highs for longs) - initial_capital
# TV max_drawdown_intrabar = max(HWM_equity - trough_equity_with_intrabar_lows)
# =========================================================================

# Build bar-by-bar equity using CLOSE prices (base equity)
# Then separately build "best case" (highs for longs) and "worst case" (lows for longs)

cumulative_pnl = 0.0
current_trade = None
trade_by_entry = {}
trade_by_exit = {}
for tr in closed_trades:
    eb = tr[11]
    xb = tr[12]
    trade_by_entry[eb] = tr
    trade_by_exit[xb] = tr

# Equity curves
equity_close = np.zeros(total_bars)
equity_high = np.zeros(total_bars)  # Best intrabar (using HIGH for longs)
equity_low = np.zeros(total_bars)  # Worst intrabar (using LOW for longs)

cum_pnl = 0.0
current_trade = None

for i in range(total_bars):
    # Exit event (process before entry for same-bar)
    if i in trade_by_exit and current_trade is not None:
        tr = trade_by_exit[i]
        if tr is current_trade:
            cum_pnl += tr[4]  # pnl
            current_trade = None

    # Entry event
    if i in trade_by_entry:
        current_trade = trade_by_entry[i]

    # Compute unrealized PnL at close, high, low
    urpnl_close = 0.0
    urpnl_high = 0.0
    urpnl_low = 0.0

    if current_trade is not None:
        entry_price = current_trade[2]  # entry_price
        size = current_trade[5]  # side
        qty = current_trade[6]  # size (quantity)
        side_str = str(current_trade[5]).lower()
        is_long = any(x in side_str for x in ("buy", "long"))

        if is_long:
            urpnl_close = (close_arr[i] - entry_price) * qty
            urpnl_high = (high_arr[i] - entry_price) * qty  # Best case
            urpnl_low = (low_arr[i] - entry_price) * qty  # Worst case
        else:
            urpnl_close = (entry_price - close_arr[i]) * qty
            urpnl_high = (entry_price - low_arr[i]) * qty  # Best case (short)
            urpnl_low = (entry_price - high_arr[i]) * qty  # Worst case (short)

    equity_close[i] = INITIAL_CAPITAL + cum_pnl + urpnl_close
    equity_high[i] = INITIAL_CAPITAL + cum_pnl + urpnl_high
    equity_low[i] = INITIAL_CAPITAL + cum_pnl + urpnl_low

print()
print("=== EQUITY CURVE STATS ===")
print(f"equity_close: min={equity_close.min():.4f}, max={equity_close.max():.4f}, final={equity_close[-1]:.4f}")
print(f"equity_high:  min={equity_high.min():.4f},  max={equity_high.max():.4f}")
print(f"equity_low:   min={equity_low.min():.4f},  max={equity_low.max():.4f}")

# Max Runup (TV): peak_equity_with_intrabar_highs - initial_capital
max_runup_intrabar_value = float(equity_high.max() - INITIAL_CAPITAL)
max_runup_intrabar_pct = max_runup_intrabar_value / INITIAL_CAPITAL * 100
print()
print("=== INTRABAR RUNUP ===")
print(
    f"max(equity_high) - initial_capital = {equity_high.max():.4f} - {INITIAL_CAPITAL:.0f} = {max_runup_intrabar_value:.4f}"
)
print(f"max_runup_intrabar_pct = {max_runup_intrabar_pct:.4f}%")
print("TV value: 537.82, TV pct: 5.38%")
print(f"Close-based runup: {equity_close.max() - INITIAL_CAPITAL:.4f}")

# Max Drawdown Intrabar (TV): max(HWM - equity_low) where HWM = cumulative peak of equity_close
# TV: drawdown from equity high-water-mark to intrabar low
hwm = np.maximum.accumulate(equity_close)  # HWM from close prices
dd_intrabar = hwm - equity_low  # Drawdown using intrabar lows
max_dd_intrabar_value = float(dd_intrabar.max())
max_dd_intrabar_pct = max_dd_intrabar_value / INITIAL_CAPITAL * 100
print()
print("=== INTRABAR DRAWDOWN ===")
print(f"max(HWM_close - equity_low) = {max_dd_intrabar_value:.4f}")
print(f"max_dd_intrabar_pct = {max_dd_intrabar_pct:.4f}%")
print("TV value: 146.99, TV pct: 1.47%")

# Alternative: use hwm of equity_high for runup
hwm_high = np.maximum.accumulate(equity_high)
dd_from_high_hwm = hwm_high - equity_low
max_dd_from_high_hwm = float(dd_from_high_hwm.max())
print(f"\nAlternative: max(HWM_high - equity_low) = {max_dd_from_high_hwm:.4f}")

# Another alternative: hwm of equity_close, dd to equity_close (close-based only)
dd_close = hwm - equity_close
max_dd_close = float(dd_close.max())
print(f"Close-based drawdown: {max_dd_close:.4f}")

# Account size required: max_margin + max_dd_intrabar = 1033.35 + 146.99 = 1180.34
# Let's check what max_margin should be
print()
print("=== ACCOUNT SIZE REQUIRED ===")
print(f"max_dd_intrabar_value = {max_dd_intrabar_value:.4f} (TV: 146.99)")
print("If max_margin = 1033.35:")
print(f"  account_size_required = {1033.35 + max_dd_intrabar_value:.4f} (TV: 1180.34)")

# =========================================================================
# MARGIN: Bar-by-bar MVS approach
# =========================================================================
print()
print("=== MARGIN (MVS BAR-BY-BAR) ===")
mvs_bar = np.zeros(total_bars)
for tr in closed_trades:
    eb = tr[11]
    xb = tr[12]
    qty = tr[6]  # size
    side_str = str(tr[5]).lower()

    for b in range(eb, min(xb + 1, total_bars)):
        mvs_bar[b] = abs(qty) * close_arr[b]  # MVS = qty * close (margin_pct=100%)

avg_margin = float(mvs_bar.mean())
max_margin = float(mvs_bar.max())
bars_in_pos = int(np.sum(mvs_bar > 0))
print(f"avg_margin (all bars, margin_pct=100%) = {avg_margin:.4f} (TV: 852.53)")
print(f"max_margin                              = {max_margin:.4f} (TV: 1033.35)")
print(f"bars in position: {bars_in_pos} / {total_bars}")

print()
print("=== DONE ===")
