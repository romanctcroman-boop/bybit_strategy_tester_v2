import sqlite3

conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
cur = conn.cursor()

# Get all data grouped by symbol and interval
cur.execute("""
    SELECT symbol, interval, COUNT(*) as cnt 
    FROM bybit_kline_audit 
    GROUP BY symbol, interval 
    ORDER BY symbol, interval
""")
rows = cur.fetchall()

# Build matrix
symbols = sorted(set(r[0] for r in rows))
intervals = ["1", "5", "15", "30", "60", "240", "D", "W", "M"]
data = {(r[0], r[1]): r[2] for r in rows}

# Print header
header = f"{'Symbol':<12}" + "".join(f"{i:>8}" for i in intervals)
print(header)
print("-" * len(header))

# Print data
for s in symbols:
    row = f"{s:<12}" + "".join(f"{data.get((s, i), 0):>8,}" for i in intervals)
    print(row)

# Total
cur.execute("SELECT COUNT(*) FROM bybit_kline_audit")
total = cur.fetchone()[0]
print("-" * len(header))
print(f"Total: {total:,} candles")

conn.close()
