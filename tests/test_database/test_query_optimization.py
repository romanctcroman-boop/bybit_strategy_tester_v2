"""
Tests for Query Performance Optimization

Tests database indexes and query execution times to verify
performance improvements from index additions.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta, UTC
from typing import List, Dict
import asyncpg

from backend.database import get_db_pool
from backend.models import Strategy, Backtest, Trade, MarketData


@pytest.fixture
async def db_pool():
    """Get database connection pool."""
    pool = await get_db_pool()
    yield pool


@pytest.fixture
async def test_data(db_pool):
    """Create test data for performance testing."""
    async with db_pool.acquire() as conn:
        # Clean up existing test data
        await conn.execute("DELETE FROM trades WHERE backtest_id IN (SELECT id FROM backtests WHERE strategy_id IN (SELECT id FROM strategies WHERE name LIKE 'PerfTest%'))")
        await conn.execute("DELETE FROM backtests WHERE strategy_id IN (SELECT id FROM strategies WHERE name LIKE 'PerfTest%')")
        await conn.execute("DELETE FROM strategies WHERE name LIKE 'PerfTest%'")
        
        # Create test strategy
        strategy_id = await conn.fetchval("""
            INSERT INTO strategies (name, description, strategy_type, is_active, created_at, updated_at)
            VALUES ('PerfTest Strategy', 'Test strategy for performance', 'momentum', true, NOW(), NOW())
            RETURNING id
        """)
        
        # Create 100 backtests
        backtest_ids = []
        for i in range(100):
            backtest_id = await conn.fetchval("""
                INSERT INTO backtests (
                    strategy_id, symbol, timeframe, start_date, end_date,
                    initial_capital, status, created_at, updated_at
                )
                VALUES ($1, 'BTCUSDT', '1h', $2, $3, 10000, 'completed', NOW(), NOW())
                RETURNING id
            """, strategy_id, 
                datetime.now(UTC) - timedelta(days=90),
                datetime.now(UTC) - timedelta(days=60)
            )
            backtest_ids.append(backtest_id)
        
        # Create 1000 trades (10 per backtest)
        for backtest_id in backtest_ids[:10]:  # Only first 10 for speed
            for j in range(100):
                await conn.execute("""
                    INSERT INTO trades (
                        backtest_id, entry_time, exit_time, side,
                        entry_price, exit_price, quantity, pnl, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                """, backtest_id,
                    datetime.now(UTC) - timedelta(hours=j*2),
                    datetime.now(UTC) - timedelta(hours=j*2-1),
                    'long' if j % 2 == 0 else 'short',
                    50000 + j * 10,
                    50000 + j * 10 + 50,
                    0.01,
                    5.0
                )
        
        yield {
            'strategy_id': strategy_id,
            'backtest_ids': backtest_ids,
        }
        
        # Cleanup
        await conn.execute("DELETE FROM trades WHERE backtest_id = ANY($1)", backtest_ids)
        await conn.execute("DELETE FROM backtests WHERE id = ANY($1)", backtest_ids)
        await conn.execute("DELETE FROM strategies WHERE id = $1", strategy_id)


class TestIndexCreation:
    """Test that indexes are created correctly."""
    
    @pytest.mark.asyncio
    async def test_indexes_exist(self, db_pool):
        """Verify all performance indexes exist."""
        async with db_pool.acquire() as conn:
            # Check strategies indexes
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE tablename = 'strategies' 
                AND indexname LIKE 'idx_%'
            """)
            assert result >= 2, "Missing strategies indexes"
            
            # Check backtests indexes
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE tablename = 'backtests' 
                AND indexname LIKE 'idx_%'
            """)
            assert result >= 4, "Missing backtests indexes"
            
            # Check trades indexes
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE tablename = 'trades' 
                AND indexname LIKE 'idx_%'
            """)
            assert result >= 3, "Missing trades indexes"
    
    @pytest.mark.asyncio
    async def test_index_usage(self, db_pool, test_data):
        """Verify indexes are used in queries."""
        async with db_pool.acquire() as conn:
            # Test strategy query uses index
            plan = await conn.fetchval("""
                EXPLAIN (FORMAT JSON)
                SELECT * FROM strategies 
                WHERE is_active = true AND strategy_type = 'momentum'
            """)
            
            # Should use index scan, not seq scan
            plan_str = str(plan)
            assert 'Index Scan' in plan_str or 'Bitmap Index Scan' in plan_str, \
                "Strategy query not using index"


class TestQueryPerformance:
    """Test query execution times."""
    
    @pytest.mark.asyncio
    async def test_get_active_strategies_performance(self, db_pool, test_data):
        """Test active strategies query performance."""
        async with db_pool.acquire() as conn:
            # Measure query time
            start = time.perf_counter()
            
            result = await conn.fetch("""
                SELECT id, name, strategy_type, is_active
                FROM strategies
                WHERE is_active = true
                ORDER BY created_at DESC
                LIMIT 20
            """)
            
            execution_time = (time.perf_counter() - start) * 1000  # ms
            
            print(f"\n📊 Active Strategies Query: {execution_time:.2f}ms")
            
            # Should be fast (<50ms)
            assert execution_time < 50, f"Query too slow: {execution_time:.2f}ms"
            assert len(result) > 0, "No results returned"
    
    @pytest.mark.asyncio
    async def test_get_backtests_for_strategy_performance(self, db_pool, test_data):
        """Test backtests query performance."""
        async with db_pool.acquire() as conn:
            start = time.perf_counter()
            
            result = await conn.fetch("""
                SELECT b.id, b.symbol, b.status, b.created_at, s.name
                FROM backtests b
                JOIN strategies s ON b.strategy_id = s.id
                WHERE b.strategy_id = $1
                ORDER BY b.created_at DESC
                LIMIT 50
            """, test_data['strategy_id'])
            
            execution_time = (time.perf_counter() - start) * 1000
            
            print(f"\n📊 Backtests Query: {execution_time:.2f}ms")
            
            # Should be fast with index (<30ms)
            assert execution_time < 30, f"Query too slow: {execution_time:.2f}ms"
            assert len(result) > 0, "No results returned"
    
    @pytest.mark.asyncio
    async def test_get_trades_for_backtest_performance(self, db_pool, test_data):
        """Test trades query performance."""
        async with db_pool.acquire() as conn:
            backtest_id = test_data['backtest_ids'][0]
            
            start = time.perf_counter()
            
            result = await conn.fetch("""
                SELECT id, entry_time, side, entry_price, exit_price, pnl
                FROM trades
                WHERE backtest_id = $1
                ORDER BY entry_time ASC
                LIMIT 1000
            """, backtest_id)
            
            execution_time = (time.perf_counter() - start) * 1000
            
            print(f"\n📊 Trades Query: {execution_time:.2f}ms")
            
            # Should be very fast with index (<20ms)
            assert execution_time < 20, f"Query too slow: {execution_time:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_complex_join_performance(self, db_pool, test_data):
        """Test complex JOIN query performance."""
        async with db_pool.acquire() as conn:
            start = time.perf_counter()
            
            result = await conn.fetch("""
                SELECT b.id, b.symbol, s.name, COUNT(t.id) as trade_count
                FROM backtests b
                JOIN strategies s ON b.strategy_id = s.id
                LEFT JOIN trades t ON t.backtest_id = b.id
                WHERE b.strategy_id = $1 AND b.status = 'completed'
                GROUP BY b.id, s.name
                ORDER BY b.created_at DESC
                LIMIT 20
            """, test_data['strategy_id'])
            
            execution_time = (time.perf_counter() - start) * 1000
            
            print(f"\n📊 Complex JOIN Query: {execution_time:.2f}ms")
            
            # Should be reasonable with indexes (<100ms)
            assert execution_time < 100, f"Query too slow: {execution_time:.2f}ms"


class TestPerformanceBenchmarks:
    """Benchmark query performance improvements."""
    
    @pytest.mark.asyncio
    async def test_benchmark_before_after_indexes(self, db_pool, test_data):
        """
        Compare query performance with and without indexes.
        
        Note: This test assumes indexes are already created.
        For comparison, we can check EXPLAIN plans.
        """
        async with db_pool.acquire() as conn:
            strategy_id = test_data['strategy_id']
            
            # Get EXPLAIN ANALYZE for query with indexes
            plan = await conn.fetchval("""
                EXPLAIN (ANALYZE, FORMAT JSON)
                SELECT b.id, b.symbol, b.status
                FROM backtests b
                WHERE b.strategy_id = $1 AND b.status = 'completed'
                ORDER BY b.created_at DESC
                LIMIT 50
            """, strategy_id)
            
            execution_time = plan[0]['Execution Time']
            planning_time = plan[0]['Planning Time']
            
            print(f"\n📊 Query with Indexes:")
            print(f"   Execution Time: {execution_time:.2f}ms")
            print(f"   Planning Time: {planning_time:.2f}ms")
            print(f"   Total Time: {execution_time + planning_time:.2f}ms")
            
            # Verify using index
            plan_str = str(plan)
            uses_index = 'Index Scan' in plan_str or 'Bitmap Index Scan' in plan_str
            
            print(f"   Uses Index: {'✅ Yes' if uses_index else '❌ No (Sequential Scan)'}")
            
            # Should use index and be fast
            assert uses_index, "Query should use index"
            assert execution_time < 50, f"Query too slow: {execution_time:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_benchmark_multiple_queries(self, db_pool, test_data):
        """Benchmark multiple common queries."""
        results = []
        
        async with db_pool.acquire() as conn:
            strategy_id = test_data['strategy_id']
            backtest_id = test_data['backtest_ids'][0]
            
            # Query 1: Get strategies
            start = time.perf_counter()
            await conn.fetch("SELECT * FROM strategies WHERE is_active = true LIMIT 20")
            results.append(('Strategies', (time.perf_counter() - start) * 1000))
            
            # Query 2: Get backtests
            start = time.perf_counter()
            await conn.fetch("""
                SELECT * FROM backtests 
                WHERE strategy_id = $1 
                ORDER BY created_at DESC LIMIT 50
            """, strategy_id)
            results.append(('Backtests', (time.perf_counter() - start) * 1000))
            
            # Query 3: Get trades
            start = time.perf_counter()
            await conn.fetch("""
                SELECT * FROM trades 
                WHERE backtest_id = $1 
                ORDER BY entry_time ASC LIMIT 100
            """, backtest_id)
            results.append(('Trades', (time.perf_counter() - start) * 1000))
            
            # Query 4: Complex aggregation
            start = time.perf_counter()
            await conn.fetch("""
                SELECT b.id, COUNT(t.id) as trade_count, AVG(t.pnl) as avg_pnl
                FROM backtests b
                LEFT JOIN trades t ON t.backtest_id = b.id
                WHERE b.strategy_id = $1
                GROUP BY b.id
            """, strategy_id)
            results.append(('Aggregation', (time.perf_counter() - start) * 1000))
        
        # Print benchmark results
        print("\n📊 Query Performance Benchmark:")
        print("-" * 50)
        total_time = 0
        for query_name, exec_time in results:
            status = "✅" if exec_time < 50 else "⚠️" if exec_time < 100 else "❌"
            print(f"   {status} {query_name:20s}: {exec_time:6.2f}ms")
            total_time += exec_time
        
        print("-" * 50)
        print(f"   Total Time: {total_time:.2f}ms")
        print(f"   Average:    {total_time/len(results):.2f}ms")
        
        # All queries should be reasonably fast
        avg_time = total_time / len(results)
        assert avg_time < 50, f"Average query time too high: {avg_time:.2f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
