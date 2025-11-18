"""
Скрипт для обновления всех DeepSeek tools в server.py
Заменяет создание нового agent на использование глобального
"""

import re
from pathlib import Path

server_file = Path("mcp-server/server.py")

# Читаем файл
content = server_file.read_text(encoding='utf-8')

# Паттерн для замены:
# from agents.deepseek import DeepSeekAgent
# agent = DeepSeekAgent()
# 
# Заменяем на:
# agent = get_deepseek_agent()
# if agent is None:
#     from agents.deepseek import DeepSeekAgent
#     agent = DeepSeekAgent()

# Паттерн 1: Полный импорт и создание
pattern1 = r'''(\s+)try:\s+from agents\.deepseek import DeepSeekAgent.*?\s+agent = DeepSeekAgent\(\)'''

replacement1 = r'''\1try:
\1    # Use global DeepSeek Agent (auto-initialized in Phase 0.5)
\1    agent = get_deepseek_agent()
\1    if agent is None:
\1        from agents.deepseek import DeepSeekAgent
\1        agent = DeepSeekAgent()'''

# Применяем замену
new_content = re.sub(pattern1, replacement1, content, flags=re.DOTALL)

# Считаем замены
replacements = len(re.findall(pattern1, content, flags=re.DOTALL))

# Сохраняем
server_file.write_text(new_content, encoding='utf-8')

print(f"✓ Обновлено {replacements} DeepSeek tools")
print(f"✓ Все tools теперь используют глобальный DeepSeek Agent")
print(f"✓ Файл сохранен: {server_file}")
