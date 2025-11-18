# 🔧 Fix Docker LSP Error

## Проблема

```
Error: Docker command exited with code 1
docker: error during connect: open //./pipe/dockerDesktopLinuxEngine: 
The system cannot find the file specified.
```

**Причина**: Docker Desktop не запущен, а VS Code пытается использовать Docker LSP расширение.

**Важно**: Эта ошибка **НЕ связана с нашим MCP сервером** - это отдельная проблема с Docker расширением.

---

## ✅ Решение 1: Отключить Docker расширение (РЕКОМЕНДУЮ)

Docker расширение **не нужно** для этого проекта.

### Шаг 1: Откройте Extensions (Расширения)

```
Ctrl+Shift+X
```

### Шаг 2: Найдите Docker расширение

В поиске введите: `@installed docker`

### Шаг 3: Отключите расширение

Найдите: **"Docker" by Microsoft**
- Нажмите на шестерёнку ⚙️
- Выберите: **"Disable (Workspace)"**

### Шаг 4: Перезагрузите VS Code

```
Ctrl+Shift+P → "Developer: Reload Window"
```

---

## 🐳 Решение 2: Запустить Docker Desktop (если нужен Docker)

### Когда Docker НУЖЕН:

- Для запуска Redis в Docker: `docker run -d -p 6379:6379 redis:latest`
- Для запуска PostgreSQL в Docker
- Для контейнеризации приложения

### Как запустить:

1. Откройте **Docker Desktop** (из меню Пуск)
2. Дождитесь: "Docker Desktop is running"
3. Проверьте: `docker ps` (должен работать без ошибок)

---

## 🎯 Что использует наш проект

### ✅ Без Docker (текущая конфигурация)

```
Redis: Установлен локально (redis-server)
PostgreSQL: Локальная установка
Backend: uvicorn backend.app:app
Workers: py -m backend.queue.worker_cli
```

### 🐳 С Docker (опционально)

```
Redis: docker run -d -p 6379:6379 redis:latest
PostgreSQL: docker-compose up postgres
Backend: docker-compose up backend
```

---

## 📝 Текущие настройки (.vscode/settings.json)

Уже добавлены настройки для отключения Docker Language Server:

```json
{
  "docker.languageServer.diagnostics.enabled": false,
  "docker.languageServer.formatter.enabled": false,
  "docker.languageserver.enabled": false,
  "docker.commands.attach": "",
  "docker.commands.build": "",
  "docker.host": ""
}
```

---

## ✅ Проверка после исправления

### 1. Проверить, что ошибки Docker исчезли

```
View → Output → Docker (не должно быть ошибок)
View → Problems (не должно быть Docker ошибок)
```

### 2. Проверить MCP сервер

```
View → Output → MCP Servers
Должно быть: "Starting server agent-to-agent-bridge" ✅
```

### 3. Проверить Backend

```powershell
curl http://localhost:8000/api/v1/health
# Должен вернуть: {"status": "ok"}
```

---

## 🚀 Следующие шаги

После отключения Docker расширения:

1. **Reload VS Code**: `Ctrl+Shift+P` → "Developer: Reload Window"
2. **Проверить MCP**: View → Output → MCP Servers
3. **Протестировать в Copilot**: `@workspace What is Phase 1?`

---

## 📊 Статус компонентов

| Компонент | Требует Docker? | Статус |
|-----------|-----------------|--------|
| Redis | ❌ Нет (локальный) | ✅ RUNNING |
| PostgreSQL | ❌ Нет (локальный) | ✅ RUNNING |
| Backend | ❌ Нет | ✅ RUNNING (port 8000) |
| Queue Workers | ❌ Нет | 🔄 Ready to start |
| MCP Server | ❌ Нет | ⚠️ Needs VS Code reload |

**Вывод**: Docker **НЕ НУЖЕН** для текущей конфигурации проекта.

---

## 💡 Рекомендация

**Отключите Docker расширение** (Решение 1), так как:
- ✅ Не используется в проекте
- ✅ Вызывает ошибки при каждом запуске VS Code
- ✅ Не влияет на функциональность MCP/Agent-to-Agent
- ✅ Ускоряет запуск VS Code

---

Generated: 2025-11-11 21:35:00
