"""
Quick Test Script для MCP Orchestrator
Проверяет все компоненты
"""

import asyncio
import httpx
from loguru import logger


async def test_orchestrator():
    """Тестирование MCP Orchestrator 2.0"""
    
    BASE_URL = "http://localhost:8765"
    
    logger.info("=" * 80)
    logger.info("🧪 TESTING MCP ORCHESTRATOR 2.0")
    logger.info("=" * 80)
    
    async with httpx.AsyncClient() as client:
        
        # Test 1: Health Check
        logger.info("\n📍 Test 1: Health Check")
        try:
            response = await client.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            logger.success(f"✅ Health check OK: {response.json()}")
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
        
        # Test 2: Run Task
        logger.info("\n📍 Test 2: Run Task")
        try:
            response = await client.post(
                f"{BASE_URL}/v1/run_task",
                json={
                    "tool": "DeepSeek",
                    "prompt": "Generate a simple trading strategy",
                    "priority": 10,
                    "context": {"language": "python"}
                }
            )
            assert response.status_code == 200
            result = response.json()
            logger.success(f"✅ Task created: {result['task_id']}")
            logger.info(f"   Queue: {result['queue']}")
            logger.info(f"   Status: {result['status']}")
        except Exception as e:
            logger.error(f"❌ Run task failed: {e}")
        
        # Test 3: Get Status
        logger.info("\n📍 Test 3: Get System Status")
        try:
            response = await client.get(f"{BASE_URL}/v1/status")
            assert response.status_code == 200
            result = response.json()
            logger.success(f"✅ System status: {result['system']['status']}")
            logger.info(f"   Version: {result['version']}")
            logger.info(f"   Queues: {list(result['system']['queues'].keys())}")
        except Exception as e:
            logger.error(f"❌ Get status failed: {e}")
        
        # Test 4: Get Analytics
        logger.info("\n📍 Test 4: Get Analytics")
        try:
            response = await client.get(f"{BASE_URL}/v1/analytics")
            assert response.status_code == 200
            result = response.json()
            logger.success(f"✅ Analytics retrieved")
            logger.info(f"   Workers: {result['current']['workers_total']}")
            logger.info(f"   Utilization: {result['current']['utilization_percent']}%")
        except Exception as e:
            logger.error(f"❌ Get analytics failed: {e}")
        
        # Test 5: Control - Scale Up
        logger.info("\n📍 Test 5: Control - Scale Workers")
        try:
            response = await client.post(
                f"{BASE_URL}/v1/control/scale",
                json={
                    "worker_type": "reasoning",
                    "action": "scale_up",
                    "count": 2
                }
            )
            assert response.status_code == 200
            result = response.json()
            logger.success(f"✅ Scaling: {result['message']}")
            logger.info(f"   Affected: {result['affected_resources']}")
        except Exception as e:
            logger.error(f"❌ Scale control failed: {e}")
        
        # Test 6: JSON-RPC Endpoint
        logger.info("\n📍 Test 6: JSON-RPC 2.0 Endpoint")
        try:
            response = await client.post(
                f"{BASE_URL}/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "run_task",
                    "params": {
                        "tool": "Perplexity",
                        "prompt": "Analyze BTC market",
                        "priority": 5
                    }
                }
            )
            assert response.status_code == 200
            result = response.json()
            logger.success(f"✅ JSON-RPC: {result['jsonrpc']}")
            logger.info(f"   Result: {result.get('result', {}).get('task_id', 'N/A')}")
        except Exception as e:
            logger.error(f"❌ JSON-RPC failed: {e}")
        
        # Test 7: Metrics
        logger.info("\n📍 Test 7: Prometheus Metrics")
        try:
            response = await client.get(f"{BASE_URL}/metrics")
            assert response.status_code == 200
            metrics_text = response.text
            logger.success(f"✅ Metrics exported ({len(metrics_text)} bytes)")
            # Показать первые несколько метрик
            lines = [line for line in metrics_text.split('\n') if line and not line.startswith('#')]
            for line in lines[:5]:
                logger.info(f"   {line}")
        except Exception as e:
            logger.error(f"❌ Metrics failed: {e}")
    
    logger.info("\n" + "=" * 80)
    logger.info("🎉 ALL TESTS COMPLETED")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_orchestrator())
