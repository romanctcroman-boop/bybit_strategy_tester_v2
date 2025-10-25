# Optimization Module

Модули оптимизации параметров торговых стратегий (ТЗ раздел 3.5).

---

## 📦 Модули

### ✅ GridOptimizer (ТЗ 3.5.1 - Базовый уровень)
**Статус:** Реализован и протестирован

**Функционал:**
- Grid search оптимизация параметров (TP, SL, Trailing Stop)
- Генерация всех комбинаций параметров (декартово произведение)
- Запуск BacktestEngine для каждой комбинации
- Ранжирование результатов по score function:
  - Sharpe Ratio (по умолчанию)
  - Profit Factor
  - Custom formula: `(Return / DD) * Sharpe * sqrt(WinRate)`
- Валидация результатов (min_trades, max_drawdown)
- Экспорт топ-N результатов в CSV

**Пример использования:**

```python
from backend.optimization import GridOptimizer, ParameterRange, OptimizationConfig
from backend.core.backtest_engine import BacktestEngine
import pandas as pd

# Конфигурация параметров
config = OptimizationConfig(
    parameters=[
        ParameterRange("tp_percent", start=2.0, stop=5.0, step=0.5),
        ParameterRange("sl_percent", start=1.0, stop=2.0, step=0.25),
        ParameterRange("trail_activation", start=1.5, stop=3.0, step=0.5),
        ParameterRange("trail_distance", start=0.5, stop=1.5, step=0.25),
    ],
    base_strategy={
        'name': 'EMA Crossover',
        'entry': {
            'type': 'ema_cross',
            'fast_period': 12,
            'slow_period': 26
        },
    },
    score_function='sharpe',  # 'sharpe', 'profit_factor', 'custom'
    min_trades=30,
    max_drawdown_limit=0.20,  # 20% max
    max_workers=4,
    top_n_results=20
)

# Загрузка данных
data = pd.read_csv('market_data.csv')

# Engine
engine = BacktestEngine(
    initial_capital=10000.0,
    commission=0.0006,
    slippage_pct=0.05
)

# Оптимизация
optimizer = GridOptimizer(engine, data, config)
results = optimizer.optimize(parallel=True)

# Экспорт результатов
optimizer.export_results(results, 'optimization_results.csv', top_n=20)

# Статистика
summary = optimizer.get_summary(results)
print(f"Best Sharpe: {summary['best_score']:.2f}")
print(f"Best params: {summary['best_parameters']}")
```

**Тесты:** `tests/test_grid_optimizer.py`
- ✅ 6/6 тестов пройдено
- Покрытие: генерация grid, валидация, CSV export, summary stats

---

### ⏳ WalkForwardOptimizer (ТЗ 3.5.2 - Продвинутый уровень)
**Статус:** Реализован в Celery tasks (частично)

**Функционал:**
- Защита от overfitting
- Rolling window optimization (in-sample / out-sample)
- Оценка стабильности параметров
- Требует дополнительной реализации standalone класса

**TODO:** Создать `backend/optimization/walk_forward.py` как standalone модуль

---

### ⏳ MonteCarloSimulator (ТЗ 3.5.3 - Продвинутый уровень)
**Статус:** Не реализован

**Функционал:**
- Случайная перестановка сделок
- Расчет probability of ruin
- Доверительные интервалы для метрик
- Оценка робастности стратегии

**TODO:** Создать `backend/optimization/monte_carlo.py`

---

## 🔌 API Integration

Модули оптимизации интегрированы через:
- **FastAPI endpoints:** `backend/api/routers/optimizations.py`
- **Celery tasks:** `backend/tasks/optimize_tasks.py`

**API Endpoints:**

```
POST   /api/optimizations/{id}/run/grid          # Запуск grid search
POST   /api/optimizations/{id}/run/walk-forward  # Запуск WFO
POST   /api/optimizations/{id}/run/bayesian      # Запуск Bayesian optimization
GET    /api/optimizations/{id}/results           # Получение результатов
GET    /api/optimizations/{id}/best              # Лучший результат
```

---

## 📊 Структура результатов

### OptimizationResult

```python
{
    "parameters": {"tp_percent": 3.5, "sl_percent": 1.5},
    "metrics": {
        "total_trades": 142,
        "win_rate": 62.5,
        "sharpe_ratio": 1.85,
        "profit_factor": 2.15,
        "max_drawdown": 0.12,
        "total_return": 0.45
    },
    "score": 1.85,
    "rank": 1,
    "valid": true,
    "validation_errors": []
}
```

### CSV Export Format

```csv
tp_percent,sl_percent,metric_total_trades,metric_win_rate,metric_sharpe_ratio,rank,score
3.5,1.5,142,62.5,1.85,1,1.8500
3.0,1.5,138,60.1,1.72,2,1.7200
...
```

---

## 🎯 Следующие шаги

1. ✅ **GridOptimizer** - DONE
2. ⏳ **WalkForwardOptimizer** - В разработке
3. ⏳ **MonteCarloSimulator** - Запланировано
4. ⏳ **Frontend UI** - Интеграция с OptimizationsPage.tsx
5. ⏳ **Heatmap visualization** - Plotly для визуализации результатов

---

**Документация обновлена:** 2025-10-25
**Статус реализации ТЗ 3.5:** 33% (1/3 модулей)
