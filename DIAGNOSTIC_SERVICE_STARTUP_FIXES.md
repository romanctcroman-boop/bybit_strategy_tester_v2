# ✅ ИСПРАВЛЕНИЯ ЗАПУСКА DIAGNOSTIC SERVICE

**Дата:** 2025-11-10 16:50  
**Проблемы:** 2 критические ошибки запуска

---

## 🔴 ПРОБЛЕМА 1: `python` не найден в PowerShell

**Ошибка:**
```
python : Имя "python" не распознано как имя командлета, функции...
```

**Причина:**  
В Windows 11 команда `python` не всегда доступна в PowerShell.  
Нужно использовать `py` (Python Launcher).

**Исправление:**  
`.vscode/tasks.json` → строка 85

```json
// БЫЛО:
"Set-Location -LiteralPath 'd:\\bybit_strategy_tester_v2'; python background_diagnostic_service.py"

// СТАЛО:
"Set-Location -LiteralPath 'd:\\bybit_strategy_tester_v2'; py background_diagnostic_service.py"
```

**Статус:** ✅ **ИСПРАВЛЕНО**

---

## 🔴 ПРОБЛЕМА 2: Diagnostic Service запускается дважды

**Ошибка:**
- При открытии IDE автоматически запускается Diagnostic Service
- При запуске "Start All Dev" он запускается снова
- Результат: **2 процесса diagnostic service**

**Причина:**  
В `.vscode/tasks.json` у task'а "Start Background Diagnostic Service" было:

```json
"runOptions": {
    "runOn": "folderOpen"  // ← Автозапуск при открытии IDE
}
```

Это приводило к запуску:
1. При открытии IDE → Diagnostic Service запускается
2. При запуске "Start All Dev" → Diagnostic Service запускается **ещё раз**

**Исправление:**  
`.vscode/tasks.json` → строки 95-98

```json
// БЫЛО:
{
    "label": "Start Background Diagnostic Service",
    // ...
    "runOptions": {
        "runOn": "folderOpen"  // ← УДАЛЕНО
    }
}

// СТАЛО:
{
    "label": "Start Background Diagnostic Service",
    // ...
    // runOptions удалён полностью
}
```

**Статус:** ✅ **ИСПРАВЛЕНО**

---

## ⚠️ ПРОБЛЕМА 3: "Tool already exists" в MCP Server (Warning)

**Предупреждения в логе:**
```
[11/10/25 16:47:31] WARNING  Tool already exists: deepseek_refactor_code
[11/10/25 16:47:31] WARNING  Tool already exists: perplexity_search
...
```

**Причина:**  
**Множество тестовых файлов импортируют `server.py` напрямую:**

```python
# Эти файлы вызывают повторную регистрацию @mcp.tool():
test_deepseek_mcp_tools.py:         from server import mcp
test_deepseek_tools_via_list.py:    from server import list_all_tools
test_deepseek_mcp_final.py:         from server import mcp
test_deepseek_10_tools.py:          from server import mcp
test_deepseek_rsi.py:               from server import initialize_providers
test_perplexity_bitcoin.py:         from server import _call_perplexity_api
test_ide_integration.py:            from server import get_deepseek_agent
...и ещё 25+ файлов!
```

**Когда возникает:**
1. MCP Server запущен (через `start_mcp_server.ps1`)
2. Запускается любой тест (например, `py test_deepseek_mcp_tools.py`)
3. Тест импортирует `server.py` → **Все @mcp.tool() регистрируются повторно**
4. FastMCP выдаёт WARNING "Tool already exists"

**Это НЕ критично** (warnings, не errors), но засоряет логи.

**Решение (долгосрочное):**  
Рефакторинг структуры:
- Переместить @mcp.tool() в отдельный модуль `tools.py`
- В `server.py` только запуск сервера
- В тестах импортировать `tools.py`, а не `server.py`

**Решение (краткосрочное):**  
Игнорировать warnings (они не влияют на работу).

**Статус:** ⚠️ **NON-CRITICAL** (требует рефакторинга)

---

## 📊 ПРАВИЛЬНАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ ЗАПУСКА

### Автоматический запуск при открытии IDE

**Запускается только 1 task автоматически:**
```json
{
    "label": "Start Perplexity MCP Server",
    "runOptions": {
        "runOn": "folderOpen"  // ← Единственный автозапуск
    }
}
```

**Результат:**  
При открытии проекта → **Только MCP Server** запускается автоматически.

### Ручной запуск всех сервисов

**Через меню:**
1. `Terminal` → `Run Task...` → `Start All Dev`

**Или через команду:**
```json
// "Start All Dev" task запускает:
"dependsOn": [
    "Start Postgres and migrate",      // Terminal 1
    "Start backend (uvicorn)",         // Terminal 2
    "Start frontend (vite)",           // Terminal 3
    "Start Perplexity MCP Server",     // Terminal 4 (уже запущен)
    "Start Background Diagnostic Service"  // Terminal 5 (запускается)
]
```

**Результат:**  
Все 5 сервисов запускаются (MCP Server уже работает, остальные стартуют).

---

## ✅ ИТОГОВАЯ КОНФИГУРАЦИЯ

### .vscode/tasks.json (финальная версия)

```json
{
    "label": "Start Perplexity MCP Server",
    "type": "shell",
    "command": "powershell",
    "args": [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "d:\\bybit_strategy_tester_v2\\scripts\\start_mcp_server.ps1"
    ],
    "isBackground": true,
    "problemMatcher": [],
    "group": "build",
    "presentation": {
        "reveal": "silent",
        "panel": "shared"
    },
    "runOptions": {
        "runOn": "folderOpen"  // ← ТОЛЬКО MCP Server автозапускается
    }
},
{
    "label": "Start Background Diagnostic Service",
    "type": "shell",
    "command": "powershell",
    "args": [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "Set-Location -LiteralPath 'd:\\bybit_strategy_tester_v2'; py background_diagnostic_service.py"
    ],
    "isBackground": true,
    "problemMatcher": [],
    "group": "build",
    "presentation": {
        "reveal": "always",   // ← Терминал виден
        "panel": "dedicated"  // ← Отдельная панель
    }
    // runOptions удалён! ← НЕ автозапускается
}
```

---

## 🎯 КАК ПРОВЕРИТЬ ИСПРАВЛЕНИЯ

### Шаг 1: Перезапуск IDE

1. **Закройте VS Code** полностью (не Reload Window!)
2. **Откройте проект** заново

**Ожидаемый результат:**
- ✅ Терминал "Start Perplexity MCP Server" запустился автоматически
- ✅ Diagnostic Service **НЕ запустился** (правильно!)
- ✅ Логи MCP Server:
  ```
  Starting MCP server 'Bybit Strategy Tester'
  ParallelDeepSeekClient initialized: 8 keys
  ```

### Шаг 2: Запуск всех сервисов

1. **Нажмите:** `Ctrl+Shift+P`
2. **Выберите:** `Tasks: Run Task`
3. **Выберите:** `Start All Dev`

**Ожидаемый результат:**
- ✅ Терминал 1: Postgres + миграции
- ✅ Терминал 2: Backend (uvicorn)
- ✅ Терминал 3: Frontend (vite)
- ✅ Терминал 4: MCP Server (уже работает)
- ✅ Терминал 5: **Background Diagnostic Service** (запустился, виден!)

**Логи Diagnostic Service:**
```
2025-11-10 16:50:00 [INFO] 🚀 BACKGROUND DIAGNOSTIC SERVICE STARTING
2025-11-10 16:50:00 [INFO] 📦 Загрузка API ключей...
2025-11-10 16:50:00 [INFO] ✅ DeepSeek: 8 ключей
2025-11-10 16:50:00 [INFO] ✅ Perplexity: 4 ключей
2025-11-10 16:50:00 [INFO] ⏳ Ожидание запуска MCP Server (5s)...
2025-11-10 16:50:05 [INFO] ✅ Сервис запущен (проверка каждые 60s)
2025-11-10 16:50:05 [INFO] 📊 Анализ агентов каждые 30 минут
2025-11-10 16:50:05 [INFO] 🔄 Цикл #1 начат
```

### Шаг 3: Проверка отсутствия дубликатов

**Проверьте количество процессов:**

```powershell
# В PowerShell:
Get-Process python | Where-Object { $_.Path -like "*background_diagnostic*" }
```

**Ожидаемый результат:**  
- ✅ **Только 1 процесс** `background_diagnostic_service.py`
- ❌ Если 2+ процесса → закройте все терминалы и перезапустите

---

## 📝 КРАТКОЕ РЕЗЮМЕ

**Исправлено:**
1. ✅ `python` → `py` (Windows PowerShell совместимость)
2. ✅ Удалён `runOn: folderOpen` из Diagnostic Service (нет двойного запуска)
3. ⚠️ Warnings "Tool already exists" → не критично (рефакторинг позже)

**Текущая работа:**
- ✅ MCP Server запускается автоматически при открытии IDE
- ✅ Diagnostic Service запускается только через "Start All Dev"
- ✅ Нет дублирующихся процессов
- ✅ Терминал Diagnostic Service видимый с логами

**Система готова к использованию!** 🚀
