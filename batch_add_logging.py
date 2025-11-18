"""
Массовое добавление логирования к Perplexity tools (batch #1 - топ-10)
"""
from pathlib import Path
import re

server_file = Path("mcp-server/server.py")

# Читаем файл
with open(server_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Топ-10 приоритетных tools (после onchain_analysis который уже сделан)
PRIORITY_TOOLS = [
    "perplexity_sentiment_analysis",
    "perplexity_whale_activity_tracker",
    "perplexity_market_scanner",
    "perplexity_portfolio_analyzer",
    "perplexity_strategy_optimizer",
    "perplexity_correlation_analysis",
    "perplexity_defi_protocol_analysis",
    "perplexity_exchange_analysis",
    "perplexity_macro_economic_analysis",
    "perplexity_altcoin_season_indicator",
]

content = "".join(lines)

print("=" * 80)
print("BATCH #1: ADDING LOGGING TO TOP-10 PRIORITY TOOLS")
print("=" * 80)
print()

updated_count = 0

for tool_name in PRIORITY_TOOLS:
    print(f"Processing: {tool_name}...")
    
    # Простой паттерн: находим "result = await _call_perplexity_api(...)" без логирования
    # и заменяем на версию с логированием
    
    # Паттерн 1: result = await _call_perplexity_api(...)\n\n    if result
    pattern1 = rf'(async def {tool_name}\([^)]*\)[^:]*:\n(?:    """[^"]*"""\n)?)((?:    [^\n]*\n)*?)(    result = await _call_perplexity_api\(([^)]+)\))\n\n(    if result\.get\("success"\):)'
    
    match1 = re.search(pattern1, content, re.MULTILINE | re.DOTALL)
    
    if match1:
        # Стандартный случай с result и if
        before = match1.group(1) + match1.group(2)
        api_call_args = match1.group(4)
        after = match1.group(5)
        
        replacement = f'''{before}    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:
        result = await _call_perplexity_api({api_call_args})
        extract_metrics(result, logger)

{after}'''
        
        content = content.replace(match1.group(0), replacement)
        updated_count += 1
        print(f"  ✅ Updated (pattern 1)")
        continue
    
    # Паттерн 2: return await _call_perplexity_api(...)
    pattern2 = rf'(async def {tool_name}\([^)]*\)[^:]*:\n(?:    """[^"]*"""\n)?)((?:    [^\n]*\n)*?)(    return await _call_perplexity_api\(([^)]+)\))'
    
    match2 = re.search(pattern2, content, re.MULTILINE | re.DOTALL)
    
    if match2:
        # Прямой return
        before = match2.group(1) + match2.group(2)
        api_call_args = match2.group(4)
        
        replacement = f'''{before}    async with log_mcp_execution("Perplexity", "{tool_name}") as logger:
        result = await _call_perplexity_api({api_call_args})
        extract_metrics(result, logger)
        return result'''
        
        content = content.replace(match2.group(0), replacement)
        updated_count += 1
        print(f"  ✅ Updated (pattern 2)")
        continue
    
    print(f"  ⚠️  Pattern not found")

print()
print(f"Updated: {updated_count}/{len(PRIORITY_TOOLS)}")

# Сохраняем
if updated_count > 0:
    with open(server_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    print()
    print("=" * 80)
    print("✅ FILE UPDATED!")
    print("=" * 80)
else:
    print()
    print("⚠️  No changes made")
