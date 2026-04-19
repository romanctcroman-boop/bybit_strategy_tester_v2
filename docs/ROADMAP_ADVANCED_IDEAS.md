# Roadmap — продвинутые и долгосрочные идеи

**Дата:** 2026-01-31  
**Источник:** ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md

---

## Статус приоритетных (выполнено 2026-01-31)

- [x] Гибридная двухфазная архитектура — формализована, `validate_best_with_fallback`
- [x] Bayesian/Optuna — `POST /sync/optuna-search`, TPE, многокритериальность
- [x] Monte Carlo robustness — добавлены `SLIPPAGE_STRESS`, `PRICE_RANDOMIZATION`
- [x] ExecutionSimulator — `backend/backtesting/execution_simulator.py`
- [x] Walk-Forward — режим `expanding`, `param_stability_report`

---

## Продвинутые идеи (roadmap)

### Event-driven движок
- **Цель:** Очередь событий, один код для backtest и live, отсутствие lookahead bias
- **Сложность:** Высокая
- **Зависимости:** Рефакторинг BacktestEngine, DataHandler, ExecutionHandler
- **Оценка:** 2–4 недели

### Multi-asset portfolio
- **Цель:** Кросс-оптимизация, корреляции, Cvxportfolio-подход
- **Сложность:** Высокая
- **Зависимости:** Расширение `advanced_backtesting/portfolio.py`
- **Оценка:** 1–2 недели

### Regime detection в бэктесте
- **Цель:** Адаптация параметров и фильтрация по режиму рынка
- **Статус:** ✅ 2026-01-31 — API `market_regime_enabled`, `market_regime_filter`, UI в strategies.html

### RL environment (Gymnasium)
- **Цель:** Стандартизация под Gymnasium, типовые reward-функции
- **Статус:** ✅ 2026-02 — TradingEnv, REWARD_FUNCTIONS (pnl, log_return, sharpe, sortino, calmar, drawdown_penalty), register_trading_env(), gymnasium.make("TradingEnv-v1"), тесты test_trading_env.py

### Backtest → Paper → Live unified API
- **Цель:** Единый API с переключаемым DataProvider и OrderExecutor
- **Статус:** ✅ 2026-02 — interfaces, HistoricalDataProvider, LiveDataProvider, SimulatedExecutor, StrategyRunner, тесты test_unified_trading.py

---

## Долгосрочные / экспериментальные

| Идея | Описание | Статус |
|------|----------|--------|
| L2 order book | Симуляция стакана, WebSocket collector | ✅ Начато |
| Generative LOB | CGAN (PyTorch), обучение на NDJSON | ✅ Скелет |
| Multi-agent simulation | Симуляция множества агентов | Research |
| Real-time parameter adaptation | Онлайн-подстройка параметров | Research |

---

## Оставшиеся крупные задачи

Сводка: [ROADMAP_REMAINING_TASKS.md](ROADMAP_REMAINING_TASKS.md)

| Задача | Оценка | Первый шаг |
|--------|--------|------------|
| Event-driven движок | 2–4 нед | Дизайн EventQueue, on_bar |
| Multi-asset portfolio | 1–2 нед | Расширение portfolio.py |
| §12 Визуализация | 3–5 дн | Parameter heatmap |
| Версионирование / Undo / Шаблоны | 3–7 дн | Таблица strategy_versions |
| L2 order book / Generative LOB | Эксперимент | Research |

---

## Ссылки

- [ROADMAP_REMAINING_TASKS.md](ROADMAP_REMAINING_TASKS.md) — детальный план оставшихся задач
- [ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md](ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md)
- [HYBRID_TWO_PHASE_PIPELINE.md](architecture/HYBRID_TWO_PHASE_PIPELINE.md)
- [ENGINE_ARCHITECTURE.md](architecture/ENGINE_ARCHITECTURE.md)
