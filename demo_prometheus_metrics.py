"""
Prometheus Metrics Demo
========================

Demonstrates Prometheus metrics integration.

Run this script and open http://localhost:9090/metrics in your browser
to see exported metrics.
"""

import time
import asyncio
import logging
from automation.metrics import start_metrics_server
from automation.metrics.collectors import (
    TestWatcherCollector,
    AuditAgentCollector,
    SystemCollector
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_test_watcher_metrics():
    """Demonstrate TestWatcher metrics."""
    logger.info("📊 Demo: TestWatcher Metrics")
    
    collector = TestWatcherCollector()
    
    # Set running status
    collector.set_running_status(True)
    
    # Simulate file processing
    for i in range(5):
        collector.record_file_processed()
        collector.update_changed_files_count(i + 1)
        
        # Simulate test execution with timer
        with collector.time_test_execution():
            await asyncio.sleep(0.2)
            # Record test results
            if i % 3 == 0:
                collector.record_test_run('pass')
            elif i % 3 == 1:
                collector.record_test_run('fail')
            else:
                collector.record_test_run('error')
        
        # Simulate API call
        with collector.time_processing():
            collector.record_api_call('deepseek', 'success', 0.5)
        
        collector.update_memory_usage()
        
        logger.info(f"  ✅ Processed file {i + 1}/5")
        await asyncio.sleep(0.5)
    
    collector.set_running_status(False)
    logger.info("✅ TestWatcher demo complete\n")


async def demo_audit_agent_metrics():
    """Demonstrate AuditAgent metrics."""
    logger.info("📊 Demo: AuditAgent Metrics")
    
    collector = AuditAgentCollector()
    
    # Simulate audit runs
    for i, trigger in enumerate(['scheduled', 'manual', 'marker_detected']):
        collector.record_run(trigger)
        
        # Simulate run with timer
        with collector.time_run():
            await asyncio.sleep(0.3)
            
            # Simulate analysis
            with collector.time_analysis():
                await asyncio.sleep(0.2)
            
            # Update coverage
            coverage = 75.0 + i * 5.0
            collector.update_coverage(coverage)
            
            if i == 2:
                collector.record_completion_marker_found()
            
            collector.record_git_commit_detected()
        
        logger.info(f"  ✅ Audit run {i + 1}/3 ({trigger}) - Coverage: {coverage}%")
        await asyncio.sleep(0.5)
    
    logger.info("✅ AuditAgent demo complete\n")


def demo_system_metrics():
    """Demonstrate system metrics collection."""
    logger.info("📊 Demo: System Metrics")
    
    collector = SystemCollector()
    
    for i in range(3):
        collector.collect_all()
        
        cpu = collector.cpu_percent._value.get()
        memory_pct = collector.memory_percent._value.get()
        memory_bytes = collector.process_memory._value.get()
        threads = collector.process_threads._value.get()
        
        logger.info(
            f"  ✅ Sample {i + 1}/3: "
            f"CPU={cpu:.1f}%, "
            f"Memory={memory_pct:.1f}% ({memory_bytes / 1024 / 1024:.1f} MB), "
            f"Threads={threads}"
        )
        time.sleep(1)
    
    logger.info("✅ System metrics demo complete\n")


async def main():
    """Main demo function."""
    logger.info("=" * 60)
    logger.info("🚀 Prometheus Metrics Demo")
    logger.info("=" * 60)
    logger.info("")
    
    # Start metrics server
    logger.info("🌐 Starting Prometheus metrics server...")
    exporter = start_metrics_server(port=9090, host='localhost')
    
    logger.info("✅ Metrics server running at http://localhost:9090/metrics")
    logger.info("")
    logger.info("📍 Open http://localhost:9090/metrics in your browser to see metrics")
    logger.info("")
    
    # Wait a moment for server to start
    await asyncio.sleep(1)
    
    # Run demos
    try:
        await demo_test_watcher_metrics()
        await demo_audit_agent_metrics()
        demo_system_metrics()
        
        logger.info("=" * 60)
        logger.info("✅ Demo Complete!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("📊 Metrics are still being exported at http://localhost:9090/metrics")
        logger.info("   Press Ctrl+C to stop the server")
        logger.info("")
        
        # Keep server running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("")
        logger.info("🛑 Stopping metrics server...")
        exporter.stop()
        logger.info("✅ Server stopped")


if __name__ == '__main__':
    asyncio.run(main())
