import re

# Читаем файл
with open('tests/test_storage_logic.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Убираем все category=category из вызовов get_klines
content = re.sub(r',\s*category=category\s*', '', content)

# Сохраняем
with open('tests/test_storage_logic.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Fixed all category parameters!")
