"""
Автоматическое добавление логирования к Perplexity tools
"""
import re
from pathlib import Path

# Путь к server.py
server_file = Path("mcp-server/server.py")

# Tools для обновления
TOOLS_TO_UPDATE = [
    "perplexity_onchain_analysis",
    "perplexity_sentiment_analysis",
    "perplexity_correlation_analysis",
    "perplexity_defi_protocol_analysis",
    "perplexity_nft_collection_analysis",
    "perplexity_macro_economic_analysis",
    "perplexity_exchange_analysis",
    "perplexity_token_unlock_calendar",
    "perplexity_whale_activity_tracker",
    "perplexity_altcoin_season_indicator",
    "perplexity_strategy_optimizer",
    "perplexity_market_scanner",
    "perplexity_portfolio_analyzer",
    "perplexity_news_impact_predictor",
    "perplexity_competitor_analysis",
    "perplexity_liquidity_analysis",
    "perplexity_seasonality_analyzer",
    "perplexity_social_sentiment_tracker",
    "perplexity_options_flow_analyzer",
    "perplexity_funding_rate_arbitrage",
    "perplexity_compare_models",
]

# Читаем файл
with open(server_file, "r", encoding="utf-8") as f:
    content = f.read()

print("=" * 80)
print("ДОБАВЛЕНИЕ ЛОГИРОВАНИЯ К 21 PERPLEXITY TOOLS")
print("=" * 80)
print()

updated_count = 0

for tool_name in TOOLS_TO_UPDATE:
    # Паттерн для поиска функции tool
    # Ищем: @mcp.tool()\nasync def TOOLNAME(...):
    #       """..."""
    #       result = await _call_perplexity_api(...)
    #       return result
    
    pattern = rf'(@mcp\.tool\(\)\nasync def {tool_name}\([^)]*\)[^:]*:\n    """[^"]*""")\n((?:    [^\n]*\n)*?)(    result = await _call_perplexity_api\([^)]+\))\n((?:    [^\n]*\n)*?)(    return result)'
    
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    
    if match:
        # Заменяем на версию с логированием
        original = match.group(0)
        
        # Извлекаем компоненты
        decorator_and_def = match.group(1)
        before_call = match.group(2)
        api_call = match.group(3)
        after_call = match.group(4)
        return_statement = match.group(5)
        
        # Создаём новую версию с логированием
        replacement = f'''{decorator_and_def}
    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:
{before_call}{api_call}
        extract_metrics(result, logger)
{after_call}{return_statement}'''
        
        content = content.replace(original, replacement)
        updated_count += 1
        print(f"✅ Обновлён: {tool_name}")
    else:
        print(f"⚠️  Не найден паттерн для: {tool_name}")

print()
print(f"Обновлено tools: {updated_count}/21")

# Сохраняем обновлённый файл
with open(server_file, "w", encoding="utf-8") as f:
    f.write(content)

print()
print("=" * 80)
print("✅ ФАЙЛ ОБНОВЛЁН!")
print("=" * 80)
