# System Patterns — Архитектура и паттерны

## Основной data flow (не нарушать!)
```
DataService.load_ohlcv()          → pd.DataFrame[OHLCV]
  ↓
Strategy.generate_signals()       → SignalResult(entries, exits, short_entries, short_exits, ...)
  ↓  (или StrategyBuilderAdapter: graph → BaseStrategy)
BacktestEngine.run()              → BacktestResult
  ↓  commission=0.0007, engine=FallbackEngineV4
MetricsCalculator.calculate_all() → Dict[166 метрик]
  ↓
FastAPI router                    → JSON + warnings[]
```

## Движки (иерархия)
| Движок | Когда | Файл |
|--------|-------|------|
| **FallbackEngineV4** | ВСЕ одиночные бэктесты | engines/fallback_engine_v4.py |
| NumbaEngineV2 | Оптимизация (20-40x быстрее, 100% parity) | numba_engine.py |
| DCAEngine | dca_enabled=True (автоматически) | engines/dca_engine.py |
| V2/V3 | ТОЛЬКО для parity-тестов (deprecated) | — |

## Критические паттерны

### Commission (ВСЕГДА так)
```python
commission = trade_value * 0.0007          # НА MARGIN, не на leveraged value
# НЕ: commission = trade_value * leverage * 0.0007  ← НЕПРАВИЛЬНО
```

### Port aliases (адаптер)
```python
"long"   ↔ "bullish"   # divergence block
"short"  ↔ "bearish"
"output" ↔ "value"
"result" ↔ "signal"
```

### Direction defaults (ЛОВУШКА)
- API BacktestCreateRequest: default = "long"
- BacktestConfig (движок): default = "both"
- Strategy Builder API: default = "both"
→ POST /api/backtests/ без direction → только long сигналы!

### SignalResult contract
```python
@dataclass
class SignalResult:
    entries: pd.Series               # bool — long entry
    exits: pd.Series                 # bool — long exit
    short_entries: pd.Series | None
    short_exits: pd.Series | None
    entry_sizes: pd.Series | None    # DCA Volume Scale
    short_entry_sizes: pd.Series | None
    extra_data: dict | None
```

### MetricsCalculator — единый источник истины
- 166 метрик, все движки ОБЯЗАНЫ использовать только его
- НЕ реализовывать формулы метрик в других местах

## Крупные файлы (знай где что)
| Файл | Строк | Что делает |
|------|-------|-----------|
| strategy_builder/adapter.py | **1399** | Graph → BaseStrategy (Phase 3 package ✅) |
| strategy_builder_adapter.py | 178 | [WRAPPER] backward-compat re-export → strategy_builder/ |
| indicators/ (package) | — | 40+ обработчиков: trend/oscillators/volatility/volume/other |
| indicator_handlers.py | 178 | [WRAPPER] backward-compat re-export → indicators/ |
| strategy_builder.js | ~7154 | Весь фронтенд Builder (Phase 5 ✅) |
| metrics_calculator.py | ~2000 | 166 метрик |
| engine.py | ~2000 | BacktestEngine (FallbackEngineV4) |

## Предупреждения API (warnings[])
| Tag | Смысл |
|-----|-------|
| [DIRECTION_MISMATCH] | direction-фильтр выбросил все сигналы |
| [NO_TRADES] | Сигналы есть, но трейдов 0 (SL/TP/фильтры убили все) |
| [INVALID_OHLC] | Битые бары удалены |
| [UNIVERSAL_BAR_MAGNIFIER] | Bar magnifier упал, переключился на heuristic |
