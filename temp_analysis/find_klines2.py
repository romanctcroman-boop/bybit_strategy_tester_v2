import sqlite3

conn = sqlite3.connect("data.sqlite3")

# Check bybit_kline_audit structure
cur = conn.execute("PRAGMA table_info(bybit_kline_audit)")
cols = cur.fetchall()
print("bybit_kline_audit columns:", [c[1] for c in cols])

cur = conn.execute("SELECT COUNT(*) FROM bybit_kline_audit")
print("bybit_kline_audit rows:", cur.fetchone()[0])

cur = conn.execute("SELECT * FROM bybit_kline_audit LIMIT 3")
rows = cur.fetchall()
for r in rows:
    print(r)

conn.close()

# Check if there's a separate klines database path configured
import sys

sys.path.insert(0, ".")
try:
    from backend.config.database_policy import DATA_START_DATE, KLINE_DB_PATH

    print(f"\nKLINE_DB_PATH: {KLINE_DB_PATH}")
    print(f"DATA_START_DATE: {DATA_START_DATE}")
except Exception as e:
    print(f"config import: {e}")

# Check DataService for kline storage path
try:
    import inspect

    from backend.services.data_service import DataService

    src = inspect.getsource(DataService)
    # Find DB path references
    for line in src.split("\n"):
        if "kline" in line.lower() and ("db" in line.lower() or "path" in line.lower() or "sqlite" in line.lower()):
            print(f"  DataService: {line.strip()}")
except Exception as e:
    print(f"DataService: {e}")
