"""
ОПТИМИЗИРОВАННЫЙ ЗАПРОС: Получение полного ответа с правильными параметрами

Проблема: DeepSeek API имеет следующие лимиты:
- max_tokens для ответа: до 4096 для некоторых моделей
- Для deepseek-chat рекомендуется 4096-8192

Решение: Разделим запрос на 3 отдельных запроса для каждой задачи
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OUTPUT_DIR = Path(__file__).parent / "ai_audit_results"
OUTPUT_DIR.mkdir(exist_ok=True)


async def ask_deepseek(prompt: str, task_name: str) -> dict:
    """Отправка запроса в DeepSeek API с оптимальными параметрами"""
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            print(f"\n🔄 Запрос для задачи: {task_name}")
            print(f"⏱️  Таймаут: 300 секунд")
            
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Ты - senior архитектор и эксперт по автоматизации Python проектов. Предоставь полный рабочий код без TODO и заглушек."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 8192  # Оптимальное значение для deepseek-chat
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            finish_reason = result.get("choices", [{}])[0].get("finish_reason")
            
            print(f"✅ Ответ получен!")
            print(f"📊 Размер: {len(content):,} символов")
            print(f"🏁 Статус: {finish_reason}")
            
            return result
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        if hasattr(e, 'response'):
            print(f"📄 Детали ответа: {e.response.text if hasattr(e.response, 'text') else 'N/A'}")
        raise


async def main():
    """Главная функция - запрашиваем каждую задачу отдельно"""
    
    print("=" * 80)
    print("🤖 ОПТИМИЗИРОВАННЫЙ ЗАПРОС К DEEPSEEK (3 ОТДЕЛЬНЫЕ ЗАДАЧИ)")
    print("=" * 80)
    print()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_results = {}
    
    # ============================
    # ЗАДАЧА 1: Test Watcher
    # ============================
    prompt_task1 = """
# ЗАДАЧА 1: Автоматическая верификация тестов после исправлений

Разработай ПОЛНОЕ решение для автоматической верификации тестов в Bybit Strategy Tester V2.

## Требования:
- Мониторинг изменений файлов проекта (Python, тесты)
- Автоматический запуск pytest + coverage при изменениях
- Debouncing для предотвращения спама (15-30 сек)
- Отправка результатов в DeepSeek API для анализа
- Сохранение отчетов в ai_audit_results/

## Что предоставить:
1. **Полный рабочий Python код** (watchdog + pytest + DeepSeek API)
2. **requirements.txt** с зависимостями
3. **Скрипт запуска** для Windows PowerShell
4. **Конфигурация** (.env пример)
5. **Документация** по использованию
6. **Оценка трудозатрат** (часы на внедрение)

## Архитектурные решения:
- Использовать watchdog (не git hooks) для мониторинга
- Event-driven подход, не polling
- Асинхронный код (asyncio + aiohttp)
- JSON формат для отчетов
- Loguru для логирования

## Ключевые функции:
```python
class TestWatcher:
    def __init__(self, watch_path, debounce_seconds)
    async def run_tests(self) -> Dict  # Запуск pytest
    async def send_to_deepseek(self, results) -> Dict  # Анализ через DeepSeek
    async def process_changes(self)  # Обработка накопленных изменений
```

**КРИТИЧЕСКИ ВАЖНО**: 
- Код должен быть готов к немедленному запуску
- Нет TODO, нет заглушек
- Полная обработка ошибок
- Все пути относительно корня проекта

Предоставь ПОЛНЫЙ код со всеми функциями и классами.
"""
    
    # ============================
    # ЗАДАЧА 2: Key Manager
    # ============================
    prompt_task2 = """
# ЗАДАЧА 2: Автоматическая расшифровка API ключей при старте MCP сервера

Разработай ПОЛНОЕ решение для безопасного управления API ключами в MCP сервере.

## Требования:
- Singleton класс KeyManager для управления ключами
- Расшифровка encrypted_secrets.json при старте MCP
- Integration с mcp-server/server.py через callback
- Декоратор @with_keys для защиты MCP tools
- НЕ логировать ключи ни при каких условиях

## Что предоставить:
1. **key_manager.py** - полный модуль управления ключами
2. **encrypt_secrets.py** - утилита для первоначального шифрования
3. **Модифицированный server.py** с интеграцией
4. **requirements.txt** дополнительные зависимости (cryptography)
5. **Документация** по настройке
6. **Оценка трудозатрат** (часы на внедрение)

## Архитектурные решения:
- Singleton pattern для KeyManager
- Fernet encryption (cryptography library)
- ENCRYPTION_KEY из .env
- @mcp.callback("startup") для автозагрузки
- Graceful error handling

## Ключевые функции:
```python
class KeyManager:
    _instance = None  # Singleton
    def __new__(cls)
    def load_keys(self, secrets_file) -> bool
    def get_key(self, key_name) -> Optional[str]
    def encrypt_and_save(self, secrets, output_file)

@with_keys  # Декоратор
async def mcp_tool_function()
```

## Пример интеграции:
```python
# mcp-server/server.py
@mcp.callback("startup")
async def on_startup():
    key_manager = KeyManager()
    key_manager.load_keys()
    # Установить в environment
```

**КРИТИЧЕСКИ ВАЖНО**: 
- Полный рабочий код
- Пример интеграции в существующий MCP сервер
- Безопасность (не логировать ключи!)
- Тесты для KeyManager

Предоставь ПОЛНЫЙ код со всеми классами и функциями.
"""
    
    # ============================
    # ЗАДАЧА 3: Audit Agent
    # ============================
    prompt_task3 = """
# ЗАДАЧА 3: Фоновый аудит-агент для автоматического мониторинга проекта

Разработай ПОЛНОЕ решение для фонового агента, который автоматически запускает аудит при достижении milestone.

## Требования:
- Фоновый процесс (daemon), работающий 24/7
- Мониторинг маркеров завершения (*_COMPLETE.md, PHASE_*.md, MILESTONE_*.md)
- Периодическая проверка (каждые 5 минут)
- Проверка coverage тестов (триггер при > 80%)
- Автоматический запуск full_ai_audit_deepseek_perplexity_deepseek.py
- Сохранение истории запусков

## Что предоставить:
1. **audit_agent.py** - полный код агента
2. **config.py** - конфигурация агента
3. **start_agent.ps1** - скрипт запуска для Windows
4. **start_agent.sh** - скрипт запуска для Linux
5. **requirements.txt** дополнительные зависимости (APScheduler, watchdog)
6. **Документация** по настройке
7. **Оценка трудозатрат** (часы на внедрение)

## Архитектурные решения:
- APScheduler для периодических задач (не cron)
- Watchdog для мониторинга создания файлов маркеров
- Event-driven + polling hybrid подход
- Subprocess для запуска аудит скрипта
- JSON для истории запусков

## Ключевые функции:
```python
class AuditAgent:
    def __init__(self, check_interval)
    async def check_completion_markers(self) -> List[str]
    async def check_test_coverage(self) -> bool
    async def run_full_audit(self, trigger_reason)
    async def periodic_check(self)
    async def start(self)
```

## Триггеры аудита:
1. Создание файла маркера (*_COMPLETE.md)
2. Coverage тестов достигло 80%+
3. Git commit с тегом [MILESTONE] или [CHECKPOINT]

**КРИТИЧЕСКИ ВАЖНО**: 
- Полный рабочий код
- Кросс-платформенность (Windows + Linux)
- Graceful shutdown (Ctrl+C)
- Самомониторинг агента

Предоставь ПОЛНЫЙ код со всеми классами и функциями.
"""
    
    # Запускаем запросы последовательно
    tasks_prompts = [
        ("Task1_TestWatcher", prompt_task1),
        ("Task2_KeyManager", prompt_task2),
        ("Task3_AuditAgent", prompt_task3)
    ]
    
    for task_name, prompt in tasks_prompts:
        try:
            print(f"\n{'='*80}")
            print(f"🚀 Запрос задачи: {task_name}")
            print(f"{'='*80}")
            
            result = await ask_deepseek(prompt, task_name)
            all_results[task_name] = result
            
            # Сохраняем каждую задачу отдельно
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            task_file = OUTPUT_DIR / f"deepseek_{task_name}_{timestamp}.md"
            with open(task_file, 'w', encoding='utf-8') as f:
                f.write(f"# {task_name.replace('_', ' ')}\n\n")
                f.write(f"**Дата**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
                f.write(f"**Размер**: {len(content):,} символов\n\n")
                f.write("---\n\n")
                f.write(content)
            
            print(f"✅ {task_name} сохранена в: {task_file.name}")
            
            # Пауза между запросами
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"❌ Ошибка при обработке {task_name}: {e}")
            all_results[task_name] = {"error": str(e)}
    
    # ============================
    # Финальная сводка
    # ============================
    print("\n" + "=" * 80)
    print("✅ ВСЕ ЗАДАЧИ ОБРАБОТАНЫ!")
    print("=" * 80)
    
    # Объединяем все результаты в один файл
    combined_file = OUTPUT_DIR / f"deepseek_ALL_TASKS_COMBINED_{timestamp}.md"
    with open(combined_file, 'w', encoding='utf-8') as f:
        f.write("# 🤖 ПОЛНОЕ РЕШЕНИЕ DEEPSEEK: ВСЕ ТРИ ЗАДАЧИ\n\n")
        f.write(f"**Дата**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n\n")
        f.write("---\n\n")
        
        for task_name, result in all_results.items():
            f.write(f"\n## {task_name.replace('_', ' ')}\n\n")
            
            if "error" in result:
                f.write(f"❌ Ошибка: {result['error']}\n\n")
            else:
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                f.write(content)
                f.write("\n\n---\n\n")
    
    print(f"\n📁 Объединенный файл: {combined_file.name}")
    print(f"📁 Директория результатов: {OUTPUT_DIR}")
    
    print("\n" + "=" * 80)
    print("СПИСОК СОЗДАННЫХ ФАЙЛОВ:")
    print("=" * 80)
    
    for file in sorted(OUTPUT_DIR.glob(f"*{timestamp}*")):
        size_kb = file.stat().st_size / 1024
        print(f"📄 {file.name} ({size_kb:.1f} KB)")
    
    print("\n✅ ГОТОВО!")


if __name__ == "__main__":
    asyncio.run(main())
