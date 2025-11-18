"""
Простой тест проверки логирования MCP
"""
import asyncio
import json
from pathlib import Path
import sys

# Добавить MCP server в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

from activity_logger import log_mcp_execution


async def test_logging_simple():
    """Тест базового логирования"""
    
    print("=" * 80)
    print("🧪 TESTING MCP ACTIVITY LOGGING")
    print("=" * 80)
    
    # Test 1: Простой лог без метрик
    print("\n1️⃣ Testing basic logging...")
    async with log_mcp_execution("TestAPI", "test_tool_1") as logger:
        await asyncio.sleep(0.1)  # Симуляция работы
        print("   ✅ Basic log executed")
    
    # Test 2: Лог с метриками
    print("\n2️⃣ Testing logging with metrics...")
    async with log_mcp_execution("Perplexity", "test_tool_2") as logger:
        logger.tokens = 500
        logger.cost = 0.001
        await asyncio.sleep(0.05)
        print("   ✅ Log with metrics executed")
    
    # Test 3: Лог с ошибкой
    print("\n3️⃣ Testing logging with error...")
    try:
        async with log_mcp_execution("TestAPI", "test_tool_3") as logger:
            await asyncio.sleep(0.02)
            raise ValueError("Test error")
    except ValueError:
        print("   ✅ Error log executed")
    
    print("\n" + "=" * 80)
    print("✅ TESTING COMPLETE")
    print("=" * 80)
    
    # Проверим файл логирования
    print("\n📂 Checking log file...")
    log_file = project_root / "logs" / "mcp_activity.jsonl"
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"\n   📝 Total log entries: {len(lines)}")
            
            if lines:
                print(f"\n   📌 Last {min(3, len(lines))} entries:")
                for i, line in enumerate(lines[-3:], 1):
                    entry = json.loads(line)
                    print(f"\n   Entry {i}:")
                    print(f"      - Time: {entry.get('timestamp')}")
                    print(f"      - API: {entry.get('api')}")
                    print(f"      - Tool: {entry.get('tool')}")
                    print(f"      - Status: {entry.get('status')}")
                    print(f"      - Duration: {entry.get('duration_ms')}ms")
                    print(f"      - Tokens: {entry.get('tokens')}")
                    print(f"      - Cost: ${entry.get('cost'):.6f}")
                    if entry.get('error'):
                        print(f"      - Error: {entry.get('error')}")
    else:
        print(f"   ⚠️ Log file not found: {log_file}")


if __name__ == "__main__":
    asyncio.run(test_logging_simple())
