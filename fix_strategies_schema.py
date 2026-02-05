"""Add missing columns to strategies table"""

import psycopg2


def main():
    conn = psycopg2.connect(host="127.0.0.1", database="bybit_strategy_tester", user="postgres", password="postgres")
    cur = conn.cursor()

    print("=== Adding missing columns to strategies table ===")

    # List of columns to add with their types
    columns_to_add = [
        ("deleted_at", "TIMESTAMP"),
        ("is_deleted", "BOOLEAN DEFAULT FALSE"),
        ("tags", "JSONB DEFAULT '[]'"),
        ("version", "INTEGER DEFAULT 1"),
        ("builder_graph", "JSONB"),
        ("builder_blocks", "JSONB"),
        ("builder_connections", "JSONB"),
        ("is_builder_strategy", "BOOLEAN DEFAULT FALSE"),
        ("position_size", "FLOAT"),
        ("stop_loss_pct", "FLOAT"),
        ("take_profit_pct", "FLOAT"),
        ("max_drawdown_pct", "FLOAT"),
        ("total_return", "FLOAT"),
        ("sharpe_ratio", "FLOAT"),
        ("win_rate", "FLOAT"),
        ("total_trades", "INTEGER"),
        ("backtest_count", "INTEGER DEFAULT 0"),
        ("last_backtest_at", "TIMESTAMP"),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cur.execute(f"ALTER TABLE strategies ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"  Added: {col_name} ({col_type})")
        except Exception as e:
            print(f"  Skipped: {col_name} - {e}")

    conn.commit()

    # Verify final schema
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'strategies'
        ORDER BY ordinal_position
    """)
    print("\\n=== Final strategies schema ===")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]}")

    cur.close()
    conn.close()
    print("\\nDone!")


if __name__ == "__main__":
    main()
