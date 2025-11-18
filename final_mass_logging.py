"""
Финальное массовое добавление логирования
Применяет inline паттерн ко всем Perplexity tools
"""
import re
from pathlib import Path


# Список всех Perplexity tools которым нужно логирование
TOOLS_TO_LOG = [
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
    "analyze_backtest_results",
    "compare_strategies",
    "risk_management_advice",
    "technical_indicator_research",
    "explain_metric",
    "market_regime_detection",
    "code_review_strategy",
    "generate_test_scenarios",
]


def add_logging_wrapper(content: str, tool_name: str) -> tuple[str, bool]:
    """
    Добавляет wrapper с логированием к функции tool
    
    Returns:
        (modified_content, success)
    """
    # Проверяем, есть ли уже логирование
    if f'log_mcp_execution' in content and f'"{tool_name}"' in content:
        return content, False  # Уже есть логирование
    
    # Паттерн: находим функцию от @mcp.tool() до result = await
    pattern = (
        rf'(@mcp\.tool\(\)\s+'
        rf'async def {tool_name}\([^)]*\)[^:]*:\s+'
        rf'""".*?"""\s*)'  # docstring
        rf'(.*?)'  # тело до API call
        rf'(\s+result = await (?:_call_perplexity_api|perplexity_cache\.query_perplexity)\([^)]+\))'
    )
    
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        return content, False
    
    start_pos = match.start()
    end_pos = match.end()
    
    # Компоненты функции
    decorator_and_doc = match.group(1)
    body_before_api = match.group(2)
    api_call_line = match.group(3)
    
    # Найдем конец функции (return или следующая функция)
    rest_start = end_pos
    next_func = content.find('\n@mcp.tool()', rest_start)
    next_func2 = content.find('\ndef ', rest_start)
    
    if next_func == -1:
        next_func = len(content)
    if next_func2 != -1 and next_func2 < next_func:
        next_func = next_func2
    
    rest_of_function = content[rest_start:next_func]
    
    # Отступы (обычно 4 пробела)
    indent = "    "
    
    # Форматируем тело функции с правильным отступом
    body_lines = body_before_api.split('\n')
    indented_body = '\n'.join(indent + line if line.strip() else line for line in body_lines)
    
    # Форматируем остаток функции
    rest_lines = rest_of_function.split('\n')
    indented_rest = '\n'.join(indent + line if line.strip() and not line.strip().startswith('return') else line for line in rest_lines)
    
    # API определение
    api_type = "Perplexity" if "perplexity" in tool_name.lower() else "Analysis"
    
    # Собираем новую функцию
    new_function = (
        f'{decorator_and_doc}'
        f'{indent}async with log_mcp_execution("{api_type}", "{tool_name}") as logger:\n'
        f'{indented_body}'
        f'{api_call_line}\n'
        f'{indent}    extract_metrics(result, logger)\n'
        f'{indented_rest}'
    )
    
    # Заменяем
    new_content = content[:start_pos] + new_function + content[next_func:]
    
    return new_content, True


def main():
    server_file = Path(__file__).parent / "mcp-server" / "server.py"
    
    print("=" * 80)
    print("🚀 ФИНАЛЬНОЕ МАССОВОЕ ДОБАВЛЕНИЕ ЛОГИРОВАНИЯ")
    print("=" * 80)
    print(f"\n📂 Файл: {server_file}")
    print(f"🎯 Tools для обработки: {len(TOOLS_TO_LOG)}\n")
    
    with open(server_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    modified = 0
    skipped = 0
    failed = 0
    
    for tool_name in TOOLS_TO_LOG:
        content, success = add_logging_wrapper(content, tool_name)
        
        if success:
            print(f"  ✅ {tool_name}")
            modified += 1
        elif f'log_mcp_execution' in content and f'"{tool_name}"' in content:
            print(f"  ⏭️  {tool_name} - уже имеет логирование")
            skipped += 1
        else:
            print(f"  ⚠️  {tool_name} - не удалось обработать")
            failed += 1
    
    if modified > 0:
        # Backup
        backup_file = server_file.with_suffix('.py.backup_final')
        with open(server_file, "r", encoding="utf-8") as f_orig:
            with open(backup_file, "w", encoding="utf-8") as f_backup:
                f_backup.write(f_orig.read())
        
        # Save
        with open(server_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"\n💾 Backup создан: {backup_file.name}")
        print(f"\n🎉 ГОТОВО!")
        print(f"  ✅ Добавлено: {modified}")
        print(f"  ⏭️  Пропущено: {skipped}")
        print(f"  ⚠️  Ошибки: {failed}")
        print(f"  📊 Всего обработано: {modified + skipped + failed}/{len(TOOLS_TO_LOG)}")
    else:
        print(f"\n✅ Все tools уже имеют логирование!")
        print(f"  ⏭️  Пропущено: {skipped}")
        print(f"  ⚠️  Не удалось: {failed}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
