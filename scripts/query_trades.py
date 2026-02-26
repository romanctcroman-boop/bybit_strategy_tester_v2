"""Query the latest backtest trades directly from SQLite."""

import sqlite3

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
cursor = conn.cursor()

# Get latest backtest for RSI_LS_11
cursor.execute("""
    SELECT id, strategy_id, status, symbol, timeframe, start_date, end_date, total_trades,
           net_profit, net_profit_pct, win_rate, max_drawdown
    FROM backtests
    WHERE strategy_id = '01cd8861-60eb-40dd-a9a9-8baa6f2db0fa'
    ORDER BY created_at DESC
    LIMIT 3
""")
rows = cursor.fetchall()
print("Recent backtests for RSI_LS_11:")
for r in rows:
    print(f"  id={r[0]} status={r[3]} status2={r[2]} trades={r[7]} pnl={r[8]} win={r[10]}")

if rows:
    bt_id = rows[0][0]
    print(f"\nLatest backtest ID: {bt_id}")

    # Get all columns from backtests
    cursor.execute("PRAGMA table_info(backtests)")
    cols = [r[1] for r in cursor.fetchall()]
    print(f"Backtest columns: {cols}")

    # Check metrics JSON
    cursor.execute("SELECT metrics, results FROM backtests WHERE id = ?", (bt_id,))
    row = cursor.fetchone()
    if row and row[0]:
        import json

        metrics = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        print(f"\nMetrics keys: {list(metrics.keys())[:20] if metrics else 'None'}")

    # Check trades table for this backtest
    cursor.execute(
        """
        SELECT COUNT(*) FROM trades WHERE backtest_id = ?
    """,
        (bt_id,),
    )
    trade_count = cursor.fetchone()[0]
    print(f"\nTrades in 'trades' table: {trade_count}")

    if trade_count == 0:
        # Try string backtest_id
        cursor.execute("SELECT DISTINCT backtest_id FROM trades LIMIT 5")
        sample_ids = cursor.fetchall()
        print(f"Sample backtest_ids in trades: {sample_ids}")

    # Get trades columns
    cursor.execute("PRAGMA table_info(trades)")
    trade_cols = [r[1] for r in cursor.fetchall()]
    print(f"\nTrades columns: {trade_cols}")

    # Try matching by string
    cursor.execute(
        """
        SELECT * FROM trades WHERE backtest_id = ? ORDER BY entry_time LIMIT 5
    """,
        (bt_id,),
    )
    trades = cursor.fetchall()
    if not trades:
        # Try other matching
        cursor.execute(
            """
            SELECT * FROM trades WHERE CAST(backtest_id AS TEXT) LIKE ?
            ORDER BY entry_time LIMIT 5
        """,
            (f"%{bt_id[:8]}%",),
        )
        trades = cursor.fetchall()
    print(f"\nFirst 5 trades: {trades}")

conn.close()
