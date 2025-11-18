"""
Автоматическое исправление устаревшего datetime.utcnow() → datetime.now(timezone.utc)

Генерировано DeepSeek Agent
"""
import re
from pathlib import Path
from typing import List, Tuple

def fix_datetime_utcnow_in_file(file_path: Path) -> Tuple[bool, int]:
    """
    Исправляет datetime.utcnow() в файле
    
    Returns:
        (changed: bool, replacements: int)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        
        # Проверяем наличие импорта datetime
        has_datetime_import = bool(re.search(r'from datetime import.*datetime', content))
        has_timezone_import = bool(re.search(r'from datetime import.*timezone', content))
        
        # Заменяем datetime.utcnow() → datetime.now(timezone.utc)
        pattern = r'datetime\.utcnow\(\)'
        replacement = 'datetime.now(timezone.utc)'
        
        content, count = re.subn(pattern, replacement, content)
        
        if count > 0:
            # Добавляем timezone в импорт если нужно
            if has_datetime_import and not has_timezone_import:
                # Найти строку импорта datetime
                import_pattern = r'from datetime import ([^(\n]+)'
                
                def add_timezone(match):
                    imports = match.group(1).strip()
                    if 'timezone' not in imports:
                        # Добавляем timezone
                        return f'from datetime import {imports}, timezone'
                    return match.group(0)
                
                content = re.sub(import_pattern, add_timezone, content, count=1)
            
            # Записываем изменения
            file_path.write_text(content, encoding='utf-8')
            return True, count
        
        return False, 0
        
    except Exception as e:
        print(f"❌ Ошибка в {file_path}: {e}")
        return False, 0


def main():
    """Основная функция"""
    project_root = Path(__file__).parent
    backend_path = project_root / 'backend'
    
    # Файлы для исправления
    files_to_fix = [
        'backend/core/logging_config.py',
        'backend/tasks/backfill_tasks.py',
        'backend/services/data_service.py',
        'backend/services/ml_hpa_monitor.py',
        'backend/services/k8s_automl_manager.py',
        'backend/services/reasoning_storage.py',
        'backend/services/slack_service.py',
        'backend/services/pagerduty_service.py',
        'backend/services/tournament_storage.py',
    ]
    
    print("🔧 Исправление datetime.utcnow() → datetime.now(timezone.utc)\n")
    
    total_files = 0
    total_replacements = 0
    
    for file_rel in files_to_fix:
        file_path = project_root / file_rel
        if not file_path.exists():
            print(f"⚠️  Файл не найден: {file_rel}")
            continue
        
        changed, count = fix_datetime_utcnow_in_file(file_path)
        
        if changed:
            total_files += 1
            total_replacements += count
            print(f"✅ {file_rel}: {count} замен")
        else:
            print(f"⏭️  {file_rel}: изменений нет")
    
    print(f"\n📊 Итого: {total_files} файлов, {total_replacements} замен")


if __name__ == '__main__':
    main()
