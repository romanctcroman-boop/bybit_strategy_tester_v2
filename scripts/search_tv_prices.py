"""Search TV for entries 89596 or 90810."""
import pandas as pd

tv = pd.read_csv('d:/TV/RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-24.csv')
print(f'Total TV rows: {len(tv)}')

# Search for entries around our key prices
for i in range(len(tv)):
    row = tv.iloc[i]
    price = row.iloc[4]  # 'Цена USDT'
    if pd.notna(price):
        try:
            p = float(price)
            if abs(p - 89596.40) < 10 or abs(p - 90810.90) < 10:
                print(f"Row {i}: Trade {row.iloc[0]}, Type={row.iloc[1]}, Price={p:.2f}, Date={row.iloc[2]}")
        except:
            pass
