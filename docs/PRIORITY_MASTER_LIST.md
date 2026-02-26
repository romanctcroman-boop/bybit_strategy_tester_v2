# 📋 Полный список приоритетов проекта (P0 → P3)

**Дата:** 2026-02-26
**Статус:** Актуализирован
**Источник:** IMPROVEMENT_ROADMAP.md, ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md, ROADMAP_*.md

---

## 📊 Сводка по приоритетам

| Приоритет | Описание | Кол-во | Выполнено | Осталось |
|-----------|----------|--------|-----------|----------|
| **P0** | Критичные (Security & Stability) | 8 | 6 (75%) | 2 |
| **P1** | Важные (Performance & UX) | 12 | 8 (67%) | 4 |
| **P2** | Желательные (Features) | 10 | 4 (40%) | 6 |
| **P3** | Опциональные (Nice to Have) | 8 | 3 (38%) | 5 |
| **ВСЕГО** | | **38** | **21 (55%)** | **17** |

---

## 🔴 P0 — Критичные (Security & Stability)

### ✅ Выполнено (6/8)

| # | Задача | Статус | Файлы |
|---|--------|--------|-------|
| P0-1 | Безопасность API ключей | ✅ | `.env`, `backend/agents/config_validator.py` |
| P0-2 | Валидация startup конфигурации | ✅ | `backend/agents/config_validator.py`, `backend/agents/mcp_config.py` |
| P0-3 | Error handling в MCP bridge | ✅ | `backend/mcp/mcp_integration.py` |
| P0-4 | **Circuit breakers на MCP инструменты** | ✅ **ВЫПОЛНЕНО** | `backend/mcp/mcp_integration.py` |
| P0-5 | **StateManager подготовка** | ✅ **ВЫПОЛНЕНО** | `frontend/js/core/StateManager.js` |
| P0-6 | **backtest_results.js миграция** | ✅ **95% ВЫПОЛНЕНО** | `frontend/js/pages/backtest_results.js` |

### ⏳ Осталось (2/8)

| # | Задача | Описание | Оценка |
|---|--------|----------|--------|
| P0-7 | **dashboard.js миграция на StateManager** | Заменить глобальные переменные | 1 час |
| P0-8 | **strategy_builder.js миграция на StateManager** | Заменить глобальные переменные | 4 часа |

---

## 🟡 P1 — Важные (Performance & UX)

### ✅ Выполнено (8/12)

| # | Задача | Статус | Файлы |
|---|--------|--------|-------|
| P1-1 | Оптимизация startup времени | ✅ | `backend/api/app.py`, `start_all.ps1` |
| P1-2 | Bar Magnifier автоматизация | ✅ | `backend/backtesting/intrabar_engine.py` |
| P1-3 | Strategy Builder: Template система | ✅ | `frontend/js/data/templates.js` |
| P1-4 | Metrics Dashboard улучшения | ✅ | `frontend/backtest-results.html` |
| P1-5 | Walk-Forward визуализация | ✅ | `backend/backtesting/walk_forward.py` |
| P1-6 | ExecutionSimulator | ✅ | `backend/backtesting/execution_simulator.py` |
| P1-7 | Regime integration в backtest | ✅ | `backend/backtesting/market_regime.py` |
| P1-8 | Bayesian/Optuna optimizer | ✅ | `backend/optimization/optuna_optimizer.py` |

### ⏳ Осталось (4/12)

| # | Задача | Описание | Оценка |
|---|--------|----------|--------|
| P1-9 | Multi-symbol backtesting | Портфельное тестирование | 3 дня |
| P1-10 | Genetic Algorithm оптимизация | Альтернатива Grid Search | 2 дня |
| P1-11 | Live Trading интеграция | Paper trading + real execution | 5 дней |
| P1-12 | Strategy Builder: Advanced блоки | ML, Sentiment, Order Flow | 3 дня |

---

## 🟢 P2 — Желательные (Features)

### ✅ Выполнено (4/10)

| # | Задача | Статус | Файлы |
|---|--------|--------|-------|
| P2-1 | Event-driven движок (скелет) | ✅ | `backend/backtesting/engines/event_driven_engine.py` |
| P2-2 | Multi-asset portfolio (аллокация) | ✅ | `backend/backtesting/portfolio.py` |
| P2-3 | §12 Визуализация | ✅ | `optimization-results.html`, `backtest-results.html` |
| P2-4 | Версионирование / Undo / Шаблоны | ✅ | `backend/database/`, `frontend/js/pages/strategy_builder.js` |

### ⏳ Осталось (6/10)

| # | Задача | Описание | Оценка |
|---|--------|----------|--------|
| P2-5 | Backtesting Reports | PDF generation, email reports | 3 дня |
| P2-6 | Strategy Builder: Advanced блоки | ML, LSTM, Sentiment | 4 дня |
| P2-7 | Social Trading | Public стратегии, leaderboard | 5 дней |
| P2-8 | L2 order book / Generative LOB | WebSocket collector, CGAN | 1 неделя |
| P2-9 | RL environment стандартизация | Gymnasium integration | 3 дня |
| P2-10 | Backtest→Live unified API | Переключаемый DataProvider | 4 дня |

---

## 🔵 P3 — Опциональные (Nice to Have)

### ✅ Выполнено (3/8)

| # | Задача | Статус | Файлы |
|---|--------|--------|-------|
| P3-1 | AI-powered strategy suggestions | ✅ | `backend/agents/` + MCP |
| P3-2 | Self-Reflection + RLHF | ✅ | `backend/agents/self_improvement/` |
| P3-3 | Hierarchical Memory | ✅ | `backend/agents/memory/hierarchical_memory.py` |

### ⏳ Осталось (5/8)

| # | Задача | Описание | Оценка |
|---|--------|----------|--------|
| P3-4 | Multi-agent simulation | Симуляция множества агентов | Research |
| P3-5 | Real-Time Parameter Adaptation | Онлайн-подстройка параметров | Research |
| P3-6 | Explainable AI Signals | SHAP/LIME интерпретация | Research |
| P3-7 | Blockchain-Verified Backtests | Аудит и верификация | Research |
| P3-8 | Federated Strategy Learning | Обучение без объединения данных | Research |

---

## 📈 Прогресс по категориям

```
P0 — Критичные:     ████████████████████ 75% ✅ (6/8)
P1 — Важные:        ██████████████░░░░░░ 67% ✅ (8/12)
P2 — Желательные:   ████████░░░░░░░░░░░░ 40% ⏳ (4/10)
P3 — Опциональные:  ███████░░░░░░░░░░░░░ 38% ⏳ (3/8)
                    ─────────────────────────────
ИТОГО:              ███████████░░░░░░░░░ 55% (21/38)
```

---

## 🎯 Текущие активные задачи (P0-3 StateManager)

### Статус миграции StateManager

| Страница | Строк | Статус | Время |
|----------|-------|--------|-------|
| **backtest_results.js** | 5,658 | ✅ 95% | 3 часа |
| **dashboard.js** | 1,955 | ⏳ 0% | 1 час |
| **strategy_builder.js** | 13,378 | ⏳ 0% | 4 часа |
| **Тесты** | — | ⏳ 0% | 3 часа |
| **Документация** | — | ✅ 100% | 3 часа |
| **ИТОГО** | **21,000+** | **31%** | **8.5/16 часов** |

---

## 📅 Дорожная карта на следующую неделю

### Неделя 1 (2026-02-26 → 2026-03-05)

**P0 — Критичные:**
- [ ] dashboard.js миграция (1 час)
- [ ] strategy_builder.js миграция (4 часа)
- [ ] Тесты StateManager (3 часа)

**P1 — Важные:**
- [ ] Multi-symbol backtesting (начало)
- [ ] Genetic Algorithm (исследование)

### Неделя 2 (2026-03-05 → 2026-03-12)

**P2 — Желательные:**
- [ ] Backtesting Reports (PDF)
- [ ] L2 order book (продолжение)

**P3 — Опциональные:**
- [ ] Multi-agent simulation (research)

---

## 📁 Ключевые документы

| Документ | Описание |
|----------|----------|
| `docs/IMPROVEMENT_ROADMAP.md` | Полный roadmap P0-P3 |
| `docs/ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md` | Предложения по движку |
| `docs/ROADMAP_REMAINING_TASKS.md` | Оставшиеся крупные задачи |
| `docs/ROADMAP_ADVANCED_IDEAS.md` | Продвинутые идеи |
| `docs/IMPLEMENTATION_PLAN.md` | План реализации AI-агентов |
| `docs/refactoring/p0-3-state-manager/PLAN.md` | План StateManager миграции |
| `CONTINUE.md` | Текущий статус и продолжение |

---

## 🔑 Следующие шаги

### Ближайшие (1-3 дня)

1. **P0-7: dashboard.js миграция** (1 час)
   - Файл: `frontend/js/pages/dashboard.js`
   - План: `docs/refactoring/p0-3-state-manager/step-2-1-dashboard.md`

2. **P0-8: strategy_builder.js миграция** (4 часа)
   - Файл: `frontend/js/pages/strategy_builder.js`
   - План: `docs/refactoring/p0-3-state-manager/step-2-3-strategy-builder.md`

3. **P0: Тесты StateManager** (3 часа)
   - Файл: `tests/frontend/pages/backtest_results.test.js`
   - План: `docs/refactoring/p0-3-state-manager/step-3-integration-tests.md`

### Среднесрочные (1-2 недели)

1. **P1-9: Multi-symbol backtesting** (3 дня)
2. **P1-10: Genetic Algorithm** (2 дня)
3. **P2-5: Backtesting Reports** (3 дня)

### Долгосрочные (1-3 месяца)

1. **P2-8: L2 order book** (1 неделя)
2. **P2-9: RL environment** (3 дня)
3. **P3-4: Multi-agent simulation** (Research)

---

*Документ актуализирован: 2026-02-26*
*Следующее обновление: 2026-03-05*
