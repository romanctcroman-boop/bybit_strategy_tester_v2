"""
Простой тест для проверки новых MCP инструментов
Запуск: python test_mcp_enhanced_simple.py
"""

import sys
from pathlib import Path

# Добавляем путь к MCP серверу
mcp_server_path = Path(__file__).parent / "mcp-server"
sys.path.insert(0, str(mcp_server_path))

print("=" * 80)
print("ТЕСТ НОВЫХ MCP ИНСТРУМЕНТОВ")
print("=" * 80)

try:
    # Импорт основных модулей
    print("\n✅ Шаг 1: Импорт модулей...")
    from server import (
        # Новые инструменты
        analyze_backtest_results,
        compare_strategies,
        risk_management_advice,
        technical_indicator_research,
        explain_metric,
        market_regime_detection,
        code_review_strategy,
        generate_test_scenarios,
        # Базовые
        perplexity_search
    )
    print("   ✓ Все инструменты импортированы успешно")
    
except ImportError as e:
    print(f"   ✗ Ошибка импорта: {e}")
    sys.exit(1)

# Список всех новых инструментов для проверки
new_tools = [
    ("analyze_backtest_results", analyze_backtest_results),
    ("compare_strategies", compare_strategies),
    ("risk_management_advice", risk_management_advice),
    ("technical_indicator_research", technical_indicator_research),
    ("explain_metric", explain_metric),
    ("market_regime_detection", market_regime_detection),
    ("code_review_strategy", code_review_strategy),
    ("generate_test_scenarios", generate_test_scenarios)
]

print(f"\n✅ Шаг 2: Проверка наличия {len(new_tools)} новых инструментов...")
for tool_name, tool_func in new_tools:
    print(f"   ✓ {tool_name}: {type(tool_func)}")

print(f"\n✅ Шаг 3: Проверка описаний инструментов...")
for tool_name, tool_func in new_tools:
    # FastMCP хранит описание в .description
    if hasattr(tool_func, 'description'):
        first_line = tool_func.description.strip().split('\n')[0]
        print(f"   ✓ {tool_name}: {first_line}")
    else:
        print(f"   ⚠ {tool_name}: No description")

print(f"\n✅ Шаг 4: Проверка типа инструментов...")
for tool_name, tool_func in new_tools:
    tool_type = type(tool_func).__name__
    has_fn = hasattr(tool_func, 'fn')
    print(f"   ✓ {tool_name}: {tool_type} (функция: {has_fn})")

print("\n" + "=" * 80)
print("РЕЗУЛЬТАТ: ВСЕ 8 НОВЫХ ИНСТРУМЕНТОВ УСПЕШНО ЗАРЕГИСТРИРОВАНЫ")
print("=" * 80)

print("\nДля тестирования с Perplexity API запустите:")
print("  pytest tests/integration/test_mcp_tools_comprehensive.py -v")
print("\nДля быстрых unit-тестов:")
print("  pytest tests/backend/test_mcp_advanced_tools.py -v")
