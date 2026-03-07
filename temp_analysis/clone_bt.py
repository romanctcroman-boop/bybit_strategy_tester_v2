"""
Clone the most recent completed backtest.
Replace all trade MFE/MAE/PnL fields with identical values,
keeping entry_time and exit_time unchanged.
Save as a new backtest row in the DB.
"""

import copy
import json
import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect("data.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ── 1. Find most recent completed backtest with trades ──────────────────────
cur.execute("""
    SELECT * FROM backtests
    WHERE status='completed' AND total_trades > 5
    ORDER BY created_at DESC LIMIT 1
""")
src = dict(cur.fetchone())
print(
    f"Source backtest: id={src['id']}  symbol={src['symbol']}  "
    f"trades={src['total_trades']}  created={src['created_at']}"
)

# ── 2. Load trades from the `trades` table ──────────────────────────────────
cur.execute("SELECT * FROM trades WHERE backtest_id=? ORDER BY trade_id", (src["id"],))
src_trades_rows = [dict(r) for r in cur.fetchall()]
print(f"Loaded {len(src_trades_rows)} trade rows from trades table")

# Also check equity_curve / trades JSON in backtests table
equity_curve_raw = src.get("equity_curve")
trades_json_raw = src.get("trades")

equity_curve = json.loads(equity_curve_raw) if equity_curve_raw else None
trades_json = json.loads(trades_json_raw) if trades_json_raw else None

print(f"equity_curve points: {len(equity_curve) if equity_curve else 'none'}")
print(f"trades JSON entries: {len(trades_json) if trades_json else 'none'}")

if trades_json and len(trades_json) > 0:
    print("Sample trade JSON keys:", list(trades_json[0].keys())[:15])

# ── 3. Pick reference values from trade[0] ──────────────────────────────────
# We'll make ALL trades identical to the first trade's MFE/MAE/pnl/etc.
# but keep entry_time and exit_time of each trade.

ref = None
if trades_json:
    ref = trades_json[0]
elif src_trades_rows:
    ref = src_trades_rows[0]

if ref:
    print("\nReference trade (index 0):")
    for k, v in ref.items():
        print(f"  {k}: {v}")

conn.close()
