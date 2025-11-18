"""
Автоматический инжектор логирования во все MCP tools
Использует простой подход с минимальными изменениями
"""

import re
from pathlib import Path


# Определить API для каждой функции
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


def inject_logging_simple(func_text: str, func_name: str, api: str) -> str:
    """
    Простой инжектор - находит первый return и оборачивает весь код
    """
    lines = func_text.split('\n')
    
    # Найти конец docstring и начало тела функции
    docstring_end = 0
    in_docstring = False
    triple_quote_count = 0
    
    for i, line in enumerate(lines):
        if '"""' in line:
            triple_quote_count += 1
            if triple_quote_count == 2:
                docstring_end = i + 1
                break
    
    # Если нет docstring
    if docstring_end == 0:
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith('#'):
                if 'def ' in line:
                    docstring_end = i + 1
                    break
    
    # Разделить
    header = '\n'.join(lines[:docstring_end])
    body = '\n'.join(lines[docstring_end:])
    
    # Определить базовый отступ
    indent = '    '
    for line in lines[docstring_end:]:
        if line.strip() and not line.strip().startswith('#'):
            indent = line[:len(line) - len(line.lstrip())]
            break
    
    # Добавить отступ ко всем строкам тела
    body_lines = body.split('\n')
    indented_body = []
    for line in body_lines:
        if line.strip():
            indented_body.append(indent + '    ' + line.lstrip())
        else:
            indented_body.append(line)
    
    # Создать новую функцию
    new_function = f'''{header}
{indent}async with log_mcp_execution("{api}", "{func_name}"):
{chr(10).join(indented_body)}'''
    
    return new_function


def process_all_functions():
    """Обработать все функции в server.py"""
    server_path = Path(__file__).parent / "mcp-server" / "server.py"
    
    print(f"📖 Чтение {server_path}...")
    with open(server_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Создать backup
    backup_path = server_path.with_suffix('.py.backup_before_logging')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"💾 Backup создан: {backup_path}")
    
    # Найти все MCP tools
    pattern = r'@mcp\.tool\(\)\s+async def (\w+)\('
    matches = re.finditer(pattern, content)
    
    already_has_logging = set()
    needs_logging = []
    
    for match in matches:
        func_name = match.group(1)
        
        # Проверить есть ли уже логирование
        # Найти тело функции
        func_start = match.start()
        # Найти следующую @mcp.tool() или конец файла
        next_tool = content.find('\n@mcp.tool()', func_start + 1)
        if next_tool == -1:
            next_tool = content.find('\ndef main():', func_start + 1)
        if next_tool == -1:
            next_tool = len(content)
        
        func_body = content[func_start:next_tool]
        
        if 'log_mcp_execution' in func_body or '@log_mcp_call' in func_body:
            already_has_logging.add(func_name)
        else:
            needs_logging.append((func_name, func_start, next_tool))
    
    print(f"\n📊 Статус функций:")
    print(f"  ✅ Уже с логированием: {len(already_has_logging)}")
    print(f"  ⚠️  Нужно добавить: {len(needs_logging)}")
    
    if not needs_logging:
        print("\n✅ Все функции уже имеют логирование!")
        return
    
    print(f"\n🔧 Добавляю логирование в {len(needs_logging)} функций...")
    
    # Обработать с конца чтобы не сбивать индексы
    modified_content = content
    processed = 0
    
    for func_name, start, end in reversed(needs_logging):
        # Извлечь полную функцию
        full_func = content[start:end]
        
        # Определить API
        api = "Perplexity" if func_name in PERPLEXITY_FUNCTIONS else "DeepSeek"
        
        try:
            # Применить инжектор
            new_func = inject_logging_simple(full_func, func_name, api)
            
            # Заменить в контенте
            modified_content = modified_content[:start] + new_func + modified_content[end:]
            
            print(f"  ✅ {func_name} ({api})")
            processed += 1
            
        except Exception as e:
            print(f"  ❌ {func_name}: {str(e)}")
    
    # Сохранить
    with open(server_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    print(f"\n✅ Обработано: {processed}/{len(needs_logging)} функций")
    print(f"📝 Изменения сохранены в {server_path}")
    print(f"💾 Backup доступен: {backup_path}")
    
    print(f"\n📋 Функции с логированием:")
    for func_name in sorted(already_has_logging):
        print(f"  ✓ {func_name}")


if __name__ == '__main__':
    print("=" * 70)
    print("  MCP MONITOR - Автоматический инжектор логирования")
    print("=" * 70)
    print()
    
    process_all_functions()
    
    print()
    print("🎉 Готово! Теперь перезапустите MCP сервер для применения изменений.")
