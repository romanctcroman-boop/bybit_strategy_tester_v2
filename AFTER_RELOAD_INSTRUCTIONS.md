# ✅ VS Code перезапущен! Что дальше?

## 📊 Текущий статус

✅ **Backend**: Работает на port 8000 (healthy)  
✅ **MCP конфигурация**: Настроена (.vscode/mcp.json)  
✅ **MCP Server Wrapper**: Готов (mcp_server_wrapper.py)  
✅ **VS Code**: Перезапущен  

---

## 🔍 Проверка что MCP Server работает

### Шаг 1: Откройте Output панель

**В VS Code:**
- `View → Output` (или `Ctrl+Shift+U`)
- В выпадающем списке выберите: **`MCP Servers`**

### Шаг 2: Найдите логи agent-to-agent-bridge

**Что искать:**
```
[agent-to-agent-bridge] Starting MCP server...
[agent-to-agent-bridge] Connected to backend at http://localhost:8000
[agent-to-agent-bridge] Registered 4 tools
```

**Если видите ошибки:**
- Проверьте что Backend запущен: `http://localhost:8000/api/v1/agent/health`
- Проверьте что Python доступен: `python --version`
- Проверьте зависимости: `pip list | findstr httpx`

### Шаг 3: Откройте GitHub Copilot Chat

**Где найти:**
- Иконка Copilot в левой боковой панели
- Или: `Ctrl+Shift+I`
- Или: Command Palette (`Ctrl+Shift+P`) → "GitHub Copilot Chat: Open"

### Шаг 4: Протестируйте Agent-to-Agent

**Попробуйте в Copilot Chat:**

```
@workspace What is machine learning?
```

**Copilot должен:**
1. Обнаружить agent-to-agent-bridge
2. Использовать send_to_deepseek tool
3. Отправить запрос в Backend
4. Получить ответ от DeepSeek
5. Показать результат

---

## 🎯 Примеры для тестирования

### Тест 1: Простой вопрос
```
@workspace Explain RSI indicator in trading
```

### Тест 2: Консенсус
```
@workspace Get consensus: Best Python library for backtesting?
```

### Тест 3: Анализ кода
```
# Выделите код в редакторе
# Затем в Copilot Chat:
@workspace Explain this code and suggest improvements
```

### Тест 4: Явный вызов tool
```
@agent-to-agent-bridge send_to_deepseek "What is cryptocurrency?"
```

---

## ⚠️ Важно знать

### MCP Server запускается лениво (lazy start)

**Это означает:**
- MCP Server НЕ запустится при старте VS Code
- Он запустится **при первом использовании** в Copilot Chat
- Первый запрос может занять 5-10 секунд
- Последующие запросы будут быстрее (2-5 секунд)

### Если MCP Server не стартует

**Причина 1: Backend не запущен**
```powershell
# Проверка:
curl http://localhost:8000/api/v1/agent/health

# Если не работает:
py run_backend.py
```

**Причина 2: Python не в PATH**
```powershell
# Проверка:
python --version

# Если ошибка - добавить Python в PATH
```

**Причина 3: Зависимости не установлены**
```powershell
# Проверка:
pip show httpx

# Если нет:
pip install httpx loguru
```

---

## 🔧 Альтернатива: CLI всегда работает

**Если MCP в Copilot не заработает сразу**, можно использовать CLI:

```powershell
# Простой вопрос
py cli_send_to_deepseek.py "Your question here"

# Интерактивный режим
py cli_send_to_deepseek.py
```

CLI работает независимо от MCP конфигурации!

---

## 📋 Checklist

Отметьте что уже сделано:

- [x] Backend запущен (port 8000)
- [x] VS Code перезапущен
- [x] MCP конфигурация добавлена
- [ ] Открыта Output панель → MCP Servers ← **СДЕЛАЙТЕ**
- [ ] Проверены логи agent-to-agent-bridge
- [ ] Открыт Copilot Chat
- [ ] Протестирован запрос в Copilot
- [ ] Получен ответ от DeepSeek ✨

---

## 🎉 Когда всё работает

**Вы увидите в Copilot Chat:**

```
User: @workspace What is machine learning?

Copilot: [Using agent-to-agent-bridge: send_to_deepseek]
Machine learning is a subset of artificial intelligence...
[Detailed explanation from DeepSeek]
```

**Теперь GitHub Copilot может:**
- ✅ Отправлять запросы в DeepSeek
- ✅ Отправлять запросы в Perplexity
- ✅ Получать консенсус от нескольких агентов
- ✅ Запускать multi-turn разговоры
- ✅ Всё это БЕЗ ограничения на 128 tools!

---

## 📚 Документация

- **`RELOAD_VSCODE_NOW.md`** ← Вы здесь
- **`MCP_SERVER_SETUP.md`** - Полная техническая документация
- **`HOW_IT_WORKS_SIMPLE.md`** - Простое объяснение работы системы
- **`AGENT_SYSTEM_PRODUCTION_READY.md`** - Production guide

---

## 💡 Следующий шаг

**ОТКРОЙТЕ OUTPUT ПАНЕЛЬ ПРЯМО СЕЙЧАС:**

1. `View → Output` (Ctrl+Shift+U)
2. Выберите "MCP Servers" из dropdown
3. Посмотрите логи agent-to-agent-bridge
4. Откройте Copilot Chat
5. Попробуйте: `@workspace What is AI?`

**Удачи! 🚀**
