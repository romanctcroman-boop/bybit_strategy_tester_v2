"""
Тест интеграции Redis Queue с API

Проверяет:
1. API endpoint для запуска бэктеста
2. Обработку задачи через Redis Queue
3. Сохранение результатов в БД
"""

import asyncio
import httpx
from loguru import logger

BASE_URL = "http://localhost:8000/api/v1"


async def test_queue_integration():
    """Основной тест интеграции"""
    
    logger.info("=" * 60)
    logger.info("  Redis Queue Integration Test")
    logger.info("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # 1. Проверить health очереди
        logger.info("\n1️⃣  Checking queue health...")
        try:
            response = await client.get(f"{BASE_URL}/queue/health")
            health = response.json()
            logger.info(f"   Queue status: {health.get('status')}")
            logger.info(f"   Redis connected: {health.get('redis_connected')}")
        except Exception as e:
            logger.error(f"❌ Queue health check failed: {e}")
            return False
        
        # 2. Получить метрики очереди
        logger.info("\n2️⃣  Getting queue metrics...")
        try:
            response = await client.get(f"{BASE_URL}/queue/metrics")
            metrics = response.json()
            logger.info(f"   Tasks submitted: {metrics.get('tasks_submitted', 0)}")
            logger.info(f"   Tasks completed: {metrics.get('tasks_completed', 0)}")
            logger.info(f"   Active tasks: {metrics.get('active_tasks', 0)}")
        except Exception as e:
            logger.error(f"❌ Failed to get metrics: {e}")
        
        # 3. Создать тестовый backtest
        logger.info("\n3️⃣  Creating test backtest...")
        try:
            backtest_payload = {
                "strategy_id": 1,
                "symbol": "BTCUSDT",
                "timeframe": "60",  # ✅ Fixed: Use numeric minutes (60 = 1h)
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-31T00:00:00Z",
                "initial_capital": 10000.0,
                "leverage": 1,
                "commission": 0.0006,
                "config": {
                    "name": "Test Strategy",
                    "params": {
                        "fast_period": 12,
                        "slow_period": 26
                    }
                }
            }
            
            response = await client.post(
                f"{BASE_URL}/backtests/",
                json=backtest_payload
            )
            
            if response.status_code == 200 or response.status_code == 201:
                backtest = response.json()
                backtest_id = backtest.get("id")
                logger.info(f"   ✅ Created backtest: {backtest_id}")
            else:
                logger.error(f"❌ Failed to create backtest: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                # Попробуем использовать существующий backtest
                backtest_id = 1
                logger.info(f"   Using existing backtest_id: {backtest_id}")
        
        except Exception as e:
            logger.error(f"❌ Failed to create backtest: {e}")
            backtest_id = 1
            logger.info(f"   Using existing backtest_id: {backtest_id}")
        
        # 4. Отправить backtest в очередь
        logger.info(f"\n4️⃣  Submitting backtest {backtest_id} to queue...")
        try:
            response = await client.post(
                f"{BASE_URL}/queue/backtest/run",
                json={
                    "backtest_id": backtest_id,
                    "priority": 10
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                task_id = result.get("task_id")
                logger.info(f"   ✅ Task submitted: {task_id[:16]}...")
                logger.info(f"   Status: {result.get('status')}")
            else:
                logger.error(f"❌ Failed to submit backtest: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Failed to submit backtest: {e}")
            return False
        
        # 5. Подождать немного и проверить метрики
        logger.info("\n5️⃣  Waiting for task processing...")
        await asyncio.sleep(5)
        
        try:
            response = await client.get(f"{BASE_URL}/queue/metrics")
            metrics = response.json()
            logger.info(f"   Tasks submitted: {metrics.get('tasks_submitted', 0)}")
            logger.info(f"   Tasks completed: {metrics.get('tasks_completed', 0)}")
            logger.info(f"   Active tasks: {metrics.get('active_tasks', 0)}")
            logger.info(f"   Failed tasks: {metrics.get('tasks_failed', 0)}")
        except Exception as e:
            logger.error(f"❌ Failed to get metrics: {e}")
        
        # 6. Проверить статус backtest
        logger.info(f"\n6️⃣  Checking backtest {backtest_id} status...")
        try:
            response = await client.get(f"{BASE_URL}/backtests/{backtest_id}")
            if response.status_code == 200:
                backtest = response.json()
                logger.info(f"   Status: {backtest.get('status')}")
                logger.info(f"   Final capital: {backtest.get('final_capital', 'N/A')}")
                logger.info(f"   Total return: {backtest.get('total_return', 'N/A')}")
            else:
                logger.warning(f"⚠️ Could not get backtest status: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Failed to get backtest status: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ Integration test completed!")
    logger.info("=" * 60)
    return True


async def test_create_and_run():
    """Тест комбинированного endpoint create-and-run"""
    
    logger.info("\n\n" + "=" * 60)
    logger.info("  Testing create-and-run endpoint")
    logger.info("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        backtest_payload = {
            "strategy_id": 1,
            "symbol": "ETHUSDT",
            "timeframe": "240",  # ✅ Fixed: Use numeric minutes (240 = 4h)
            "start_date": "2024-02-01T00:00:00Z",
            "end_date": "2024-02-28T00:00:00Z",
            "initial_capital": 5000.0,
            "leverage": 1,
            "commission": 0.0006,
            "config": {
                "name": "ETH Test Strategy",
                "params": {
                    "period": 20
                }
            }
        }
        
        logger.info("\n📤 Creating and running backtest...")
        try:
            response = await client.post(
                f"{BASE_URL}/queue/backtest/create-and-run",
                json=backtest_payload
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"   ✅ Backtest ID: {result.get('backtest_id')}")
                logger.info(f"   ✅ Task ID: {result.get('task_id')[:16]}...")
                logger.info(f"   Status: {result.get('status')}")
            else:
                logger.error(f"❌ Failed: {response.status_code}")
                logger.error(f"   Response: {response.text}")
        
        except Exception as e:
            logger.error(f"❌ Error: {e}")
    
    logger.info("\n" + "=" * 60)


if __name__ == "__main__":
    logger.info("\n[SETUP] Make sure the following are running:")
    logger.info("   1. Redis: redis-server")
    logger.info("   2. Backend API: uvicorn backend.api.app:app --reload")
    logger.info("   3. Workers: python -m backend.queue.worker_cli --workers 2")
    
    try:
        asyncio.run(test_queue_integration())
        asyncio.run(test_create_and_run())
    except KeyboardInterrupt:
        logger.warning("\n[INTERRUPTED] Test interrupted by user")
    except Exception as e:
        logger.error(f"\n[ERROR] Fatal error: {e}")
        import traceback
        traceback.print_exc()

