import csv

with open(r"c:\Users\roman\Downloads\trades_9fb161a0-336f-4776-9e9f-edbbd41e68ed.csv") as _f:
    rows = list(csv.DictReader(_f))
print(f"Total trades: {len(rows)}")
print(f"Date range: {rows[0]['Entry Time']} → {rows[-1]['Exit Time']}")
print()
print("First 8 trades:")
for r in rows[:8]:
    print(
        f"  #{r['#']:>3}  {r['Entry Time'][:16]}  entry={float(r['Entry Price']):.2f}"
        f"  exit={float(r['Exit Price']):.2f}  size={float(r['Size']):.4f}  pnl={r['P&L']}"
    )
print()
# Check where entry price looks like 3-digit (divided by 10?)
small_entry = [r for r in rows if float(r["Entry Price"]) < 1000]
print(f"Trades with entry_price < 1000: {len(small_entry)}")
if small_entry:
    r = small_entry[0]
    print(f"  Example: #{r['#']} entry={r['Entry Price']} size={r['Size']} pnl={r['P&L']}")
    print(f"  If entry*10 = {float(r['Entry Price']) * 10:.2f}")
