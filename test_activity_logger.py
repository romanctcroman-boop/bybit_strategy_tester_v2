#!/usr/bin/env python3
"""
Тест логирования MCP активности
"""

import sys
from pathlib import Path

# Добавить путь к модулю
mcp_server_path = Path(__file__).parent / "mcp-server"
sys.path.insert(0, str(mcp_server_path))

print(f"MCP Server path: {mcp_server_path}")
print(f"Path exists: {mcp_server_path.exists()}")

from activity_logger import get_activity_logger

def test_logging():
    logger = get_activity_logger()
    
    print("Testing activity logger...")
    print(f"Log file: {logger.activity_log}")
    
    # Тест 1: Простая запись
    logger.log_tool_call(
        api="Test",
        tool="test_manual",
        status="SUCCESS",
        duration_ms=100,
        tokens=50,
        cost=0.005
    )
    print("✅ Test 1: Manual log entry written")
    
    # Тест 2: Запись с ошибкой
    logger.log_tool_call(
        api="Test",
        tool="test_error",
        status="FAILED",
        duration_ms=50,
        error="Test error message"
    )
    print("✅ Test 2: Error log entry written")
    
    # Проверка файла
    if logger.activity_log.exists():
        with open(logger.activity_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"\n📊 Total log entries: {len(lines)}")
            if lines:
                print("\nLast entry:")
                print(lines[-1])
    else:
        print("❌ Log file not found!")

if __name__ == "__main__":
    test_logging()
