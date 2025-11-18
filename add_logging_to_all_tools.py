"""
Скрипт для автоматического добавления логирования во все MCP tools
"""

import re
from pathlib import Path

def add_logging_to_tool(func_code: str, func_name: str, api_name: str) -> str:
    """
    Добавить inline логирование в функцию MCP tool
    
    Args:
        func_code: Исходный код функции
        func_name: Имя функции
        api_name: Имя API (DeepSeek/Perplexity)
    
    Returns:
        Код функции с добавленным логированием
    """
    
    # Определить является ли функция async
    is_async = func_code.strip().startswith('async def')
    
    # Найти начало тела функции (после docstring)
    lines = func_code.split('\n')
    
    # Найти конец docstring
    in_docstring = False
    docstring_end = 0
    for i, line in enumerate(lines):
        if '"""' in line:
            if not in_docstring:
                in_docstring = True
            else:
                docstring_end = i + 1
                break
    
    # Разделить на части
    header = '\n'.join(lines[:docstring_end])
    body_lines = lines[docstring_end:]
    
    # Найти уровень отступа
    indent = '    '
    for line in body_lines:
        if line.strip() and not line.strip().startswith('#'):
            indent = line[:len(line) - len(line.lstrip())]
            break
    
    # Подготовить код логирования
    logging_setup = f"""{indent}import time
{indent}start_time = time.time()
{indent}
{indent}try:"""
    
    # Изменить отступ существующего кода
    body_with_indent = []
    for line in body_lines:
        if line.strip():
            body_with_indent.append(indent + '    ' + line.lstrip())
        else:
            body_with_indent.append(line)
    
    # Найти последний return
    last_return_idx = -1
    for i in range(len(body_with_indent) - 1, -1, -1):
        if 'return' in body_with_indent[i]:
            last_return_idx = i
            break
    
    # Добавить логирование успеха перед return
    if last_return_idx > 0:
        return_line = body_with_indent[last_return_idx]
        result_var = 'result'
        
        # Извлечь возвращаемое значение
        return_match = re.search(r'return\s+(.+)', return_line.strip())
        if return_match:
            result_var = return_match.group(1).strip()
        
        success_log = f"""
{indent}    # Логирование успешного вызова
{indent}    duration_ms = int((time.time() - start_time) * 1000)
{indent}    try:
{indent}        from activity_logger import get_activity_logger
{indent}        get_activity_logger().log_tool_call(
{indent}            api="{api_name}",
{indent}            tool="{func_name}",
{indent}            status="SUCCESS",
{indent}            duration_ms=duration_ms
{indent}        )
{indent}    except Exception as log_error:
{indent}        pass  # Не падать если логирование не работает
"""
        
        body_with_indent.insert(last_return_idx, success_log)
    
    # Добавить except блок
    except_block = f"""
{indent}except Exception as e:
{indent}    # Логирование ошибки
{indent}    duration_ms = int((time.time() - start_time) * 1000)
{indent}    try:
{indent}        from activity_logger import get_activity_logger
{indent}        get_activity_logger().log_tool_call(
{indent}            api="{api_name}",
{indent}            tool="{func_name}",
{indent}            status="FAILED",
{indent}            duration_ms=duration_ms,
{indent}            error=str(e)
{indent}        )
{indent}    except Exception as log_error:
{indent}        pass  # Не падать если логирование не работает
{indent}    raise
"""
    
    # Собрать полный код
    result = header + '\n' + logging_setup + '\n' + '\n'.join(body_with_indent) + except_block
    
    return result


def process_server_file():
    """
    Обработать server.py и добавить логирование во все tools
    """
    server_path = Path(__file__).parent / "mcp-server" / "server.py"
    
    with open(server_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Найти все функции с @mcp.tool()
    pattern = r'@mcp\.tool\(\)\s+(async\s+)?def\s+(\w+)\s*\([^)]*\)\s*->\s*[^:]+:\s*"""[^"]+"""[^}]*?(?=\n@mcp\.tool\(\)|\ndef main\(\):|\Z)'
    
    matches = list(re.finditer(pattern, content, re.DOTALL))
    
    print(f"Найдено {len(matches)} функций с @mcp.tool()")
    
    # Определить API для каждой функции
    perplexity_tools = [
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
    
    for match in matches:
        func_name = match.group(2)
        api_name = "Perplexity" if func_name in perplexity_tools else "DeepSeek"
        
        print(f"  - {func_name} ({api_name})")
    
    print("\nПримечание: Для полной реализации используйте ручное редактирование")
    print("Этот скрипт показывает список функций для обработки")


if __name__ == '__main__':
    process_server_file()
