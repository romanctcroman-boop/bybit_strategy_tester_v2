# backend/optimization/ — Контекст модуля

## Структура
```
optimization/
  optuna_optimizer.py    — Bayesian (TPE/CMA-ES) через Optuna — ОСНОВНОЙ
  builder_optimizer.py   — Strategy Builder parameter optimization
  ray_optimizer.py       — Ray-distributed (для параллельных запусков)
  scoring.py             — Функции скоринга (20 метрик)
  workers.py             — Workers для distributed optimization
  filters.py             — Фильтры результатов
  recommendations.py     — Рекомендации по результатам
```

## Движок оптимизации
- **NumbaEngineV2** используется для optimization loops (20-40x быстрее V4)
- VectorBT НЕ используется для standalone оптимизации
- Optuna: `n_trials` → TPE → CMA-ES (при достаточном кол-ве трейлов)

## Критические детали

### Параметры (из BacktestConfig)
```python
# optimization/models.py — дефолты для оптимизации
initial_capital = 10000.0    # строка 31/188
leverage = 10                # ← ВНИМАНИЕ: дефолт 10, не 1!
commission_value = 0.0007    # НЕЛЬЗЯ МЕНЯТЬ
pyramiding = request_params.get("pyramiding", 1)  # читается из params, не хардкод
```

### Известная несогласованность (ADR-006)
- `leverage`: optimizer/UI дефолт = **10**, live trading дефолт = **1.0**
- `position_size`: в optimizer — fraction (0-1), в live trading — percent

### scoring.py — метрики оптимизации
| Метрика | Направление |
|---------|-------------|
| net_profit, total_return | maximize ↑ |
| sharpe_ratio, sortino_ratio | maximize ↑ |
| calmar_ratio | maximize ↑ |
| win_rate, profit_factor | maximize ↑ |
| expectancy, recovery_factor | maximize ↑ |
| max_drawdown | minimize ↓ (scorer negates) |

### builder_optimizer.py — Builder-специфичное
- Оптимизирует параметры блоков Strategy Builder
- Использует тот же `INDICATOR_DISPATCH` из indicator_handlers.py
- Тест: `tests/test_builder_optimizer.py`

## Правила при изменении
- Все метрики — через `MetricsCalculator.calculate_all()` (не реализовывать отдельно)
- commission = 0.0007 **везде** — проверяй grep
- n_trials capped at 1000 (API limit)
- Предупреждай об overfitting если период < 90 дней или trades < 30

## Тесты
```bash
pytest tests/test_builder_optimizer.py -v
pytest tests/backend/ -v -k "optim"
```
