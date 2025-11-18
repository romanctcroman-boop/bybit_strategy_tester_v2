"""
Performance Profiling Suite
Automated CPU, Memory, and I/O profiling for production optimization

Based on Phase 3 Deployment Plan from Perplexity AI
"""

import asyncio
import cProfile
import pstats
import io
import time
import tracemalloc
import psutil
from pathlib import Path
from datetime import datetime
from typing import Callable, Any
import json


# ============================================================================
# CPU PROFILING
# ============================================================================

class CPUProfiler:
    """CPU profiling using cProfile."""
    
    def __init__(self, output_dir: Path = Path("profiling_results")):
        """
        Initialize CPU profiler.
        
        Args:
            output_dir: Directory to save profiling results
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.profiler = cProfile.Profile()
    
    def start(self):
        """Start CPU profiling."""
        self.profiler.enable()
        print("✅ CPU profiling started")
    
    def stop(self, filename: str = None):
        """
        Stop CPU profiling and save results.
        
        Args:
            filename: Output filename (default: cpu_profile_<timestamp>.prof)
        """
        self.profiler.disable()
        
        if filename is None:
            filename = f"cpu_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.prof"
        
        output_path = self.output_dir / filename
        self.profiler.dump_stats(str(output_path))
        
        # Print top 20 time-consuming functions
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)
        
        report = s.getvalue()
        
        # Save text report
        text_path = self.output_dir / f"{filename}.txt"
        text_path.write_text(report, encoding='utf-8')
        
        print(f"✅ CPU profiling stopped")
        print(f"   Profile: {output_path}")
        print(f"   Report:  {text_path}")
        print("\n📊 Top 20 Functions by Cumulative Time:")
        print(report[:2000])  # Print first 2000 chars
        
        return output_path


# ============================================================================
# MEMORY PROFILING
# ============================================================================

class MemoryProfiler:
    """Memory profiling using tracemalloc."""
    
    def __init__(self, output_dir: Path = Path("profiling_results")):
        """
        Initialize memory profiler.
        
        Args:
            output_dir: Directory to save profiling results
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.snapshots = []
        self.labels = []
    
    def start(self):
        """Start memory profiling."""
        tracemalloc.start()
        print("✅ Memory profiling started")
    
    def snapshot(self, label: str = ""):
        """
        Take a memory snapshot.
        
        Args:
            label: Label for this snapshot
        """
        snapshot = tracemalloc.take_snapshot()
        self.snapshots.append(snapshot)
        self.labels.append(label or f"snapshot_{len(self.snapshots)}")
        
        # Current memory stats
        current, peak = tracemalloc.get_traced_memory()
        print(f"📸 Memory snapshot '{label}': current={current/1024/1024:.1f}MB, peak={peak/1024/1024:.1f}MB")
    
    def stop(self, filename: str = None):
        """
        Stop memory profiling and save results.
        
        Args:
            filename: Output filename (default: memory_profile_<timestamp>.txt)
        """
        if filename is None:
            filename = f"memory_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        output_path = self.output_dir / filename
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("MEMORY PROFILING REPORT")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Final stats
        current, peak = tracemalloc.get_traced_memory()
        report_lines.append(f"Final Memory Usage:")
        report_lines.append(f"  Current: {current / 1024 / 1024:.2f} MB")
        report_lines.append(f"  Peak:    {peak / 1024 / 1024:.2f} MB")
        report_lines.append("")
        
        # Snapshot comparisons
        for i in range(1, len(self.snapshots)):
            report_lines.append("=" * 80)
            report_lines.append(f"Snapshot Comparison: {self.labels[i-1]} → {self.labels[i]}")
            report_lines.append("=" * 80)
            
            top_stats = self.snapshots[i].compare_to(
                self.snapshots[i-1], 
                'lineno'
            )
            
            report_lines.append("\nTop 10 Memory Changes:")
            for stat in top_stats[:10]:
                report_lines.append(str(stat))
            
            report_lines.append("")
        
        # Top current allocations
        if self.snapshots:
            report_lines.append("=" * 80)
            report_lines.append("Top 20 Current Memory Allocations")
            report_lines.append("=" * 80)
            
            top_stats = self.snapshots[-1].statistics('lineno')
            for stat in top_stats[:20]:
                report_lines.append(str(stat))
        
        report = "\n".join(report_lines)
        output_path.write_text(report, encoding='utf-8')
        
        tracemalloc.stop()
        
        print(f"✅ Memory profiling stopped")
        print(f"   Report: {output_path}")
        print(f"\n📊 Summary:")
        print(f"   Snapshots: {len(self.snapshots)}")
        print(f"   Peak Memory: {peak / 1024 / 1024:.2f} MB")
        
        return output_path


# ============================================================================
# I/O PROFILING
# ============================================================================

class IOProfiler:
    """I/O profiling for async operations."""
    
    def __init__(self, output_dir: Path = Path("profiling_results")):
        """
        Initialize I/O profiler.
        
        Args:
            output_dir: Directory to save profiling results
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.operations = []
    
    async def profile_operation(
        self,
        operation: Callable,
        label: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Profile an async I/O operation.
        
        Args:
            operation: Async callable to profile
            label: Label for this operation
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result of operation
        """
        start_time = time.time()
        start_cpu = psutil.Process().cpu_percent()
        
        try:
            result = await operation(*args, **kwargs)
            
            elapsed = time.time() - start_time
            end_cpu = psutil.Process().cpu_percent()
            
            self.operations.append({
                'label': label,
                'elapsed_seconds': elapsed,
                'cpu_percent': (start_cpu + end_cpu) / 2,
                'status': 'success'
            })
            
            print(f"⏱️ I/O operation '{label}': {elapsed:.3f}s (CPU: {end_cpu:.1f}%)")
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            
            self.operations.append({
                'label': label,
                'elapsed_seconds': elapsed,
                'status': 'error',
                'error': str(e)
            })
            
            print(f"❌ I/O operation '{label}' failed after {elapsed:.3f}s: {e}")
            raise
    
    def save_report(self, filename: str = None):
        """
        Save I/O profiling report.
        
        Args:
            filename: Output filename (default: io_profile_<timestamp>.json)
        """
        if filename is None:
            filename = f"io_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output_path = self.output_dir / filename
        
        # Calculate statistics
        successful_ops = [op for op in self.operations if op['status'] == 'success']
        
        report = {
            'total_operations': len(self.operations),
            'successful_operations': len(successful_ops),
            'failed_operations': len(self.operations) - len(successful_ops),
            'total_time_seconds': sum(op['elapsed_seconds'] for op in self.operations),
            'average_time_seconds': sum(op['elapsed_seconds'] for op in successful_ops) / len(successful_ops) if successful_ops else 0,
            'operations': self.operations
        }
        
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        print(f"✅ I/O profiling report saved: {output_path}")
        print(f"\n📊 Summary:")
        print(f"   Total ops: {report['total_operations']}")
        print(f"   Success:   {report['successful_operations']}")
        print(f"   Failed:    {report['failed_operations']}")
        print(f"   Avg time:  {report['average_time_seconds']:.3f}s")
        
        return output_path


# ============================================================================
# COMPREHENSIVE PROFILING SESSION
# ============================================================================

class ProfilingSession:
    """Comprehensive profiling session (CPU + Memory + I/O)."""
    
    def __init__(self, name: str = "profiling_session"):
        """
        Initialize profiling session.
        
        Args:
            name: Session name for output files
        """
        self.name = name
        self.cpu_profiler = CPUProfiler()
        self.memory_profiler = MemoryProfiler()
        self.io_profiler = IOProfiler()
        
        print(f"\n{'='*80}")
        print(f"🔬 PROFILING SESSION: {name}")
        print(f"{'='*80}\n")
    
    def start(self):
        """Start all profilers."""
        self.cpu_profiler.start()
        self.memory_profiler.start()
        self.memory_profiler.snapshot("start")
    
    def memory_checkpoint(self, label: str):
        """Take a memory snapshot checkpoint."""
        self.memory_profiler.snapshot(label)
    
    async def profile_async_op(self, operation: Callable, label: str, *args, **kwargs):
        """Profile an async operation."""
        return await self.io_profiler.profile_operation(operation, label, *args, **kwargs)
    
    def stop(self):
        """Stop all profilers and save reports."""
        self.memory_profiler.snapshot("end")
        
        print(f"\n{'='*80}")
        print(f"📊 SAVING PROFILING REPORTS")
        print(f"{'='*80}\n")
        
        cpu_report = self.cpu_profiler.stop(f"{self.name}_cpu.prof")
        memory_report = self.memory_profiler.stop(f"{self.name}_memory.txt")
        io_report = self.io_profiler.save_report(f"{self.name}_io.json")
        
        print(f"\n{'='*80}")
        print(f"✅ PROFILING SESSION COMPLETE")
        print(f"{'='*80}")
        print(f"Reports saved in: profiling_results/")
        print(f"  - CPU:    {cpu_report.name}")
        print(f"  - Memory: {memory_report.name}")
        print(f"  - I/O:    {io_report.name}")


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_profiling_session():
    """Example of comprehensive profiling session."""
    
    session = ProfilingSession("example_session")
    
    # Start profiling
    session.start()
    
    # Simulate data loading
    async def load_data():
        await asyncio.sleep(0.1)
        return [1, 2, 3, 4, 5] * 1000
    
    data = await session.profile_async_op(load_data, "load_data")
    session.memory_checkpoint("after_data_load")
    
    # Simulate processing
    async def process_data(data):
        await asyncio.sleep(0.2)
        return [x * 2 for x in data]
    
    processed = await session.profile_async_op(process_data, "process_data", data)
    session.memory_checkpoint("after_processing")
    
    # Simulate save
    async def save_results(data):
        await asyncio.sleep(0.05)
        return True
    
    await session.profile_async_op(save_results, "save_results", processed)
    session.memory_checkpoint("after_save")
    
    # Stop profiling
    session.stop()


if __name__ == "__main__":
    """
    Run this script to test profiling suite:
    
    python performance_profiling.py
    
    Results will be saved in profiling_results/ directory.
    """
    asyncio.run(example_profiling_session())
