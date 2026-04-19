# Qwen Skills — Bybit Strategy Tester v2

> **Назначение:** Специализированные навыки для AI-ассистента Qwen.
> **Версия:** 1.0 (2026-02-26)
> **Статус:** ✅ Готово к использованию

---

## 📚 Что такое скилы?

**Скилы (skills)** — это специализированные инструкции и паттерны для AI-ассистента Qwen, которые определяют:

- **Рабочий процесс** для конкретного типа задач
- **Паттерны кода** и лучшие практики
- **Чеклисты** для верификации результатов
- **Примеры** использования и тестирования

---

## 🎯 Доступные скилы

### Базовые скилы

| Скил | Директория | Назначение | Когда использовать |
|------|------------|------------|-------------------|
| **Base Skills** | [`SKILL.md`](SKILL.md) | Общие настройки проекта | Всегда активен |
| **Code Development** | [`code-development/`](code-development/SKILL.md) | Написание нового кода | Добавление функциональности |
| **Safe Refactoring** | [`safe-refactoring/`](safe-refactoring/SKILL.md) | Безопасный рефакторинг | Улучшение структуры кода |
| **Debugging** | [`debugging/`](debugging/SKILL.md) | Отладка и исправление багов | Поиск и устранение ошибок |
| **Test Generation** | [`test-generation/`](test-generation/SKILL.md) | Написание тестов | Покрытие кода тестами |
| **Documentation** | [`documentation/`](documentation/SKILL.md) | Генерация документации | Документирование кода |

### Специализированные скилы

| Скил | Директория | Назначение | Когда использовать |
|------|------------|------------|-------------------|
| **Backtest Execution** | [`backtest-execution/`](backtest-execution/SKILL.md) | Запуск бэктестов | Тестирование стратегий |
| **Strategy Development** | [`strategy-development/`](strategy-development/SKILL.md) | Создание стратегий | Разработка новых стратегий |

---

## 🚀 Как использовать

### Автоматический выбор скила

Qwen автоматически выбирает подходящий скил на основе задачи:

```
Задача → Анализ → Выбор скила → Применение паттернов → Выполнение
```

### Примеры задач и соответствующих скилов

| Задача | Скил |
|--------|------|
| "Добавь новый API endpoint для экспорта данных" | `code-development` |
| "Раздели этот файл на модули" | `safe-refactoring` |
| "Найди баг в расчёте Sharpe ratio" | `debugging` |
| "Напиши тесты для BacktestEngine" | `test-generation` |
| "Задокументируй класс MetricsCalculator" | `documentation` |
| "Запусти бэктест для RSI стратегии" | `backtest-execution` |
| "Создай стратегию MACD кроссовер" | `strategy-development` |

---

## 📖 Структура скила

Каждый скил содержит:

```
skill-name/
└── SKILL.md          # Основное описание скила
```

### Содержимое SKILL.md

1. **Overview** — назначение скила
2. **Workflow** — пошаговый процесс выполнения
3. **Code Patterns** — шаблоны кода
4. **Checklist** — контрольный список
5. **Examples** — примеры использования
6. **Testing** — требования к тестам
7. **Related** — ссылки на связанные документы

---

## 🎯 Критические правила

### 1. Commission Rate = 0.0007

```python
# NEVER change without explicit approval
commission_rate = 0.0007  # 0.07% TradingView parity
```

### 2. Engine Selection

```python
# FallbackEngineV4 — gold standard
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
```

### 3. High-Risk Variables

**Всегда делать grep перед изменением:**

```bash
grep -rn "commission_rate" backend/ frontend/
grep -rn "strategy_params" backend/ frontend/
grep -rn "initial_capital" backend/ frontend/
```

---

## 🧪 Development Workflow

### Для простых задач (< 15 минут)

1. Выполнить напрямую
2. Запустить тесты: `pytest tests/ -v`
3. Проверить линтинг: `ruff check . --fix && ruff format .`
4. Обновить `CHANGELOG.md`
5. Сообщить о завершении

### Для сложных задач (> 15 минут)

1. **Анализ:** Прочитать затронутые файлы
2. **План:** Создать план выполнения
3. **Одобрение:** Запросить одобрение плана
4. **Выполнение:** Делать по одному атомарному изменению
5. **Верификация:** Тесты после каждого изменения
6. **Документирование:** Обновить документацию

---

## 📊 Сравнение с другими AI skills

### Анализ существующих решений

| Платформа | Формат | Особенности |
|-----------|--------|-------------|
| **Claude** | `.claude/agents/*.md`, `.claude/commands/*.md` | Агент-ориентированный подход |
| **Copilot** | `.github/skills/*/SKILL.md` | Навыки с чёткой специализацией |
| **Cursor** | `.cursor/rules/*.mdc`, `.cursor/rules/*.md` | Правила с alwaysApply и globs |
| **Gemini** | `.gemini/artifacts/documentation/` | Документация навыков |

### Qwen Skills

| Особенность | Реализация |
|-------------|------------|
| **Формат** | Markdown с YAML frontmatter |
| **Структура** | Иерархическая: `.qwen/skills/*/SKILL.md` |
| **Активация** | Автоматическая по типу задачи |
| **Специализация** | 8 скилов: code, refactor, debug, test, docs, backtest, strategy |

---

## 🔧 Интеграция с проектом

### Конфигурация

- **Главный файл:** `.qwen/QWEN.md` — общая конфигурация
- **Базовые скилы:** `.qwen/skills/SKILL.md` — настройки проекта
- **Специализированные:** `.qwen/skills/*/SKILL.md` — конкретные навыки

### Связанные документы

| Документ | Назначение |
|----------|------------|
| [`CLAUDE.md`](../CLAUDE.md) | Архитектура проекта |
| [`CHANGELOG.md`](../CHANGELOG.md) | История изменений |
| [`docs/DECISIONS.md`](../docs/DECISIONS.md) | Принятые решения |
| [`AGENTS.MD`](../AGENTS.MD) | Глобальные правила агентов |

---

## 📝 Создание нового скила

### Шаблон скила

```markdown
---
name: Skill Name
description: "Brief description of the skill."
---

# Skill Name for Qwen

## Overview

[Description of what this skill does]

## Workflow

### Step 1: [Name]

[Description and examples]

### Step 2: [Name]

[Description and examples]

## Code Patterns

```python
# Example code pattern
```

## Checklist

- [ ] Item 1
- [ ] Item 2
- [ ] Item 3

## Examples

[Concrete examples with explanations]

## Testing

[Test requirements and examples]

## Related

- [Link to related skills]
- [Link to documentation]
```

### Процесс добавления

1. Создать директорию: `.qwen/skills/skill-name/`
2. Создать файл: `.qwen/skills/skill-name/SKILL.md`
3. Обновить этот README
4. Обновить `.qwen/QWEN.md`

---

## 🚀 Быстрый старт

### 1. Прочитать документацию

```bash
# Главная конфигурация
cat .qwen/QWEN.md

# Базовые скилы
cat .qwen/skills/SKILL.md

# Конкретный скил
cat .qwen/skills/code-development/SKILL.md
```

### 2. Использовать в работе

Просто опишите задачу — Qwen автоматически выберет подходящий скил:

```
"Добавь новый индикатор RSI с возможностью выбора источника данных"
→ Code Development + Strategy Development
```

### 3. Проверить результат

```powershell
# Запустить тесты
pytest tests/ -v

# Проверить линтинг
ruff check . --fix && ruff format .

# Убедиться в импортах
python -c "from backend.api.app import app; print('OK')"
```

---

## 📈 Roadmap

### Текущая версия (1.0)

- ✅ 6 базовых скилов
- ✅ 2 специализированных скила
- ✅ Интеграция с проектом
- ✅ Документация

### Планируется (1.1)

- ⏳ API Endpoint skill
- ⏳ Database Operations skill
- ⏳ Metrics Calculator skill
- ⏳ Optimization skill

### Будущие улучшения

- ⏮️ Контекстная активация скилов
- ⏮️ Комбинация нескольких скилов
- ⏮️ Адаптивные паттерны
- ⏮️ Интеграция с MCP

---

## 🤝 Вклад в развитие

### Как улучшить скилы

1. **Заметили пробел?** — Создайте новый скил
2. **Нашли ошибку?** — Исправьте через PR
3. **Есть улучшение?** — Предложите в discussion
4. **Хотите поделиться?** — Добавьте пример использования

### Контакты

- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions
- **Documentation:** `.qwen/skills/`

---

*Создано: 2026-02-26*
*На основе анализа: Claude, Copilot, Cursor, Gemini skills*
*Проект: Bybit Strategy Tester v2*
