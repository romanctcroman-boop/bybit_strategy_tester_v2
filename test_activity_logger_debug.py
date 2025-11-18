"""
Прямой тест activity_logger
"""

import sys
from pathlib import Path

# Добавить путь к mcp-server
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from activity_logger import get_activity_logger, log_mcp_execution
import asyncio
import time


async def test_context_manager():
    """Тест контекстного менеджера"""
    print("🧪 Тест контекстного менеджера log_mcp_execution...")
    
    try:
        async with log_mcp_execution("TestAPI", "test_function") as logger:
            print(f"  ✅ Контекстный менеджер вошёл")
            await asyncio.sleep(0.1)
            print(f"  ✅ Работа завершена")
        print(f"  ✅ Контекстный менеджер вышел")
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


def test_direct_logging():
    """Тест прямого логирования"""
    print("\n🧪 Тест прямого логирования...")
    
    try:
        logger = get_activity_logger()
        print(f"  ✅ Logger получен: {logger}")
        print(f"  📁 Log файл: {logger.activity_log}")
        
        logger.log_tool_call(
            api="DirectTest",
            tool="test_direct",
            status="SUCCESS",
            duration_ms=100
        )
        print(f"  ✅ Запись добавлена")
        
        # Проверить файл
        if logger.activity_log.exists():
            content = logger.activity_log.read_text()
            print(f"  📊 Размер файла: {len(content)} байт")
            if content:
                print(f"  ✅ Файл содержит данные")
                print(f"\n  Содержимое:\n{content}")
            else:
                print(f"  ⚠️  Файл пуст")
        else:
            print(f"  ❌ Файл не существует")
            
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("=" * 70)
    print("  MCP Activity Logger - Диагностический тест")
    print("=" * 70)
    print()
    
    test_direct_logging()
    
    print()
    asyncio.run(test_context_manager())
    
    print()
    print("✅ Тесты завершены")
