import sqlite3
conn = sqlite3.connect('d:/bybit_strategy_tester_v2/data.sqlite3')

print('Total rows in bybit_kline_audit:')
rows = conn.execute("SELECT COUNT(*) FROM bybit_kline_audit").fetchall()
print(f'  Total: {rows[0][0]}')

print('\nETHUSDT rows:')
rows = conn.execute("SELECT COUNT(*) FROM bybit_kline_audit WHERE symbol = 'ETHUSDT'").fetchall()
print(f'  ETHUSDT: {rows[0][0]}')

print('\nETHUSDT 30m rows:')
rows = conn.execute("SELECT COUNT(*) FROM bybit_kline_audit WHERE symbol = 'ETHUSDT' AND interval = '30m'").fetchall()
print(f'  ETHUSDT 30m: {rows[0][0]}')

print('\nFirst ETHUSDT 30m row:')
rows = conn.execute("""
    SELECT * FROM bybit_kline_audit 
    WHERE symbol = 'ETHUSDT' AND interval = '30m'
    LIMIT 1
""").fetchall()
if rows:
    print(f'  id={rows[0][0]}, symbol={rows[0][1]}, interval={rows[0][2]}, market_type={rows[0][3]}, open_time={rows[0][4]}, open_time_dt={rows[0][5]}')
else:
    print('  No rows found!')

conn.close()
