"""
Автоматическое добавление inline логирования во все MCP tools
"""
import re
from pathlib import Path


def add_logging_to_tools():
    """Добавить логирование во все tools, которые его еще не имеют"""
    
    server_file = Path(__file__).parent / "mcp-server" / "server.py"
    
    with open(server_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Список tools для логирования (популярные Perplexity tools)
    tools_to_log = [
        "perplexity_strategy_research",
        "perplexity_market_news",
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
    ]
    
    modified_count = 0
    
    for tool_name in tools_to_log:
        # Паттерн для поиска функции tool
        pattern = rf'(@mcp\.tool\(\)\s+async def {tool_name}\([^)]+\)[^:]+:\s+"""[^"]*""")\s+([^@]+?)(\s+result = await _call_perplexity_api\([^)]+\))'
        
        # Проверяем, есть ли уже логирование
        if f'log_mcp_execution("Perplexity", "{tool_name}")' in content:
            print(f"  ⏭️  {tool_name} - уже имеет логирование")
            continue
        
        # Ищем функцию
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            # Заменяем на версию с логированием
            before = match.group(1)
            middle = match.group(2).strip()
            api_call = match.group(3).strip()
            
            # Создаем новую версию с логированием
            replacement = f'{before}\n    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:\n        {middle}\n        \n        {api_call}\n        extract_metrics(result, logger)  # ✨ Auto-logging\n        '
            
            content = content[:match.start()] + replacement + content[match.end():]
            modified_count += 1
            print(f"  ✅ {tool_name} - добавлено логирование")
        else:
            print(f"  ❌ {tool_name} - не найдена (возможно другой паттерн)")
    
    # Сохраняем изменения
    if modified_count > 0:
        with open(server_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"\n🎉 Успешно добавлено логирование в {modified_count} tools!")
        print(f"📝 Изменен файл: {server_file}")
    else:
        print("\n⚠️  Ничего не изменено")


if __name__ == "__main__":
    print("=" * 80)
    print("🔧 АВТОМАТИЧЕСКОЕ ДОБАВЛЕНИЕ ЛОГИРОВАНИЯ В MCP TOOLS")
    print("=" * 80)
    print()
    
    add_logging_to_tools()
