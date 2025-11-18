# 🤖 Multi-Agent AI для VS Code - Quick Start

## ⚡ 3-минутная установка

### 1. Настройка API ключей

```bash
# Создайте .env файл в корне проекта (d:\bybit_strategy_tester_v2\.env)
PERPLEXITY_API_KEY=pplx-xxxxxxxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxx
```

**Где получить ключи:**
- Perplexity: https://www.perplexity.ai/settings/api (уже настроен ✅)
- DeepSeek: https://platform.deepseek.com/api_keys

### 2. Копирование VS Code конфигураций

```bash
# Задачи для Command Palette (Ctrl+Shift+P)
cp .vscode/ai-tasks.json .vscode/tasks.json

# Горячие клавиши (необязательно)
# cp .vscode/ai-keybindings.json .vscode/keybindings.json
```

### 3. Запуск MCP сервера

```powershell
cd D:\bybit_strategy_tester_v2
.\.venv\Scripts\Activate.ps1
python mcp-server\server.py
```

**Ожидаемый вывод:**
```
🚀 Starting Bybit Strategy Tester MCP Server v3.0 (MULTI-AGENT)...
🔧 Available Tools: 🎉 51 total
   ├─ 🤖 Multi-Agent Tools: 4 (route, pipeline, list_agents, routing_info)
   ...
🎯 Multi-Agent Architecture:
   ├─ Copilot (IDE integration)
   ├─ DeepSeek (code generation & reasoning)
   └─ Sonar Pro (logic analysis & research)
✅ Server ready on http://localhost:8765
```

## 🎯 Использование

### Вариант 1: Горячие клавиши (самый быстрый)

| Hotkey | Action | Agent |
|--------|--------|-------|
| `Ctrl+Shift+G` | Generate Code | DeepSeek |
| `Ctrl+Shift+R` | Refactor Code | DeepSeek |
| `Ctrl+Shift+A` | Analyze Logic | Sonar Pro |
| `Ctrl+Shift+E` | Explain Selection | Sonar Pro |
| `Ctrl+Shift+D` | Generate Docs | DeepSeek |

**Workflows (цепочки задач):**

| Hotkey | Workflow | Steps |
|--------|----------|-------|
| `Ctrl+Shift+W` → `Ctrl+Shift+C` | Code Review | Analyze → Improve → Summarize |
| `Ctrl+Shift+W` → `Ctrl+Shift+S` | Strategy Development | Research → Generate → Document |
| `Ctrl+Shift+W` → `Ctrl+Shift+R` | Refactor with Audit | Refactor → Audit → Finalize |

### Вариант 2: Command Palette

1. Нажмите `Ctrl+Shift+P`
2. Введите "Tasks: Run Task"
3. Выберите задачу (например, "AI: Generate Code")
4. Введите prompt

### Вариант 3: CLI (командная строка)

```powershell
# Активировать venv
.\.venv\Scripts\Activate.ps1

# Простая задача
python mcp-server\vscode_integration.py --task code-generation --prompt "Create a FastAPI endpoint for health check"

# Code Review для файла
python mcp-server\vscode_integration.py --workflow code-review --file backend\core\backtest.py

# Разработка стратегии
python mcp-server\vscode_integration.py --workflow strategy-development --prompt "RSI mean reversion with dynamic thresholds"
```

## 📋 Примеры использования

### 1. Генерация кода

**Через hotkey:**
1. Нажмите `Ctrl+Shift+G`
2. Введите: "Create a Pydantic model for user registration with email validation"
3. Получите готовый код от DeepSeek

**Через CLI:**
```powershell
python mcp-server\vscode_integration.py `
  --task code-generation `
  --prompt "Create a Pydantic model for user registration with email validation"
```

### 2. Code Review

**Через hotkey:**
1. Откройте файл `backend\core\backtest.py`
2. Нажмите `Ctrl+Shift+W` → `Ctrl+Shift+C`
3. Получите:
   - **Step 1:** Анализ логики (Sonar Pro)
   - **Step 2:** Улучшенную версию (DeepSeek)
   - **Step 3:** Summary отчет (Sonar Pro)

**Через CLI:**
```powershell
python mcp-server\vscode_integration.py `
  --workflow code-review `
  --file backend\core\backtest.py
```

### 3. Разработка торговой стратегии

**Через hotkey:**
1. Нажмите `Ctrl+Shift+W` → `Ctrl+Shift+S`
2. Введите описание: "RSI mean reversion with dynamic thresholds"
3. Получите:
   - **Step 1:** Research findings (Sonar Pro)
   - **Step 2:** Полный код стратегии (DeepSeek)
   - **Step 3:** Документацию (DeepSeek)

**Через CLI:**
```powershell
python mcp-server\vscode_integration.py `
  --workflow strategy-development `
  --prompt "RSI mean reversion with dynamic thresholds"
```

### 4. Рефакторинг с аудитом

**Через hotkey:**
1. Откройте файл для рефакторинга
2. Нажмите `Ctrl+Shift+W` → `Ctrl+Shift+R`
3. Получите улучшенный код с безопасностью + производительностью

**Через CLI:**
```powershell
python mcp-server\vscode_integration.py `
  --workflow refactor-with-audit `
  --file frontend\src\components\BacktestResults.tsx
```

## 🔧 Доступные агенты

| Agent | API | Специализация | Task Types |
|-------|-----|---------------|------------|
| 🧑‍💻 **Copilot** | VS Code Extension | IDE integration, autocomplete | (integrated) |
| 🤖 **DeepSeek** | HTTP API | Code generation, refactoring, documentation | code-generation, refactoring, documentation, code-review-improvements |
| 🔍 **Sonar Pro** | Perplexity API | Logic analysis, research, audit | logic-analysis, explain, research, audit, market-analysis |

## 🧪 Проверка работы

### Test 1: API Keys

```powershell
.\.venv\Scripts\Activate.ps1
python -c "import os; print('Perplexity:', 'OK' if os.getenv('PERPLEXITY_API_KEY') else 'MISSING'); print('DeepSeek:', 'OK' if os.getenv('DEEPSEEK_API_KEY') else 'MISSING')"
```

**Ожидаемый результат:**
```
Perplexity: OK
DeepSeek: OK
```

### Test 2: MCP Server

```powershell
.\.venv\Scripts\Activate.ps1
python mcp-server\server.py
# Должен запуститься без ошибок
# Нажмите Ctrl+C для остановки
```

### Test 3: CLI Integration

```powershell
.\.venv\Scripts\Activate.ps1

# Простой запрос к Sonar Pro
python mcp-server\vscode_integration.py `
  --task explain `
  --prompt "What is FastAPI?"
```

**Ожидаемый результат:**
```json
{
  "status": "success",
  "agent": "sonar-pro",
  "result": "FastAPI is a modern, fast (high-performance)..."
}
```

### Test 4: VS Code Tasks

1. Откройте VS Code
2. Нажмите `Ctrl+Shift+P`
3. Введите "Tasks: Run Task"
4. Должны увидеть 8 AI задач:
   - AI: Generate Code (DeepSeek)
   - AI: Refactor Code (DeepSeek)
   - AI: Analyze Logic (Sonar Pro)
   - AI: Code Review Workflow
   - AI: Strategy Development Workflow
   - AI: Refactor with Audit Workflow
   - AI: Explain Code (Sonar Pro)
   - AI: Generate Documentation (DeepSeek)

## 📚 Полная документация

- **Архитектура:** [docs/MULTI_AGENT.md](docs/MULTI_AGENT.md)
- **MCP Сервер:** [mcp-server/README.md](mcp-server/README.md)
- **Dark Mode:** [docs/DARK_MODE.md](docs/DARK_MODE.md)
- **E2E Testing:** [frontend/tests/README.md](frontend/tests/README.md)

## 🎨 Типы задач (18 total)

### DeepSeek Tasks
- `code-generation` - Генерация кода
- `refactoring` - Рефакторинг
- `documentation` - Генерация документации
- `code-review-improvements` - Улучшения после ревью
- `debugging` - Отладка
- `test-generation` - Генерация тестов

### Sonar Pro Tasks
- `logic-analysis` - Анализ логики
- `explain` - Объяснение кода
- `research` - Исследование
- `audit` - Аудит безопасности
- `market-analysis` - Анализ рынка
- `code-review-summary` - Summary ревью

### Copilot Tasks
- `autocomplete` - Автодополнение (VS Code)
- `inline-suggestions` - Inline предложения (VS Code)

## 🔥 Pro Tips

1. **Используйте workflows для сложных задач** - они автоматически создают reasoning chains
2. **Добавляйте context через --context** - передавайте дополнительную информацию агентам
3. **Проверяйте логи MCP сервера** - request_id помогает отследить проблемы
4. **Настройте горячие клавиши** - копируйте `ai-keybindings.json` для быстрого доступа
5. **Используйте --file для file-based tasks** - автоматически читает содержимое

## ⚠️ Troubleshooting

### Проблема: "DEEPSEEK_API_KEY not found"

**Решение:**
```powershell
# Добавьте в .env файл
echo "DEEPSEEK_API_KEY=sk-your-key-here" >> .env
```

### Проблема: "Connection refused to localhost:8765"

**Решение:**
```powershell
# Убедитесь, что MCP сервер запущен
python mcp-server\server.py
```

### Проблема: "Task 'AI: Generate Code' not found"

**Решение:**
```powershell
# Скопируйте tasks в правильное место
cp .vscode\ai-tasks.json .vscode\tasks.json
# Перезапустите VS Code
```

### Проблема: Hotkeys не работают

**Решение:**
```powershell
# Скопируйте keybindings
cp .vscode\ai-keybindings.json .vscode\keybindings.json
# Перезапустите VS Code
# Или используйте Command Palette (Ctrl+Shift+P)
```

## 🚀 Готово!

Теперь у вас **мультиагентная AI система** интегрированная в VS Code:

✅ **DeepSeek** - генерация и рефакторинг кода  
✅ **Sonar Pro** - анализ логики и исследование  
✅ **Copilot** - автодополнение в IDE  
✅ **8 горячих клавиш** для быстрого доступа  
✅ **3 workflow** для сложных задач  
✅ **CLI** для автоматизации  

**Начните с простого:**
1. Нажмите `Ctrl+Shift+G`
2. Введите: "Create a hello world FastAPI endpoint"
3. Магия! ✨

---

**Версия:** 3.0 (MULTI-AGENT)  
**Последнее обновление:** 2025-01-XX  
**Поддержка:** [docs/MULTI_AGENT.md](docs/MULTI_AGENT.md)
