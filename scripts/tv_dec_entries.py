"""Find TV long entries in December 2025."""
import pandas as pd

tv = pd.read_csv('d:/TV/RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-24.csv')

# Print all long entries in December
for i in range(len(tv)):
    row = tv.iloc[i]
    trade_type = str(row.iloc[1])
    date = str(row.iloc[2])
    price = row.iloc[4]

    if 'длинную' in trade_type and 'Вход' in trade_type and '2025-12' in date:
        print(f"Row {i}: Trade {row.iloc[0]}, {trade_type}, Price={price}, Date={date}")
