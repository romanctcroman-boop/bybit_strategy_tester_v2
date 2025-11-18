# ТИПЫ ДАННЫХ ДЛЯ ТОРГОВОЙ ПЛАТФОРМЫ

**Версия:** 1.1 (исправлено 2025-01-26)
**Соответствие:** ТЕХНИЧЕСКОЕ ЗАДАНИЕ.md раздел 4

---

## 1. ИСТОРИЧЕСКИЕ ДАННЫЕ (OHLCV)

### 1.1. Свечные данные (Candlestick)

```typescript
// TypeScript Interface
interface OHLCVCandle {
  timestamp: number;        // Unix timestamp в миллисекундах
  time: string;             // ISO 8601 формат "2025-07-01T16:15:00Z"
  open: number;             // Цена открытия
  high: number;             // Максимум
  low: number;              // Минимум
  close: number;            // Цена закрытия
  volume: number;           // Объем торгов
  turnover?: number;        // Оборот в USDT (опционально)
}
```

```python
# Python Pydantic Model
from pydantic import BaseModel
from datetime import datetime

class OHLCVCandle(BaseModel):
    """
    Свечные данные OHLCV
    Источник: Bybit API v5 /v5/market/kline
    Использование: Основа для всех графиков и индикаторов
    """
    timestamp: int          # Unix ms, например: 1719847200000
    time: datetime          # Преобразованное время
    open: float             # Пример: 38.999
    high: float             # Пример: 39.311
    low: float              # Пример: 38.567
    close: float            # Пример: 39.147
    volume: float           # Пример: 145234.56
    turnover: float | None = None  # Опционально
```

**Комментарий:** Базовый тип для всех графиков. В RAM хранится 500 последних свечей на каждый таймфрейм.

---

## 2. СДЕЛКИ (TRADES LOG)

### 2.1. Запись сделки (Trade Entry)

```typescript
interface TradeEntry {
  tradeNumber: number;           // Номер сделки (уникальный)
  type: 'Entry long' | 'Exit long' | 'Entry short' | 'Exit short';
  dateTime: string;              // Формат: "YYYY-MM-DD HH:MM" (ISO 8601)
  signal: string;                // "buy" | "L_2" | "L_3" | "Long Trail" | "Long Cond TP" | "Long Cond SL"
  priceUSDT: number;             // Цена исполнения
  positionSizeQty: number;       // Количество контрактов
  positionSizeValue: number;     // Стоимость позиции в USDT
  netPLUSDT: number;             // Чистый P&L (с учетом комиссий)
  netPLPercent: number;          // P&L в процентах
  runUpUSDT: number;             // Максимальная прибыль внутри сделки
  runUpPercent: number;          // Run-up в %
  drawdownUSDT: number;          // Максимальный убыток внутри сделки
  drawdownPercent: number;       // Drawdown в %
  cumulativePLUSDT: number;      // Накопленный P&L
  cumulativePLPercent: number;   // Накопленный P&L в %
}
```

```python
class TradeEntry(BaseModel):
    """
    Запись о входе/выходе в позицию
    Источник: Генерируется движком бэктестирования
    CSV: List-of-trades.csv
    Использование: Основной лог всех сделок для анализа
    
    ⚠️ ВАЖНО: Формат даты изменен на ISO 8601 для соответствия ТЗ раздел 4.1
    """
    trade_number: int                    # Trade #
    type: Literal['Entry long', 'Exit long', 'Entry short', 'Exit short']
    date_time: str                       # "2025-07-02 19:00" (YYYY-MM-DD HH:MM)
    signal: str                          # Название сигнала
    price_usdt: float                    # 39.311
    position_size_qty: float             # 3.725
    position_size_value: float           # 145.271275
    net_pl_usdt: float                   # 1.02
    net_pl_percent: float                # 0.70
    run_up_usdt: float                   # 1.75
    run_up_percent: float                # 1.20
    drawdown_usdt: float                 # -8.13
    drawdown_percent: float              # -5.59
    cumulative_pl_usdt: float            # 0.84
    cumulative_pl_percent: float         # 0.08
```

**Комментарий:** Каждая сделка состоит из 2 записей (Entry + Exit). Используется для построения equity curve и расчета всех метрик.

**⚠️ ИЗМЕНЕНИЕ от версии 1.0:**
- Старый формат: `"02.07.2025 19:00"` (DD.MM.YYYY HH:MM)
- Новый формат: `"2025-07-02 19:00"` (YYYY-MM-DD HH:MM)
- Причина: Соответствие ТЗ раздел 4.1 и ISO 8601 стандарт

---

## 3. МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ

### 3.1. Performance Metrics

```typescript
interface PerformanceMetrics {
  // Для каждого направления: All, Long, Short
  openPL: {
    usdt: number;                // Открытый P&L
    percent: number;
  };
  netProfit: {
    usdt: number;                // Чистая прибыль
    percent: number;             // 42.42%
  };
  grossProfit: {
    usdt: number;                // Сумма всех прибыльных сделок
    percent: number;
  };
  grossLoss: {
    usdt: number;                // Сумма всех убыточных сделок
    percent: number;
  };
  commissionPaid: {
    usdt: number;                // Уплаченные комиссии
  };
  buyHoldReturn: {
    usdt: number;                // Пассивная доходность
    percent: number;
  };
  maxEquityRunUp: {
    usdt: number;                // Макс. рост капитала
    percent: number;
  };
  maxEquityDrawdown: {
    usdt: number;                // Макс. просадка
    percent: number;
  };
  maxContractsHeld: number;      // Макс. позиций одновременно
}
```

```python
class PerformanceMetrics(BaseModel):
    """
    Метрики производительности стратегии
    Источник: Расчет на основе List-of-trades.csv
    CSV: Performance.csv
    Использование: Главные показатели эффективности
    """
    open_pl_usdt: float                  # -4.22
    open_pl_percent: float               # -0.30
    net_profit_usdt: float               # 424.19
    net_profit_percent: float            # 42.42
    gross_profit_usdt: float             # 965.45
    gross_profit_percent: float          # 96.54
    gross_loss_usdt: float               # 541.25
    gross_loss_percent: float            # 54.13
    commission_paid_usdt: float          # 48.22
    buy_hold_return_usdt: float          # 4.64
    buy_hold_return_percent: float       # 0.46
    max_equity_run_up_usdt: float        # 450.07
    max_equity_run_up_percent: float     # 31.04
    max_equity_drawdown_usdt: float      # 94.86
    max_equity_drawdown_percent: float   # 6.55
    max_contracts_held: int              # 18
```

**Комментарий:** Рассчитывается после завершения бэктеста. Отображается в карточках метрик на дашборде.

---

### 3.2. Risk-Performance Ratios

```typescript
interface RiskPerformanceRatios {
  sharpeRatio: number;           // 1.59
  sortinoRatio: number;          // 0 (если не рассчитан)
  profitFactor: number;          // 1.784 (Gross Profit / Gross Loss)
  marginCalls: number;           // 0
}
```

```python
class RiskPerformanceRatios(BaseModel):
    """
    Коэффициенты риска и эффективности
    Источник: Расчет на основе equity curve и распределения доходности
    CSV: Risk-performance-ratios.csv
    Использование: Оценка риск-скорректированной доходности
    
    Формулы (ТЗ 3.4.2):
    - Sharpe: (returns.mean() * 252) / (returns.std() * sqrt(252))
    - Sortino: (returns.mean() * 252) / (downside_std * sqrt(252))
    - Profit Factor: gross_profit / gross_loss
    """
    sharpe_ratio: float                  # 1.59
    sortino_ratio: float                 # 0 или рассчитанное значение
    profit_factor: float                 # 1.784
    margin_calls: int                    # 0
```

**Комментарий:** Sharpe > 1.5 и Profit Factor > 1.5 — хорошие показатели для стратегии.

---

### 3.3. Trades Analysis

```typescript
interface TradesAnalysis {
  totalTrades: number;                   // 331
  totalOpenTrades: number;               // 2
  winningTrades: number;                 // 248
  losingTrades: number;                  // 83
  percentProfitable: number;             // 74.92
  avgPL: {
    usdt: number;                        // 1.28
    percent: number;                     // 1.12
  };
  avgWinningTrade: {
    usdt: number;                        // 3.89
    percent: number;                     // 2.87
  };
  avgLosingTrade: {
    usdt: number;                        // 6.52 (абсолютное значение)
    percent: number;                     // 4.08
  };
  ratioAvgWinAvgLoss: number;           // 0.597
  largestWinningTrade: {
    usdt: number;                        // 12.81
    percent: number;                     // 6.78
  };
  largestLosingTrade: {
    usdt: number;                        // 14.12
    percent: number;                     // 9.71
  };
  avgBarsInTrades: number;              // 56
  avgBarsInWinningTrades: number;       // 50
  avgBarsInLosingTrades: number;        // 75
}
```

```python
class TradesAnalysis(BaseModel):
    """
    Детальный анализ сделок
    Источник: Статистический анализ List-of-trades.csv
    CSV: Trades-analysis.csv
    Использование: Диагностика качества сделок
    """
    total_trades: int                              # 331
    total_open_trades: int                         # 2
    winning_trades: int                            # 248
    losing_trades: int                             # 83
    percent_profitable: float                      # 74.92
    avg_pl_usdt: float                             # 1.28
    avg_pl_percent: float                          # 1.12
    avg_winning_trade_usdt: float                  # 3.89
    avg_winning_trade_percent: float               # 2.87
    avg_losing_trade_usdt: float                   # 6.52
    avg_losing_trade_percent: float                # 4.08
    ratio_avg_win_avg_loss: float                  # 0.597
    largest_winning_trade_usdt: float              # 12.81
    largest_winning_trade_percent: float           # 6.78
    largest_losing_trade_usdt: float               # 14.12
    largest_losing_trade_percent: float            # 9.71
    avg_bars_in_trades: int                        # 56
    avg_bars_in_winning_trades: int                # 50
    avg_bars_in_losing_trades: int                 # 75
```

**Комментарий:** Процент прибыльных > 60% и Ratio > 0.5 — признаки устойчивой стратегии.

---

## 4. КОНФИГУРАЦИЯ СТРАТЕГИИ

### 4.1. Entry Conditions

```typescript
interface EntryConditions {
  capital: {
    initialDeposit: number;              // 1000.0
    leverage: number;                    // 1-100
    maxPositions: number;                // 3
    positionSizing: 'fixed_pct' | 'kelly' | 'volatility_based';
    riskPerTrade: number;                // 2.0%
  };
  signals: Signal[];
  filters: Filter[];
}

interface Signal {
  name: string;                          // "buy" | "L_2" | "L_3"
  type: 'indicator_cross' | 'pattern' | 'price_action';
  params: Record<string, any>;
}

interface Filter {
  name: string;                          // "trend_filter"
  type: 'moving_average' | 'atr' | 'volume';
  params: Record<string, any>;
}
```

```python
from typing import Any, Literal

class Signal(BaseModel):
    """
    Сигнал входа в позицию
    Использование: Условие для открытия сделки
    """
    name: str                            # "buy", "L_2", "L_3"
    type: Literal['indicator_cross', 'pattern', 'price_action']
    params: dict[str, Any]

class Filter(BaseModel):
    """
    Фильтр для подтверждения сигнала
    Использование: Дополнительное условие входа
    """
    name: str                            # "trend_filter"
    type: Literal['moving_average', 'atr', 'volume', 'time']
    params: dict[str, Any]

class CapitalConfig(BaseModel):
    """Конфигурация капитала"""
    initial_deposit: float               # 1000.0
    leverage: int                        # 1-100
    max_positions: int                   # 3
    position_sizing: Literal['fixed_pct', 'kelly', 'volatility_based']
    risk_per_trade: float                # 2.0

class EntryConditions(BaseModel):
    """
    Полный набор условий входа
    Использование: Конфигурация стратегии
    """
    capital: CapitalConfig
    signals: list[Signal]
    filters: list[Filter]
```

---

### 4.2. Exit Conditions

```typescript
interface ExitConditions {
  takeProfit: {
    enabled: boolean;
    type: 'fixed_pct' | 'atr_based' | 'dynamic';
    value: number;                       // 5.0%
    signalName: string;                  // "Long Cond TP"
  };
  stopLoss: {
    enabled: boolean;
    type: 'fixed_pct' | 'atr_based';
    value: number;                       // 2.0%
    signalName: string;                  // "Long Cond SL"
  };
  trailingStop: {
    enabled: boolean;
    activation: number;                  // 2.0%
    distance: number;                    // 1.0%
    signalName: string;                  // "Long Trail"
  };
  timeExit: {
    enabled: boolean;
    maxBars: number;                     // 50
    signalName: string;
  };
}
```

```python
class TakeProfitConfig(BaseModel):
    """Конфигурация тейк-профита"""
    enabled: bool
    type: Literal['fixed_pct', 'atr_based', 'dynamic']
    value: float
    signal_name: str

class StopLossConfig(BaseModel):
    """Конфигурация стоп-лосса"""
    enabled: bool
    type: Literal['fixed_pct', 'atr_based']
    value: float
    signal_name: str

class TrailingStopConfig(BaseModel):
    """Конфигурация трейлинг-стопа"""
    enabled: bool
    activation: float
    distance: float
    signal_name: str

class TimeExitConfig(BaseModel):
    """Конфигурация выхода по времени"""
    enabled: bool
    max_bars: int
    signal_name: str

class ExitConditions(BaseModel):
    """
    Полный набор условий выхода
    Использование: Управление рисками и фиксация прибыли
    """
    take_profit: TakeProfitConfig
    stop_loss: StopLossConfig
    trailing_stop: TrailingStopConfig
    time_exit: TimeExitConfig
```

---

## 5. РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ

### 5.1. Optimization Result

```typescript
interface OptimizationResult {
  parameters: Record<string, number>;    // {tp: 5.0, sl: 2.0, trail: 1.0}
  metrics: {
    netProfit: number;
    maxDrawdown: number;
    sharpeRatio: number;
    profitFactor: number;
    percentProfitable: number;
  };
  score: number;                         // Функция полезности
  rank: number;                          // Позиция в рейтинге
}
```

```python
class OptimizationResult(BaseModel):
    """
    Результат одной комбинации параметров
    Источник: Модуль оптимизации
    Использование: Сравнение и выбор лучших параметров
    """
    parameters: dict[str, float]         # {"tp_percent": 5.0, "sl_percent": 2.0}
    metrics: PerformanceMetrics
    score: float                         # Например: (net_profit / max_dd) * sharpe
    rank: int                            # Позиция в топе
```

---

## 6. EQUITY CURVE

```typescript
interface EquityPoint {
  timestamp: number;
  dateTime: string;                      // "YYYY-MM-DD HH:MM" (ISO 8601)
  equity: number;                        // Текущий капитал
  drawdown: number;                      // Просадка от пика
  cumulativePL: number;                  // Накопленный P&L
}
```

```python
class EquityPoint(BaseModel):
    """
    Точка на equity curve
    Источник: Cumulative P&L из List-of-trades.csv
    Использование: Построение графика роста капитала
    """
    timestamp: int
    date_time: str                       # "2025-07-02 19:00" (YYYY-MM-DD HH:MM)
    equity: float                        # initial_deposit + cumulative_pl
    drawdown: float                      # max(equity) - equity
    cumulative_pl: float
```

---

## 📝 CHANGELOG

### Version 1.1 (2025-01-26)

**Изменения:**
- ✅ Формат даты изменен с `DD.MM.YYYY HH:MM` на `YYYY-MM-DD HH:MM`
- ✅ Добавлены комментарии к формулам Risk-Performance Ratios
- ✅ Добавлена структура CapitalConfig, TakeProfitConfig и др.
- ✅ Улучшена документация для всех типов

**Причина изменений:**
- Соответствие ТЕХНИЧЕСКОЕ ЗАДАНИЕ.md раздел 4.1
- Стандарт ISO 8601 для международной совместимости
- Упрощение парсинга дат в различных локалях

### Version 1.0 (исходная)

**Первоначальная версия из PERP/Demo/**

---

**Это полный набор типов данных для проекта bybit_strategy_tester_v2.**
**Все типы взаимосвязаны и обеспечивают работу всех модулей платформы.**
