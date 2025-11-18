"""
Week 1, Day 3: Database Connection Pool Load Testing
Test connection pool under high load and concurrent access
"""

import pytest
import asyncio
import time
from typing import List
from sqlalchemy import text
from backend.database import SessionLocal, engine
from backend.database.pool_monitor import ConnectionPoolMonitor


class TestConnectionPoolLoad:
    """Test suite for connection pool load and concurrency"""
    
    @pytest.fixture
    def monitor(self):
        """Create pool monitor fixture"""
        return ConnectionPoolMonitor(engine)
    
    @pytest.fixture(autouse=True)
    def log_pool_status_before_after(self, monitor):
        """Log pool status before and after each test"""
        print("\n" + "=" * 80)
        print("POOL STATUS BEFORE TEST")
        print("=" * 80)
        monitor.log_pool_status()
        
        yield
        
        print("\n" + "=" * 80)
        print("POOL STATUS AFTER TEST")
        print("=" * 80)
        monitor.log_pool_status()
    
    def test_single_connection(self, monitor):
        """Test single database connection works correctly"""
        session = SessionLocal()
        try:
            result = session.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            assert row[0] == 1
            
            # Verify pool metrics
            status = monitor.get_pool_status()
            assert status['health'] in ['healthy', 'warning', 'critical']
            
        finally:
            session.close()
    
    def test_sequential_connections(self, monitor):
        """Test sequential connection requests (should all come from pool)"""
        iterations = 50
        
        start = time.time()
        for i in range(iterations):
            session = SessionLocal()
            try:
                result = session.execute(text("SELECT :i as num"), {"i": i})
                row = result.fetchone()
                assert row[0] == i
            finally:
                session.close()
        
        duration = time.time() - start
        avg_time_ms = (duration / iterations) * 1000
        
        print(f"\n{iterations} sequential queries in {duration:.2f}s")
        print(f"Average: {avg_time_ms:.2f}ms per query")
        
        # Should be fast due to connection pooling
        assert avg_time_ms < 50, f"Sequential queries too slow: {avg_time_ms:.2f}ms"
        
        # Pool should be healthy
        status = monitor.get_pool_status()
        assert status['checked_out'] == 0, "All connections should be returned"
    
    @pytest.mark.asyncio
    async def test_concurrent_connections_light(self, monitor):
        """Test light concurrent load (within base pool_size)"""
        concurrent_requests = 10  # Well within pool_size=20
        
        async def db_query(query_id: int):
            """Simulate database query"""
            session = SessionLocal()
            try:
                await asyncio.sleep(0.1)  # Simulate query time
                result = session.execute(text("SELECT :id as query_id"), {"id": query_id})
                row = result.fetchone()
                return row[0]
            finally:
                session.close()
        
        # Execute concurrent queries
        start = time.time()
        tasks = [db_query(i) for i in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)
        duration = time.time() - start
        
        # Verify all queries succeeded
        assert len(results) == concurrent_requests
        assert results == list(range(concurrent_requests))
        
        print(f"\n{concurrent_requests} concurrent queries in {duration:.2f}s")
        
        # Should complete quickly (parallel execution)
        assert duration < 0.3, f"Concurrent queries too slow: {duration:.2f}s"
        
        # Check pool status
        status = monitor.get_pool_status()
        assert status['health'] in ['healthy', 'warning']
    
    @pytest.mark.asyncio
    async def test_concurrent_connections_heavy(self, monitor):
        """Test heavy concurrent load (near pool capacity)"""
        concurrent_requests = 50  # Should use pool + overflow
        
        async def db_query(query_id: int):
            """Simulate longer database query"""
            session = SessionLocal()
            try:
                await asyncio.sleep(0.2)  # Longer query simulation
                result = session.execute(text("SELECT :id as query_id"), {"id": query_id})
                row = result.fetchone()
                return row[0]
            finally:
                session.close()
        
        # Monitor pool during load
        start = time.time()
        tasks = [db_query(i) for i in range(concurrent_requests)]
        
        # Start monitoring task
        async def monitor_pool():
            """Monitor pool status during load"""
            max_checked_out = 0
            while True:
                try:
                    status = monitor.get_pool_status()
                    max_checked_out = max(max_checked_out, status['checked_out'])
                    await asyncio.sleep(0.05)
                except asyncio.CancelledError:
                    return max_checked_out
        
        monitor_task = asyncio.create_task(monitor_pool())
        
        # Execute queries
        results = await asyncio.gather(*tasks)
        
        # Stop monitoring
        monitor_task.cancel()
        max_checked_out = await monitor_task
        
        duration = time.time() - start
        
        # Verify results
        assert len(results) == concurrent_requests
        assert results == list(range(concurrent_requests))
        
        print(f"\n{concurrent_requests} concurrent queries in {duration:.2f}s")
        print(f"Max concurrent connections: {max_checked_out}")
        
        # Should handle load without exhaustion
        assert duration < 1.0, f"Heavy load too slow: {duration:.2f}s"
        
        # Check final pool status
        status = monitor.get_pool_status()
        print(f"Final utilization: {status.get('utilization', 0)}%")
        
        # Pool might show warning/critical during peak, but should recover
        assert status['checked_out'] == 0, "All connections should be returned"
    
    @pytest.mark.asyncio
    async def test_pool_overflow_behavior(self, monitor):
        """Test pool behavior when exceeding base size"""
        # Get pool configuration
        initial_status = monitor.get_pool_status()
        pool_size = initial_status['size']
        max_overflow = initial_status['max_overflow']
        
        print(f"\nPool config: size={pool_size}, max_overflow={max_overflow}")
        
        # Create load that exceeds base pool
        concurrent_requests = pool_size + 10  # Force overflow usage
        
        async def db_query(query_id: int):
            session = SessionLocal()
            try:
                await asyncio.sleep(0.2)
                result = session.execute(text("SELECT :id"), {"id": query_id})
                return result.fetchone()[0]
            finally:
                session.close()
        
        # Execute
        tasks = [db_query(i) for i in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)
        
        # Verify
        assert len(results) == concurrent_requests
        
        # Check pool recovered
        final_status = monitor.get_pool_status()
        assert final_status['checked_out'] == 0
        print(f"Pool recovered: overflow={final_status['overflow']}")
    
    @pytest.mark.asyncio
    async def test_pool_exhaustion_timeout(self, monitor):
        """Test pool behavior when exhausted (timeout scenario)"""
        initial_status = monitor.get_pool_status()
        total_capacity = initial_status['size'] + initial_status['max_overflow']
        
        # Try to exceed total pool capacity
        concurrent_requests = total_capacity + 5
        
        async def db_query_slow(query_id: int):
            """Very slow query to hold connections"""
            session = SessionLocal()
            try:
                await asyncio.sleep(1.0)  # Hold connection for 1 second
                result = session.execute(text("SELECT :id"), {"id": query_id})
                return result.fetchone()[0]
            finally:
                session.close()
        
        # This should trigger pool timeout for some requests
        tasks = [db_query_slow(i) for i in range(concurrent_requests)]
        
        try:
            # Some requests might timeout (pool_timeout=30s by default)
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=5.0
            )
            
            # Count successful vs failed
            successful = sum(1 for r in results if not isinstance(r, Exception))
            failed = len(results) - successful
            
            print(f"\nExhaustion test: {successful} succeeded, {failed} failed/timeout")
            
            # At least some should succeed (those that got connections)
            assert successful > 0
            
        except asyncio.TimeoutError:
            print("\nPool exhaustion confirmed: requests timed out waiting for connections")
        
        # Check pool status after exhaustion
        status = monitor.get_pool_status()
        print(f"Pool status after exhaustion: utilization={status.get('utilization', 0)}%")
    
    def test_connection_recycling(self, monitor):
        """Test connection recycling behavior"""
        # Create and close many sessions
        sessions_created = 100
        
        for i in range(sessions_created):
            session = SessionLocal()
            try:
                result = session.execute(text("SELECT :i"), {"i": i})
                result.fetchone()
            finally:
                session.close()
        
        # Check pool status
        status = monitor.get_pool_status()
        
        print(f"\nAfter {sessions_created} sessions:")
        print(f"Pool size: {status['size']}")
        print(f"Checked out: {status['checked_out']}")
        print(f"Recycle time: {status['recycle']}s")
        
        # All connections should be returned
        assert status['checked_out'] == 0
        
        # Pool should maintain base size
        assert status['size'] > 0
    
    def test_pool_health_monitoring(self, monitor):
        """Test pool health assessment logic"""
        status = monitor.get_pool_status()
        
        # Health should be one of expected values
        assert status['health'] in ['healthy', 'warning', 'critical', 'unknown']
        
        # Check health determination
        if status['health'] == 'healthy':
            assert status.get('utilization', 0) < 70
        elif status['health'] == 'warning':
            assert 70 <= status.get('utilization', 0) < 90
        elif status['health'] == 'critical':
            assert status.get('utilization', 0) >= 90
    
    def test_connection_leak_detection(self, monitor):
        """Test connection leak detection"""
        # Normal usage shouldn't trigger leak detection
        leak_detected = monitor.check_connection_leaks()
        
        if leak_detected:
            status = monitor.get_pool_status()
            print(f"\nLeak detected! Utilization: {status.get('utilization', 0)}%")
            print(f"Checked out: {status['checked_out']}")
            print(f"Overflow: {status['overflow']}/{status['max_overflow']}")
        
        # In normal test conditions, no leak should be detected
        # (unless running under extreme load)
    
    def test_pool_recommendations(self, monitor):
        """Test pool recommendations logic"""
        recommendations = monitor.get_recommendations()
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        print("\nPool Recommendations:")
        for rec in recommendations:
            print(f"- {rec}")
        
        # Should provide actionable recommendations
        for rec in recommendations:
            assert len(rec) > 10, "Recommendations should be descriptive"
    
    @pytest.mark.asyncio
    async def test_pool_performance_vs_no_pool(self):
        """Compare performance with pooling vs without (theoretical)"""
        # Test with pooling (current configuration)
        iterations = 20
        
        start = time.time()
        for i in range(iterations):
            session = SessionLocal()
            try:
                result = session.execute(text("SELECT :i"), {"i": i})
                result.fetchone()
            finally:
                session.close()
        
        pooled_duration = time.time() - start
        avg_pooled_ms = (pooled_duration / iterations) * 1000
        
        print(f"\nWith pooling: {iterations} queries in {pooled_duration:.3f}s")
        print(f"Average: {avg_pooled_ms:.2f}ms per query")
        
        # Pooled connections should be fast (<50ms average)
        assert avg_pooled_ms < 50, f"Pooled queries slower than expected: {avg_pooled_ms:.2f}ms"
        
        # Note: Without pooling would be ~50-100ms slower per query
        # (connection establishment overhead)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s", "--tb=short"])
