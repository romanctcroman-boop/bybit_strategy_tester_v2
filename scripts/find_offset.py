"""Find exact timestamp offset between DB and TV data"""
import sqlite3

import pandas as pd

# Load DB SPOT data (overlapping period only)
conn = sqlite3.connect('data.sqlite3')
db = pd.read_sql_query("""
    SELECT open_time, open_price FROM bybit_kline_audit
    WHERE symbol='BTCUSDT' AND interval='15' AND market_type='spot'
    AND open_time >= 1727740800000
    ORDER BY open_time LIMIT 100
""", conn)
conn.close()

db['datetime'] = pd.to_datetime(db['open_time'], unit='ms')

# Load TV
tv = pd.read_csv(r'd:\TV\BYBIT_BTCUSDT, 15 (2).csv')
tv.columns = ['datetime', 'open', 'high', 'low', 'close']
tv['datetime'] = pd.to_datetime(tv['datetime']).dt.tz_localize(None)

print('DB first 10:')
for _, r in db.head(10).iterrows():
    print(f'  {r["datetime"]} | ${r["open_price"]:.2f}')

print('\nTV first 10:')
for _, r in tv.head(10).iterrows():
    print(f'  {r["datetime"]} | ${r["open"]:.2f}')

# Find matching prices
print('\n' + '='*60)
print('Looking for EXACT price matches...')
print('='*60)

for _db_idx, db_row in db.head(20).iterrows():
    db_price = db_row['open_price']
    db_time = db_row['datetime']

    # Find in TV
    matches = tv[abs(tv['open'] - db_price) < 0.1]
    if len(matches) > 0:
        tv_row = matches.iloc[0]
        offset_hours = (tv_row['datetime'] - db_time).total_seconds() / 3600
        print(f'MATCH: DB {db_time} ${db_price:.2f}')
        print(f'       TV {tv_row["datetime"]} ${tv_row["open"]:.2f}')
        print(f'       Offset: {offset_hours:.1f} hours')
        print()
