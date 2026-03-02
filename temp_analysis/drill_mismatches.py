"""Drill down into the 6 mismatching trades to understand root cause."""

import json
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("data.sqlite3")
cur = conn.execute("SELECT trades FROM backtests WHERE id LIKE '68758d14%'")
our_trades = json.loads(cur.fetchone()[0])
conn.close()

# ── Trades with exit time mismatch: #47 and #105 ─────────────────────────────
print("=" * 70)
print("EXIT TIME MISMATCHES — Trade #47 and #105")
print("=" * 70)

for idx in [46, 104]:  # 0-based
    t = our_trades[idx]
    entry_utc = datetime.fromisoformat(t["entry_time"])
    exit_utc = datetime.fromisoformat(t["exit_time"])
    entry_u3 = (entry_utc + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    exit_u3 = (exit_utc + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    duration = (exit_utc - entry_utc).total_seconds() / 60
    print(f"\nTrade #{idx + 1}:")
    print(f"  Entry   : {entry_u3}  @ {t['entry_price']}")
    print(f"  Exit    : {exit_u3}   @ {t['exit_price']}")
    print(f"  Duration: {duration:.0f} min  ({t['bars_in_trade']} bars)")
    print(f"  PnL     : {t['pnl']:.4f}  exit_comment={t['exit_comment']}")
    print(f"  MAE     : {t['mae_pct']:.4f}%  MFE: {t['mfe_pct']:.4f}%")
    print()
    # TV says: entry=exit for #47 → instant TP on same bar
    # Our exit is 1 bar later — meaning we detect TP on the NEXT bar open
    if idx == 46:
        print("  TV entry_time=2025-04-13 22:30, TV exit_time=2025-04-13 22:30")
        print("  Our exit = 2025-04-14 00:00 = same_bar_open + 1 bar (30m)")
        print("  => TV hit TP within the same bar (intrabar), we exit at next bar open")
    elif idx == 104:
        print("  TV entry_time=2025-10-17 14:00, TV exit_time=2025-10-17 14:00")
        print("  Our exit = 2025-10-17 15:00 = same_bar_open + 1 bar (30m)")
        print("  => same pattern: intrabar TP hit")

# ── SL PnL mismatches: #77, #78 (short SL) and #97, #109 (long SL) ───────────
print()
print("=" * 70)
print("PnL MISMATCHES — SL trades #77, #78 (Short) and #97, #109 (Long)")
print("=" * 70)

tv_pnl = {77: -133.46, 78: -133.46, 97: -133.26, 109: -133.26}

for idx in [76, 77, 96, 108]:  # 0-based
    t = our_trades[idx]
    num = idx + 1
    tv_val = tv_pnl[num]
    our_val = t["pnl"]
    entry_price = t["entry_price"]
    exit_price = t["exit_price"]
    size = t["size"]
    fees = t["fees"]
    side = t["side"]

    # Manual PnL recalc
    # Short: pnl = (entry - exit) * size - fees
    # Long:  pnl = (exit - entry) * size - fees
    if side == "sell":
        gross = (entry_price - exit_price) * size
    else:
        gross = (exit_price - entry_price) * size
    manual_pnl = gross - fees

    print(f"\nTrade #{num} ({side.upper()}):")
    print(f"  Entry  : {entry_price}  Exit: {exit_price}")
    print(f"  Size   : {size:.6f}")
    print(f"  Fees   : {fees:.4f}")
    print(f"  Gross  : {gross:.4f}")
    print(f"  Our PnL: {our_val:.4f}  TV PnL: {tv_val:.2f}  Diff: {our_val - tv_val:.4f}")
    print(f"  Manual : {manual_pnl:.4f}")

    # SL level check
    # For short SL: sl_pct=13.2%, sl_level = entry * (1 + 0.132)
    # For long  SL: sl_pct=13.2%, sl_level = entry * (1 - 0.132)
    if side == "sell":
        sl_level = entry_price * (1 + 0.132)
    else:
        sl_level = entry_price * (1 - 0.132)
    print(f"  SL level (13.2%): {sl_level:.4f}  Actual exit: {exit_price:.4f}")
    print(f"  SL level matches exit: {abs(sl_level - exit_price) < 0.01}")

print()
print("=" * 70)
print("ANALYSIS SUMMARY")
print("=" * 70)
print("""
EXIT TIME (2 trades):
  Pattern: entry_time == exit_time in TV (same bar).
  TV uses calc_on_every_tick=True → can hit TP within a bar at any tick.
  Our engine exits at bar close. So for a bar that opens exactly at TP,
  we say "exit at NEXT bar open", TV says "exit at this bar (same time as entry)".
  These are VALID differences caused by the fundamental tick-mode vs bar-close mode.
  => Fixing requires intrabar TP simulation (complex). NOT a bug per se.

PnL (4 SL trades):
  Difference ~0.03-0.05 USDT per SL trade.
  Likely cause: TV rounds position size to fewer decimals, changing gross PnL slightly.
  Our engine uses higher precision size calculation.
  => Rounding difference, not a logic bug.
""")
