"""
Автоматическое добавление логирования во все MCP tools
"""

import re
from pathlib import Path

# Список всех Perplexity функций
PERPLEXITY_TOOLS = [
    'perplexity_search', 'perplexity_search_streaming', 'perplexity_analyze_crypto',
    'perplexity_market_news', 'perplexity_sentiment_analysis', 'perplexity_market_scanner',
    'perplexity_strategy_research', 'perplexity_compare_models', 'perplexity_batch_analyze',
    'perplexity_correlation_analysis', 'perplexity_onchain_analysis', 'perplexity_defi_protocol_analysis',
    'perplexity_nft_collection_analysis', 'perplexity_exchange_analysis', 'perplexity_liquidity_analysis',
    'perplexity_funding_rate_arbitrage', 'perplexity_options_flow_analyzer', 'perplexity_whale_activity_tracker',
    'perplexity_social_sentiment_tracker', 'perplexity_news_impact_predictor', 'perplexity_seasonality_analyzer',
    'perplexity_portfolio_analyzer', 'perplexity_strategy_optimizer', 'perplexity_competitor_analysis',
    'perplexity_macro_economic_analysis', 'perplexity_token_unlock_calendar', 'perplexity_altcoin_season_indicator'
]

# Остальные функции - DeepSeek
DEEPSEEK_TOOLS = [
    'health_check', 'list_all_tools', 'get_project_structure', 'explain_project_architecture',
    'get_backtest_capabilities', 'get_supported_timeframes', 'get_testing_summary',
    'check_system_status', 'list_available_strategies', 'analyze_backtest_results',
    'explain_metric', 'market_regime_detection', 'risk_management_advice', 
    'technical_indicator_research', 'generate_test_scenarios', 'code_review_strategy',
    'compare_strategies', 'cache_clear', 'cache_stats', 'cache_config'
]

def wrap_function_body(func_body: str, indent: str = "    ") -> str:
    """Обернуть тело функции в async with"""
    lines = func_body.split('\n')
    wrapped = []
    
    for line in lines:
        if line.strip():
            # Добавить дополнительный отступ
            wrapped.append(indent + '    ' + line.lstrip())
        else:
            wrapped.append(line)
    
    return '\n'.join(wrapped)


def add_logging_to_function(func_code: str, func_name: str) -> str:
    """
    Добавить логирование в функцию MCP tool
    
    Args:
        func_code: Исходный код функции
        func_name: Имя функции
    
    Returns:
        Код функции с добавленным логированием
    """
    
    # Определить API
    if func_name in PERPLEXITY_TOOLS:
        api_name = "Perplexity"
    else:
        api_name = "DeepSeek"
    
    # Найти конец docstring
    lines = func_code.split('\n')
    docstring_end = 0
    in_docstring = False
    docstring_count = 0
    
    for i, line in enumerate(lines):
        if '"""' in line:
            docstring_count += line.count('"""')
            if docstring_count >= 2:
                docstring_end = i + 1
                break
    
    if docstring_end == 0:
        # Нет docstring, найти первую строку после def
        for i, line in enumerate(lines):
            if line.strip().startswith('def ') or line.strip().startswith('async def '):
                docstring_end = i + 1
                break
    
    # Разделить на части
    header_lines = lines[:docstring_end]
    body_lines = lines[docstring_end:]
    
    # Определить уровень отступа
    indent = "    "
    for line in body_lines:
        if line.strip() and not line.strip().startswith('#'):
            indent = line[:len(line) - len(line.lstrip())]
            break
    
    # Создать обёртку
    wrapper = f'{indent}async with log_mcp_execution("{api_name}", "{func_name}"):\n'
    
    # Обернуть тело функции
    wrapped_body = wrap_function_body('\n'.join(body_lines), indent)
    
    # Собрать полный код
    result = '\n'.join(header_lines) + '\n' + wrapper + wrapped_body
    
    return result


def process_file():
    """Обработать server.py"""
    server_path = Path(__file__).parent / "mcp-server" / "server.py"
    
    with open(server_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Найти все функции
    all_tools = PERPLEXITY_TOOLS + DEEPSEEK_TOOLS
    
    modified_content = content
    functions_updated = []
    
    for tool_name in all_tools:
        # Пропустить уже обработанные
        if tool_name in ['quick_reasoning_analysis', 'chain_of_thought_analysis']:
            continue
        
        # Найти функцию
        pattern = rf'(@mcp\.tool\(\)\s+async def {tool_name}\([^)]*\)[^:]*:.*?)(?=\n@mcp\.tool\(\)|\ndef main\(\):|\Z)'
        match = re.search(pattern, modified_content, re.DOTALL)
        
        if match:
            old_func = match.group(1)
            
            # Проверить есть ли уже log_mcp_execution
            if 'log_mcp_execution' in old_func:
                print(f"  ⏭️  {tool_name} - уже обработана")
                continue
            
            try:
                new_func = add_logging_to_function(old_func, tool_name)
                modified_content = modified_content.replace(old_func, new_func)
                functions_updated.append(tool_name)
                print(f"  ✅ {tool_name}")
            except Exception as e:
                print(f"  ❌ {tool_name}: {str(e)}")
    
    # Сохранить
    backup_path = server_path.with_suffix('.py.backup2')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    with open(server_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    print(f"\n✅ Обработано функций: {len(functions_updated)}")
    print(f"📦 Backup сохранён: {backup_path}")
    print(f"\nОбновлённые функции:")
    for func in functions_updated:
        print(f"  - {func}")


if __name__ == '__main__':
    print("🔧 Добавление логирования во все MCP tools...\n")
    process_file()
