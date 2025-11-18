"""
Автоматическое исправление отступов в analysis_tools.py
"""

import re

file_path = "d:/bybit_strategy_tester_v2/mcp-server/tools/analysis/analysis_tools.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Паттерн: находим места где декораторы @cached и @log_tool_execution идут после кода функции
# Это неправильно - они должны быть ПЕРЕД функцией

# Паттерн 1: return result + декораторы на следующих строках
pattern1 = r'(\n@cached\([^\)]+\)\n@log_tool_execution\([^\)]+\)\n)(    return result)'
replacement1 = r'\2\n\n\1'

content_fixed = re.sub(pattern1, replacement1, content)

# Паттерн 2: Убираем пустые строки после return и перед async def
pattern2 = r'(    return result)\n\n\n\n(async def )'
replacement2 = r'\1\n\n\n\2'

content_fixed = re.sub(pattern2, replacement2, content_fixed)

# Паттерн 3: Декораторы посреди функции (самая сложная проблема)
# Находим: строка кода + декораторы + return
pattern3 = r'(        result\[[^\]]+\] = [^\n]+)\n(@cached\([^\)]+\)\n@log_tool_execution\([^\)]+\)\n)(        result\[[^\]]+\] = )'
replacement3 = r'\1\n\3'

content_fixed = re.sub(pattern3, replacement3, content_fixed)

# Паттерн 4: return result с неправильным отступом после декораторов
pattern4 = r'(@cached\([^\)]+\)\n@log_tool_execution\([^\)]+\)\n)(    return result)'
replacement4 = r'\2\n\n\1'

content_fixed = re.sub(pattern4, replacement4, content_fixed)

# Запишем исправленный файл
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content_fixed)

print("✅ Файл исправлен!")
print(f"Найдено и исправлено проблем")
