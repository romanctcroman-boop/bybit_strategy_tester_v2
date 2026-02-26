# Qwen Skills — Bybit Strategy Tester v2

> **Назначение:** Специализированные навыки для AI-ассистента Qwen в проекте Bybit Strategy Tester v2.
> **Версия:** 1.0 (2026-02-26)
> **Стек:** Python 3.14, FastAPI, SQLAlchemy, Pandas, NumPy, Bybit API v5

---

## 📚 Список скилов

| Скил | Назначение | Когда использовать |
|------|------------|-------------------|
| [`code-development`](code-development/) | Написание нового кода, функций, классов | Добавление функциональности |
| [`safe-refactoring`](safe-refactoring/) | Безопасный рефакторинг кода | Улучшение структуры без изменения поведения |
| [`backtest-execution`](backtest-execution/) | Запуск и анализ бэктестов | Тестирование стратегий |
| [`strategy-development`](strategy-development/) | Создание торговых стратегий | Разработка новых стратегий |
| [`api-endpoint`](api-endpoint/) | Добавление API endpoints | Расширение API |
| [`database-operations`](database-operations/) | Работа с БД и миграциями | Изменение схемы данных |
| [`test-generation`](test-generation/) | Написание тестов | Покрытие кода тестами |
| [`documentation`](documentation/) | Генерация документации | Документирование кода |
| [`debugging`](debugging/) | Отладка и исправление багов | Поиск и устранение ошибок |
| [`metrics-calculator`](metrics-calculator/) | Работа с метриками | Расчёт метрик TradingView |

---

## 🎯 Критические константы (NEVER CHANGE)

```python
# Комиссия для TradingView parity — 10+ файлов зависят
commission_rate = 0.0007  # 0.07%

# Движок по умолчанию — золотой стандарт
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4

# Дата начала данных — импортировать отсюда
from backend.config.database_policy import DATA_START_DATE  # 2025-01-01

# Поддерживаемые таймфреймы
ALL_TIMEFRAMES = ["1", "5", "15", "30", "60", "240", "D", "W", "M"]
```

---

## 🔒 High-Risk Variables (grep перед изменением)

| Переменная | Файлов | Риск |
|------------|--------|------|
| `commission_rate` / `commission_value` | 10+ | TradingView parity |
| `strategy_params` | Все стратегии, UI | Ломает всю систему |
| `initial_capital` | Engine, metrics, UI | Неверные расчёты |
| Port aliases (`long↔bullish`) | Адаптер | Тихая потеря сигналов |

---

## 📖 Рабочий процесс

### Для простых задач (< 15 минут)

1. Выполнить напрямую
2. Запустить тесты: `pytest tests/ -v`
3. Проверить линтинг: `ruff check . --fix && ruff format .`
4. Обновить `CHANGELOG.md`
5. Сообщить о завершении

### Для сложных задач (> 15 минут)

1. **Анализ:** Прочитать受影响нные файлы
2. **План:** Создать план выполнения
3. **Одобрение:** Запросить одобрение плана
4. **Выполнение:** Делать по одному атомарному изменению
5. **Верификация:** Тесты после каждого изменения
6. **Документирование:** Обновить документацию

---

## 🧪 Команды разработки

```powershell
# Запуск сервера
.\dev.ps1 run
# или
py -3.14 -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

# Тесты
pytest tests/ -v                     # Все тесты
pytest tests/ -v -m "not slow"       # Быстрые тесты
pytest tests/ --cov=backend          # С покрытием

# Линтинг
ruff check . --fix
ruff format .

# Миграции БД
alembic upgrade head
```

---

## 📂 Структура проекта

```
d:/bybit_strategy_tester_v2/
├── backend/
│   ├── backtesting/          # Ядро: engine, strategies, adapter
│   ├── api/routers/          # 70+ API роутеров
│   ├── services/             # Сервисы: data, risk, live trading
│   ├── optimization/         # Optuna, Ray, scoring
│   ├── core/                 # MetricsCalculator, config
│   ├── trading/              # Live trading execution
│   └── agents/               # AI агенты
├── frontend/
│   ├── strategy-builder.html # Основной UI
│   └── js/pages/             # Логика frontend
├── tests/                    # 214 тестовых файлов
└── docs/                     # Документация
```

---

## 🤝 Взаимодействие с другими AI

### Приоритет конфигурации

1. **Model-specific:** `.qwen/QWEN.md` (если существует)
2. **Глобальные правила:** Этот файл (`SKILL.md`)
3. **Проектные навыки:** `.github/skills/`
4. **Knowledge Items:** `.ai/` директория

### Контекст

Перед началом работы:
- Прочитать `CLAUDE.md` (актуальная архитектура)
- Проверить `CHANGELOG.md` (последние изменения)
- Изучить `docs/DECISIONS.md` (принятые решения)

---

## ⚠️ Запреты

- **НЕ** менять `commission_rate` с `0.0007` без явного одобрения
- **НЕ** использовать `FallbackEngineV2/V3` для нового кода
- **НЕ** хардкодить пути `d:\...` или API ключи
- **НЕ** использовать Bash (нестабильно на Windows) — использовать инструменты
- **НЕ** создавать новые файлы, если можно редактировать существующие
- **НЕ** добавлять комментарии в код, который не меняли

---

## ✅ Чеклист перед коммитом

- [ ] Все тесты проходят: `pytest tests/ -v`
- [ ] Линтинг пройден: `ruff check . --fix && ruff format .`
- [ ] `CHANGELOG.md` обновлён
- [ ] High-risk переменные проверены через `grep`
- [ ] Типы данных указаны (type hints)
- [ ] Документация обновлена (если нужно)

---

*Создано: 2026-02-26 для Qwen Code*
*На основе анализа: Claude, Copilot, Cursor, Gemini skills*
