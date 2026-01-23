# Universal Bar Magnifier Architecture

## Обзор

Универсальный Bar Magnifier — это система, которая генерирует **псевдотики из 1m свечей** 
для любого старшего таймфрейма, обеспечивая:

- **Точное определение порядка SL/TP/Entry**
- **Реалистичное исполнение ордеров**
- **Аккуратное отслеживание MFE/MAE**

## Архитектура: 3 слоя

```
┌─────────────────────────────────────────────────────────────┐
│                    BarRunner (любой TF)                     │
│         Основной цикл стратегии по барам T                 │
│         for bar_T in bars_T: process(bar_T)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 IntrabarEngine (1m → ticks)                 │
│    Генератор псевдотиков из 1m баров внутри бара T         │
│    Режимы: O-H-L-C, O-L-H-C, O-HL-heuristic                │
│    for tick in engine.generate_ticks(bar_T): ...           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    BrokerEmulator                           │
│    Исполнение ордеров на каждом тике                       │
│    Приоритеты: Liquidation → SL/TP → Entry → TrailingStop  │
│    broker.process_tick(price, timestamp)                   │
└─────────────────────────────────────────────────────────────┘
```

## Файлы реализации

| Файл | Описание |
|------|----------|
| `intrabar_engine.py` | Генератор псевдотиков из 1m баров |
| `broker_emulator.py` | Tick-by-tick исполнение ордеров |
| `bar_magnifier.py` | Legacy модуль (совместимость) |
| `models.py` | Конфигурация BacktestConfig |

## Режимы генерации тиков (OHLC Path)

### 1. `O-H-L-C` (консервативный для short)

```
Open ──► High ──► Low ──► Close
```

- Для шортов: сначала показывает worst (High), потом best (Low)
- Предотвращает нереалистичный сценарий "сначала TP, потом SL"

### 2. `O-L-H-C` (консервативный для long)

```
Open ──► Low ──► High ──► Close
```

- Для лонгов: сначала показывает worst (Low), потом best (High)
- Консервативный подход к исполнению

### 3. `O-HL-heuristic` (TradingView-style, **default**)

```
If |Open - High| < |Open - Low|:
    Open ──► High ──► Low ──► Close
Else:
    Open ──► Low ──► High ──► Close
```

- Определяет путь по близости Open к High/Low
- Наиболее реалистичная эвристика

### 4. `conservative_long` / `conservative_short`

- Явно указывает для какой стороны оптимизировать

## Subticks (интерполяция)

Для более плавного пути можно добавить промежуточные тики:

```python
config = BacktestConfig(
    intrabar_subticks=2,  # 2 тика между каждой OHLC точкой
)

# Результат: 4 OHLC точки + 2*3 subticks = 10 тиков на 1m бар
# Для 1h бара: 60 * 10 = 600 тиков
```

## Приоритеты исполнения на каждом тике

```
1. Margin calls / ликвидации
   └── Проверка maintenance margin

2. SL/TP ордера
   ├── Stop Loss (если sl_priority=True)
   └── Take Profit

3. Entry ордера
   ├── Market orders
   ├── Limit orders
   └── Stop orders

4. Trailing Stop update
   └── Обновление trail price

5. MFE/MAE update
   └── Отслеживание max favorable/adverse
```

## Конфигурация

```python
from backend.backtesting.models import BacktestConfig

config = BacktestConfig(
    symbol="BTCUSDT",
    interval="60",  # 1h основной TF
    
    # Bar Magnifier
    use_bar_magnifier=True,
    bar_magnifier_timeframe="1",  # или None для авто
    bar_magnifier_max_bars=200000,
    
    # OHLC Path Model
    intrabar_ohlc_path="O-HL-heuristic",  # TradingView-style
    intrabar_subticks=0,  # 0 = только 4 точки OHLC
    
    # SL/TP
    stop_loss=0.02,
    take_profit=0.04,
    sl_priority=True,  # SL имеет приоритет
)
```

## Данные и производительность

### Количество тиков на бар

| TF | 1m баров | Тиков (subticks=0) | Тиков (subticks=2) |
|----|----------|--------------------|--------------------|
| 15m | 15 | 60 | 150 |
| 1h | 60 | 240 | 600 |
| 4h | 240 | 960 | 2,400 |
| 1d | 1,440 | 5,760 | 14,400 |

### Требования к 1m данным (1 год)

| TF | 1m свечей | ~Размер в памяти |
|----|-----------|-----------------|
| 15m | 525,600 | ~100 MB |
| 1h | 525,600 | ~100 MB |
| 4h | 525,600 | ~100 MB |
| 1d | 525,600 | ~100 MB |

## Ограничения модели

### Микроструктура рынка

- Внутри 1m могут быть сотни реальных тиков
- Модель даёт ~4-10 точек на минуту
- Для HFT/скальпинга — недостаточно

### Volume distribution

- Объём распределяется эвристикой (O:10%, H:30%, L:30%, C:30%)
- Для объёмных стратегий — условно

### Флаги в результатах

```python
result.metadata = {
    "uses_synthetic_ticks": True,
    "data_granularity": "1m->synthetic_ticks",
    "ohlc_path_model": "O-HL-heuristic",
    "subticks_per_minute": 0,
    "microstructure_risk": "medium",
}
```

## Сравнение режимов исполнения

| Режим | Данные | Внутрибара путь | Реализм | Скорость |
|-------|--------|-----------------|---------|----------|
| `bar_close` | бары T | нет (1 тик = close) | низкий | высокий |
| `intrabar_ohlc_1m` | бары T + 1m | O-H-L-C по 1m | средний | средний |
| `intrabar_subticks` | бары T + 1m | OHLC + N интерполированных | выше | ниже |
| `real_tick` (будущее) | бары T + тики | реальные тики | высокий | низкий |

## Примеры разницы

### Standard mode vs Bar Magnifier

```
Standard (bar_close):
  Trade #1: entry=89090, exit=89313 (SL), PnL=-$254
  
Bar Magnifier:
  Trade #1: entry=89090, exit=88441 (TP), PnL=+$724
  
Разница: TP сработал ПЕРВЫМ в реальности!
```

### Общий результат тестирования (январь 2026)

```
Standard Mode:
  Net Profit: -$5,273.10
  Win Rate: 21.15%
  Max Drawdown: 39.46%
  SL Exits: 41, TP Exits: 10

Bar Magnifier Mode (O-HL-heuristic, 0 subticks):
  Net Profit: -$4,864.05
  Win Rate: 23.08%
  Max Drawdown: 35.84%
  SL Exits: 40, TP Exits: 11

Улучшение:
  Net Profit: +$409.05 (+7.8%)
  Win Rate: +1.92pp
  Max Drawdown: -3.62pp (меньше просадка)
  1 сделка изменила SL → TP благодаря точному определению порядка
```

## Использование API

```python
from backend.backtesting.intrabar_engine import IntrabarEngine, IntrabarConfig, OHLCPath
from backend.backtesting.broker_emulator import BrokerEmulator, BrokerConfig

# 1. Создать IntrabarEngine
intrabar_config = IntrabarConfig(
    ohlc_path=OHLCPath.O_HL_HEURISTIC,
    subticks_per_segment=0,
)
intrabar = IntrabarEngine(intrabar_config)
intrabar.load_m1_data(m1_dataframe)

# 2. Создать BrokerEmulator
broker_config = BrokerConfig(
    leverage=10.0,
    taker_fee=0.0004,
    sl_priority=True,
)
broker = BrokerEmulator(broker_config, initial_capital=10000.0)

# 3. Основной цикл
for bar_T in bars_T:
    # Получить сигналы стратегии
    signals = strategy.generate_signals(bar_T)
    
    # Обработать тики внутри бара
    bar_start_ms = int(bar_T.name.timestamp() * 1000)
    bar_end_ms = bar_start_ms + interval_ms
    
    for tick in intrabar.generate_ticks(bar_start_ms, bar_end_ms):
        # Обработать ордера на тике
        fills = broker.process_tick(tick.price, tick.timestamp_ms)
        
        # Логировать fills
        for fill in fills:
            print(f"Fill: {fill.side} {fill.size} @ {fill.price}")
```

## Roadmap

- [x] IntrabarEngine - генератор тиков
- [x] BrokerEmulator - tick-by-tick исполнение
- [x] Config fields в BacktestConfig
- [x] Интеграция в основной engine.py
- [x] Frontend UI для выбора OHLC path
- [x] MFE/MAE на основе тиков (аудит метрик)
- [x] exit_comment для отслеживания типа выхода
- [ ] Real tick data support (будущее)
- [ ] WebSocket real-time tick streaming (будущее)
