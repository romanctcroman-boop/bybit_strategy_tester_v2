"""Parse TV trades from as4.csv and compare with engine trades around root divergences."""

import sys

import pandas as pd

# Read TV trades
tv_raw = pd.read_csv(r"c:\Users\roman\Downloads\as4.csv", sep=";")
print(f"TV columns: {tv_raw.columns.tolist()}")
print(f"Total rows: {len(tv_raw)}")
print()

# Parse entry/exit pairs
# Columns: № Сделки, Тип, Дата и время, Сигнал, Цена USDT, ...
# Each trade has 2 rows: Entry and Exit (Exit comes first in the CSV)
trades = []
for i in range(0, len(tv_raw), 2):
    exit_row = tv_raw.iloc[i]
    entry_row = tv_raw.iloc[i + 1]

    trade_num = int(str(exit_row["№ Сделки"]).strip())

    # Direction from entry type
    entry_type = str(entry_row["Тип"]).strip()
    if "short" in entry_type.lower():
        direction = "short"
    else:
        direction = "long"

    # Parse times (Moscow UTC+3)
    entry_time = str(entry_row["Дата и время"]).strip()
    exit_time = str(exit_row["Дата и время"]).strip()

    # Parse prices
    entry_price = float(str(entry_row["Цена USDT"]).replace(",", ".").strip())
    exit_price = float(str(exit_row["Цена USDT"]).replace(",", ".").strip())

    exit_signal = str(exit_row["Сигнал"]).strip()

    trades.append(
        {
            "num": trade_num,
            "direction": direction,
            "entry_time_msk": entry_time,
            "exit_time_msk": exit_time,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_signal": exit_signal,
        }
    )

print(f"Total TV trades parsed: {len(trades)}")
longs = [t for t in trades if t["direction"] == "long"]
shorts = [t for t in trades if t["direction"] == "short"]
print(f"Long: {len(longs)}, Short: {len(shorts)}")
print()

# Show trades around roots
# TV trade #8, #9 (Root #9 equivalent)
# TV trade #11, #12 (Root #12)
# ...
for idx in [8, 9, 10, 11, 12, 13, 84, 85, 86, 88, 89, 90, 91, 92, 143, 144, 145]:
    if idx <= len(trades):
        t = trades[idx - 1]  # 0-indexed
        # Convert Moscow to UTC: subtract 3 hours
        entry_msk = pd.Timestamp(t["entry_time_msk"])
        exit_msk = pd.Timestamp(t["exit_time_msk"])
        entry_utc = entry_msk - pd.Timedelta(hours=3)
        exit_utc = exit_msk - pd.Timedelta(hours=3)
        print(
            f"TV #{t['num']:3d} {t['direction']:5s} | "
            f"Entry: {entry_utc} | Exit: {exit_utc} | "
            f"Price: {t['entry_price']:.2f} → {t['exit_price']:.2f} | "
            f"Exit: {t['exit_signal']}"
        )
