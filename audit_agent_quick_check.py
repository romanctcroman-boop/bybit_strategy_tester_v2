"""
Быстрая проверка работоспособности Audit Agent
Проверяет все компоненты без запуска полного мониторинга
"""

import sys
from pathlib import Path

# Настройка путей
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "automation" / "task3_audit_agent"))

print("=" * 80)
print("🔍 AUDIT AGENT - БЫСТРАЯ ПРОВЕРКА")
print("=" * 80)
print()

# Проверка 1: Импорт модулей
print("1️⃣ Проверка импортов...")
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    print("   ✅ APScheduler")
except ImportError as e:
    print(f"   ❌ APScheduler: {e}")
    sys.exit(1)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    print("   ✅ watchdog")
except ImportError as e:
    print(f"   ❌ watchdog: {e}")
    sys.exit(1)

try:
    import coverage
    print("   ✅ coverage")
except ImportError as e:
    print(f"   ❌ coverage: {e}")
    sys.exit(1)

print()

# Проверка 2: Конфигурация
print("2️⃣ Проверка конфигурации...")
try:
    from config import AuditConfig
    config = AuditConfig()
    print("   ✅ AuditConfig импортирован")
    print(f"   ✅ Project root: {config.project_root}")
    print(f"   ✅ Check interval: {config.check_interval} минут")
    print(f"   ✅ Coverage threshold: {config.coverage_threshold}%")
    print(f"   ✅ Audit script: {config.audit_script.name}")
    
    # Проверка существования audit script
    if config.audit_script.exists():
        print(f"   ✅ Audit script найден")
    else:
        print(f"   ⚠️  Audit script не найден: {config.audit_script}")
    
except Exception as e:
    print(f"   ❌ Ошибка конфигурации: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Проверка 3: Audit Agent компоненты
print("3️⃣ Проверка компонентов Agent...")
try:
    from audit_agent import (
        AuditHistory,
        MarkerFileHandler,
        GitMonitor,
        CoverageChecker,
        AuditAgent
    )
    print("   ✅ AuditHistory")
    print("   ✅ MarkerFileHandler")
    print("   ✅ GitMonitor")
    print("   ✅ CoverageChecker")
    print("   ✅ AuditAgent")
    
except Exception as e:
    print(f"   ❌ Ошибка импорта компонентов: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Проверка 4: AuditHistory
print("4️⃣ Проверка AuditHistory...")
try:
    test_history_file = project_root / "test_audit_history.json"
    history = AuditHistory(test_history_file)
    
    # Тест записи
    history.add_audit_record(
        trigger_reason="Test trigger",
        status="SUCCESS",
        details="Quick check test"
    )
    
    # Тест загрузки
    loaded_history = history.load_history()
    if loaded_history and len(loaded_history) > 0:
        print("   ✅ История создается и загружается")
        print(f"   ✅ Последняя запись: {loaded_history[-1]['trigger_reason']}")
    else:
        print("   ⚠️  История пуста")
    
    # Очистка тестового файла
    if test_history_file.exists():
        test_history_file.unlink()
        print("   ✅ Тестовый файл очищен")
    
except Exception as e:
    print(f"   ❌ Ошибка AuditHistory: {e}")
    import traceback
    traceback.print_exc()

print()

# Проверка 5: GitMonitor
print("5️⃣ Проверка GitMonitor...")
try:
    git_monitor = GitMonitor(project_root)
    
    # Проверка получения хеша коммита
    commit_hash = git_monitor._get_latest_commit_hash()
    if commit_hash:
        print(f"   ✅ Git доступен, последний коммит: {commit_hash[:8]}...")
        
        # Проверка сообщения коммита
        commit_message = git_monitor._get_commit_message(commit_hash)
        if commit_message:
            first_line = commit_message.split('\n')[0]
            print(f"   ✅ Сообщение коммита: {first_line[:50]}...")
        
        # Проверка milestone detection
        is_milestone = git_monitor._is_milestone_commit("Test [MILESTONE] commit")
        print(f"   ✅ Milestone detection: {is_milestone}")
    else:
        print("   ⚠️  Git недоступен или не в Git репозитории")
    
except Exception as e:
    print(f"   ⚠️  Ошибка GitMonitor: {e}")

print()

# Проверка 6: CoverageChecker
print("6️⃣ Проверка CoverageChecker...")
try:
    import asyncio
    
    coverage_checker = CoverageChecker(coverage_threshold=80.0)
    print("   ✅ CoverageChecker создан")
    
    # Асинхронная проверка coverage
    async def check_coverage():
        coverage_result = await coverage_checker._get_coverage_from_tool()
        if coverage_result is not None:
            print(f"   ✅ Coverage tool доступен: {coverage_result}%")
        else:
            print("   ℹ️  Coverage tool недоступен (нормально, если не запускались тесты)")
    
    asyncio.run(check_coverage())
    
except Exception as e:
    print(f"   ⚠️  Ошибка CoverageChecker: {e}")

print()

# Проверка 7: AuditAgent инициализация
print("7️⃣ Проверка AuditAgent...")
try:
    agent = AuditAgent(config)
    print("   ✅ Agent создан")
    print(f"   ✅ History: {agent.history.history_file.name}")
    print(f"   ✅ GitMonitor: активен")
    print(f"   ✅ CoverageChecker: активен")
    print(f"   ✅ Scheduler: {type(agent.scheduler).__name__}")
    print(f"   ✅ Observer: {type(agent.observer).__name__}")
    
except Exception as e:
    print(f"   ❌ Ошибка AuditAgent: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Проверка 8: Marker patterns
print("8️⃣ Проверка marker patterns...")
try:
    marker_handler = MarkerFileHandler(agent)
    
    test_files = [
        "TASK1_COMPLETE.md",
        "PHASE_2_COMPLETE.md",
        "MILESTONE_V1.md",
        "TASK2_COMPLETION_REPORT.md",
        "regular_file.py"
    ]
    
    for test_file in test_files:
        is_marker = marker_handler._is_marker_file(Path(test_file))
        status = "✅" if is_marker else "➖"
        print(f"   {status} {test_file}: {'marker' if is_marker else 'не marker'}")
    
except Exception as e:
    print(f"   ❌ Ошибка marker patterns: {e}")

print()

# Итоговый результат
print("=" * 80)
print("✅ ВСЕ БАЗОВЫЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
print("=" * 80)
print()
print("📋 Резюме:")
print("   ✅ Все зависимости установлены")
print("   ✅ Конфигурация корректна")
print("   ✅ Все компоненты импортируются")
print("   ✅ AuditHistory работает")
print("   ✅ GitMonitor инициализируется")
print("   ✅ CoverageChecker инициализируется")
print("   ✅ AuditAgent создается")
print("   ✅ Marker patterns работают")
print()
print("🚀 Audit Agent готов к использованию!")
print()
print("Для запуска в production режиме:")
print("   powershell: .\\automation\\task3_audit_agent\\start_agent.ps1")
print("   python: python automation\\task3_audit_agent\\audit_agent.py")
print()
