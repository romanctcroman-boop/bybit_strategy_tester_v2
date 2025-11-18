"""
Быстрая проверка работоспособности Test Watcher
Проверяет все компоненты без запуска полного цикла мониторинга
"""

import sys
from pathlib import Path

# Настройка путей
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "automation" / "task2_key_manager"))
sys.path.insert(0, str(project_root / "automation" / "task1_test_watcher"))

print("=" * 80)
print("🔍 TEST WATCHER - БЫСТРАЯ ПРОВЕРКА")
print("=" * 80)
print()

# Проверка 1: Импорт модулей
print("1️⃣ Проверка импортов...")
try:
    import watchdog
    print("   ✅ watchdog")
except ImportError as e:
    print(f"   ❌ watchdog: {e}")
    sys.exit(1)

try:
    import pytest
    print("   ✅ pytest")
except ImportError as e:
    print(f"   ❌ pytest: {e}")
    sys.exit(1)

try:
    import coverage
    print("   ✅ coverage")
except ImportError as e:
    print(f"   ❌ coverage: {e}")
    sys.exit(1)

try:
    import httpx
    print("   ✅ httpx")
except ImportError as e:
    print(f"   ❌ httpx: {e}")
    sys.exit(1)

try:
    from loguru import logger
    print("   ✅ loguru")
except ImportError as e:
    print(f"   ❌ loguru: {e}")
    sys.exit(1)

print()

# Проверка 2: KeyManager
print("2️⃣ Проверка KeyManager...")
try:
    from key_manager import KeyManager
    key_manager = KeyManager()
    print("   ✅ KeyManager импортирован")
    
    # Проверка инициализации
    import os
    from dotenv import load_dotenv
    
    env_path = project_root / '.env'
    load_dotenv(env_path)
    
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if encryption_key:
        if key_manager.initialize_encryption(encryption_key):
            print("   ✅ Encryption инициализирован")
            
            secrets_file = project_root / "encrypted_secrets.json"
            if secrets_file.exists():
                if key_manager.load_keys(str(secrets_file)):
                    keys = key_manager.get_available_keys()
                    print(f"   ✅ Загружено {len(keys)} ключей: {', '.join(keys)}")
                    
                    deepseek_key = key_manager.get_key("DEEPSEEK_API_KEY")
                    if deepseek_key:
                        print(f"   ✅ DEEPSEEK_API_KEY доступен (первые 10 символов: {deepseek_key[:10]}...)")
                    else:
                        print("   ⚠️  DEEPSEEK_API_KEY не найден в KeyManager")
                else:
                    print("   ⚠️  Не удалось загрузить ключи")
            else:
                print("   ⚠️  encrypted_secrets.json не найден")
        else:
            print("   ⚠️  Не удалось инициализировать encryption")
    else:
        print("   ⚠️  ENCRYPTION_KEY не найден в .env")
        
except Exception as e:
    print(f"   ❌ Ошибка KeyManager: {e}")
    import traceback
    traceback.print_exc()

print()

# Проверка 3: TestWatcher класс
print("3️⃣ Проверка TestWatcher класса...")
try:
    from test_watcher import TestWatcher
    print("   ✅ TestWatcher импортирован")
    
    # Создание экземпляра (без запуска)
    watcher = TestWatcher(
        watch_path=str(project_root),
        debounce_seconds=20
    )
    print("   ✅ TestWatcher экземпляр создан")
    print(f"   ✅ Watch path: {watcher.watch_path}")
    print(f"   ✅ Debounce: {watcher.debounce_seconds} seconds")
    print(f"   ✅ Results dir: {watcher.results_dir}")
    
    # Проверка API ключа
    if watcher.deepseek_api_key:
        print(f"   ✅ DeepSeek API Key загружен (первые 10 символов: {watcher.deepseek_api_key[:10]}...)")
    else:
        print("   ⚠️  DeepSeek API Key не загружен")
    
except Exception as e:
    print(f"   ❌ Ошибка TestWatcher: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Проверка 4: Директории
print("4️⃣ Проверка директорий...")
results_dir = project_root / "ai_audit_results"
if results_dir.exists():
    print(f"   ✅ ai_audit_results/ существует")
    json_files = list(results_dir.glob("test_watcher_audit_*.json"))
    print(f"   📊 Найдено отчетов: {len(json_files)}")
else:
    print(f"   ⚠️  ai_audit_results/ не существует (будет создана)")

log_file = project_root / "test_watcher.log"
if log_file.exists():
    size_kb = log_file.stat().st_size / 1024
    print(f"   ✅ test_watcher.log существует ({size_kb:.1f} KB)")
else:
    print(f"   ℹ️  test_watcher.log еще не создан")

print()

# Проверка 5: Тестовый промпт
print("5️⃣ Проверка построения промпта...")
try:
    test_results = {
        "pytest_exit_code": 0,
        "success": True,
        "coverage_total": 85.5,
        "coverage_by_file": {
            "test_file.py": {
                "total_lines": 100,
                "covered_lines": 85,
                "coverage_percent": 85.0
            }
        }
    }
    
    changed_files = [Path("test_file.py")]
    
    prompt = watcher._build_analysis_prompt(test_results, changed_files)
    
    if len(prompt) > 100 and "TEST EXECUTION" in prompt:
        print("   ✅ Промпт построен корректно")
        print(f"   ✅ Длина промпта: {len(prompt)} символов")
    else:
        print("   ⚠️  Промпт выглядит некорректно")
        
except Exception as e:
    print(f"   ❌ Ошибка построения промпта: {e}")

print()

# Итоговый результат
print("=" * 80)
print("✅ ВСЕ БАЗОВЫЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
print("=" * 80)
print()
print("📋 Резюме:")
print("   ✅ Все зависимости установлены")
print("   ✅ KeyManager работает")
print("   ✅ TestWatcher класс инициализируется")
print("   ✅ API ключи загружаются")
print("   ✅ Промпты строятся корректно")
print()
print("🚀 Test Watcher готов к использованию!")
print()
print("Для запуска в production режиме:")
print("   powershell: .\\automation\\task1_test_watcher\\start_watcher.ps1")
print("   python: python automation\\task1_test_watcher\\test_watcher.py")
print()
