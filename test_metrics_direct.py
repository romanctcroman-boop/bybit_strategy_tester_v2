"""
Тестовый скрипт для проверки записи метрик напрямую
"""
import asyncio
import sys
sys.path.insert(0, 'D:\\bybit_strategy_tester_v2')

from backend.monitoring.agent_metrics import record_agent_call, get_agent_performance
from loguru import logger

async def test_metrics():
    logger.info("🧪 Testing direct metrics recording...")
    
    try:
        # Test recording
        await record_agent_call(
            agent_name="deepseek",
            response_time_ms=1234.56,
            success=True,
            iterations=2,
            context={"test": "direct"}
        )
        logger.info("✅ Metrics recorded successfully")
        
        # Wait a bit
        await asyncio.sleep(1)
        
        # Try to read metrics
        performance = await get_agent_performance("deepseek", hours=1)
        logger.info(f"📊 Retrieved performance: {performance}")
        
    except Exception as e:
        logger.error(f"❌ Error: {type(e).__name__}: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_metrics())
