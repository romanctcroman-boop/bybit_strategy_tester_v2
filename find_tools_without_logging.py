"""
Автоматическое добавление логирования ко всем Perplexity tools
"""
import re
from pathlib import Path

# Путь к server.py
server_file = Path("mcp-server/server.py")

# Читаем файл
with open(server_file, "r", encoding="utf-8") as f:
    content = f.read()

# Tools которые УЖЕ имеют логирование (пропускаем их)
TOOLS_WITH_LOGGING = {
    "perplexity_search_streaming",
    "perplexity_search",
    "perplexity_analyze_crypto",
    "perplexity_strategy_research",
    "perplexity_market_news",
    "perplexity_batch_analyze",
    "chain_of_thought_analysis",
    "quick_reasoning_analysis",
}

# Паттерн для поиска Perplexity tools
tool_pattern = r'@mcp\.tool\(\)\nasync def (perplexity_\w+)\([^)]*\)[^:]*:\n    """'

# Найти все Perplexity tools
matches = list(re.finditer(tool_pattern, content))

print(f"Найдено Perplexity tools: {len(matches)}")
print()

tools_to_update = []

for match in matches:
    tool_name = match.group(1)
    
    # Пропустить tools с уже существующим логированием
    if tool_name in TOOLS_WITH_LOGGING:
        print(f"⏭️  Пропуск {tool_name} (уже есть логирование)")
        continue
    
    tools_to_update.append((tool_name, match))
    print(f"➕ Добавим логирование: {tool_name}")

print()
print(f"Всего tools для обновления: {len(tools_to_update)}")
print()

# Выводим список для ручного добавления
print("=" * 80)
print("СПИСОК TOOLS БЕЗ ЛОГИРОВАНИЯ:")
print("=" * 80)
for tool_name, _ in tools_to_update:
    print(f"  - {tool_name}")

print()
print("=" * 80)
print("Для добавления логирования нужно обернуть код каждого tool в:")
print("=" * 80)
print("""
async with log_mcp_execution("Perplexity", "TOOL_NAME") as logger:
    result = await _call_perplexity_api(...)
    extract_metrics(result, logger)
    return result
""")
