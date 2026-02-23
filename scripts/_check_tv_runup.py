import csv

for fname in ["1.csv", "2.csv"]:
    print(f"\n=== {fname} ===")
    with open(rf"C:\Users\roman\Downloads\{fname}", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
    for row in rows:
        if len(row) >= 2:
            key = row[0].lower()
            if "run" in key or "drawdown" in key or "margin" in key or "max" in key:
                print(f"  {row[0]!r}: {row[1]!r}")
