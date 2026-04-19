
import pandas as pd

TV_CSV = r"C:\Users\roman\Downloads\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-02-23.csv"

df = pd.read_csv(TV_CSV, encoding="utf-8-sig")
print(f"Total rows: {len(df)}")
print(f"\nColumns: {list(df.columns)}")
print("\nFirst 20 rows:")
print(df.head(20).to_string())
