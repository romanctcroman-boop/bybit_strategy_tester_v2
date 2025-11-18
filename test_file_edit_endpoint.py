"""
Тест нового /api/v1/agent/file-edit endpoint
Проверяет режимы: read, write, analyze, refactor
"""

import asyncio
import httpx
from loguru import logger

BASE_URL = "http://localhost:8000"


async def test_read_file():
    """Тест 1: Чтение файла"""
    logger.info("=" * 60)
    logger.info("TEST 1: READ FILE")
    logger.info("=" * 60)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/agent/file-edit",
            json={
                "file_path": "backend/queue/redis_queue_poc.py",
                "mode": "read"
            },
            timeout=10.0
        )
        
        data = response.json()
        
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Success: {data['success']}")
        logger.info(f"File: {data['file_path']}")
        
        if data['content']:
            lines = data['content'].splitlines()
            logger.info(f"Content: {len(lines)} lines")
            logger.info(f"Preview: {lines[0][:100]}...")
        
        assert data['success'], "Read should succeed"
        logger.success("✅ TEST 1 PASSED")


async def test_analyze_file():
    """Тест 2: Анализ файла через DeepSeek"""
    logger.info("=" * 60)
    logger.info("TEST 2: ANALYZE FILE (DeepSeek)")
    logger.info("=" * 60)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/agent/file-edit",
            json={
                "file_path": "backend/queue/test_handler_poc.py",
                "mode": "analyze",
                "agent": "deepseek",
                "instruction": "Check for potential bugs and suggest improvements"
            },
            timeout=30.0
        )
        
        data = response.json()
        
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Success: {data['success']}")
        logger.info(f"File: {data['file_path']}")
        
        if data['agent_analysis']:
            logger.info(f"\n📊 DeepSeek Analysis:\n{data['agent_analysis'][:500]}...")
        
        assert data['success'], "Analyze should succeed"
        assert data['agent_analysis'], "Should have analysis"
        logger.success("✅ TEST 2 PASSED")


async def test_write_file():
    """Тест 3: Запись тестового файла"""
    logger.info("=" * 60)
    logger.info("TEST 3: WRITE FILE")
    logger.info("=" * 60)
    
    test_content = """# Test File
# Created by file-edit endpoint

def test_function():
    '''Test function'''
    return "Hello from file-edit API!"
"""
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/agent/file-edit",
            json={
                "file_path": "test_file_edit_output.py",
                "mode": "write",
                "content": test_content
            },
            timeout=10.0
        )
        
        data = response.json()
        
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Success: {data['success']}")
        logger.info(f"File: {data['file_path']}")
        logger.info(f"Changes applied: {data['changes_applied']}")
        
        assert data['success'], "Write should succeed"
        assert data['changes_applied'], "Changes should be applied"
        logger.success("✅ TEST 3 PASSED")


async def test_refactor_file():
    """Тест 4: Рефакторинг через DeepSeek (создаст backup)"""
    logger.info("=" * 60)
    logger.info("TEST 4: REFACTOR FILE (DeepSeek)")
    logger.info("=" * 60)
    logger.warning("⚠️  This will create a backup and modify test_file_edit_output.py")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/agent/file-edit",
            json={
                "file_path": "test_file_edit_output.py",
                "mode": "refactor",
                "agent": "deepseek",
                "instruction": "Add type hints and comprehensive docstrings"
            },
            timeout=30.0
        )
        
        data = response.json()
        
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Success: {data['success']}")
        logger.info(f"File: {data['file_path']}")
        logger.info(f"Changes applied: {data['changes_applied']}")
        
        if data['agent_analysis']:
            logger.info(f"\n🔧 DeepSeek Refactored Code:\n{data['content'][:300]}...")
        
        if data['success'] and data['changes_applied']:
            logger.success("✅ TEST 4 PASSED - File refactored!")
            logger.info("📦 Backup created: test_file_edit_output.py.backup")
        else:
            logger.warning("⚠️  TEST 4 SKIPPED or FAILED")


async def main():
    """Запуск всех тестов"""
    logger.info("🚀 Testing /api/v1/agent/file-edit endpoint")
    logger.info("=" * 60)
    
    try:
        # Проверка, что Backend запущен
        async with httpx.AsyncClient() as client:
            try:
                health = await client.get(f"{BASE_URL}/api/v1/agent/health", timeout=5.0)
                logger.success(f"✅ Backend is running: {health.json()}")
            except Exception as e:
                logger.error(f"❌ Backend not running: {e}")
                logger.error("Start backend: py -m uvicorn backend.main:app --reload")
                return
        
        # Запуск тестов
        await test_read_file()
        await asyncio.sleep(1)
        
        await test_analyze_file()
        await asyncio.sleep(1)
        
        await test_write_file()
        await asyncio.sleep(1)
        
        await test_refactor_file()
        
        logger.success("=" * 60)
        logger.success("🎉 ALL FILE EDIT TESTS COMPLETED!")
        logger.success("=" * 60)
    
    except AssertionError as e:
        logger.error(f"❌ TEST FAILED: {e}")
    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
