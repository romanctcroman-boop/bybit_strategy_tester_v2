"""
Unit tests for BatchWriter - Database Batch Operations
"""

import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.database.batch_writer import (
    BatchWriter,
    BatchUpdateWriter,
    batch_insert,
    batch_update
)


# Test model
Base = declarative_base()


class TestTask(Base):
    """Test model for batch operations"""
    __tablename__ = 'test_tasks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    data = Column(String(500))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))


@pytest.fixture
def session():
    """Create in-memory SQLite session for testing"""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestBatchWriter:
    """Test BatchWriter functionality"""
    
    @pytest.mark.asyncio
    async def test_basic_batch_insert(self, session):
        """Test basic batch insert operation"""
        async with BatchWriter(session, batch_size=10) as writer:
            for i in range(5):
                await writer.add(TestTask, {
                    'task_type': 'BACKTEST',
                    'status': 'PENDING',
                    'data': f'task_{i}'
                })
        
        # Verify records in database
        count = session.query(TestTask).count()
        assert count == 5
    
    @pytest.mark.asyncio
    async def test_auto_flush_on_batch_size(self, session):
        """Test auto-flush when batch size reached"""
        writer = BatchWriter(session, batch_size=3, auto_flush=True)
        
        # Add 3 records - should auto-flush
        for i in range(3):
            await writer.add(TestTask, {
                'task_type': 'BACKTEST',
                'status': 'PENDING',
                'data': f'task_{i}'
            })
        
        # Check writer stats
        stats = writer.get_stats()
        assert stats['total_added'] == 3
        assert stats['total_flushed'] == 3
        assert stats['flush_count'] == 1
        
        # Add 2 more - should not auto-flush yet
        for i in range(2):
            await writer.add(TestTask, {
                'task_type': 'BACKTEST',
                'status': 'PENDING',
                'data': f'task_{i+3}'
            })
        
        stats = writer.get_stats()
        assert stats['total_added'] == 5
        assert stats['total_flushed'] == 3  # Still 3 (2 buffered)
        assert stats['buffered'] == 2
        
        # Manual flush
        await writer.flush()
        
        stats = writer.get_stats()
        assert stats['total_flushed'] == 5
        assert stats['buffered'] == 0
        
        # Verify all records in database
        count = session.query(TestTask).count()
        assert count == 5
    
    @pytest.mark.asyncio
    async def test_large_batch(self, session):
        """Test inserting large batch of records"""
        async with BatchWriter(session, batch_size=50) as writer:
            for i in range(150):
                await writer.add(TestTask, {
                    'task_type': 'BACKTEST',
                    'status': 'PENDING',
                    'data': f'task_{i}'
                })
        
        # Verify all records inserted
        count = session.query(TestTask).count()
        assert count == 150
        
        # Verify data integrity
        tasks = session.query(TestTask).order_by(TestTask.id).all()
        assert len(tasks) == 150
        assert tasks[0].data == 'task_0'
        assert tasks[149].data == 'task_149'
    
    @pytest.mark.asyncio
    async def test_multiple_models(self, session):
        """Test batching multiple models simultaneously"""
        # Note: For this test we'll just use TestTask twice
        # In production, you'd have different models
        
        async with BatchWriter(session, batch_size=10) as writer:
            # Add records for "model 1"
            for i in range(5):
                await writer.add(TestTask, {
                    'task_type': 'BACKTEST',
                    'status': 'PENDING',
                    'data': f'model1_task_{i}'
                })
            
            # Add records for "model 2"
            for i in range(5):
                await writer.add(TestTask, {
                    'task_type': 'ANALYSIS',
                    'status': 'PENDING',
                    'data': f'model2_task_{i}'
                })
        
        # Verify all records
        count = session.query(TestTask).count()
        assert count == 10
        
        # Verify by type
        backtest_count = session.query(TestTask).filter(
            TestTask.task_type == 'BACKTEST'
        ).count()
        assert backtest_count == 5
        
        analysis_count = session.query(TestTask).filter(
            TestTask.task_type == 'ANALYSIS'
        ).count()
        assert analysis_count == 5
    
    @pytest.mark.asyncio
    async def test_manual_flush(self, session):
        """Test manual flush without context manager"""
        writer = BatchWriter(session, batch_size=100, auto_flush=False)
        
        # Add records without auto-flush
        for i in range(10):
            await writer.add(TestTask, {
                'task_type': 'BACKTEST',
                'status': 'PENDING',
                'data': f'task_{i}'
            })
        
        # No records in DB yet (not flushed)
        count = session.query(TestTask).count()
        assert count == 0
        
        # Manual flush
        flushed = await writer.flush()
        assert flushed == 10
        
        # Now records are in DB
        count = session.query(TestTask).count()
        assert count == 10
    
    @pytest.mark.asyncio
    async def test_created_at_auto_added(self, session):
        """Test that created_at is automatically added"""
        async with BatchWriter(session, batch_size=10) as writer:
            await writer.add(TestTask, {
                'task_type': 'BACKTEST',
                'status': 'PENDING',
                'data': 'test'
            })
        
        task = session.query(TestTask).first()
        assert task is not None
        assert task.created_at is not None
        assert isinstance(task.created_at, datetime)
    
    @pytest.mark.asyncio
    async def test_stats_tracking(self, session):
        """Test statistics tracking"""
        writer = BatchWriter(session, batch_size=5)
        
        # Add 12 records (2 full batches + 2 remaining)
        for i in range(12):
            await writer.add(TestTask, {
                'task_type': 'BACKTEST',
                'status': 'PENDING',
                'data': f'task_{i}'
            })
        
        stats = writer.get_stats()
        assert stats['total_added'] == 12
        assert stats['total_flushed'] == 10  # 2 batches of 5
        assert stats['buffered'] == 2
        assert stats['flush_count'] == 2
        assert stats['batch_size'] == 5
    
    @pytest.mark.asyncio
    async def test_error_handling_with_rollback(self, session):
        """Test error handling and rollback"""
        with pytest.raises(Exception):
            async with BatchWriter(session, batch_size=10) as writer:
                # Add valid record
                await writer.add(TestTask, {
                    'task_type': 'BACKTEST',
                    'status': 'PENDING',
                    'data': 'task_1'
                })
                
                # Raise exception to trigger rollback
                raise ValueError("Simulated error")
        
        # No records should be in database due to rollback
        count = session.query(TestTask).count()
        assert count == 0


class TestBatchUpdateWriter:
    """Test BatchUpdateWriter functionality"""
    
    @pytest.mark.asyncio
    async def test_basic_batch_update(self, session):
        """Test basic batch update operation"""
        # Insert initial records
        tasks = [
            TestTask(task_type='BACKTEST', status='PENDING', data=f'task_{i}')
            for i in range(5)
        ]
        session.add_all(tasks)
        session.commit()
        
        # Get IDs
        task_ids = [task.id for task in tasks]
        
        # Update via batch
        async with BatchUpdateWriter(session, batch_size=10) as writer:
            for task_id in task_ids:
                await writer.add(TestTask, {
                    'id': task_id,
                    'status': 'COMPLETED'
                })
        
        # Verify updates
        completed_count = session.query(TestTask).filter(
            TestTask.status == 'COMPLETED'
        ).count()
        assert completed_count == 5
    
    @pytest.mark.asyncio
    async def test_large_batch_update(self, session):
        """Test updating large batch of records"""
        # Insert 100 records
        tasks = [
            TestTask(task_type='BACKTEST', status='PENDING', data=f'task_{i}')
            for i in range(100)
        ]
        session.add_all(tasks)
        session.commit()
        
        # Update all via batch
        async with BatchUpdateWriter(session, batch_size=50) as writer:
            for task in tasks:
                await writer.add(TestTask, {
                    'id': task.id,
                    'status': 'COMPLETED'
                })
        
        # Verify all updated
        completed_count = session.query(TestTask).filter(
            TestTask.status == 'COMPLETED'
        ).count()
        assert completed_count == 100


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @pytest.mark.asyncio
    async def test_batch_insert_function(self, session):
        """Test batch_insert convenience function"""
        records = [
            {'task_type': 'BACKTEST', 'status': 'PENDING', 'data': f'task_{i}'}
            for i in range(20)
        ]
        
        count = await batch_insert(session, TestTask, records, batch_size=10)
        
        assert count == 20
        
        # Verify in database
        db_count = session.query(TestTask).count()
        assert db_count == 20
    
    @pytest.mark.asyncio
    async def test_batch_update_function(self, session):
        """Test batch_update convenience function"""
        # Insert initial records
        tasks = [
            TestTask(task_type='BACKTEST', status='PENDING', data=f'task_{i}')
            for i in range(20)
        ]
        session.add_all(tasks)
        session.commit()
        
        # Prepare update records
        updates = [
            {'id': task.id, 'status': 'COMPLETED'}
            for task in tasks
        ]
        
        count = await batch_update(session, TestTask, updates, batch_size=10)
        
        assert count == 20
        
        # Verify updates
        completed_count = session.query(TestTask).filter(
            TestTask.status == 'COMPLETED'
        ).count()
        assert completed_count == 20


class TestPerformance:
    """Performance benchmarks"""
    
    @pytest.mark.asyncio
    async def test_performance_comparison(self, session):
        """Compare individual vs batch insert performance"""
        import time
        
        # Test 1: Individual inserts (baseline)
        start = time.time()
        for i in range(100):
            task = TestTask(
                task_type='BACKTEST',
                status='PENDING',
                data=f'individual_{i}'
            )
            session.add(task)
            session.commit()
        individual_time = time.time() - start
        
        # Clear database
        session.query(TestTask).delete()
        session.commit()
        
        # Test 2: Batch inserts
        start = time.time()
        async with BatchWriter(session, batch_size=50) as writer:
            for i in range(100):
                await writer.add(TestTask, {
                    'task_type': 'BACKTEST',
                    'status': 'PENDING',
                    'data': f'batch_{i}'
                })
        batch_time = time.time() - start
        
        # Batch should be significantly faster
        speedup = individual_time / batch_time
        
        print(f"\n[Performance Benchmark]")
        print(f"  Individual inserts: {individual_time:.3f}s")
        print(f"  Batch inserts:      {batch_time:.3f}s")
        print(f"  Speedup:            {speedup:.1f}x")
        
        # Batch should be at least 2x faster (often 10-20x)
        assert speedup >= 2.0, f"Batch should be faster (got {speedup:.1f}x)"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
