import json
import sqlite3

conn = sqlite3.connect("data.sqlite3")
bt_id = "68758d14"

cur = conn.execute("SELECT id FROM backtests WHERE id LIKE ?", (bt_id + "%",))
full_bt_id = cur.fetchone()[0]

cur = conn.execute("SELECT trades FROM backtests WHERE id = ?", (full_bt_id,))
trades = json.loads(cur.fetchone()[0])
conn.close()

# TV trades from й4.csv (times are UTC+3, so -3h for UTC)
# TV times format: "YYYY-MM-DD HH:MM" UTC+3 → UTC = subtract 3 hours
tv_trades = [
    # (side, entry_time_utc+3, entry_price, exit_time_utc+3, exit_signal, pnl)
    ("Short", "2025-01-01 16:30", 3334.62, "2025-01-08 20:00", "TP", 21.61),
    ("Short", "2025-01-09 02:30", 3322.53, "2025-01-09 16:30", "TP", 21.61),
    ("Short", "2025-01-09 20:30", 3285.67, "2025-01-09 22:30", "TP", 21.62),
    ("Short", "2025-01-11 00:00", 3257.99, "2025-01-13 09:30", "TP", 21.62),
    ("Long", "2025-01-13 16:30", 3075.39, "2025-01-14 03:00", "TP", 21.58),
    ("Short", "2025-01-14 16:30", 3069.31, "2025-01-16 04:30", "TP", 21.58),
    ("Short", "2025-01-15 18:00", 3022.98, "2025-01-16 04:30", "TP", None),
    ("Short", "2025-01-16 08:30", 2982.12, "2025-01-16 15:30", "TP", 21.58),
    ("Long", "2025-01-21 07:30", 3193.25, "2025-01-21 11:30", "TP", 21.65),
    ("Short", "2025-01-24 15:00", 3397.39, "2025-01-31 14:00", "TP", 21.61),
]

print("=== Trade-by-Trade Comparison (UTC+3 display) ===")
print("Note: TV times are UTC+3. Our times stored as UTC. Adding +3h to ours for display.")
print()
print(
    f"{'#':>3} | {'TV Side':6} | {'TV Entry (UTC+3)':18} | {'TV Price':9} | {'Our Entry (UTC+3)':18} | {'Our Price':9} | {'dPrice':7} | {'TV PnL':7} | {'Our PnL':7} | {'Match':5}"
)
print("-" * 140)

for i, tv in enumerate(tv_trades):
    tv_side, tv_entry, tv_ep, tv_exit, tv_sig, tv_pnl = tv
    if i < len(trades):
        t = trades[i]
        # Convert our UTC to UTC+3 for display
        from datetime import datetime, timedelta

        ours_entry_utc = datetime.fromisoformat(t["entry_time"])
        ours_entry_utc3 = ours_entry_utc + timedelta(hours=3)
        our_entry_str = ours_entry_utc3.strftime("%Y-%m-%d %H:%M")

        our_side = "Long" if t["side"] == "buy" else "Short"
        delta_price = t["entry_price"] - tv_ep
        our_pnl = t["pnl"]
        tv_pnl_v = tv_pnl or 0
        price_match = "✅" if abs(delta_price) < 0.01 else f"❌({delta_price:+.2f})"
        time_match = "✅" if our_entry_str == tv_entry else "❌"
        side_match = "✅" if our_side == tv_side else "❌"
        overall = "✅" if abs(delta_price) < 0.01 and our_entry_str == tv_entry else "❌"

        print(
            f"{i + 1:>3} | {tv_side:6} | {tv_entry:18} | {tv_ep:9.2f} | {our_entry_str:18} | {t['entry_price']:9.4f} | {delta_price:+7.4f} | {tv_pnl_v:7.2f} | {our_pnl:7.2f} | {overall} T:{time_match} S:{side_match}"
        )
    else:
        print(
            f"{i + 1:>3} | {tv_side:6} | {tv_entry:18} | {tv_ep:9.2f} | {'NO TRADE':18} | {'':9} | {'':7} | {tv_pnl or 0:7.2f} | {'':7} | ❌"
        )

print("\n=== All 155 trades: entry time/price check ===")
from datetime import datetime, timedelta

mismatches = 0
for i, t in enumerate(trades):
    ours_entry_utc = datetime.fromisoformat(t["entry_time"])
    ours_entry_utc3 = ours_entry_utc + timedelta(hours=3)
    print(
        f"  #{i + 1:3d} {('Long' if t['side'] == 'buy' else 'Short'):5} entry: {ours_entry_utc3.strftime('%Y-%m-%d %H:%M')} @ {t['entry_price']:9.4f}  exit: {(datetime.fromisoformat(t['exit_time']) + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M')} @ {t['exit_price']:9.4f}  pnl: {t['pnl']:8.2f}  {t['exit_comment']}"
    )
