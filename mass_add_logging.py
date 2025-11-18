"""
Массовое добавление inline логирования во все Perplexity MCP tools
Автоматическое применение паттерна с extract_metrics()
"""
import re
from pathlib import Path


def add_logging_to_remaining_tools():
    """Добавить логирование во все оставшиеся Perplexity tools"""
    
    server_file = Path(__file__).parent / "mcp-server" / "server.py"
    
    print(f"📂 Читаю файл: {server_file}")
    with open(server_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Список всех Perplexity tools для логирования
    tools_to_add = [
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
        "perplexity_compare_models",
    ]
    
    modified_count = 0
    already_has_logging = 0
    
    for tool_name in tools_to_add:
        # Проверяем, есть ли уже логирование
        if f'log_mcp_execution("Perplexity", "{tool_name}")' in content:
            print(f"  ⏭️  {tool_name} - уже имеет логирование")
            already_has_logging += 1
            continue
        
        # Ищем определение функции и вызов API
        # Паттерн 1: Простой вызов result = await _call_perplexity_api(...)
        pattern1 = (
            rf'(@mcp\.tool\(\)\s+'
            rf'async def {tool_name}\([^)]*\)[^:]*:\s+'
            rf'"""[^"]*"""\s*)'
            rf'(.*?)'
            rf'(\n\s+result = await _call_perplexity_api\([^)]+\))'
        )
        
        match = re.search(pattern1, content, re.DOTALL)
        
        if match:
            decorator_and_doc = match.group(1)
            body_before_api = match.group(2)
            api_call = match.group(3)
            
            # Найдем конец функции (следующий @mcp.tool или конец файла)
            func_start = match.start()
            func_body_start = match.end()
            
            # Найдем весь остаток функции
            next_decorator = content.find("\n@mcp.tool()", func_body_start)
            if next_decorator == -1:
                next_decorator = len(content)
            
            func_end = next_decorator
            rest_of_function = content[func_body_start:func_end]
            
            # Создаем новую версию с логированием
            new_function = (
                f'{decorator_and_doc}'
                f'    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:\n'
                f'{body_before_api}'
                f'{api_call}\n'
                f'        extract_metrics(result, logger)\n'
                f'{rest_of_function}'
            )
            
            content = content[:func_start] + new_function + content[func_end:]
            modified_count += 1
            print(f"  ✅ {tool_name} - добавлено логирование")
        else:
            print(f"  ⚠️  {tool_name} - паттерн не найден (возможно другая структура)")
    
    # Сохраняем изменения
    if modified_count > 0:
        # Создаем backup
        backup_file = server_file.with_suffix('.py.backup_mass_logging')
        with open(backup_file, "w", encoding="utf-8") as f:
            # Читаем оригинальный файл еще раз для backup
            with open(server_file, "r", encoding="utf-8") as orig:
                f.write(orig.read())
        
        print(f"\n💾 Создан backup: {backup_file}")
        
        # Сохраняем новую версию
        with open(server_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"\n🎉 Успешно добавлено логирование в {modified_count} tools!")
        print(f"⏭️  Уже имели логирование: {already_has_logging} tools")
        print(f"📝 Изменен файл: {server_file}")
        return modified_count
    else:
        print(f"\n⚠️  Ничего не изменено")
        print(f"⏭️  Уже имели логирование: {already_has_logging} tools")
        return 0


if __name__ == "__main__":
    print("=" * 80)
    print("🔧 МАССОВОЕ ДОБАВЛЕНИЕ ЛОГИРОВАНИЯ В MCP TOOLS")
    print("=" * 80)
    print()
    
    count = add_logging_to_remaining_tools()
    
    print()
    print("=" * 80)
    if count > 0:
        print(f"✅ Готово! Добавлено логирование в {count} tools")
    else:
        print("ℹ️  Все tools уже имеют логирование")
    print("=" * 80)
