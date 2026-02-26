"""Verify timezone hypothesis: TV uses UTC+3, we use UTC."""

import sqlite3
from datetime import datetime, timedelta, timezone

UTC3 = timezone(timedelta(hours=3))
UTC = timezone.utc

conn = sqlite3.connect("data.sqlite3")

# TV trade 1: short, 2025-11-01 14:30 @ 110003.6
# If TV uses UTC+3:  14:30 UTC+3 = 11:30 UTC
# Bar open_time 11:30 UTC -> open=110003.6 ✓

# Let's check: our trade 1 entry_time = "2025-11-01T06:30"
# 06:30 UTC+3 = 03:30 UTC -> bar at 03:30?
# But our entry was 06:30 UTC... hmm

# Load our trades
import json

row = conn.execute("SELECT trades FROM backtests WHERE id='aa920b43-e2bf-49f8-b0ae-9d8cb11a681e'").fetchone()
trades = json.loads(row[0])

# TV trades (entry_time as UTC+3)
tv_trades = [
    ("short", "2025-11-01 14:30", 110003.6),
    ("long", "2025-11-03 08:15", 107903.8),
    ("long", "2025-11-04 09:15", 104835.7),
    ("long", "2025-11-04 21:45", 101212.5),
    ("short", "2025-11-06 00:00", 103789.8),
    ("long", "2025-11-06 20:00", 100806.7),
    ("short", "2025-11-07 07:45", 101766.1),
    ("long", "2025-11-07 14:45", 100110.0),
    ("short", "2025-11-08 05:45", 103087.8),
    ("short", "2025-11-09 00:15", 101983.3),
]

print("TV time (UTC+3) -> UTC equivalent -> Our entry time (UTC) -> Our price")
print("-" * 80)
for i, (side, tv_time_str, tv_price) in enumerate(tv_trades):
    tv_dt = datetime.strptime(tv_time_str, "%Y-%m-%d %H:%M").replace(tzinfo=UTC3)
    utc_dt = tv_dt.astimezone(UTC)

    our_t = trades[i]
    our_entry = our_t["entry_time"]
    our_price = our_t["entry_price"]

    utc_str = utc_dt.strftime("%Y-%m-%d %H:%M")
    match = "✓" if utc_str == our_entry[:16] else "✗"
    price_match = "✓" if abs(tv_price - our_price) < 50 else "✗"
    print(
        f"#{i + 1:2d} {side:5s} TV={tv_time_str} -> UTC={utc_str} {match} | Our={our_entry[:16]} | TV_price={tv_price} Our_price={our_price:.1f} {price_match}"
    )

conn.close()
