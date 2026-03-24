# backend/backtesting/ — Контекст модуля

## Иерархия движков
1. **FallbackEngineV4** (`engines/fallback_engine_v4.py`) — gold standard, всегда используй для одиночных бэктестов
2. **NumbaEngineV2** (`numba_engine.py`) — только для optimization loops (20-40x быстрее)
3. **DCAEngine** (`engines/dca_engine.py`) — автоматически если `dca_enabled=True`
4. V2/V3 — deprecated, только для parity-тестов

## Ключевые файлы модуля
| Файл | Строк | Роль |
|------|-------|------|
| `engine.py` | ~2000 | BacktestEngine — точка входа |
| `engines/fallback_engine_v4.py` | большой | Реализация gold standard |
| `strategy_builder/adapter.py` | **1399** | Graph → BaseStrategy (Phase 3 ✅) |
| `strategy_builder/block_executor.py` | — | Исполнение блоков |
| `strategy_builder/graph_parser.py` | — | Парсинг и нормализация графа |
| `strategy_builder/signal_router.py` | — | Port aliases, routing |
| `strategy_builder/topology.py` | — | Топологическая сортировка |
| `indicator_handlers.py` | **2217** | INDICATOR_DISPATCH + 40+ обработчиков |
| `models.py` | ~1300 | BacktestConfig, BacktestResult, PerformanceMetrics |
| `numba_engine.py` | ~1000 | JIT-движок |
| `engine_selector.py` | ~200 | Маршрутизация по engine_type |

## Правила при изменении движка
- Все метрики — только через `MetricsCalculator.calculate_all()` (не реализовывать самому)
- Commission = `trade_value * 0.0007` (на margin, НЕ на leveraged value)
- Entry выполняется на открытии СЛЕДУЮЩЕГО бара (не на баре сигнала)
- SL/TP проверяется внутри бара при `use_bar_magnifier=True`
- После изменений: `pytest tests/backend/backtesting/ -v`

## Adapter — важные детали
- `_execute_indicator()` → делегирует в `INDICATOR_DISPATCH[block_type]`
- `_normalize_connections()` — вызывается один раз в `__init__`
- Таймфреймы `"Chart"` → резолвятся в `main_interval` из Properties
- `_clamp_period(p)` — все периоды зажаты в [1, 500]
- Port aliases: `long↔bullish`, `short↔bearish`, `output↔value`, `result↔signal`

## SignalResult — контракт
```python
SignalResult(
    entries,           # pd.Series bool — long entry
    exits,             # pd.Series bool — long exit
    short_entries,     # pd.Series bool | None
    short_exits,       # pd.Series bool | None
    entry_sizes,       # pd.Series float | None (DCA)
    short_entry_sizes, # pd.Series float | None
    extra_data,        # dict | None
)
# Все Series должны иметь тот же index что и input DataFrame
```

## Тесты
```bash
pytest tests/backend/backtesting/ -v
pytest tests/backend/backtesting/test_engine.py -v
pytest tests/backend/backtesting/test_strategy_builder_parity.py -v
```
