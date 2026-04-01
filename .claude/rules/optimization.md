---
paths:
  - "backend/optimization/**/*.py"
  - "tests/backend/optimization/**"
  - "tests/integration/test_optimizer*.py"
---

# Optimization Pipeline Rules

## Движок для оптимизации
- Всегда **NumbaEngineV2** (20-40x быстрее, 100% parity с FallbackEngineV4)
- VectorBT используется только внутри оптимизации, НИКОГДА для standalone backtests

## Параметры по умолчанию в оптимизации
| Параметр | Значение | Примечание |
|---------|---------|-----------|
| `commission_value` | **0.0007** | НЕ МЕНЯТЬ |
| `leverage` | 10 | Отличается от live (1.0)! |
| `initial_capital` | 10000 | Как в движке |
| `pyramiding` | из `request_params` | Исправлено в d5d0eb2 |

## Известные исправленные баги (не вводить повторно)
- `generate_builder_param_combinations` возвращает `tuple(iterator, total_count, was_capped)` — нужно распаковывать
- `max_drawdown_limit` в запросе — в долях (0.0–1.0); `max_drawdown` в результате — в процентах (0–100)
- NaN/inf в Optuna objective → `TrialPruned()`, не падение
- OOS data leakage: предварять 200 warmup-барами перед OOS-периодом

## Метрики / цели
```python
# maximize: net_profit, sharpe_ratio, sortino_ratio, calmar_ratio, win_rate, profit_factor
# minimize: max_drawdown (scorer автоматически меняет знак)
rank_by_multi_criteria()  # average-rank метод для мульти-цели
```

## `bollinger` блок (ловушка)
- Выводит price bands (upper/middle/lower) — НЕ bool-сигналы
- Для entry-сигналов использовать `keltner_bollinger`

## Тесты
```bash
pytest tests/integration/test_optimizer_real_data.py -v
pytest tests/backend/optimization/ -v
```
