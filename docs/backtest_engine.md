# BacktestEngine - Руководство

## ✅ Реализовано (MVP)

### Основной движок бэктестирования

Файл: `backend/core/backtest_engine.py`

**Возможности:**
- ✅ Bar-by-bar симуляция торговли
- ✅ EMA Crossover стратегия
- ✅ RSI стратегия (заготовка)
- ✅ Take Profit / Stop Loss
- ✅ Trailing Stop
- ✅ Commission и Slippage
- ✅ Position sizing (fixed %)
- ✅ Run-up / Drawdown tracking
- ✅ Все метрики из ТЗ (Performance, Risk, Trades-analysis)

---

## 🚀 Быстрый старт

### 1. Простой пример (синтетические данные)

```python
from backend.core.backtest_engine import BacktestEngine
import pandas as pd

# Создаём тестовые данные
data = pd.DataFrame({
    'timestamp': pd.date_range('2024-01-01', periods=300, freq='1h'),
    'open': range(100, 400),
    'high': range(101, 401),
    'low': range(99, 399),
    'close': range(100, 400),
    'volume': [1000] * 300
})

# Настройка движка
engine = BacktestEngine(
    initial_capital=10_000.0,
    commission=0.0006,  # 0.06%
    slippage_pct=0.05   # 0.05%
)

# Конфигурация стратегии
strategy_config = {
    'type': 'ema_crossover',
    'fast_ema': 50,
    'slow_ema': 200,
    'take_profit_pct': 5.0,
    'stop_loss_pct': 2.0,
    'risk_per_trade_pct': 2.0,
}

# Запуск
results = engine.run(data, strategy_config)

print(f"Total return: {results['total_return']*100:.2f}%")
print(f"Total trades: {results['total_trades']}")
print(f"Win rate: {results['win_rate']*100:.2f}%")
```

### 2. Реальные данные Bybit

```bash
# Демо-скрипт с готовыми примерами
python scripts/demo_backtest.py BTCUSDT --interval 15 --fast-ema 20 --slow-ema 50

# Параметры:
#   --interval 15       # 15-минутные свечи
#   --limit 500         # 500 баров
#   --capital 10000     # Начальный капитал
#   --fast-ema 20       # Быстрая EMA
#   --slow-ema 50       # Медленная EMA
#   --tp 5.0            # Take Profit 5%
#   --sl 2.0            # Stop Loss 2%
#   --risk 2.0          # Риск на сделку 2%
```

---

## 📊 Конфигурация стратегий

### EMA Crossover

```python
strategy_config = {
    'type': 'ema_crossover',
    'fast_ema': 50,              # Период быстрой EMA
    'slow_ema': 200,             # Период медленной EMA
    'take_profit_pct': 5.0,      # Take Profit %
    'stop_loss_pct': 2.0,        # Stop Loss %
    'trailing_stop_pct': 1.0,    # Trailing Stop % (0 = выключен)
    'risk_per_trade_pct': 2.0,   # Риск на сделку %
    'signal_exit': False,        # Выход по противоположному сигналу
    'max_positions': 1,          # Макс. одновременных позиций
}
```

**Логика входа:**
- Вход в лонг: fast EMA пересекает slow EMA снизу вверх

**Логика выхода (приоритет сверху вниз):**
1. Take Profit достигнут
2. Stop Loss достигнут
3. Trailing Stop сработал
4. Signal exit (fast EMA пересекает slow EMA сверху вниз)

### RSI Strategy (заготовка)

```python
strategy_config = {
    'type': 'rsi',
    'rsi_period': 14,            # Период RSI
    'rsi_oversold': 30,          # Уровень перепроданности
    'rsi_overbought': 70,        # Уровень перекупленности
    'ma_period': 200,            # MA для фильтра тренда
    'take_profit_pct': 5.0,
    'stop_loss_pct': 2.0,
    'risk_per_trade_pct': 2.0,
}
```

---

## 📈 Результаты бэктеста

### Структура возвращаемого словаря

```python
{
    # Основные метрики
    'final_capital': 10500.0,
    'total_return': 0.05,          # 5% (как decimal)
    'total_trades': 10,
    'winning_trades': 7,
    'losing_trades': 3,
    'win_rate': 0.7,               # 70%
    'sharpe_ratio': 1.5,
    'sortino_ratio': 2.1,
    'max_drawdown': 0.05,          # 5%
    'profit_factor': 2.5,
    
    # Расширенные метрики
    'metrics': {
        'net_profit': 500.0,
        'gross_profit': 800.0,
        'gross_loss': -300.0,
        'total_commission': 15.0,
        'max_drawdown_abs': 250.0,
        'max_drawdown_pct': 2.5,
        'max_runup_abs': 600.0,
        'buy_hold_return': 3.5,
        'avg_pnl': 50.0,
        'avg_win': 114.28,
        'avg_loss': -100.0,
        'max_win': 250.0,
        'max_loss': -150.0,
        'avg_bars': 25.5,
        'avg_bars_win': 30.0,
        'avg_bars_loss': 15.0,
    },
    
    # Список сделок
    'trades': [
        {
            'entry_time': '2024-01-01T10:00:00',
            'exit_time': '2024-01-02T15:30:00',
            'entry_price': 100.0,
            'exit_price': 105.0,
            'quantity': 2.0,
            'side': 'long',
            'pnl': 10.0,
            'pnl_pct': 5.0,
            'commission': 0.12,
            'run_up': 12.0,
            'run_up_pct': 6.0,
            'drawdown': 3.0,
            'drawdown_pct': 1.5,
            'bars_held': 30,
            'exit_reason': 'take_profit'
        },
        # ... остальные сделки
    ],
    
    # Equity curve (каждый бар)
    'equity_curve': [
        {
            'timestamp': datetime(...),
            'equity': 10000.0,
            'capital': 10000.0,
            'unrealized_pnl': 0.0,
            'positions_count': 0
        },
        # ...
    ]
}
```

---

## 🧪 Тестирование

```bash
# Запуск всех тестов движка
pytest tests/test_backtest_engine.py -v

# Конкретный тест
pytest tests/test_backtest_engine.py::test_ema_crossover_strategy -v -s
```

### Тесты покрывают:
- ✅ Базовую работу движка
- ✅ EMA Crossover стратегию
- ✅ Trailing Stop
- ✅ Commission и Slippage
- ✅ Обработку пустых данных

---

## 🔧 Расширение функциональности

### Добавление новой стратегии

1. **Добавить расчёт индикаторов** в `_calculate_indicators()`:

```python
elif strategy_type == 'my_strategy':
    # Ваши индикаторы
    indicators['custom_indicator'] = df['close'].rolling(window=20).mean()
```

2. **Добавить логику входа** в `_check_entry()`:

```python
elif strategy_type == 'my_strategy':
    indicator = state.indicators['custom_indicator']
    signal = (bar['close'] > indicator.iloc[i])
```

3. **Опционально: логика выхода** в `_check_exit_signal()`:

```python
elif strategy_type == 'my_strategy':
    return (bar['close'] < indicator.iloc[i])
```

### Пример: Mean Reversion стратегия

```python
# В _calculate_indicators():
if strategy_type == 'mean_reversion':
    period = config.get('ma_period', 20)
    std_mult = config.get('std_multiplier', 2.0)
    
    ma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    indicators['ma'] = ma
    indicators['upper_band'] = ma + (std * std_mult)
    indicators['lower_band'] = ma - (std * std_mult)

# В _check_entry():
elif strategy_type == 'mean_reversion':
    lower = state.indicators['lower_band'].iloc[i]
    if not pd.isna(lower) and bar['close'] < lower:
        signal = True  # Вход когда цена ниже нижней полосы

# В _check_exit_signal():
elif strategy_type == 'mean_reversion':
    ma = state.indicators['ma'].iloc[i]
    return not pd.isna(ma) and bar['close'] > ma  # Выход при возврате к MA
```

---

## 📝 TODO / Будущие улучшения

### Приоритет 1 (для продакшена):
- [ ] Short позиции (сейчас только Long)
- [ ] Пирамидинг (multiple entries как L_2, L_3 из CSV)
- [ ] Kelly Criterion для position sizing
- [ ] Volatility-based position sizing
- [ ] Time-based exits (макс. баров в позиции)
- [ ] Margin trading simulation

### Приоритет 2 (дополнительно):
- [ ] Multi-asset портфели
- [ ] Hedging логика
- [ ] Partial exits (закрытие части позиции)
- [ ] Динамический TP/SL (на основе ATR)
- [ ] Backtesting на tick data (не bar-by-bar)

### Приоритет 3 (оптимизация):
- [ ] Numba JIT компиляция для скорости
- [ ] Cython версия критичных участков
- [ ] Векторизация расчётов
- [ ] Multi-threading для оптимизации

---

## 🐛 Известные ограничения

1. **Только Long позиции** - Short не реализованы
2. **Одна позиция одновременно** (если max_positions=1)
3. **Bar-by-bar execution** - не учитывается intra-bar price action
4. **Упрощённый slippage** - фиксированный процент, не учитывает объём/ликвидность
5. **Нет реализма биржевых стаканов** - предполагается мгновенное исполнение

---

## 📚 Соответствие ТЗ

### Реализовано из ТЗ:

✅ **Модуль 3.3 - Движок Бэктестирования**
- `BacktestEngine` класс
- `run()` метод
- `_process_bar()` логика
- Модель издержек (Commission + Slippage)

✅ **Модуль 3.4 - Метрики**
- Performance metrics (Net Profit, Gross Profit/Loss, Max DD)
- Risk metrics (Sharpe, Sortino, Profit Factor)
- Trades analysis (Win Rate, Avg PnL, etc.)
- Run-up / Drawdown tracking

✅ **Выходные данные**
- Соответствуют `List-of-trades.csv` формату
- Equity curve для визуализации
- Детальная статистика по сделкам

### Частично реализовано:

⚠️ **Модуль 3.2 - Параметры стратегии**
- Entry config: только EMA crossover (не все фильтры)
- Exit config: TP/SL/Trailing (нет time-based, signal частично)
- Position sizing: только fixed % (нет Kelly, volatility-based)

### Не реализовано (запланировано):

❌ **Полный набор индикаторов** из ТЗ
❌ **Пирамидинг** (L_2, L_3 уровни)
❌ **Все типы фильтров** (trend, volatility)
❌ **Short позиции**
❌ **Signal exit** для всех стратегий

---

## 💡 Примеры использования

### Оптимизация параметров вручную

```python
from backend.core.backtest_engine import BacktestEngine
import pandas as pd

# Загрузка данных
data = pd.read_csv('data.csv')

# Grid search по параметрам
best_result = None
best_sharpe = -999

for fast in [10, 20, 50]:
    for slow in [50, 100, 200]:
        if fast >= slow:
            continue
            
        engine = BacktestEngine(initial_capital=10_000.0)
        config = {
            'type': 'ema_crossover',
            'fast_ema': fast,
            'slow_ema': slow,
            'take_profit_pct': 5.0,
            'stop_loss_pct': 2.0,
        }
        
        results = engine.run(data, config)
        
        if results['sharpe_ratio'] > best_sharpe:
            best_sharpe = results['sharpe_ratio']
            best_result = (fast, slow, results)

print(f"Best: EMA({best_result[0]}/{best_result[1]}) - Sharpe: {best_sharpe:.2f}")
```

---

Автор: BacktestEngine Team
Версия: 1.0.0 (MVP)
Дата: 2025-10-25
