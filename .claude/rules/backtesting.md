---
paths:
  - "backend/backtesting/**/*.py"
  - "backend/core/metrics_calculator.py"
  - "tests/backend/backtesting/**"
  - "tests/backtesting/**"
---

# Backtesting Rules

## Критические инварианты
- `commission_value = 0.0007` — НЕ МЕНЯТЬ. Формула: `trade_value × 0.0007` (НЕ `leveraged_value × 0.0007`)
- `commission_on_margin=True` (default) — комиссия на маржу, как в TradingView
- Вход всегда на open следующего бара (не на баре сигнала)
- `FallbackEngineV4` — золотой стандарт. V2/V3 — только для parity-тестов
- Все метрики — только через `MetricsCalculator.calculate_all()`. Никогда не переопределять

## Выбор движка
- `auto/single/fallback/v4` → FallbackEngineV4
- `optimization/numba` → NumbaEngineV2 (20-40x быстрее, 100% parity)
- `dca_enabled=True` → DCAEngine (всегда, независимо от engine_type)

## Ловушка direction
- `BacktestCreateRequest` (API) default = `"long"` → short-сигналы молча отбрасываются!
- `BacktestConfig` (движок) default = `"both"`
- Strategy Builder API default = `"both"`

## Port alias mapping (адаптер)
```
long    ↔ bullish
short   ↔ bearish
output  ↔ value
result  ↔ signal
```

## SignalResult контракт
```python
@dataclass
class SignalResult:
    entries: pd.Series               # bool — long entry
    exits: pd.Series                 # bool — long exit
    short_entries: pd.Series | None
    short_exits: pd.Series | None
    entry_sizes: pd.Series | None
    short_entry_sizes: pd.Series | None
    extra_data: dict | None
```

## Коды предупреждений API
- `[DIRECTION_MISMATCH]` — direction-фильтр отбросил все сигналы
- `[NO_TRADES]` — сигналы есть, но сделок нет (SL/TP убил всё)
- `[INVALID_OHLC]` — неверные бары удалены
- `[UNIVERSAL_BAR_MAGNIFIER]` — bar magnifier не работает (STUB — фактически SL/TP по закрытию бара)

## Тесты
```bash
pytest tests/backend/backtesting/test_engine.py -v
pytest tests/backend/backtesting/test_strategy_builder_parity.py -v
```
