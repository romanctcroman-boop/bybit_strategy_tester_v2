# 🤖 Autonomous System для Bybit Strategy Tester V2

**Полностью автономная система**, способная:
- ✅ Анализировать состояние проекта
- ✅ Редактировать код через AI (DeepSeek/Perplexity)
- ✅ Запускать тесты и скрипты
- ✅ Исправлять ошибки автоматически
- ✅ Принимать решения о развитии проекта

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                 AUTONOMOUS SYSTEM                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  autonomous_project_manager.py                               │
│  ├─ Анализ проекта (через Agent-to-Agent)                   │
│  ├─ Создание задач из рекомендаций DeepSeek                 │
│  ├─ Выполнение задач (File Edit + Tests)                    │
│  └─ Принятие решений о следующих шагах                      │
│                                                              │
│  autonomous_executor.py                                      │
│  ├─ Запуск любого скрипта проекта                           │
│  ├─ Анализ результатов через AI                             │
│  ├─ Автоисправление ошибок                                  │
│  └─ Retry механизм с умным анализом                         │
│                                                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
    ┌────────────┐ ┌────────────┐ ┌────────────┐
    │  Agent-to- │ │ File Edit  │ │ Existing   │
    │  Agent API │ │ Endpoint   │ │ Scripts    │
    └────────────┘ └────────────┘ └────────────┘
```

---

## 🚀 Быстрый старт

### 1️⃣ Запуск Backend (если ещё не запущен)

```powershell
# Активировать venv
& D:\bybit_strategy_tester_v2\.venv\Scripts\Activate.ps1

# Запустить Backend
py -m uvicorn backend.main:app --reload
```

Backend должен быть запущен на `http://localhost:8000`.

### 2️⃣ Использование Autonomous Executor

**Простое выполнение скрипта:**
```powershell
python autonomous_executor.py test_agent_to_agent.py
```

**С анализом результатов:**
```powershell
python autonomous_executor.py test_redis_queue_poc.py --analyze
```

**С автоисправлением ошибок:**
```powershell
python autonomous_executor.py verify_system.py --auto-fix
```

**С повторными попытками:**
```powershell
python autonomous_executor.py test_file_edit_endpoint.py --auto-fix --max-retries 5
```

### 3️⃣ Использование Autonomous Project Manager

**Полностью автономный режим:**
```powershell
python autonomous_project_manager.py
```

**Что происходит:**
1. 🔍 Анализирует весь проект через DeepSeek
2. 📋 Создаёт список приоритетных задач
3. 🚀 Выполняет задачи автоматически
4. 🧪 Запускает тесты
5. 🔧 Исправляет ошибки
6. 🔄 Повторяет цикл до достижения целей

---

## 📊 Примеры использования

### Пример 1: Автоматическое тестирование с исправлением

```powershell
# Запустить тест, если не прошёл - исправить и повторить
python autonomous_executor.py test_redis_queue_poc.py --auto-fix --max-retries 3
```

**Что происходит:**
1. Запускает `test_redis_queue_poc.py`
2. Если ошибка → DeepSeek анализирует stderr/stdout
3. DeepSeek предлагает исправления в коде
4. File Edit Endpoint применяет исправления (создаёт backup)
5. Повторяет тест (до 3 попыток)

### Пример 2: Автономное развитие проекта

```powershell
python autonomous_project_manager.py
```

**Консольный вывод:**
```
🤖 Autonomous Project Manager initialized
Backend: http://localhost:8000
Workspace: D:\bybit_strategy_tester_v2

============================================================
ITERATION 1/10
============================================================

📊 Analyzing project state...
✅ Project analysis complete: health=warning

📊 Health: warning (75/100)
📋 Issues: 2
💡 Recommendations: 3

✅ Task created: task-20251111-150000 - Complete Phase 1 Redis Queue implementation
✅ Task created: task-20251111-150001 - Optimize Agent-to-Agent latency
✅ Task created: task-20251111-150002 - Add comprehensive error handling

🚀 Executing task: task-20251111-150000
📄 Analyzing backend/queue/redis_queue_manager.py...
✅ Analysis: File looks good, minor improvements suggested...

🧪 Running tests: ['test_redis_queue_poc.py']
Running test_redis_queue_poc.py...
✅ Test passed: test_redis_queue_poc.py

✅ Task completed: task-20251111-150000
Task result: Tests passed: 1/1

============================================================
ITERATION 2/10
============================================================

...
```

### Пример 3: Запуск конкретного скрипта с анализом

```powershell
python autonomous_executor.py analyze_project_with_mcp.py --analyze
```

**Что получите:**
```
🚀 Executing: analyze_project_with_mcp.py
✅ Script completed in 45.32s

📊 Analyzing execution result via deepseek...
✅ Analysis complete: status=success

📊 Analysis: Script completed successfully, no issues found
🔍 Issues found: 0
🔧 Fixes recommended: 0

============================================================
EXECUTION SUMMARY
============================================================
Script: analyze_project_with_mcp.py
Success: True
Exit Code: 0
Duration: 45.32s
```

---

## 🎯 Возможности Autonomous Executor

### Режимы работы:

| Режим | Команда | Описание |
|-------|---------|----------|
| **Simple** | `python autonomous_executor.py script.py` | Просто запустить скрипт |
| **Analyze** | `--analyze` | Анализировать результат через DeepSeek |
| **Auto-fix** | `--auto-fix` | Автоматически исправлять ошибки |
| **Retry** | `--max-retries 5` | Повторные попытки с умным анализом |

### Поддерживаемые скрипты:

Все `.py` файлы в корне проекта:
- ✅ `test_agent_to_agent.py` - Agent-to-Agent тесты
- ✅ `test_redis_queue_poc.py` - Redis Queue тесты
- ✅ `test_file_edit_endpoint.py` - File Edit тесты
- ✅ `verify_system.py` - Проверка системы
- ✅ `analyze_project_with_mcp.py` - MCP анализ
- ✅ И любые другие скрипты проекта

---

## 🤖 Возможности Autonomous Project Manager

### Автоматические действия:

1. **Анализ проекта** (через `/api/v1/agent/send` → DeepSeek)
   - Читает критичные файлы
   - Оценивает здоровье проекта (0-100)
   - Находит issues (critical/high/medium/low)
   - Предлагает приоритетные задачи

2. **Создание задач** из рекомендаций
   - Приоритезация (CRITICAL → LOW)
   - Определение файлов для редактирования
   - Определение тестов для запуска
   - Критерии успеха

3. **Выполнение задач**
   - Анализ файлов (через `/api/v1/agent/file-edit` mode=analyze)
   - Рефакторинг (через mode=refactor, создаёт backup)
   - Запуск тестов (через subprocess)
   - Валидация результатов

4. **Принятие решений**
   - Если health=good и score≥90 → останавливается
   - Если есть критичные issues → продолжает
   - Если задачи не проходят → retry (до 3 попыток)
   - Создаёт финальный отчёт

---

## 📋 API Endpoints (используются автономной системой)

### 1. Agent-to-Agent Communication

**POST /api/v1/agent/send**
```json
{
  "from_agent": "copilot",
  "to_agent": "deepseek",
  "content": "Analyze this code...",
  "message_type": "query"
}
```

### 2. File Edit Endpoint

**POST /api/v1/agent/file-edit**

**Mode: read**
```json
{
  "file_path": "backend/queue/redis_queue_poc.py",
  "mode": "read"
}
```

**Mode: analyze**
```json
{
  "file_path": "backend/queue/redis_queue_poc.py",
  "mode": "analyze",
  "agent": "deepseek",
  "instruction": "Check for bugs and suggest improvements"
}
```

**Mode: refactor**
```json
{
  "file_path": "test_file.py",
  "mode": "refactor",
  "agent": "deepseek",
  "instruction": "Add type hints and docstrings"
}
```
*Автоматически создаёт backup: `test_file.py.backup`*

**Mode: write**
```json
{
  "file_path": "new_file.py",
  "mode": "write",
  "content": "def hello():\n    return 'world'\n"
}
```

---

## 🔧 Конфигурация

### Переменные окружения (опционально):

```bash
# Backend URL
AUTONOMOUS_BACKEND_URL=http://localhost:8000

# Workspace root
AUTONOMOUS_WORKSPACE_ROOT=D:\bybit_strategy_tester_v2

# Agent preference
AUTONOMOUS_DEFAULT_AGENT=deepseek  # или perplexity

# Timeouts
AUTONOMOUS_SCRIPT_TIMEOUT=300
AUTONOMOUS_AGENT_TIMEOUT=60
```

### Логирование:

По умолчанию логи выводятся в консоль через `loguru`. Для сохранения в файл:

```python
# В начале autonomous_executor.py или autonomous_project_manager.py
from loguru import logger

logger.add("autonomous_execution_{time}.log", rotation="1 day")
```

---

## 🎯 Roadmap: Следующие возможности

### Планируется добавить:

1. **Web Dashboard** для мониторинга автономной работы
   - Real-time статус задач
   - Визуализация execution history
   - Интерактивное управление (pause/resume/stop)

2. **Scheduled Autonomous Runs**
   ```powershell
   # Запускать каждые 6 часов
   python autonomous_project_manager.py --schedule "0 */6 * * *"
   ```

3. **Multi-Agent Collaboration**
   - DeepSeek + Perplexity работают параллельно
   - Voting механизм для принятия решений
   - Consensus для критичных изменений

4. **Git Integration**
   - Автоматические коммиты после успешных исправлений
   - Branch management (создание feature/* для задач)
   - Pull Request creation с описанием изменений

5. **Metrics & Analytics**
   - Prometheus metrics для автономной работы
   - Grafana dashboard
   - Alert system для критичных ситуаций

6. **VS Code Extension Integration**
   - Команда "Run Autonomous Analysis"
   - Status bar indicator
   - Output panel для real-time логов

---

## ⚠️ Важные замечания

### Безопасность:

- ✅ **Backup создаётся автоматически** перед refactor (`.backup` suffix)
- ✅ **Dry-run mode** планируется (покажет изменения без применения)
- ⚠️ **Проверяйте изменения** после автоисправления
- ⚠️ **Git commit перед запуском** автономного режима

### Ограничения:

- ❌ Не редактирует конфигурационные файлы (.env, .vscode/settings.json)
- ❌ Не удаляет файлы без подтверждения
- ❌ Не делает git push (только локальные изменения)
- ⚠️ Требует Backend на порту 8000

### Рекомендации:

1. **Запускайте в отдельной ветке:**
   ```bash
   git checkout -b autonomous-improvements
   ```

2. **Проверяйте изменения:**
   ```bash
   git diff
   ```

3. **Откатывайте при необходимости:**
   ```bash
   git checkout -- path/to/file.py
   # Или восстанавливайте из backup:
   cp file.py.backup file.py
   ```

---

## 📊 Статистика использования

После запуска `autonomous_project_manager.py` вы получите финальный отчёт:

```
============================================================
AUTONOMOUS CYCLE COMPLETE - FINAL REPORT
============================================================

✅ Completed: 3
❌ Failed: 0
⏳ Pending: 1

✅ COMPLETED TASKS:
  - Complete Phase 1 Redis Queue implementation
  - Optimize Agent-to-Agent latency
  - Add comprehensive error handling
```

---

## 🚀 Начало работы

**1. Убедитесь, что Backend запущен:**
```powershell
curl http://localhost:8000/api/v1/agent/health
```

**2. Запустите простой тест:**
```powershell
python autonomous_executor.py test_agent_to_agent.py --analyze
```

**3. Если всё работает → запустите автономный режим:**
```powershell
python autonomous_project_manager.py
```

**4. Наблюдайте за выполнением в консоли:**
```
🤖 Autonomous Project Manager - Starting...
✅ Backend running
🔄 Starting autonomous work cycle...

ITERATION 1/10
...
```

---

## 🤝 Интеграция с существующей инфраструктурой

Autonomous System полностью совместима:

- ✅ **Redis Queue** - может запускать workers через tasks
- ✅ **Agent-to-Agent** - использует существующий API
- ✅ **MCP Server** - может взаимодействовать через MCP tools
- ✅ **Existing Tests** - запускает все `test_*.py` скрипты
- ✅ **File Edit Endpoint** - создан специально для автономии

**Не нужны изменения в существующем коде!**

---

## 📞 Поддержка

Если что-то не работает:

1. **Проверьте Backend:**
   ```powershell
   curl http://localhost:8000/api/v1/agent/health
   ```

2. **Проверьте логи:**
   - Autonomous Executor - в консоли
   - Backend - в терминале uvicorn

3. **Проверьте зависимости:**
   ```powershell
   pip install httpx loguru fastapi
   ```

---

**🎉 Система готова к автономной работе!**

Запустите `python autonomous_project_manager.py` и наблюдайте, как AI улучшает проект самостоятельно! 🤖
