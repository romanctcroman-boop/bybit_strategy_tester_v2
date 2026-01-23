"""Investigate Trade #11 which has P&L difference"""
import pandas as pd

tv = pd.read_csv(r'd:\TV\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-21.csv', encoding='utf-8-sig')

# Trade 11 (using index from our matching)
print("All unique trade numbers:", tv['№ Сделки'].unique()[:20])

# Find the trade that has +19.34 P&L
pnl_col = 'Чистая прибыль / убыток USDT'
high_pnl = tv[tv[pnl_col] == 19.34]
print("\n=== Trade with +19.34 P&L ===")
for _, row in high_pnl.iterrows():
    print(f"Trade #: {row['№ Сделки']}")
    print(f"Type: {row['Тип']}")
    print(f"Time: {row['Дата и время']}")
    print(f"Price: {row['Цена USDT']}")
    print(f"Signal: {row['Сигнал']}")
    print()

# Find trade with +15.43
high_pnl2 = tv[tv[pnl_col] == 15.43]
print("=== Trade with +15.43 P&L ===")
for _, row in high_pnl2.iterrows():
    print(f"Trade #: {row['№ Сделки']}")
    print(f"Type: {row['Тип']}")
    print(f"Time: {row['Дата и время']}")
    print(f"Price: {row['Цена USDT']}")
    print(f"Signal: {row['Сигнал']}")
    print()
