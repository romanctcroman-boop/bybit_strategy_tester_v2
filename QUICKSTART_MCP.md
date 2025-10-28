# 🚀 MCP Quick Start (5 минут)

## Шаг 1: Установка (2 минуты)

### Windows
```powershell
cd d:\bybit_strategy_tester_v2
.\scripts\install_mcp.ps1
```

### Linux/Mac
```bash
cd /path/to/bybit_strategy_tester_v2
chmod +x scripts/install_mcp.sh
./scripts/install_mcp.sh
```

---

## Шаг 2: API Ключи (2 минуты)

### Perplexity AI
1. Откройте: https://www.perplexity.ai/settings/api
2. Создайте ключ
3. Скопируйте (начинается с `pplx-`)

### GitHub Token
1. Откройте: https://github.com/settings/tokens
2. "Generate new token (classic)"
3. Выберите scopes: `repo`, `workflow`, `write:packages`, `read:org`
4. Скопируйте (начинается с `ghp_`)

### Добавить в .env
```bash
# Откройте файл .env (или создайте из .env.example)
PERPLEXITY_API_KEY=pplx-ВАXКЛЮЧ
GITHUB_TOKEN=ghp_ВАШКЛЮЧ
```

---

## Шаг 3: Перезапуск (1 минута)

1. Закройте VS Code полностью
2. Откройте проект снова
3. MCP серверы запустятся автоматически!

---

## Шаг 4: Первый запуск (немедленно!)

```
Ctrl+Shift+P
→ Tasks: Run Task
→ Workflow: High Priority Anomalies (4-7)
```

**Или через PowerShell**:
```powershell
.\scripts\mcp_workflow.ps1
Start-AnomalyWorkflow -AnomalyNumbers @(4,5,6,7)
```

---

## ✅ Проверка работы

### Проверить установку
```powershell
npm list -g | Select-String mcp
```

Должны увидеть:
```
@modelcontextprotocol/server-perplexity-ask
@modelcontextprotocol/server-capiton-github
```

### Проверить переменные
```powershell
echo $env:PERPLEXITY_API_KEY
echo $env:GITHUB_TOKEN
```

Должны увидеть ваши ключи.

### Проверить серверы
```powershell
Get-Process | Where-Object {$_.ProcessName -like "*node*"}
```

Должны увидеть процессы Node.js.

---

## 🎯 Что дальше?

### Автоматизация аномалий 4-7
Система автоматически:
1. ✅ Perplexity анализирует проблемы
2. ✅ Capiton создаёт GitHub issues
3. ✅ Perplexity генерирует код
4. ✅ Capiton создаёт Pull Requests

**Экономия времени**: 7 дней → 2-3 дня (60-70%)!

### Мониторинг
```
Ctrl+Shift+P → MCP: Show Metrics
```

### Документация
- **Полное руководство**: `.vscode/MCP_SETUP_GUIDE.md`
- **Интеграция**: `MCP_INTEGRATION.md`
- **Чеклист**: `MCP_CHECKLIST.md`
- **Отчёт**: `MCP_IMPLEMENTATION_REPORT.md`

---

## 🚨 Проблемы?

### Серверы не запускаются
```powershell
.\scripts\install_mcp.ps1
```

### Ключи не работают
- Perplexity: https://www.perplexity.ai/settings/api
- GitHub: https://github.com/settings/tokens

### GitHub интеграция не работает
Проверьте scopes: `repo`, `workflow`, `write:packages`, `read:org`

---

## 📚 Полная документация

- `MCP_SUMMARY.md` - всё в одном месте
- `MCP_INTEGRATION.md` - детальная интеграция
- `.vscode/MCP_SETUP_GUIDE.md` - полное руководство

---

**ГОТОВО! Система запущена и готова к автоматизации! 🎉**
