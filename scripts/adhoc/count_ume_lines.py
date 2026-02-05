"""Count lines in Universal Math Engine."""

import os

path = "backend/backtesting/universal_engine"
files = [f for f in os.listdir(path) if f.endswith(".py") and f != "__init__.py"]

total = 0
for f in sorted(files):
    full = os.path.join(path, f)
    lines = len(open(full, encoding="utf-8").readlines())
    total += lines
    print(f"{f:35} {lines:5} lines")

print("=" * 45)
print(f"TOTAL: {len(files)} modules, {total:,} lines of code")
