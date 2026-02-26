import datetime
import sqlite3

conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")

# All tables
rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("data.sqlite3 tables:", [r[0] for r in rows])

# ── Check bybit_klines_15m.db ─────────────────────────────────────────────
print("\n--- bybit_klines_15m.db ---")
conn2 = sqlite3.connect(r"d:\bybit_strategy_tester_v2\bybit_klines_15m.db")
tbls2 = conn2.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("Tables:", [r[0] for r in tbls2])
for t in tbls2:
    tname = t[0]
    cols = conn2.execute(f"PRAGMA table_info({tname})").fetchall()
    colnames = [c[1] for c in cols]
    cnt = conn2.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
    print(f"  {tname}: {cnt} rows, cols={colnames}")
    # Show distinct symbols/market_type if present
    if "symbol" in colnames:
        syms = conn2.execute(f"SELECT DISTINCT symbol FROM {tname} LIMIT 20").fetchall()
        print(f"    symbols: {[r[0] for r in syms]}")
    if "market_type" in colnames:
        mts = conn2.execute(f"SELECT DISTINCT market_type FROM {tname}").fetchall()
        print(f"    market_types: {[r[0] for r in mts]}")
conn2.close()

# klines market_type for BTCUSDT
try:
    rows2 = conn.execute(
        "SELECT symbol, interval, market_type, COUNT(*) as cnt FROM klines "
        "WHERE symbol='BTCUSDT' AND interval='30' GROUP BY symbol, interval, market_type"
    ).fetchall()
    print("\nklines BTCUSDT 30m:")
    for r in rows2:
        print(" ", r)
    if not rows2:
        print("  (no rows)")
except Exception as e:
    print("klines error:", e)

# Check first/last candle timestamps for BTCUSDT 30m
try:
    row3 = conn.execute(
        "SELECT MIN(open_time), MAX(open_time), COUNT(*) FROM klines WHERE symbol='BTCUSDT' AND interval='30'"
    ).fetchone()
    import datetime

    mn = datetime.datetime.fromtimestamp(row3[0] / 1000, tz=datetime.timezone.utc) if row3[0] else None
    mx = datetime.datetime.fromtimestamp(row3[1] / 1000, tz=datetime.timezone.utc) if row3[1] else None
    print(f"\nBTCUSDT 30m range: {mn} .. {mx}  total={row3[2]}")
except Exception as e:
    print("range error:", e)

# Check columns of klines table
try:
    cols = conn.execute("PRAGMA table_info(klines)").fetchall()
    print("\nklines columns:", [c[1] for c in cols])
except Exception as e:
    print("pragma error:", e)

conn.close()
