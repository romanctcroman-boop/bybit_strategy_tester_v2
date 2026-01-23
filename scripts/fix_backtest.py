"""Fix broken backtest record"""
import sqlite3

conn = sqlite3.connect('d:/bybit_strategy_tester_v2/data.sqlite3')
c = conn.cursor()

# Check the broken backtest
c.execute("SELECT id, start_date, end_date FROM backtests WHERE id = '2b8027a9-84cc-447f-aac4-cd895512b3a7'")
result = c.fetchall()
print(f"Broken backtest: {result}")

if result:
    print("Deleting broken backtest...")
    c.execute("DELETE FROM backtests WHERE id = '2b8027a9-84cc-447f-aac4-cd895512b3a7'")
    conn.commit()
    print("Done!")
else:
    print("Backtest not found")

conn.close()
