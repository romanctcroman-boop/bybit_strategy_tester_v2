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

---

## Key optimization metrics (scoring targets)

The optimizer (`scoring.py`) supports 20 metrics as objective functions. Most commonly used:

| Metric            | Direction | Notes                                                                |
| ----------------- | --------- | -------------------------------------------------------------------- |
| `net_profit`      | higher ↑  | Absolute profit in capital currency                                  |
| `total_return`    | higher ↑  | Return as percentage                                                 |
| `sharpe_ratio`    | higher ↑  | Risk-adjusted return (uses `risk_free_rate`)                         |
| `sortino_ratio`   | higher ↑  | Like Sharpe but penalizes only downside volatility                   |
| `calmar_ratio`    | higher ↑  | `total_return / max_drawdown` — computed in scorer                   |
| `max_drawdown`    | lower ↓   | Reported in **percent** (17.29 = 17.29%); scorer negates for sorting |
| `win_rate`        | higher ↑  | Winning trades / total trades × 100                                  |
| `profit_factor`   | higher ↑  | Gross profit / gross loss                                            |
| `expectancy`      | higher ↑  | Average expected profit per trade                                    |
| `recovery_factor` | higher ↑  | Net profit / max drawdown                                            |

> `rank_by_multi_criteria()` ranks results across multiple criteria simultaneously using average-rank method.

## MM parameter dependencies

```
initial_capital × position_size          → trade_value (capital per entry)
trade_value × leverage                   → leveraged_position_value
leveraged_position_value × commission_value  → commission (if commission_on_margin=False)
trade_value × commission_value           → commission (TradingView style, commission_on_margin=True)

stop_loss (decimal) → closes long at entry_price × (1 - stop_loss)
take_profit (decimal)→ closes long at entry_price × (1 + take_profit)
sl_type = 'average_price' → SL from avg entry (DCA standard)
sl_type = 'last_order'    → SL from last DCA order price

trailing_stop_activation → trailing starts when PnL > activation%
trailing_stop_offset     → SL set at peak_price × (1 - offset%)

pyramiding ≥ 2
    → allows multiple concurrent entries
    → close_rule = ALL/FIFO/LIFO determines close order

dca_martingale_coef × position_size per level → size of each DCA order
dca_drawdown_threshold → triggers safety close when account_drawdown > threshold%
```

## Optimization Filter Unit Mismatch (важно!)

`passes_filters()` в `backend/optimization/filters.py`:
- `max_drawdown_limit` в **request** = fraction (0.0–1.0)
- `max_drawdown` в **result** = percentage (0–100)

Не путать единицы измерения при передаче фильтров!
