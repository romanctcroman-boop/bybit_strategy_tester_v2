"""
Автоматическое исправление IndentationError в analysis_tools.py

Проблема: 21 функция имеет неправильное размещение декораторов:
    result["field"] = value
@cached(...)
@log_tool_execution(...)
    return result    # ← НЕПРАВИЛЬНЫЙ отступ (8 пробелов)

async def function_name():

Правильно должно быть:
    result["field"] = value
    
    return result    # ← ПРАВИЛЬНЫЙ отступ (4 пробела)


@cached(...)
@log_tool_execution(...)
async def function_name():
"""

import re
from pathlib import Path

def fix_analysis_tools():
    file_path = Path("mcp-server/tools/analysis/analysis_tools.py")
    
    if not file_path.exists():
        print(f"❌ Файл не найден: {file_path}")
        return False
    
    # Читаем файл
    content = file_path.read_text(encoding='utf-8')
    original_content = content
    
    # Паттерн для поиска проблемных мест:
    # Реальная проблема:
    # result["analysis_type"] = "..."
    # <пустая строка БЕЗ отступа>
    # @cached(...) <-- БЕЗ отступа
    # @log_tool_execution(...) <-- БЕЗ отступа
    #     return result <-- С отступом (НЕПРАВИЛЬНО!)
    # <4 пустых строки>
    # async def function_name
    
    pattern = re.compile(
        r'(    result\["analysis_type"\] = "[^"]+"\n)'  # result["analysis_type"] = "value"
        r'    \n'                                        # пустая строка С отступом
        r'(@cached\(get_cache\("perplexity_cache"\), ttl=\d+\)\n)'  # @cached БЕЗ отступа
        r'(@log_tool_execution\("[^"]+", logger\)\n)'   # @log_tool_execution БЕЗ отступа
        r'(    return result\n)'                        # return result С отступом (НЕПРАВИЛЬНО!)
        r'\n\n\n\n'                                     # 4 пустых строки
        r'(async def )',                                # async def
        re.MULTILINE
    )
    
    # Замена: правильные отступы
    def replacement(match):
        result_line = match.group(1)       # result["field"] = "value"
        cached_decorator = match.group(2)   # @cached
        log_decorator = match.group(3)      # @log_tool_execution
        async_def = match.group(5)         # async def
        
        # Возвращаем правильную структуру:
        # 1. result["field"] = "value"
        # 2. пустая строка
        # 3. return result (правильный отступ)
        # 4. две пустые строки
        # 5. @cached декоратор
        # 6. @log_tool_execution декоратор
        # 7. async def
        return (
            f"{result_line}"               # result["field"] = "value"
            f"    \n"                      # пустая строка
            f"    return result\n"         # ПРАВИЛЬНЫЙ return (4 пробела)
            f"\n"                          # пустая строка
            f"\n"                          # ещё одна пустая строка
            f"{cached_decorator}"          # @cached
            f"{log_decorator}"             # @log_tool_execution
            f"{async_def}"                 # async def
        )
    
    # Применяем замену
    fixed_content = pattern.sub(replacement, content)
    
    # Подсчитываем количество замен
    fixes_count = len(pattern.findall(content))
    
    if fixes_count == 0:
        print("⚠️ Не найдено проблемных паттернов")
        return False
    
    if fixed_content == original_content:
        print("⚠️ Контент не изменился после применения паттерна")
        return False
    
    # Сохраняем исправленный файл
    file_path.write_text(fixed_content, encoding='utf-8')
    
    print(f"✅ Исправлено {fixes_count} функций в {file_path}")
    print(f"📊 Размер до: {len(original_content)} байт")
    print(f"📊 Размер после: {len(fixed_content)} байт")
    
    return True

if __name__ == "__main__":
    print("🔧 Начинаем исправление analysis_tools.py...")
    print()
    
    success = fix_analysis_tools()
    
    if success:
        print()
        print("✅ Исправление завершено!")
        print("🔍 Проверка синтаксиса...")
        
        # Проверяем синтаксис
        import py_compile
        try:
            py_compile.compile("mcp-server/tools/analysis/analysis_tools.py", doraise=True)
            print("✅ Синтаксис корректен!")
        except SyntaxError as e:
            print(f"❌ Ошибка синтаксиса: {e}")
            print(f"   Строка {e.lineno}: {e.text}")
    else:
        print()
        print("❌ Исправление не удалось")
