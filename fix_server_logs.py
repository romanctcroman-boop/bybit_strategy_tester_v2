"""
Исправляет количество tools в логах MCP server.py
"""

import sys
from pathlib import Path

server_path = Path(__file__).parent / "mcp-server" / "server.py"

# Читаем с правильной кодировкой
with open(server_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Заменяем старые строки на новые
old_block = '''    logger.info(f"\\n🔧 Available Tools: 🎉 65 total (FULL INTEGRATION: DEEPSEEK + PERPLEXITY + PROJECT)")
    logger.info(f"   ├─ 🚀 Perplexity AI Tools: 27 (market analysis, research, sentiment)")
    logger.info(f"   ├─ 🤖 DeepSeek Code Tools: 22 (generation, analysis, refactoring, testing)")'''

new_block = '''    logger.info(f"\\n🔧 Available Tools: 🎉 65 total (FULL MCP INTEGRATION)")
    logger.info(f"   ├─ 🚀 Perplexity AI: 28 tools (market, research, sentiment)")
    logger.info(f"   ├─ 🤖 DeepSeek Code: 14 tools (generation, analysis, refactoring)")'''

if old_block in content:
    content = content.replace(old_block, new_block)
    print("✅ Found and replaced block")
else:
    print("❌ Block not found, trying alternative...")
    # Альтернативный поиск - по первой строке
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "Available Tools: 🎉 65 total" in line:
            print(f"Found at line {i+1}: {line[:80]}")
            # Заменяем следующие 6 строк
            if i+6 < len(lines):
                lines[i] = '    logger.info(f"\\n🔧 Available Tools: 🎉 65 total (FULL MCP INTEGRATION)")'
                lines[i+1] = '    logger.info(f"   ├─ 🚀 Perplexity AI: 28 tools (market, research, sentiment)")'
                lines[i+2] = '    logger.info(f"   ├─ 🤖 DeepSeek Code: 14 tools (generation, analysis, refactoring)")'
                lines[i+3] = '    logger.info(f"   └─ 📁 Project/Test/Utility: 23 tools (structure, backtests, cache)")'
                # Удаляем строки 4-6 (старые записи)
                del lines[i+4:i+7]
                content = '\n'.join(lines)
                print("✅ Applied alternative replacement")
                break

# Записываем обратно
with open(server_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✅ Updated {server_path}")
print("\n📊 Tool counts updated to:")
print("  - Perplexity: 28")
print("  - DeepSeek: 14")
print("  - Other: 23")
print("  - TOTAL: 65")
