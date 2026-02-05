# Find when Trade 45 TP triggers
import pandas as pd

ohlc = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
tp_price = 91800 * (1 - 0.015)
print(f'TP price: {tp_price:.2f}')
for i in range(6045, 6330):
    if ohlc['low'].iloc[i] <= tp_price:
        print(f'Bar {i}: Low={ohlc["low"].iloc[i]:.2f} <= TP @ {ohlc["timestamp"].iloc[i]}')
        break
