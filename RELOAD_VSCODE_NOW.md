# ✅ MCP Server настроен! Инструкция по перезапуску

## 🎉 Что сделано

- ✅ Создан `mcp_server_wrapper.py` - MCP сервер для Agent-to-Agent
- ✅ Добавлена конфигурация в `.vscode/mcp.json`
- ✅ Backend работает на `http://localhost:8000`
- ✅ 4 новых tool готовы к использованию

---

## 🔄 ПЕРЕЗАПУСТИТЕ VS CODE СЕЙЧАС

### Вариант 1: Быстрый перезапуск (рекомендуется)

**Нажмите:**
1. `Ctrl + Shift + P`
2. Наберите: `Developer: Reload Window`
3. Enter

⏱️ Займёт 5 секунд

### Вариант 2: Полный перезапуск

1. Закройте VS Code
2. Откройте заново
3. Откройте эту же папку

⏱️ Займёт 10-15 секунд

---

## ✅ Как проверить что MCP Server работает

### После перезапуска VS Code:

**Шаг 1: Откройте Output панель**
- `View > Output` (или Ctrl+Shift+U)
- В dropdown выберите: `MCP Servers` или `GitHub Copilot`

**Шаг 2: Проверьте логи**
Должны увидеть:
```
[agent-to-agent-bridge] Starting...
[agent-to-agent-bridge] Connected to backend
[agent-to-agent-bridge] 4 tools registered
```

**Шаг 3: Откройте Copilot Chat**
- Нажмите на иконку Copilot в боковой панели
- Или: `Ctrl + Shift + P` → `GitHub Copilot Chat: Open`

**Шаг 4: Проверьте доступные tools**
В Copilot Chat наберите:
```
@workspace What tools are available?
```

Должны увидеть в списке:
- ✅ send_to_deepseek
- ✅ send_to_perplexity
- ✅ get_consensus
- ✅ start_conversation

---

## 🎯 Примеры использования

### Пример 1: Простой вопрос
```
User: @workspace Explain what is RSI indicator
Copilot: [автоматически использует send_to_deepseek]
```

### Пример 2: Консенсус от нескольких агентов
```
User: @workspace Get consensus: Best Python library for backtesting?
Copilot: [использует get_consensus с DeepSeek + Perplexity]
```

### Пример 3: Явный вызов
```
User: @agent-to-agent-bridge send_to_deepseek "Analyze this trading strategy"
Copilot: [напрямую отправит в DeepSeek]
```

### Пример 4: Анализ кода
```
# Выделите код в редакторе
# В Copilot Chat:
User: @workspace Explain this code and suggest improvements
Copilot: [использует send_to_deepseek с контекстом кода]
```

---

## 🐛 Troubleshooting

### Проблема: MCP Server не стартует

**Проверка 1: Backend работает?**
```powershell
# В терминале:
curl http://localhost:8000/api/v1/agent/health
```

Если не работает:
```powershell
py run_backend.py
```

**Проверка 2: Python доступен?**
```powershell
python --version
# Должна быть 3.8+
```

**Проверка 3: Зависимости установлены?**
```powershell
python -c "import httpx, loguru; print('OK')"
```

Если ошибка:
```powershell
pip install httpx loguru
```

### Проблема: Copilot не видит tools

1. Проверьте Output панель → `MCP Servers`
2. Найдите ошибки от `agent-to-agent-bridge`
3. Перезапустите VS Code полностью (не Reload Window)

### Проблема: Tools не работают

**Проверка: Backend отвечает?**
```powershell
# Тест через CLI:
py cli_send_to_deepseek.py "Test message"
```

Если CLI работает, но Copilot нет:
1. Проверьте `.vscode/mcp.json` (правильные пути?)
2. Проверьте логи MCP сервера в Output панели
3. Перезапустите VS Code

---

## 📊 Что изменилось

### До настройки:
```
GitHub Copilot
  ↓
  ❌ Ограничение 128 tools
  ❌ Не видит DeepSeek/Perplexity
```

### После настройки:
```
GitHub Copilot
  ↓
  ✅ MCP Protocol
  ↓
  agent-to-agent-bridge (mcp_server_wrapper.py)
  ↓
  FastAPI Backend (port 8000)
  ↓
  ✅ DeepSeek Agent (8 keys)
  ✅ Perplexity Agent (8 keys)
```

---

## 🚀 Следующие шаги

1. **СЕЙЧАС:** Перезапустить VS Code (Ctrl+Shift+P → Reload Window)
2. Проверить Output панель → MCP Servers
3. Открыть Copilot Chat
4. Попробовать: `@workspace What is machine learning?`
5. Наслаждаться! 🎉

---

## 📝 Дополнительная информация

- **Полная документация:** `MCP_SERVER_SETUP.md`
- **Простое объяснение:** `HOW_IT_WORKS_SIMPLE.md`
- **Production guide:** `AGENT_SYSTEM_PRODUCTION_READY.md`
- **CLI альтернатива:** `py cli_send_to_deepseek.py "question"`

---

## ✅ Checklist перед использованием

- [x] Backend запущен (port 8000)
- [x] mcp_server_wrapper.py создан
- [x] .vscode/mcp.json настроен
- [ ] VS Code перезапущен ← **СДЕЛАЙ ЭТО СЕЙЧАС!**
- [ ] Проверены логи в Output панели
- [ ] Протестирован в Copilot Chat

---

**🔄 ПЕРЕЗАПУСТИ VS CODE ПРЯМО СЕЙЧАС!**

`Ctrl + Shift + P` → `Developer: Reload Window`

После перезапуска GitHub Copilot сможет использовать DeepSeek и Perplexity как обычные tools! 🚀
