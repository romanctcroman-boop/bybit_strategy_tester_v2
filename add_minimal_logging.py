"""
Минимальное добавление логирования - только в начало и конец функции
БЕЗ изменения структуры кода
"""

import re
from pathlib import Path

# Функции которые уже имеют логирование
SKIP_FUNCTIONS = {
    'quick_reasoning_analysis',  # Уже есть async with
    'chain_of_thought_analysis',  # Уже есть async with  
    'perplexity_search',  # Уже есть async with
}

# Perplexity функции
PERPLEXITY_FUNCTIONS = {
    'perplexity_search_streaming', 'perplexity_analyze_crypto',
    'perplexity_market_news', 'perplexity_sentiment_analysis', 'perplexity_market_scanner',
    'perplexity_strategy_research', 'perplexity_compare_models', 'perplexity_batch_analyze',
    'perplexity_correlation_analysis', 'perplexity_onchain_analysis', 'perplexity_defi_protocol_analysis',
    'perplexity_nft_collection_analysis', 'perplexity_exchange_analysis', 'perplexity_liquidity_analysis',
    'perplexity_funding_rate_arbitrage', 'perplexity_options_flow_analyzer', 'perplexity_whale_activity_tracker',
    'perplexity_social_sentiment_tracker', 'perplexity_news_impact_predictor', 'perplexity_seasonality_analyzer',
    'perplexity_portfolio_analyzer', 'perplexity_strategy_optimizer', 'perplexity_competitor_analysis',
    'perplexity_macro_economic_analysis', 'perplexity_token_unlock_calendar', 'perplexity_altcoin_season_indicator'
}


def add_minimal_logging(content: str) -> tuple[str, int]:
    """
    Добавить минимальное логирование в начало и конец каждой функции
    
    Returns:
        (modified_content, count_modified)
    """
    
    lines = content.split('\n')
    modified = []
    i = 0
    count = 0
    
    while i < len(lines):
        line = lines[i]
        modified.append(line)
        
        # Найти @mcp.tool()
        if line.strip() == '@mcp.tool()':
            # Следующая строка должна быть async def
            if i + 1 < len(lines) and 'async def ' in lines[i + 1]:
                # Извлечь имя функции
                func_match = re.search(r'async def (\w+)\(', lines[i + 1])
                if func_match:
                    func_name = func_match.group(1)
                    
                    # Пропустить уже обработанные
                    if func_name in SKIP_FUNCTIONS:
                        i += 1
                        continue
                    
                    # Определить API
                    api = "Perplexity" if func_name in PERPLEXITY_FUNCTIONS else "DeepSeek"
                    
                    # Добавить строку def
                    i += 1
                    modified.append(lines[i])
                    
                    # Пропустить docstring
                    i += 1
                    while i < len(lines):
                        modified.append(lines[i])
                        if '"""' in lines[i] and lines[i].count('"""') >= 2:
                            # Однострочный docstring
                            break
                        elif '"""' in lines[i]:
                            # Начало многострочного
                            i += 1
                            while i < len(lines):
                                modified.append(lines[i])
                                if '"""' in lines[i]:
                                    break
                                i += 1
                            break
                        i += 1
                    
                    # Теперь добавить логирование ВНУТРЬ функции
                    # Найти первую непустую строку после docstring
                    i += 1
                    while i < len(lines) and not lines[i].strip():
                        modified.append(lines[i])
                        i += 1
                    
                    # Получить отступ первой строки кода
                    if i < len(lines) and lines[i].strip():
                        indent = len(lines[i]) - len(lines[i].lstrip())
                        indent_str = ' ' * indent
                        
                        # Вставить начальное логирование
                        modified.append(f'{indent_str}# MCP Monitor logging')
                        modified.append(f'{indent_str}import time')
                        modified.append(f'{indent_str}_start_time = time.time()')
                        modified.append(f'{indent_str}try:')
                        
                        # Добавить отступ ко всем оставшимся строкам функции
                        # Найти конец функции (следующий @mcp.tool() или def main())
                        func_lines = []
                        while i < len(lines):
                            if lines[i].strip().startswith('@mcp.tool()') or lines[i].strip().startswith('def main('):
                                break
                            if lines[i].strip():
                                # Добавить отступ
                                func_lines.append('    ' + lines[i])
                            else:
                                func_lines.append(lines[i])
                            i += 1
                        
                        # Найти все return в func_lines и добавить логирование перед ними
                        for fi, fline in enumerate(func_lines):
                            if 'return ' in fline:
                                # Добавить логирование перед return
                                return_indent = len(fline) - len(fline.lstrip())
                                log_lines = [
                                    ' ' * (return_indent - 4) + f'    try:',
                                    ' ' * (return_indent - 4) + f'        get_activity_logger().log_tool_call("{api}", "{func_name}", "SUCCESS", int((time.time() - _start_time) * 1000))',
                                    ' ' * (return_indent - 4) + f'    except: pass'
                                ]
                                func_lines[fi:fi] = log_lines
                                break
                        
                        modified.extend(func_lines)
                        
                        # Добавить except блок
                        modified.append(f'{indent_str}except Exception as e:')
                        modified.append(f'{indent_str}    try:')
                        modified.append(f'{indent_str}        get_activity_logger().log_tool_call("{api}", "{func_name}", "FAILED", int((time.time() - _start_time) * 1000), error=str(e))')
                        modified.append(f'{indent_str}    except: pass')
                        modified.append(f'{indent_str}    raise')
                        
                        count += 1
                        print(f"  ✅ {func_name} ({api})")
                        
                        # Уменьшить i чтобы не пропустить следующую функцию
                        i -= 1
        
        i += 1
    
    return '\n'.join(modified), count


def main():
    server_path = Path(__file__).parent / "mcp-server" / "server.py"
    
    print("📖 Чтение server.py...")
    with open(server_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n🔧 Добавление минимального логирования...")
    modified, count = add_minimal_logging(content)
    
    if count > 0:
        # Создать backup
        backup = server_path.with_suffix('.py.backup_minimal')
        with open(backup, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Сохранить
        with open(server_path, 'w', encoding='utf-8') as f:
            f.write(modified)
        
        print(f"\n✅ Обработано: {count} функций")
        print(f"💾 Backup: {backup}")
    else:
        print("\n⚠️ Нет функций для обработки")


if __name__ == '__main__':
    print("=" * 70)
    print("  Минимальное логирование MCP tools")
    print("=" * 70)
    print()
    main()
