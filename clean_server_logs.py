"""
Удаляет поврежденные строки с неправильными эмодзи
"""

from pathlib import Path

server_path = Path(__file__).parent / "mcp-server" / "server.py"

with open(server_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Находим строки с поврежденным символом 📁 (который отображается как �)
new_lines = []
skip_lines = {6126, 6127, 6128, 6129}  # 0-indexed будет 6125-6128

for i, line in enumerate(lines, start=1):
    # Пропускаем поврежденные строки
    if i in skip_lines or ("� Project Management" in line or "� Analysis & Testing" in line or 
                           "� Research Tools" in line):
        print(f"Skipping line {i}: {line[:60]}...")
        continue
    new_lines.append(line)

# Записываем обратно
with open(server_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"\n✅ Cleaned {server_path}")
print(f"📝 Removed {len(lines) - len(new_lines)} corrupted lines")
