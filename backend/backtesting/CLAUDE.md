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

---

## Strategy Builder — Graph Format

The adapter (`StrategyBuilderAdapter`) accepts a `strategy_graph: dict` with this shape:

```jsonc
{
    "name": "My RSI Strategy", // optional, default "Builder Strategy"
    "description": "...", // optional
    "interval": "15", // main chart timeframe (resolves "Chart" in blocks)
    "blocks": [
        {
            "id": "block_1",
            "type": "rsi",
            "params": {
                "period": 14,
                "oversold": 30,
                "overbought": 70,
                "timeframe": "Chart", // resolved to "interval" above
            },
            "isMain": false,
        },
        {
            "id": "strategy_node",
            "type": "strategy", // the main collector node
            "params": {},
            "isMain": true, // exactly ONE block must be isMain
        },
    ],
    "connections": [
        {
            "from": "block_1",
            "fromPort": "long", // output port of source block
            "to": "strategy_node",
            "toPort": "entry_long", // input port of target block
        },
    ],
    // optional shortcut:
    "main_strategy": { "id": "strategy_node", "isMain": true },
}
```

**Block types:** `rsi`, `macd`, `stochastic`, `stoch_rsi`, `bollinger`, `ema`, `sma`, `wma`, `dema`, `tema`, `hull_ma`, `supertrend`, `ichimoku`, `atr`, `adx`, `cci`, `cmf`, `mfi`, `roc`, `williams_r`, `rvi`, `cmo`, `qqe`, `obv`, `pvt`, `ad_line`, `vwap`, `donchian`, `keltner`, `parabolic_sar`, `aroon`, `atrp`, `stddev`, `pivot_points`, `divergence`, `highest_lowest_bar`, `two_mas`, `channel`, `momentum`, `price_action`, `strategy`, `condition`, `filter`, `exit`.

**Strategy node input ports:** `entry_long`, `entry_short`, `exit_long`, `exit_short`.

**Timeframe keys** — params with value `"Chart"` → resolved to `main_interval`:
`timeframe`, `two_mas_timeframe`, `channel_timeframe`, `rvi_timeframe`, `mfi_timeframe`,
`cci_timeframe`, `momentum_timeframe`, `channel_close_timeframe`, `rsi_close_timeframe`, `stoch_close_timeframe`.

---

## SignalResult — полный контракт

```python
@dataclass
class SignalResult:
    entries: pd.Series               # bool — long entry signals
    exits: pd.Series                 # bool — long exit signals
    short_entries: pd.Series | None  # bool — short entry signals
    short_exits: pd.Series | None    # bool — short exit signals
    entry_sizes: pd.Series | None    # float — per-entry position size (DCA Volume Scale)
    short_entry_sizes: pd.Series | None
    extra_data: dict | None          # additional data (ATR series, etc.) passed to engine
```

All series must have the same index as the input OHLCV DataFrame.

---

## Параметры Built-in стратегий

| Strategy               | Parameter       | Type      | Range / Default                       | Constraint                      |
| ---------------------- | --------------- | --------- | ------------------------------------- | ------------------------------- |
| `sma_crossover`        | `fast_period`   | int       | ≥2; default 10                        | must be < slow_period           |
| `sma_crossover`        | `slow_period`   | int       | > fast_period; default 30             |                                 |
| `rsi` (**deprecated**) | `period`        | int       | ≥2; default 14                        | Use universal RSI block instead |
| `rsi`                  | `oversold`      | float     | 0 < x < overbought; default 30        |                                 |
| `rsi`                  | `overbought`    | float     | < 100; default 70                     |                                 |
| `macd`                 | `fast_period`   | int       | < slow_period; default 12             |                                 |
| `macd`                 | `slow_period`   | int       | > fast_period; default 26             |                                 |
| `macd`                 | `signal_period` | int       | default 9                             |                                 |
| `bollinger_bands`      | `period`        | int       | ≥2; default 20                        |                                 |
| `bollinger_bands`      | `std_dev`       | float     | >0; default 2.0                       |                                 |
| `grid`                 | `grid_levels`   | int       | ≥2; default 5                         | set pyramiding = grid_levels    |
| `grid`                 | `grid_spacing`  | float (%) | >0; default 1.0%                      |                                 |
| `grid`                 | `take_profit`   | float (%) | default 1.5%                          |                                 |
| `grid`                 | `direction`     | enum str  | `"long"` / `"both"`; default `"long"` |                                 |

## Параметры Strategy Builder блоков

All indicator periods clamped to **[1, 500]** via `_clamp_period()`.

| Indicator                                 | Key params                                 | Notes                                        |
| ----------------------------------------- | ------------------------------------------ | -------------------------------------------- |
| SMA, EMA, WMA, DEMA, TEMA, HullMA         | `period` int                               |                                              |
| RSI (universal)                           | `period`, `oversold`, `overbought`, `mode` | Use this, not built-in RSI                   |
| MACD                                      | `fast`, `slow`, `signal`                   |                                              |
| Bollinger Bands                           | `period`, `std_dev`                        |                                              |
| Stochastic                                | `k_period`, `d_period`, `smooth`           |                                              |
| Stoch RSI                                 | `rsi_period`, `stoch_period`, `k`, `d`     |                                              |
| ADX                                       | `period`                                   |                                              |
| ATR                                       | `period`                                   |                                              |
| Supertrend                                | `period`, `multiplier`                     |                                              |
| Ichimoku                                  | `tenkan`, `kijun`, `senkou_b`              |                                              |
| Donchian                                  | `period`                                   |                                              |
| Keltner                                   | `ema_period`, `atr_period`, `multiplier`   |                                              |
| Parabolic SAR                             | `acceleration`, `max_acceleration`         |                                              |
| CCI, CMF, MFI, ROC, Williams %R, RVI, CMO | `period`                                   |                                              |
| OBV, PVT, A/D Line                        | —                                          | volume-based, no period                      |
| VWAP                                      | —                                          | built-in                                     |
| QQE                                       | `rsi_period`, `sf`, `q`                    |                                              |
| Divergence                                | —                                          | returns `long`/`short` + `bullish`/`bearish` |
| Pivot Points                              | `type`, `lookback`                         |                                              |

## Port alias mapping — полная таблица

```python
# StrategyBuilderAdapter class constants
_PORT_ALIASES: dict[str, list[str]] = {
    "long":   ["bullish", "signal", "output", "value", "result"],
    "short":  ["bearish", "signal", "output", "value", "result"],
    "output": ["value",   "signal", "result"],
    "result": ["signal",  "output", "value"],
}
_SIGNAL_PORT_ALIASES: dict[str, list[str]] = {
    "long":  ["bullish"],
    "short": ["bearish"],
}
```

Primary canonical aliases: `"long" ↔ "bullish"`, `"short" ↔ "bearish"`, `"output" ↔ "value"`, `"result" ↔ "signal"`

---

## BacktestConfig — полные параметры (`backend/backtesting/models.py`)

| Parameter                  | Type        | Range                                              | Default            | Purpose                                        |
| -------------------------- | ----------- | -------------------------------------------------- | ------------------ | ---------------------------------------------- |
| `initial_capital`          | float       | 100 – 100 000 000                                  | 10 000.0           | Starting capital                               |
| `position_size`            | float       | 0.01 – 1.0                                         | 1.0                | Fraction of capital per trade                  |
| `leverage`                 | float       | 1.0 – 125.0                                        | 1.0                | Leverage (Bybit max)                           |
| `direction`                | enum str    | `long` / `short` / `both`                          | `"both"`           | Trading direction                              |
| `commission_value`         | float       | ≥0.0                                               | **0.0007**         | Commission — NEVER change                      |
| `commission_type`          | enum str    | `percent` / `cash_per_contract` / `cash_per_order` | `"percent"`        | Commission type                                |
| `commission_on_margin`     | bool        | —                                                  | True               | TV-style: commission on margin, not full value |
| `maker_fee`                | float       | 0 – 0.01                                           | 0.0002             | Maker fee                                      |
| `taker_fee`                | float       | 0 – 0.01                                           | 0.0004             | Taker fee                                      |
| `slippage`                 | float       | 0 – 0.05                                           | 0.0005             | Slippage (decimal)                             |
| `slippage_ticks`           | int         | 0 – 100                                            | 0                  | Slippage in ticks                              |
| `stop_loss`                | float\|None | 0.001 – 0.5                                        | None               | SL (decimal from entry price)                  |
| `take_profit`              | float\|None | 0.001 – 1.0                                        | None               | TP (decimal from entry price)                  |
| `max_drawdown`             | float\|None | 0.01 – 1.0                                         | None               | Drawdown limit                                 |
| `trailing_stop_activation` | float\|None | 0.001 – 0.5                                        | None               | Trailing stop activation                       |
| `trailing_stop_offset`     | float\|None | 0.001 – 0.2                                        | None               | Trailing stop offset from peak                 |
| `breakeven_enabled`        | bool        | —                                                  | False              | Move SL to breakeven after TP                  |
| `breakeven_activation_pct` | float       | 0 – 0.5                                            | 0.005              | Breakeven activation threshold                 |
| `breakeven_offset`         | float       | 0 – 0.1                                            | 0.0                | Breakeven offset from entry                    |
| `sl_type`                  | enum str    | `average_price` / `last_order`                     | `"average_price"`  | SL reference price                             |
| `risk_free_rate`           | float       | 0 – 0.20                                           | 0.02               | Risk-free rate (Sharpe/Sortino)                |
| `pyramiding`               | int         | 0 – 99                                             | 1                  | Max concurrent entries (TV compatible)         |
| `close_rule`               | enum str    | `ALL` / `FIFO` / `LIFO`                            | `"ALL"`            | Position close order                           |
| `partial_exit_percent`     | float\|None | 0.1 – 0.99                                         | None               | Partial exit at TP                             |
| `close_only_in_profit`     | bool        | —                                                  | False              | Close via signal only if trade is profitable   |
| `no_trade_days`            | tuple[int]  | 0–6 (Mon–Sun)                                      | ()                 | Days to block trading                          |
| `market_type`              | enum str    | `spot` / `linear`                                  | `"linear"`         | Market data source                             |
| `use_bar_magnifier`        | bool        | —                                                  | True               | Precise SL/TP intrabar detection (stub — bar close only) |
| `intrabar_ohlc_path`       | enum str    | see models.py                                      | `"O-HL-heuristic"` | OHLC path model                                |

### DCA Grid параметры

| Parameter                     | Type      | Range                                              | Default               |
| ----------------------------- | --------- | -------------------------------------------------- | --------------------- |
| `dca_enabled`                 | bool      | —                                                  | False                 |
| `dca_order_count`             | int       | 2 – 15                                             | 5                     |
| `dca_grid_size_percent`       | float (%) | 0.1 – 50.0                                         | 1.0                   |
| `dca_martingale_coef`         | float     | 1.0 – 5.0                                          | 1.5                   |
| `dca_martingale_mode`         | enum str  | `multiply_each` / `multiply_total` / `progressive` | `"multiply_each"`     |
| `dca_drawdown_threshold`      | float (%) | 5 – 90                                             | 30.0                  |
| `dca_safety_close_enabled`    | bool      | —                                                  | True                  |
| `dca_tp1/2/3/4_percent`       | float (%) | 0 – 100                                            | 0.5 / 1.0 / 2.0 / 3.0 |
| `dca_tp1/2/3/4_close_percent` | float (%) | 0 – 100                                            | 25.0 each             |

### MM dependencies (формулы)

```
initial_capital × position_size          → trade_value (capital per entry)
trade_value × leverage                   → leveraged_position_value
trade_value × commission_value           → commission (TradingView style, commission_on_margin=True)

stop_loss (decimal) → closes long at entry_price × (1 - stop_loss)
take_profit (decimal)→ closes long at entry_price × (1 + take_profit)
sl_type = 'average_price' → SL from avg entry (DCA standard)
sl_type = 'last_order'    → SL from last DCA order price

trailing_stop_activation → trailing starts when PnL > activation%
trailing_stop_offset     → SL set at peak_price × (1 - offset%)
```
