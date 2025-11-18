"""
Комплексный тест Redis Queue с реальным API и Workers
Тестирует полный flow: API → Queue → Worker → Database
"""

import asyncio
import httpx
from loguru import logger
import sys

BASE_URL = "http://127.0.0.1:8000"
API_V1 = f"{BASE_URL}/api/v1"


async def test_full_integration():
    """Полный интеграционный тест"""
    
    logger.info("=" * 60)
    logger.info("  Full Redis Queue Integration Test")
    logger.info("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        
        # 1. Проверить API health
        logger.info("\n1️⃣  Checking API Health...")
        try:
            r = await client.get(f"{BASE_URL}/healthz")
            health = r.json()
            logger.info(f"   Status: {health.get('status')}")
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            logger.error("   Make sure API is running:")
            logger.error("   uvicorn backend.api.app:app --port 8000")
            return False
        
        # 2. Получить metrics
        logger.info("\n2️⃣  Getting Queue Metrics...")
        try:
            r = await client.get(f"{API_V1}/queue/metrics")
            metrics = r.json()
            logger.info(f"   Tasks submitted: {metrics.get('tasks_submitted', 0)}")
            logger.info(f"   Tasks completed: {metrics.get('tasks_completed', 0)}")
            logger.info(f"   Active tasks: {metrics.get('active_tasks', 0)}")
        except Exception as e:
            logger.error(f"❌ Metrics failed: {e}")
        
        # 3. Создать тестовую стратегию (если нет)
        logger.info("\n3️⃣  Checking test strategy...")
        try:
            r = await client.get(f"{API_V1}/strategies")
            if r.status_code == 200:
                data = r.json()
                strategies = data.get("items", []) if isinstance(data, dict) else data
                
                if not strategies:
                    logger.warning("   No strategies found, creating test strategy...")
                    r = await client.post(
                        f"{API_V1}/strategies/",
                        json={
                            "name": "Test EMA Crossover",
                            "description": "Test strategy for queue integration",
                            "strategy_type": "custom",
                            "config": {
                                "code": "def strategy(data):\n    return 1",
                                "parameters": {"fast": 12, "slow": 26}
                            }
                        }
                    )
                    if r.status_code in (200, 201):
                        strategy = r.json()
                        strategy_id = strategy.get("id")
                        logger.success(f"   ✅ Strategy created: ID={strategy_id}")
                    else:
                        logger.error(f"   ❌ Failed to create strategy: {r.status_code}")
                        logger.error(f"   Response: {r.text}")
                        return False
                else:
                    strategy_id = strategies[0]["id"]
                    logger.info(f"   ✅ Using existing strategy: ID={strategy_id}")
            else:
                logger.error(f"   ❌ Failed to get strategies: {r.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Strategy check failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 4. Создать и отправить backtest через queue
        logger.info("\n4️⃣  Submitting backtest via queue...")
        try:
            r = await client.post(
                f"{API_V1}/queue/backtest/create-and-run",
                json={
                    "strategy_id": strategy_id,
                    "symbol": "BTCUSDT",
                    "timeframe": "60",
                    "start_date": "2024-01-01T00:00:00Z",
                    "end_date": "2024-01-31T00:00:00Z",
                    "initial_capital": 10000.0,
                    "leverage": 1,
                    "commission": 0.0006,
                    "config": {
                        "name": "Queue Integration Test",
                        "params": {"fast": 12, "slow": 26}
                    }
                }
            )
            
            if r.status_code == 200:
                result = r.json()
                backtest_id = result.get("backtest_id")
                task_id = result.get("task_id")
                logger.success(f"   ✅ Backtest submitted!")
                logger.info(f"   Backtest ID: {backtest_id}")
                logger.info(f"   Task ID: {task_id[:16]}...")
            else:
                logger.error(f"   ❌ Failed: {r.status_code}")
                logger.error(f"   Response: {r.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Submit failed: {e}")
            return False
        
        # 5. Подождать обработки
        logger.info("\n5️⃣  Waiting for worker to process (15 seconds)...")
        await asyncio.sleep(15)
        
        # 6. Проверить metrics после обработки
        logger.info("\n6️⃣  Checking metrics after processing...")
        try:
            r = await client.get(f"{API_V1}/queue/metrics")
            metrics = r.json()
            logger.info(f"   Tasks submitted: {metrics.get('tasks_submitted', 0)}")
            logger.info(f"   Tasks completed: {metrics.get('tasks_completed', 0)}")
            logger.info(f"   Tasks failed: {metrics.get('tasks_failed', 0)}")
            logger.info(f"   Active tasks: {metrics.get('active_tasks', 0)}")
            
            # Проверить прогресс
            submitted = metrics.get('tasks_submitted', 0)
            completed = metrics.get('tasks_completed', 0)
            
            if submitted > 0:
                progress = (completed / submitted) * 100
                logger.info(f"\n   Progress: {progress:.1f}%")
                
                if progress >= 80:
                    logger.success("\n✅ Workers are processing tasks!")
                else:
                    logger.warning("\n⚠️  Workers may not be running. Start workers:")
                    logger.warning("   python -m backend.queue.worker_cli --workers 2")
            
        except Exception as e:
            logger.error(f"❌ Metrics check failed: {e}")
        
        # 7. Проверить статус backtest
        logger.info("\n7️⃣  Checking backtest status...")
        try:
            r = await client.get(f"{API_V1}/backtests/{backtest_id}")
            if r.status_code == 200:
                backtest = r.json()
                status = backtest.get("status")
                logger.info(f"   Status: {status}")
                
                if status == "completed":
                    logger.success("   ✅ Backtest completed!")
                    logger.info(f"   Final capital: {backtest.get('final_capital', 'N/A')}")
                    logger.info(f"   Total return: {backtest.get('total_return', 'N/A')}")
                elif status == "queued":
                    logger.info("   ⏳ Backtest still in queue (workers not running?)")
                elif status == "running":
                    logger.info("   🔄 Backtest is being processed...")
                else:
                    logger.warning(f"   ⚠️  Unknown status: {status}")
            else:
                logger.error(f"   ❌ Failed to get backtest: {r.status_code}")
        except Exception as e:
            logger.error(f"❌ Backtest check failed: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.success("✅ Integration test completed!")
    logger.info("=" * 60)
    
    logger.info("\nℹ️  To process tasks, make sure workers are running:")
    logger.info("   python -m backend.queue.worker_cli --workers 2")
    
    return True


if __name__ == "__main__":
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    
    asyncio.run(test_full_integration())
