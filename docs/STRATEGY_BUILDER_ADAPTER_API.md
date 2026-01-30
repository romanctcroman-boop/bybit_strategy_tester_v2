# Strategy Builder Adapter API Reference

> **Version**: 1.0.0  
> **Updated**: 2026-01-30  
> **Coverage**: 110/110 blocks (100%)

## Overview

The Strategy Builder Adapter converts visual strategy blocks from the frontend into executable trading signals. It processes OHLCV data through a chain of indicators, filters, conditions, and actions to generate entry/exit signals.

## Architecture

```
Frontend (strategy_builder.js)
         ↓
    blockLibrary (186 blocks)
         ↓
API POST /api/v1/backtests/visual
         ↓
StrategyBuilderAdapter.execute()
         ↓
    Trading Signals
```

## Core Class

### `StrategyBuilderAdapter`

```python
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter()
result = adapter.execute(df, blocks, connections)
```

#### Parameters

| Parameter     | Type           | Description                                                                    |
| ------------- | -------------- | ------------------------------------------------------------------------------ |
| `df`          | `pd.DataFrame` | OHLCV data with columns: `open`, `high`, `low`, `close`, `volume`, `timestamp` |
| `blocks`      | `list[dict]`   | Strategy blocks from frontend                                                  |
| `connections` | `list[dict]`   | Block connections defining execution flow                                      |

#### Returns

```python
{
    "signal": pd.Series,      # 1 = buy, -1 = sell, 0 = no signal
    "stop_loss": float,       # Optional stop loss level
    "take_profit": float,     # Optional take profit level
    "metadata": dict          # Additional execution metadata
}
```

---

## Block Categories

### 1. Indicators (34 blocks)

#### Momentum Indicators

| Block ID     | Name             | Parameters                                     | Output                 |
| ------------ | ---------------- | ---------------------------------------------- | ---------------------- |
| `rsi`        | RSI              | `period` (14)                                  | 0-100 oscillator       |
| `stochastic` | Stochastic       | `k_period` (14), `d_period` (3), `slowing` (3) | %K, %D lines           |
| `stoch_rsi`  | StochRSI         | `period` (14), `rsi_period` (14)               | 0-100 oscillator       |
| `williams_r` | Williams %R      | `period` (14)                                  | -100 to 0 oscillator   |
| `roc`        | Rate of Change   | `period` (10)                                  | Percentage change      |
| `mfi`        | Money Flow Index | `period` (14)                                  | 0-100 oscillator       |
| `cmo`        | Chande Momentum  | `period` (9)                                   | -100 to 100 oscillator |
| `cci`        | CCI              | `period` (20)                                  | Unbounded oscillator   |

#### Trend Indicators

| Block ID        | Name           | Parameters                                  | Output                     |
| --------------- | -------------- | ------------------------------------------- | -------------------------- |
| `sma`           | Simple MA      | `period` (20)                               | Price line                 |
| `ema`           | Exponential MA | `period` (20)                               | Price line                 |
| `wma`           | Weighted MA    | `period` (20)                               | Price line                 |
| `dema`          | Double EMA     | `period` (20)                               | Price line                 |
| `tema`          | Triple EMA     | `period` (20)                               | Price line                 |
| `hull_ma`       | Hull MA        | `period` (9)                                | Price line                 |
| `macd`          | MACD           | `fast` (12), `slow` (26), `signal` (9)      | MACD, Signal, Histogram    |
| `adx`           | ADX            | `period` (14)                               | 0-100 trend strength       |
| `supertrend`    | SuperTrend     | `period` (10), `multiplier` (3.0)           | Direction + levels         |
| `ichimoku`      | Ichimoku Cloud | `tenkan` (9), `kijun` (26), `senkou_b` (52) | 5 lines + cloud            |
| `parabolic_sar` | Parabolic SAR  | `af` (0.02), `max_af` (0.2)                 | Stop levels                |
| `aroon`         | Aroon          | `period` (25)                               | Aroon Up, Down, Oscillator |
| `qqe`           | QQE            | `rsi_period` (14), `smoothing` (5)          | QQE line + signals         |

#### Volatility Indicators

| Block ID    | Name               | Parameters                                           | Output               |
| ----------- | ------------------ | ---------------------------------------------------- | -------------------- |
| `atr`       | ATR                | `period` (14)                                        | Volatility value     |
| `atrp`      | ATR Percent        | `period` (14)                                        | ATR as % of price    |
| `bollinger` | Bollinger Bands    | `period` (20), `std` (2.0)                           | Upper, Middle, Lower |
| `keltner`   | Keltner Channel    | `period` (20), `atr_period` (10), `multiplier` (2.0) | Upper, Middle, Lower |
| `donchian`  | Donchian Channel   | `period` (20)                                        | Upper, Lower         |
| `stddev`    | Standard Deviation | `period` (20)                                        | Volatility value     |

#### Volume Indicators

| Block ID  | Name               | Parameters    | Output                |
| --------- | ------------------ | ------------- | --------------------- |
| `obv`     | On Balance Volume  | -             | Cumulative volume     |
| `vwap`    | VWAP               | -             | Volume weighted price |
| `cmf`     | Chaikin Money Flow | `period` (20) | -1 to 1 oscillator    |
| `ad_line` | A/D Line           | -             | Cumulative A/D        |
| `pvt`     | Price Volume Trend | -             | Cumulative PVT        |

#### Support/Resistance

| Block ID       | Name         | Parameters            | Output           |
| -------------- | ------------ | --------------------- | ---------------- |
| `pivot_points` | Pivot Points | `method` ("standard") | PP, R1-R3, S1-S3 |

#### Multi-Timeframe

| Block ID | Name          | Parameters                         | Output              |
| -------- | ------------- | ---------------------------------- | ------------------- |
| `mtf`    | MTF Indicator | `timeframe`, `indicator`, `period` | HTF indicator value |

---

### 2. Filters (24 blocks)

| Block ID                | Name              | Description       | Parameters                           |
| ----------------------- | ----------------- | ----------------- | ------------------------------------ |
| `rsi_filter`            | RSI Filter        | RSI range/cross   | `min`, `max`, `mode`                 |
| `supertrend_filter`     | SuperTrend Filter | Trend direction   | `mode` (trend/signal)                |
| `two_ma_filter`         | Two MA Filter     | MA cross          | `fast_period`, `slow_period`, `mode` |
| `stochastic_filter`     | Stochastic Filter | Stoch range/cross | `k_period`, `d_period`, `mode`       |
| `macd_filter`           | MACD Filter       | Zero/signal cross | `mode` (zero/signal/histogram)       |
| `qqe_filter`            | QQE Filter        | QQE signals       | `rsi_period`, `smoothing`            |
| `cci_filter`            | CCI Filter        | CCI range         | `period`, `level`                    |
| `momentum_filter`       | Momentum Filter   | Momentum range    | `period`, `threshold`                |
| `dmi_filter`            | DMI/ADX Filter    | DI cross + ADX    | `period`, `adx_threshold`            |
| `cmf_filter`            | CMF Filter        | Money flow        | `period`, `threshold`                |
| `bop_filter`            | Balance of Power  | Bulls vs Bears    | `period`, `smoothing`                |
| `levels_filter`         | Levels Break      | S/R breaks        | `period`, `mode`                     |
| `atr_filter`            | ATR Volatility    | ATR threshold     | `period`, `threshold`, `mode`        |
| `volume_compare_filter` | Volume Compare    | Vol vs MA         | `period`, `multiplier`               |
| `highest_lowest_filter` | High/Low Bar      | N-bar breakout    | `period`, `mode`                     |
| `accumulation_filter`   | Accumulation      | Volume zones      | `vol_period`, `range_period`         |
| `linreg_filter`         | Linear Regression | LinReg channel    | `period`, `deviation`                |
| `divergence_filter`     | Divergence        | Price/indicator   | `indicator`, `lookback`              |
| `price_action_filter`   | Price Action      | Candle patterns   | `pattern`                            |
| `trend_filter`          | Trend Filter      | EMA slope/ADX     | `period`, `mode`                     |
| `volume_filter`         | Volume Filter     | Volume threshold  | `period`, `multiplier`               |
| `volatility_filter`     | Volatility Filter | ATR/BB width      | `indicator`, `threshold`             |
| `time_filter`           | Time Filter       | Session/days      | `start_hour`, `end_hour`, `days`     |
| `price_filter`          | Price Filter      | Price level       | `level`, `mode`                      |

---

### 3. Actions (17 blocks)

#### Entry Actions

| Block ID      | Name        | Description         | Parameters       |
| ------------- | ----------- | ------------------- | ---------------- |
| `buy`         | Buy         | Open long position  | -                |
| `sell`        | Sell        | Open short position | -                |
| `limit_entry` | Limit Entry | Entry at price      | `offset_percent` |
| `stop_entry`  | Stop Entry  | Entry on breakout   | `offset_percent` |

#### Exit Actions

| Block ID      | Name        | Description         | Parameters |
| ------------- | ----------- | ------------------- | ---------- |
| `close`       | Close       | Close any position  | -          |
| `close_long`  | Close Long  | Close long only     | -          |
| `close_short` | Close Short | Close short only    | -          |
| `close_all`   | Close All   | Close all positions | -          |

#### Risk Management Actions

| Block ID          | Name            | Description      | Parameters                                    |
| ----------------- | --------------- | ---------------- | --------------------------------------------- |
| `stop_loss`       | Stop Loss       | Set SL level     | `percent` (1.0)                               |
| `take_profit`     | Take Profit     | Set TP level     | `percent` (2.0)                               |
| `trailing_stop`   | Trailing Stop   | Dynamic SL       | `percent` (1.0), `activation` (0.5)           |
| `atr_stop`        | ATR Stop        | ATR-based SL     | `period` (14), `multiplier` (2.0)             |
| `chandelier_stop` | Chandelier Stop | From high - ATR  | `period` (22), `multiplier` (3.0)             |
| `break_even`      | Break Even      | Move SL to entry | `trigger_percent` (1.0)                       |
| `profit_lock`     | Profit Lock     | Lock min profit  | `trigger_percent` (2.0), `lock_percent` (1.0) |
| `scale_out`       | Scale Out       | Partial close    | `close_percent` (50), `profit_target` (1.5)   |
| `multi_tp`        | Multi TP        | TP1/TP2/TP3      | `tp1_percent`, `tp1_close`, `tp2_percent`...  |

---

### 4. Exits (12 blocks)

| Block ID             | Name            | Description        | Parameters                         |
| -------------------- | --------------- | ------------------ | ---------------------------------- |
| `tp_percent`         | TP Percent      | Exit at % profit   | `percent` (2.0)                    |
| `sl_percent`         | SL Percent      | Exit at % loss     | `percent` (1.0)                    |
| `trailing_stop_exit` | Trailing Exit   | Dynamic trailing   | `percent`, `activation`            |
| `atr_exit`           | ATR Exit        | ATR-based TP/SL    | `atr_period`, `tp_mult`, `sl_mult` |
| `time_exit`          | Time Exit       | Exit after N bars  | `bars` (10)                        |
| `session_exit`       | Session Exit    | Exit at hour       | `exit_hour` (16)                   |
| `signal_exit`        | Signal Exit     | Exit on opposite   | -                                  |
| `indicator_exit`     | Indicator Exit  | Exit on condition  | `indicator`, `condition`, `value`  |
| `break_even_exit`    | Break Even Exit | Move SL to entry   | `trigger_percent`                  |
| `partial_close`      | Partial Close   | Close % at targets | `close1_pct`, `target1`...         |
| `multi_tp_exit`      | Multi TP Exit   | TP1/TP2/TP3 levels | `tp1`, `tp1_pct`, `tp2`...         |
| `chandelier_exit`    | Chandelier Exit | ATR from high/low  | `period`, `multiplier`             |

---

### 5. Price Action (9 blocks)

| Block ID             | Name                | Description               | Signal                        |
| -------------------- | ------------------- | ------------------------- | ----------------------------- |
| `engulfing`          | Engulfing           | Bullish/Bearish engulfing | 1 = bullish, -1 = bearish     |
| `hammer_hangman`     | Hammer/Hanging Man  | Reversal candles          | 1 = hammer, -1 = hanging      |
| `doji_patterns`      | Doji Patterns       | All doji types            | 1 = detected                  |
| `shooting_star`      | Shooting Star       | Bearish reversal          | -1 = detected                 |
| `marubozu`           | Marubozu            | Strong momentum           | 1 = bull, -1 = bear           |
| `tweezer`            | Tweezer             | Top/Bottom reversal       | 1 = bottom, -1 = top          |
| `three_methods`      | Three Methods       | Continuation              | 1 = rising, -1 = falling      |
| `piercing_darkcloud` | Piercing/Dark Cloud | Two-candle reversal       | 1 = piercing, -1 = dark cloud |
| `harami`             | Harami              | Inside bar                | 1 = bullish, -1 = bearish     |

---

### 6. Divergence (5 blocks)

| Block ID           | Name                  | Description      | Parameters                           |
| ------------------ | --------------------- | ---------------- | ------------------------------------ |
| `rsi_divergence`   | RSI Divergence        | RSI vs price     | `period` (14), `lookback` (5)        |
| `macd_divergence`  | MACD Divergence       | MACD vs price    | `fast`, `slow`, `signal`, `lookback` |
| `stoch_divergence` | Stochastic Divergence | Stoch K vs price | `k_period`, `d_period`, `lookback`   |
| `obv_divergence`   | OBV Divergence        | OBV vs price     | `lookback` (5)                       |
| `mfi_divergence`   | MFI Divergence        | MFI vs price     | `period` (14), `lookback` (5)        |

---

### 7. Close Conditions (9 blocks)

| Block ID              | Name          | Description         | Parameters                   |
| --------------------- | ------------- | ------------------- | ---------------------------- |
| `close_by_time`       | Close by Time | After N bars        | `bars` (10)                  |
| `close_rsi_reach`     | RSI Reach     | RSI at level        | `level` (70), `direction`    |
| `close_rsi_cross`     | RSI Cross     | RSI crosses level   | `level`, `direction`         |
| `close_stoch_reach`   | Stoch Reach   | Stoch at level      | `level`, `direction`         |
| `close_stoch_cross`   | Stoch Cross   | Stoch crosses level | `level`, `direction`         |
| `close_channel_break` | Channel Break | BB/Keltner break    | `channel`, `direction`       |
| `close_ma_cross`      | MA Cross      | MA1/MA2 cross       | `fast_period`, `slow_period` |
| `close_psar`          | PSAR Close    | On PSAR signal      | `af`, `max_af`               |
| `close_profit_only`   | Profit Only   | Min profit required | `min_profit` (0.5)           |

---

## Usage Examples

### Basic RSI Strategy

```python
blocks = [
    {
        "id": "block_1",
        "type": "rsi",
        "category": "indicator",
        "params": {"period": 14}
    },
    {
        "id": "block_2",
        "type": "rsi_filter",
        "category": "filter",
        "params": {"min": 0, "max": 30, "mode": "range"}
    },
    {
        "id": "block_3",
        "type": "buy",
        "category": "action",
        "params": {}
    }
]

connections = [
    {"from": "block_1", "to": "block_2"},
    {"from": "block_2", "to": "block_3"}
]

adapter = StrategyBuilderAdapter()
result = adapter.execute(df, blocks, connections)
```

### Multi-Timeframe with ATR Stop

```python
blocks = [
    {
        "id": "block_1",
        "type": "mtf",
        "category": "indicator",
        "params": {
            "timeframe": "4h",
            "indicator": "ema",
            "period": 50
        }
    },
    {
        "id": "block_2",
        "type": "trend_filter",
        "category": "filter",
        "params": {"period": 50, "mode": "slope_up"}
    },
    {
        "id": "block_3",
        "type": "buy",
        "category": "action",
        "params": {}
    },
    {
        "id": "block_4",
        "type": "atr_stop",
        "category": "action",
        "params": {"period": 14, "multiplier": 2.5}
    }
]

connections = [
    {"from": "block_1", "to": "block_2"},
    {"from": "block_2", "to": "block_3"},
    {"from": "block_3", "to": "block_4"}
]
```

### Price Action with Multi-TP

```python
blocks = [
    {
        "id": "block_1",
        "type": "engulfing",
        "category": "price_action",
        "params": {}
    },
    {
        "id": "block_2",
        "type": "trend_filter",
        "category": "filter",
        "params": {"period": 20, "mode": "slope_up"}
    },
    {
        "id": "block_3",
        "type": "buy",
        "category": "action",
        "params": {}
    },
    {
        "id": "block_4",
        "type": "multi_tp",
        "category": "action",
        "params": {
            "tp1_percent": 1.0, "tp1_close": 30,
            "tp2_percent": 2.0, "tp2_close": 30,
            "tp3_percent": 3.0, "tp3_close": 40
        }
    }
]
```

---

## Error Handling

The adapter handles errors gracefully:

```python
try:
    result = adapter.execute(df, blocks, connections)
except ValueError as e:
    # Invalid block configuration
    print(f"Config error: {e}")
except KeyError as e:
    # Missing required parameter
    print(f"Missing param: {e}")
```

Common errors:

- `Unknown block type: xyz` - Block not implemented
- `Missing required parameter: period` - Required param not provided
- `Invalid timeframe for MTF` - Unsupported MTF timeframe

---

## Performance Considerations

1. **Large datasets**: Use `numba` JIT for price action patterns (47 patterns optimized)
2. **MTF indicators**: Resampling adds overhead, cache results
3. **Complex strategies**: Limit to 20-30 blocks for optimal performance
4. **WebSocket validation**: Debounced at 150ms to prevent spam

---

## Exotic Candlestick Patterns

The adapter now supports 11 additional exotic candlestick patterns via Numba JIT:

| Pattern ID          | Name              | Signal Type | Description                                |
| ------------------- | ----------------- | ----------- | ------------------------------------------ |
| `three_line_strike` | Three Line Strike | Reversal    | 3 candles + engulfing (strongest reversal) |
| `kicker`            | Kicker            | Reversal    | Gap reversal (very reliable)               |
| `abandoned_baby`    | Abandoned Baby    | Reversal    | Doji with gaps on both sides               |
| `belt_hold`         | Belt Hold         | Reversal    | Single candle opening at low/high          |
| `counterattack`     | Counterattack     | Reversal    | Equal close after opposite candle          |
| `gap_pattern`       | Gap Up/Down       | Both        | Price gaps with fill detection             |
| `ladder_pattern`    | Ladder Bottom/Top | Reversal    | 5-candle exhaustion pattern                |
| `stick_sandwich`    | Stick Sandwich    | Reversal    | 3 candles with matching closes             |
| `homing_pigeon`     | Homing Pigeon     | Bullish     | Two reds where second is inside first      |
| `matching_low_high` | Matching Low/High | S/R         | Two candles with equal lows/highs          |

---

## WebSocket Real-Time Validation API

### Endpoint

```
ws://host/api/v1/strategy-builder/ws/validate
```

### Message Types

- `validate_param` - Single parameter validation
- `validate_block` - Full block validation
- `validate_connection` - Connection compatibility check
- `validate_strategy` - Entire strategy validation
- `heartbeat` - Keep-alive

### Validation Severity Levels

| Level     | Description                         |
| --------- | ----------------------------------- |
| `error`   | Critical issue, strategy won't work |
| `warning` | Potential issue, strategy may fail  |
| `info`    | Informational message               |

---

## Changelog

- **v1.1.0** (2026-01-30): Added 11 exotic patterns, WebSocket validation API
- **v1.0.0** (2026-01-30): Initial release with 110/110 block coverage
- **v0.9.0** (2026-01-30): Added MTF indicator and 6 filters
- **v0.8.0** (2026-01-29): Core indicators and filters
