"""
Финальный batch - добавление логирования к последним 13 tools
"""
from pathlib import Path

server_file = Path("mcp-server/server.py")

# Читаем файл
with open(server_file, "r", encoding="utf-8") as f:
    content = f.read()

# Оставшиеся 13 tools для обновления
REMAINING_TOOLS = [
    "perplexity_defi_protocol_analysis",
    "perplexity_nft_collection_analysis",
    "perplexity_macro_economic_analysis",
    "perplexity_exchange_analysis",
    "perplexity_token_unlock_calendar",
    "perplexity_altcoin_season_indicator",
    "perplexity_strategy_optimizer",
    "perplexity_news_impact_predictor",
    "perplexity_competitor_analysis",
    "perplexity_liquidity_analysis",
    "perplexity_seasonality_analyzer",
    "perplexity_social_sentiment_tracker",
    "perplexity_options_flow_analyzer",
    "perplexity_funding_rate_arbitrage",
    "perplexity_compare_models",
]

print("=" * 80)
print("BATCH ОБНОВЛЕНИЕ ПОСЛЕДНИХ 15 TOOLS")
print("=" * 80)
print()

updated = 0

for tool_name in REMAINING_TOOLS:
    # Простая замена: ищем "result = await" без async with
    # и заменяем на версию с логированием
    
    old_pattern = f'    result = await _call_perplexity_api(query, model="sonar-pro")\n    \n    if result.get("success"):'
    new_pattern = f'''    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:
        result = await _call_perplexity_api(query, model="sonar-pro")
        extract_metrics(result, logger)
    
    if result.get("success"):'''
    
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern, 1)
        updated += 1
        print(f"✅ {tool_name}")
        continue
    
    # Попробуем вариант с model="sonar"
    old_pattern2 = f'    result = await _call_perplexity_api(query, model="sonar")\n    \n    if result.get("success"):'
    new_pattern2 = f'''    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:
        result = await _call_perplexity_api(query, model="sonar")
        extract_metrics(result, logger)
    
    if result.get("success"):'''
    
    if old_pattern2 in content:
        content = content.replace(old_pattern2, new_pattern2, 1)
        updated += 1
        print(f"✅ {tool_name} (sonar)")
        continue
    
    # Попробуем без пустой строки
    old_pattern3 = f'    result = await _call_perplexity_api(query, model="sonar-pro")\n\n    if result.get("success"):'
    new_pattern3 = f'''    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:
        result = await _call_perplexity_api(query, model="sonar-pro")
        extract_metrics(result, logger)

    if result.get("success"):'''
    
    if old_pattern3 in content:
        content = content.replace(old_pattern3, new_pattern3, 1)
        updated += 1
        print(f"✅ {tool_name} (2 newlines)")
        continue
    
    # Вариант с return
    old_pattern4 = f'    return await _call_perplexity_api(query, model="sonar-pro")'
    new_pattern4 = f'''    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:
        result = await _call_perplexity_api(query, model="sonar-pro")
        extract_metrics(result, logger)
        return result'''
    
    if old_pattern4 in content:
        content = content.replace(old_pattern4, new_pattern4, 1)
        updated += 1
        print(f"✅ {tool_name} (return)")
        continue
    
    print(f"⚠️  {tool_name} - не найден")

print()
print(f"Обновлено: {updated}/{len(REMAINING_TOOLS)}")

if updated > 0:
    with open(server_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    print()
    print("=" * 80)
    print("✅ ФАЙЛ СОХРАНЁН!")
    print("=" * 80)
