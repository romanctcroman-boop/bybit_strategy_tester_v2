"""
Массовое добавление логирования ко ВСЕМ оставшимся Perplexity tools
Цель: 100% coverage
"""
import re
from pathlib import Path

server_file = Path("mcp-server/server.py")

# Читаем файл
with open(server_file, "r", encoding="utf-8") as f:
    content = f.read()

# Tools которые УЖЕ имеют логирование (пропускаем)
TOOLS_WITH_LOGGING = {
    "perplexity_search_streaming",
    "perplexity_search",
    "perplexity_analyze_crypto",
    "perplexity_strategy_research",
    "perplexity_market_news",
    "perplexity_batch_analyze",
    "chain_of_thought_analysis",
    "quick_reasoning_analysis",
    "perplexity_onchain_analysis",
    "perplexity_sentiment_analysis",
    "perplexity_whale_activity_tracker",
    "perplexity_market_scanner",
    "perplexity_portfolio_analyzer",
}

print("=" * 80)
print("АВТОМАТИЧЕСКОЕ ДОБАВЛЕНИЕ ЛОГИРОВАНИЯ КО ВСЕМ PERPLEXITY TOOLS")
print("=" * 80)
print()

# Находим все Perplexity tools
pattern = r'@mcp\.tool\(\)\nasync def (perplexity_\w+)\('
all_perplexity_tools = re.findall(pattern, content)

print(f"Найдено Perplexity tools: {len(all_perplexity_tools)}")
print(f"Уже с логированием: {len(TOOLS_WITH_LOGGING)}")
print(f"Нужно обновить: {len(all_perplexity_tools) - len(TOOLS_WITH_LOGGING)}")
print()

updated_count = 0

# Обрабатываем каждый tool
for tool_name in all_perplexity_tools:
    if tool_name in TOOLS_WITH_LOGGING:
        continue
    
    # ПАТТЕРН 1: result = await _call_perplexity_api(...)\n\n    if result.get("success"):
    pattern1 = rf'(async def {tool_name}\([^)]*\)(?:[^:]*)?:[^\n]*\n(?:    """[^"]*?"""[^\n]*\n)?(?:(?:    [^\n]*\n)*?))(    result = await _call_perplexity_api\(([^)]+)\))\n\n(    if result\.get\("success"\):)'
    
    replacement1 = lambda m: (
        f'{m.group(1)}    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:\n'
        f'        result = await _call_perplexity_api({m.group(3)})\n'
        f'        extract_metrics(result, logger)\n\n'
        f'{m.group(4)}'
    )
    
    new_content = re.sub(pattern1, replacement1, content, count=1)
    
    if new_content != content:
        content = new_content
        updated_count += 1
        print(f"✅ {tool_name}")
        continue
    
    # ПАТТЕРН 2: return await _call_perplexity_api(...)
    pattern2 = rf'(async def {tool_name}\([^)]*\)(?:[^:]*)?:[^\n]*\n(?:    """[^"]*?"""[^\n]*\n)?(?:(?:    [^\n]*\n)*?))(    return await _call_perplexity_api\(([^)]+)\))'
    
    replacement2 = lambda m: (
        f'{m.group(1)}    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:\n'
        f'        result = await _call_perplexity_api({m.group(3)})\n'
        f'        extract_metrics(result, logger)\n'
        f'        return result'
    )
    
    new_content = re.sub(pattern2, replacement2, content, count=1)
    
    if new_content != content:
        content = new_content
        updated_count += 1
        print(f"✅ {tool_name}")
        continue
    
    # ПАТТЕРН 3: result = await perplexity_cache.query_perplexity(...)
    pattern3 = rf'(async def {tool_name}\([^)]*\)(?:[^:]*)?:[^\n]*\n(?:    """[^"]*?"""[^\n]*\n)?(?:(?:    [^\n]*\n)*?))(    result = await perplexity_cache\.query_perplexity\(([^)]+)\))\n\n(    if result\.get\("success"\):)'
    
    replacement3 = lambda m: (
        f'{m.group(1)}    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:\n'
        f'        result = await perplexity_cache.query_perplexity({m.group(3)})\n'
        f'        extract_metrics(result, logger)\n\n'
        f'{m.group(4)}'
    )
    
    new_content = re.sub(pattern3, replacement3, content, count=1)
    
    if new_content != content:
        content = new_content
        updated_count += 1
        print(f"✅ {tool_name} (cache)")
        continue
    
    print(f"⚠️  {tool_name} - паттерн не найден")

print()
print(f"Обновлено: {updated_count} tools")

if updated_count > 0:
    # Сохраняем
    with open(server_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    print()
    print("=" * 80)
    print("✅ ФАЙЛ ОБНОВЛЁН!")
    print(f"Новый coverage: {len(TOOLS_WITH_LOGGING) + updated_count}/{len(all_perplexity_tools)} Perplexity tools")
    print(f"Percentage: {((len(TOOLS_WITH_LOGGING) + updated_count) / len(all_perplexity_tools) * 100):.1f}%")
    print("=" * 80)
else:
    print()
    print("⚠️  Изменений не внесено")
