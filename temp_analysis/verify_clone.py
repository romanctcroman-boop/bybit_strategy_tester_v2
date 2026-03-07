import sqlite3

conn = sqlite3.connect("data.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT id, status, total_trades, notes, created_at FROM backtests ORDER BY created_at DESC LIMIT 5")
for r in cur.fetchall():
    d = dict(r)
    notes = (d["notes"] or "")[:70]
    print(f"{d['id']}  trades={d['total_trades']}  {notes}")
conn.close()
