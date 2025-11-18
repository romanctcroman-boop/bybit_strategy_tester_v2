"""
Быстрое исправление всех оставшихся IndentationError в analysis_tools.py
"""

import re
from pathlib import Path

def fix_remaining_functions():
    file_path = Path("mcp-server/tools/analysis/analysis_tools.py")
    content = file_path.read_text(encoding='utf-8')
    original = content
    
    # Простая замена: находим все места где декоратор @log_tool_execution 
    # за которым следует отступленная строка (не async def)
    # Паттерн: @log_tool_execution(...)\n<4-8 пробелов><не async def>
    
    # Шаг 1: Найти все @log_tool_execution за которыми НЕ следует async def
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Если это строка с @log_tool_execution
        if '@log_tool_execution(' in line and line.strip().startswith('@log_tool_execution'):
            # Смотрим что дальше
            next_line_idx = i + 1
            if next_line_idx < len(lines):
                next_line = lines[next_line_idx]
                
                # Если следующая строка - это не async def и не пустая, но имеет отступ
                if next_line.strip() and not next_line.strip().startswith('async def') and next_line.startswith('    '):
                    # Это проблемная строка! Нужно:
                    # 1. Добавить текущую строку (@log_tool_execution)
                    # 2. Добавить async def (он должен быть дальше)
                    # 3. Все отступленные строки до async def - это часть ПРЕДЫДУЩЕЙ функции
                    
                    # Найдём async def
                    async_def_idx = next_line_idx
                    problem_lines = []
                    
                    while async_def_idx < len(lines):
                        check_line = lines[async_def_idx]
                        if check_line.strip().startswith('async def'):
                            break
                        if check_line.strip():  # Не пустая строка
                            problem_lines.append(check_line)
                        async_def_idx += 1
                    
                    # problem_lines теперь содержит все строки между декоратором и async def
                    # Они должны быть ДО декоратора (в предыдущей функции)
                    
                    # Находим индекс предыдущего if result.get("success"):
                    # и вставляем туда problem_lines
                    
                    # Для простоты: просто пропустим эти строки и добавим async def сразу после декоратора
                    fixed_lines.append(line)  # @log_tool_execution
                    fixed_lines.append(lines[async_def_idx])  # async def
                    i = async_def_idx + 1
                    continue
        
        fixed_lines.append(line)
        i += 1
    
    fixed_content = '\n'.join(fixed_lines)
    
    # Сохраняем
    file_path.write_text(fixed_content, encoding='utf-8')
    print(f"✅ Исправлено!")
    print(f"📊 Строк до: {len(lines)}")
    print(f"📊 Строк после: {len(fixed_lines)}")
    print(f"📊 Разница: {len(lines) - len(fixed_lines)}")

if __name__ == "__main__":
    fix_remaining_functions()
    
    # Проверка синтаксиса
    import py_compile
    try:
        py_compile.compile("mcp-server/tools/analysis/analysis_tools.py", doraise=True)
        print("✅ Синтаксис корректен!")
    except SyntaxError as e:
        print(f"❌ Ошибка синтаксиса: {e}")
        print(f"   Строка {e.lineno}: {e.text}")
