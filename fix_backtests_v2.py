"""Fix backtests table schema to match SQLAlchemy model"""

import psycopg2

OUTPUT_FILE = "d:/bybit_strategy_tester_v2/fix_output.txt"


def log(msg):
    print(msg)
    with open(OUTPUT_FILE, "a") as f:
        f.write(msg + "\\n")


def main():
    # Clear output file
    with open(OUTPUT_FILE, "w") as f:
        f.write("")

    conn = psycopg2.connect(host="127.0.0.1", database="bybit_strategy_tester", user="postgres", password="postgres")
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Check if backtests table has wrong types
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'backtests' AND column_name IN ('id', 'strategy_id', 'user_id')
        """)
        cols = {r[0]: r[1] for r in cur.fetchall()}
        log(f"Current types: {cols}")

        needs_rebuild = cols.get("id") == "integer" or cols.get("strategy_id") == "integer"

        if needs_rebuild:
            log("\\n=== Rebuilding backtests table ===")

            # Backup existing data
            cur.execute("SELECT COUNT(*) FROM backtests")
            count = cur.fetchone()[0]
            log(f"Existing records: {count}")

            # Rename old table
            cur.execute("ALTER TABLE IF EXISTS backtests RENAME TO backtests_old")
            log("Renamed backtests -> backtests_old")

            # Create new table with correct schema
            cur.execute("""
                CREATE TABLE backtests (
                    id VARCHAR(36) PRIMARY KEY,
                    strategy_id VARCHAR(36),
                    strategy_type VARCHAR(50) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    symbol VARCHAR(20) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    start_date TIMESTAMP NOT NULL,
                    end_date TIMESTAMP NOT NULL,
                    initial_capital FLOAT NOT NULL DEFAULT 10000.0,
                    parameters JSONB DEFAULT '{}',
                    total_return FLOAT,
                    annual_return FLOAT,
                    sharpe_ratio FLOAT,
                    sortino_ratio FLOAT,
                    calmar_ratio FLOAT,
                    max_drawdown FLOAT,
                    win_rate FLOAT,
                    profit_factor FLOAT,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    avg_trade_pnl FLOAT,
                    best_trade FLOAT,
                    worst_trade FLOAT,
                    final_capital FLOAT,
                    peak_capital FLOAT,
                    net_profit FLOAT,
                    net_profit_pct FLOAT,
                    gross_profit FLOAT,
                    gross_loss FLOAT,
                    total_commission FLOAT,
                    buy_hold_return FLOAT,
                    buy_hold_return_pct FLOAT,
                    cagr FLOAT,
                    cagr_long FLOAT,
                    cagr_short FLOAT,
                    recovery_factor FLOAT,
                    expectancy FLOAT,
                    volatility FLOAT,
                    ulcer_index FLOAT,
                    max_consecutive_wins INTEGER,
                    max_consecutive_losses INTEGER,
                    long_trades INTEGER DEFAULT 0,
                    short_trades INTEGER DEFAULT 0,
                    long_pnl FLOAT,
                    short_pnl FLOAT,
                    long_win_rate FLOAT,
                    short_win_rate FLOAT,
                    avg_bars_in_trade FLOAT,
                    exposure_time FLOAT,
                    equity_curve JSONB,
                    trades JSONB,
                    metrics_json JSONB,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    execution_time_ms INTEGER,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    user_id VARCHAR(36),
                    notes TEXT
                )
            """)
            log("Created new backtests table")

            # Create indexes
            cur.execute("CREATE INDEX IF NOT EXISTS ix_backtests_strategy_id ON backtests(strategy_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_backtests_user_id ON backtests(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_backtests_symbol ON backtests(symbol)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_backtests_created_at ON backtests(created_at)")
            log("Created indexes")

            # Try to migrate data if old table has compatible columns
            if count > 0:
                try:
                    cur.execute("""
                        INSERT INTO backtests (
                            id, strategy_type, status, error_message, symbol, timeframe,
                            start_date, end_date, initial_capital, parameters,
                            total_return, sharpe_ratio, sortino_ratio, calmar_ratio,
                            max_drawdown, win_rate, profit_factor, total_trades,
                            winning_trades, losing_trades, final_capital,
                            equity_curve, trades, metrics_json,
                            created_at, updated_at, notes
                        )
                        SELECT
                            COALESCE(CAST(id AS VARCHAR(36)), gen_random_uuid()::text),
                            COALESCE(strategy_type, 'unknown'),
                            COALESCE(status, 'completed'),
                            error_message,
                            symbol,
                            timeframe,
                            start_date,
                            end_date,
                            initial_capital,
                            COALESCE(parameters, config, '{}'),
                            total_return,
                            sharpe_ratio,
                            sortino_ratio,
                            calmar_ratio,
                            max_drawdown,
                            win_rate,
                            profit_factor,
                            total_trades,
                            winning_trades,
                            losing_trades,
                            final_capital,
                            equity_curve,
                            trades,
                            COALESCE(metrics_json, results),
                            created_at,
                            COALESCE(created_at, NOW()),
                            notes
                        FROM backtests_old
                    """)
                    log(f"Migrated {cur.rowcount} records")
                except Exception as e:
                    log(f"Data migration failed (OK if new): {e}")

            # Drop old table
            cur.execute("DROP TABLE IF EXISTS backtests_old CASCADE")
            log("Dropped old backtests table")

            conn.commit()
            log("\\n=== Table rebuilt successfully! ===")
        else:
            log("\\n=== backtests table already has correct types ===")

        # Verify final schema
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'backtests'
            ORDER BY ordinal_position
        """)
        log("\\n=== Final schema ===")
        for row in cur.fetchall():
            log(f"  {row[0]}: {row[1]}")

        log("\\nDONE!")

    except Exception as e:
        conn.rollback()
        log(f"\\nERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
