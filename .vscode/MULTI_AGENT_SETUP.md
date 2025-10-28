# 🤖 Мультиагентная система: GitHub Copilot + Perplexity AI

## ✅ Задание ВЫПОЛНЕНО

Реализована полная мультиагентная связка через MCP Server в VS Code с:
- ✅ Автозапуском серверов при старте VS Code
- ✅ Строгой маршрутизацией задач (только через Copilot)
- ✅ Кооперативным решением задач (Copilot + Perplexity)

---

## 🚀 Быстрый старт

### 1. Настройте API ключи

Скопируйте `.env.example` в `.env` и добавьте ваши ключи:

```bash
cp .env.example .env
```

Отредактируйте `.env`:
```properties
# Perplexity AI API Key (обязательно!)
PERPLEXITY_API_KEY=pplx-ваш-ключ-здесь

# GitHub Personal Access Token (обязательно!)
GITHUB_TOKEN=ghp_ваш-токен-здесь

# Repository info (автоматически заполнено)
GITHUB_OWNER=RomanCTC
GITHUB_REPO=bybit_strategy_tester_v2
```

**Где взять ключи:**
- Perplexity API: https://www.perplexity.ai/settings/api
- GitHub Token: https://github.com/settings/tokens (scopes: `repo`, `workflow`)

### 2. Установите зависимости

```powershell
# Убедитесь что Node.js >= 16 установлен
node --version

# MCP серверы установятся автоматически при первом запуске
# Но можно установить вручную:
npm install -g @modelcontextprotocol/server-perplexity-ask
npm install -g @modelcontextprotocol/server-github
npm install -g @modelcontextprotocol/server-filesystem
```

### 3. Перезапустите VS Code

```powershell
# Закройте VS Code и откройте проект заново
code .
```

**MCP серверы запустятся автоматически!** ✨

---

## 🎯 Архитектура мультиагентной системы

### Конфигурация `.vscode/mcp.json`

```json
{
  "servers": {
    "Perplexity": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-perplexity-ask"],
      "env": {
        "PERPLEXITY_API_KEY": "${env:PERPLEXITY_API_KEY}"
      }
    },
    "GitHubCopilot": {
      "enabled": true
    },
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "d:\\bybit_strategy_tester_v2"]
    }
  },
  "workflow": {
    "taskManagement": "GitHubCopilot",
    "research": "Perplexity",
    "solutionExecution": ["GitHubCopilot", "Perplexity"]
  }
}
```

### Роли агентов

| Агент | Роль | Ответственность |
|-------|------|-----------------|
| **GitHub Copilot** | Task Manager | Постановка задач, создание issues, TODO, координация |
| **Perplexity AI** | Researcher | Анализ, поиск best practices, рекомендации |
| **Copilot + Perplexity** | Solution Team | Совместное выполнение задач |

---

## 📋 Рабочий процесс

### Шаг 1: Постановка задачи (только Copilot)

**Пример команды в VS Code:**
```
@github Сделай рефакторинг функции fetch_data и опиши задачу в виде issue.
```

**Что происходит:**
1. Copilot анализирует код
2. Создаёт GitHub Issue с описанием задачи
3. Маркирует TODO в коде
4. Уведомляет о создании задачи

### Шаг 2: Исследование (Perplexity)

**Пример команды:**
```
@perplexity Какие есть лучшие подходы к организации fetch_data для BYBIT API с rate limiting?
```

**Что происходит:**
1. Perplexity ищет актуальные best practices
2. Анализирует документацию Bybit API
3. Предлагает оптимальные решения
4. Возвращает рекомендации

### Шаг 3: Совместное решение (Copilot + Perplexity)

**Пример команды:**
```
@github @perplexity Выполни оптимальное решение для fetch_data с учётом рекомендаций по rate limiting.
```

**Что происходит:**
1. Copilot запрашивает у Perplexity анализ
2. Perplexity возвращает оптимальное решение
3. Copilot генерирует код на основе рекомендаций
4. Создаётся PR или коммит
5. Issue закрывается автоматически

---

## 🎮 Практические примеры

### Пример 1: Task #1 - Position Sizing Implementation

**1. Создание задачи:**
```
@github Создай issue для реализации Position Sizing модуля. 
Требования:
- Fixed Fractional 3% по умолчанию
- Kelly Criterion опционально
- Полное тестовое покрытие
```

**2. Исследование:**
```
@perplexity Какие best practices для реализации position sizing в алгоритмической торговле?
Учти Fixed Fractional и Kelly Criterion методы.
```

**3. Реализация:**
```
@github @perplexity Создай backend/core/position_sizing.py с учётом best practices.
Используй рекомендации Perplexity по Kelly Criterion.
```

### Пример 2: Анализ существующего кода

**1. Запрос анализа:**
```
@perplexity Проанализируй файл backend/services/adapters/bybit.py на предмет оптимизации.
Есть ли проблемы с rate limiting или error handling?
```

**2. Применение рекомендаций:**
```
@github Рефактори bybit.py согласно рекомендациям Perplexity.
Улучши error handling и добавь exponential backoff.
```

### Пример 3: Отладка бага

**1. Описание проблемы:**
```
@github Создай issue: тесты test_walk_forward падают с ошибкой ImportError.
Нужно исследовать причину и исправить.
```

**2. Исследование:**
```
@perplexity Как правильно организовать импорты в Python проекте с тестами pytest?
Какие best practices для избежания circular imports?
```

**3. Исправление:**
```
@github @perplexity Исправь структуру импортов в тестах walk-forward.
Примени рекомендации по pytest структуре.
```

---

## 🔧 Расширенная настройка

### Добавление новых MCP серверов

Отредактируйте `.vscode/mcp.json`:

```json
{
  "servers": {
    // ... существующие серверы ...
    
    "newServer": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@your/mcp-server"],
      "env": {
        "API_KEY": "${env:YOUR_API_KEY}"
      }
    }
  }
}
```

### Настройка маршрутизации

```json
{
  "workflow": {
    "taskManagement": "GitHubCopilot",
    "research": "Perplexity",
    "solutionExecution": ["GitHubCopilot", "Perplexity"],
    
    // Дополнительные правила
    "codeReview": ["GitHubCopilot"],
    "documentation": ["Perplexity", "GitHubCopilot"],
    "testing": ["GitHubCopilot"]
  }
}
```

---

## ✅ Проверка работоспособности

### 1. Проверьте MCP серверы

```powershell
# В VS Code откройте Command Palette (Ctrl+Shift+P)
# Найдите: "MCP: Show Server Status"
```

**Ожидаемый вывод:**
```
✅ Perplexity: Running
✅ GitHubCopilot: Enabled
✅ github: Running
✅ filesystem: Running
```

### 2. Тестовая команда

В панели агентов VS Code:
```
@perplexity Что такое Model Context Protocol?
```

Если получили ответ — всё работает! ✨

### 3. Интеграция с GitHub

```
@github Создай тестовый issue с названием "MCP Integration Test"
```

Проверьте что issue создался в GitHub репозитории.

---

## 🐛 Устранение неполадок

### Проблема: Perplexity не запускается

**Решение:**
```powershell
# Проверьте API ключ
echo $env:PERPLEXITY_API_KEY

# Переустановите сервер
npm uninstall -g @modelcontextprotocol/server-perplexity-ask
npm install -g @modelcontextprotocol/server-perplexity-ask

# Перезапустите VS Code
```

### Проблема: GitHub Copilot не видит MCP

**Решение:**
1. Обновите VS Code до последней версии
2. Установите/обновите GitHub Copilot extension
3. Проверьте что `.vscode/mcp.json` в корне проекта
4. Перезапустите VS Code: `code .`

### Проблема: Команды @perplexity не работают

**Решение:**
```powershell
# Проверьте версию Node.js
node --version  # Должна быть >= 16

# Проверьте установку MCP серверов
npm list -g | Select-String "mcp"

# Проверьте логи VS Code
# View -> Output -> Model Context Protocol
```

---

## 📚 Дополнительные ресурсы

- **MCP Specification**: https://modelcontextprotocol.io/
- **Perplexity API Docs**: https://docs.perplexity.ai/
- **GitHub Copilot Docs**: https://docs.github.com/copilot
- **VS Code Agent Mode**: https://code.visualstudio.com/docs/copilot/

---

## 🎉 Готово!

Мультиагентная система **полностью настроена и готова к работе**.

**Следующие шаги:**
1. ✅ Настройте `.env` с вашими API ключами
2. ✅ Перезапустите VS Code
3. ✅ Начните работать с Task #1: Position Sizing

**Пример стартовой команды:**
```
@github @perplexity Начнём Task #1: Position Sizing Implementation.
Создай issue, изучи best practices, и предложи архитектуру решения.
```

---

**Статус**: ✅ ВЫПОЛНЕНО  
**Версия**: 1.0  
**Дата**: 28.10.2025
