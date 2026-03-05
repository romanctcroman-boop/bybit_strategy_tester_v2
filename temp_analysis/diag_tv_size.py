"""Check TV entry rows for SL trades"""

import pandas as pd

df = pd.read_csv(r"d:\bybit_strategy_tester_v2\temp_analysis\a4.csv", sep=";")

# SL trades
sl = df[df["Сигнал"].str.contains("SL", na=False)]
sl_nums = sl["№ Сделки"].tolist()

print("=== TV SL TRADE ENTRY+EXIT DETAILS ===")
print(f"{'#':>4}  {'Type':22}  {'DateTime':17}  {'Signal':15}  {'Price':10}  {'Qty':8}  {'Notional':12}  {'PnL':8}")
for n in sl_nums:
    rows = df[df["№ Сделки"] == n]
    for _, row in rows.iterrows():
        print(
            f"  {n:3d}  {str(row['Тип'])[:22]:22}  {row['Дата и время']:17}  {str(row['Сигнал'])[:15]:15}  {row['Цена USDT']:10.4f}  {row['Размер позиции (кол-во)']:8.4f}  {row['Размер позиции (цена)']:12.6f}  {row['Чистая прибыль / убыток USDT']:8.2f}"
        )
    print()

print("\n=== CHECK NOTIONAL CALCULATION ===")
print("For trades #77, #78, #97, #109 specifically:")
for n in [77, 78, 97, 109]:
    rows = df[df["№ Сделки"] == n]
    entry_row = rows[~rows["Сигнал"].str.contains("SL", na=False)].iloc[0]
    exit_row = rows[rows["Сигнал"].str.contains("SL", na=False)].iloc[0]
    ep = entry_row["Цена USDT"]
    qty = entry_row["Размер позиции (кол-во)"]
    notional = entry_row["Размер позиции (цена)"]
    xp = exit_row["Цена USDT"]
    pnl = exit_row["Чистая прибыль / убыток USDT"]
    print(f"Trade #{n}:")
    print(f"  Entry: price={ep:.4f}  qty={qty:.6f}  notional={notional:.6f}")
    print(f"  Exit:  price={xp:.4f}")
    print(f"  PnL:   {pnl:.2f}")
    print(f"  entry*qty = {ep * qty:.6f}  (notional = {notional:.6f})")
    # How does TV compute qty?
    # For capital=10000, pos_size=10%, leverage=10:
    # option A: qty = capital * pos_size / entry_price (without leverage)
    qty_a = 10000 * 0.1 / ep
    qty_b = 10000 * 0.1 * 10 / ep
    # option C: qty = round_to_lots(capital * pos_size / entry_price)
    print(f"  qty options:")
    print(f"    A (capital*pos/price): {qty_a:.6f}")
    print(f"    B (capital*pos*lev/price): {qty_b:.6f}")
    print(f"    TV actual qty: {qty:.6f}")
    print(f"    TV qty * entry = {qty * ep:.6f}")
    print()

# Check if TV rounds qty to some number of decimal places
print("=== QTY PRECISION ANALYSIS ===")
for n in [77, 78, 94, 97, 109, 128]:
    rows = df[df["№ Сделки"] == n]
    if rows.empty:
        continue
    entry_row = rows.iloc[0]
    ep = entry_row["Цена USDT"]
    qty = entry_row["Размер позиции (кол-во)"]
    notional = entry_row["Размер позиции (цена)"]
    # Check if notional = 1000 exactly or slightly off
    # and if there's rounding in qty
    print(f"Trade #{n}: entry={ep}, qty={qty}, notional={notional}, qty*entry={qty * ep:.6f}")
    # What is the lot size step? Try: qty = round(1000/entry, 4)
    qty_4dp = round(1000 / ep, 4)
    print(f"  round(1000/entry, 4) = {qty_4dp}")
    # Try round to 3dp
    qty_3dp = round(1000 / ep, 3)
    print(f"  round(1000/entry, 3) = {qty_3dp}")
