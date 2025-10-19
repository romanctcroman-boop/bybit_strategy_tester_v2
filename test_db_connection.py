"""
PostgreSQL Connection Test Script

Tests database connection and basic CRUD operations.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json

# Connection parameters
CONN_PARAMS = {
    "host": "localhost",
    "port": 5432,
    "database": "bybit_strategy_tester",
    "user": "postgres",
    "password": "postgres123"
}

def test_connection():
    """Test basic PostgreSQL connection"""
    print("\n" + "="*70)
    print("  POSTGRESQL CONNECTION TEST")
    print("="*70 + "\n")
    
    try:
        conn = psycopg2.connect(**CONN_PARAMS)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test 1: Database version
        print("[1/8] Testing database connection...")
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        print(f"✅ PostgreSQL version: {version['version'][:50]}...")
        
        # Test 2: Check TimescaleDB (optional)
        print("\n[2/8] Checking TimescaleDB extension...")
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
        tsdb = cursor.fetchone()
        if tsdb:
            print(f"✅ TimescaleDB version: {tsdb['extversion']}")
        else:
            print("⚠️  TimescaleDB not installed (OK for basic operations)")
        
        # Test 3: List all tables
        print("\n[3/8] Listing database tables...")
        cursor.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        tables = cursor.fetchall()
        print(f"✅ Tables found: {len(tables)}")
        for table in tables:
            print(f"   - {table['tablename']}")
        
        # Test 4: Check strategies table structure
        print("\n[4/8] Checking strategies table structure...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'strategies'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        print(f"✅ Strategies table columns: {len(columns)}")
        for col in columns:
            print(f"   - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
        
        # Test 5: Count existing strategies
        print("\n[5/8] Counting existing strategies...")
        cursor.execute("SELECT COUNT(*) as count FROM strategies")
        count = cursor.fetchone()
        print(f"✅ Strategies in database: {count['count']}")
        
        # Test 6: Insert test strategy
        print("\n[6/8] Inserting test strategy...")
        test_strategy = {
            "name": "Test RSI Strategy - " + datetime.now().strftime("%H:%M:%S"),
            "description": "Automated test strategy for connection verification",
            "strategy_type": "Indicator-Based",
            "config": json.dumps({
                "rsi_period": 14,
                "oversold": 30,
                "overbought": 70,
                "timeframe": "15m"
            })
        }
        
        cursor.execute("""
            INSERT INTO strategies (name, description, strategy_type, config)
            VALUES (%(name)s, %(description)s, %(strategy_type)s, %(config)s)
            RETURNING id, name, created_at
        """, test_strategy)
        
        inserted = cursor.fetchone()
        print(f"✅ Strategy inserted:")
        print(f"   ID: {inserted['id']}")
        print(f"   Name: {inserted['name']}")
        print(f"   Created: {inserted['created_at']}")
        
        # Test 7: Read strategy back
        print("\n[7/8] Reading strategy back...")
        cursor.execute("""
            SELECT id, name, description, strategy_type, config, created_at
            FROM strategies
            WHERE id = %s
        """, (inserted['id'],))
        
        strategy = cursor.fetchone()
        print(f"✅ Strategy retrieved:")
        print(f"   ID: {strategy['id']}")
        print(f"   Name: {strategy['name']}")
        print(f"   Type: {strategy['strategy_type']}")
        print(f"   Config: {strategy['config']}")
        
        # Test 8: List all strategies
        print("\n[8/8] Listing all strategies...")
        cursor.execute("""
            SELECT id, name, strategy_type, created_at
            FROM strategies
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        strategies = cursor.fetchall()
        print(f"✅ Recent strategies: {len(strategies)}")
        for strat in strategies:
            print(f"   [{strat['id']}] {strat['name']} ({strat['strategy_type']})")
        
        # Commit and close
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED - Database is ready for use!")
        print("="*70 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        print("\nTroubleshooting:")
        print("  1. Check PostgreSQL service is running:")
        print("     Get-Service postgresql-x64-16")
        print("  2. Check database exists:")
        print("     .\check_postgres.ps1")
        print("  3. Verify connection parameters in script")
        print("  4. Check .env file has correct DATABASE_URL\n")
        return False


def test_backtest_table():
    """Test backtest table for storing results"""
    print("\n" + "="*70)
    print("  BACKTEST TABLE TEST")
    print("="*70 + "\n")
    
    try:
        conn = psycopg2.connect(**CONN_PARAMS)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get a strategy ID
        cursor.execute("SELECT id FROM strategies LIMIT 1")
        strategy = cursor.fetchone()
        
        if not strategy:
            print("⚠️  No strategies found. Create one first.")
            return False
        
        strategy_id = strategy['id']
        
        # Insert test backtest
        print("[1/3] Inserting test backtest result...")
        cursor.execute("""
            INSERT INTO backtests (
                strategy_id, symbol, timeframe, start_date, end_date,
                initial_capital, final_capital, total_return_pct,
                total_trades, winning_trades, losing_trades, win_rate,
                profit_factor, sharpe_ratio, max_drawdown_pct,
                avg_trade_pct, largest_win_pct, largest_loss_pct,
                config, status
            ) VALUES (
                %s, 'BTCUSDT', '15m', '2025-01-01', '2025-10-16',
                10000, 12500, 25.00,
                100, 60, 40, 60.00,
                1.75, 1.85, -15.50,
                2.50, 8.50, -5.25,
                %s, 'completed'
            )
            RETURNING id, symbol, final_capital, total_return_pct
        """, (strategy_id, json.dumps({"test": True})))
        
        backtest = cursor.fetchone()
        print(f"✅ Backtest created:")
        print(f"   ID: {backtest['id']}")
        print(f"   Symbol: {backtest['symbol']}")
        print(f"   Final Capital: ${backtest['final_capital']}")
        print(f"   Return: {backtest['total_return_pct']}%")
        
        # Insert some trades
        print("\n[2/3] Inserting test trades...")
        trades_data = [
            ('2025-10-01 10:00:00', 'LONG', 65000, 100, '2025-10-01 14:00:00', 'CLOSED', 66000, 1000, 1.54),
            ('2025-10-02 09:30:00', 'SHORT', 64500, 150, '2025-10-02 15:00:00', 'CLOSED', 64000, 750, 1.16),
            ('2025-10-03 11:00:00', 'LONG', 65500, 120, '2025-10-03 16:00:00', 'CLOSED', 64800, -840, -1.07),
        ]
        
        for trade in trades_data:
            cursor.execute("""
                INSERT INTO trades (
                    backtest_id, entry_time, side, entry_price, quantity,
                    exit_time, status, exit_price, pnl, return_pct
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (backtest['id'],) + trade)
        
        print(f"✅ {len(trades_data)} trades inserted")
        
        # Query backtest with stats
        print("\n[3/3] Querying backtest statistics...")
        cursor.execute("""
            SELECT 
                b.id,
                b.symbol,
                b.total_trades,
                b.win_rate,
                b.final_capital,
                b.total_return_pct,
                COUNT(t.id) as trade_count,
                AVG(t.return_pct) as avg_return
            FROM backtests b
            LEFT JOIN trades t ON t.backtest_id = b.id
            WHERE b.id = %s
            GROUP BY b.id
        """, (backtest['id'],))
        
        stats = cursor.fetchone()
        print(f"✅ Backtest statistics:")
        print(f"   Symbol: {stats['symbol']}")
        print(f"   Total Trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']}%")
        print(f"   Return: {stats['total_return_pct']}%")
        print(f"   Trade Count: {stats['trade_count']}")
        print(f"   Avg Return: {stats['avg_return']:.2f}%")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n✅ Backtest table tests passed!\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Backtest test failed: {e}\n")
        return False


if __name__ == "__main__":
    # Run connection test
    success = test_connection()
    
    if success:
        # Run backtest table test
        test_backtest_table()
        
        print("="*70)
        print("🎉 All database tests completed successfully!")
        print("="*70)
        print("\nNext steps:")
        print("  1. Connect VS Code PostgreSQL extension")
        print("  2. Create backend database module (backend/database/)")
        print("  3. Add API endpoints for database operations")
        print("  4. Start using PostgreSQL for result storage\n")
    else:
        print("\n⚠️  Fix connection issues before proceeding\n")
