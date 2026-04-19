# Universal Math Engine v2.4 - AI/ML Suite

## 🎯 Назначение

Universal Math Engine решает критическую проблему архитектуры - **фрагментированные движки** с неполным покрытием параметров.

**Версия 2.4** добавляет полноценный **AI/ML Suite** для продвинутого трейдинга.

### Проблема до этого:

| Engine            | RSI | MACD | DCA | Trailing | Breakeven | MTF     | Position Sizing |
| ----------------- | --- | ---- | --- | -------- | --------- | ------- | --------------- |
| FastGridOptimizer | ✅  | ❌   | ❌  | ❌       | ❌        | ❌      | ❌              |
| FallbackEngineV4  | ✅  | ✅   | ✅  | ✅       | ✅        | Partial | Partial         |
| MTFOptimizer      | ✅  | ❌   | ❌  | ❌       | ❌        | ✅      | ❌              |

### Решение:

**UniversalMathEngine v2.4** - единый модульный движок с **100%+ покрытием** всех 167+ параметров из `BacktestInput` + **AI/ML возможности**.

## 📦 Архитектура v2.4

```
backend/backtesting/universal_engine/
├── __init__.py              # Экспорты (200+ классов) - v2.4.0
├── core.py                  # Главный оркестратор UniversalMathEngine
├── core_v23.py              # Расширенный v2.3 движок с интеграциями
│
├── # === CORE MODULES (v1.0) ===
├── signal_generator.py      # Генерация сигналов (RSI, MACD, Bollinger, etc.)
├── filter_engine.py         # Фильтрация (MTF, BTC, Volume, Volatility, etc.)
├── position_manager.py      # Position sizing (Fixed, Risk, Kelly, Volatility)
├── risk_manager.py          # Risk limits (Max DD, consecutive losses, etc.)
├── trade_executor.py        # Execution (SL/TP/Trailing/Breakeven/DCA)
├── optimizer.py             # Grid/Random optimization
│
├── # === ADVANCED MODULES (v2.0-v2.2) ===
├── advanced_features.py     # Scale-in, Partial Close, Time Exit, Slippage
├── advanced_optimization.py # Bayesian, Genetic, Walk-Forward, Monte Carlo
├── portfolio_metrics.py     # Portfolio Mode, Correlation Manager
├── realistic_simulation.py  # Tick simulation, Liquidation
├── trading_enhancements.py  # Orders, Risk Management, Filters
│
├── # === V2.3 MODULES ===
├── order_book.py            # L2 Orderbook, Market Impact
├── gpu_acceleration.py      # CUDA/OpenCL GPU Acceleration
├── multi_exchange.py        # Multi-Exchange Arbitrage
├── realtime_data.py         # WebSocket Streaming
├── advanced_signals.py      # ML Feature Engineering
│
├── # === V2.4 MODULES (AI/ML Suite) ===
├── regime_detection.py      # ⭐ ML Market Regime Detection
├── sentiment_analysis.py    # ⭐ Sentiment & Fear/Greed Index
├── risk_parity.py           # ⭐ Portfolio Optimization (HRP, MVO)
├── automl_strategies.py     # ⭐ AutoML Strategy Generation
├── reinforcement_learning.py # ⭐ RL Agents (DQN, PPO)
├── options_strategies.py    # ⭐ Options Pricing (Black-Scholes)
├── live_trading.py          # ⭐ Paper/Live Trading Bridge
├── visualization.py         # ⭐ Advanced Plotly Charts
│
└── tests/
    └── test_v24_features.py # 61 tests for v2.4
```

## 🆕 Новое в v2.4 (AI/ML Suite)

### 🧠 Regime Detection (regime_detection.py)

- **MarketRegime**: BULL, BEAR, SIDEWAYS, HIGH_VOLATILITY, LOW_VOLATILITY
- **RuleBasedDetector**: Детекция на правилах
- **ClusteringDetector**: K-Means, DBSCAN кластеризация
- **EnsembleDetector**: Ансамбль методов

### 📊 Sentiment Analysis (sentiment_analysis.py)

- **Fear & Greed Index**: Расчёт индекса страха/жадности
- **LexiconAnalyzer**: Анализ текста по словарю
- **NewsAnalyzer**: Анализ новостей
- **SentimentLevel**: EXTREME_FEAR → EXTREME_GREED

### 💼 Risk Parity (risk_parity.py)

- **RiskParityOptimizer**: Risk Parity оптимизация
- **HierarchicalRiskParity**: HRP по Marcos Lopez de Prado
- **MeanVarianceOptimizer**: Классическая MVO
- **CovarianceEstimator**: Ledoit-Wolf, MCD

### 🤖 Reinforcement Learning (reinforcement_learning.py)

- **DQNAgent**: Deep Q-Network
- **PPOAgent**: Proximal Policy Optimization
- **TradingEnvironment**: Gym-like trading env
- **ExperienceReplay**: Replay buffer

### 📈 Options Strategies (options_strategies.py)

- **BlackScholes**: Call/Put pricing
- **GreeksCalculator**: Delta, Gamma, Theta, Vega
- **BinomialTree**: American options
- **VolatilitySurface**: IV surface

### 🔴 Live Trading (live_trading.py)

- **PaperTradingEngine**: Paper trading (async)
- **RiskManager**: Лимиты и контроль
- **LiveTradingBridge**: Bridge к биржам
- **Async Operations**: Non-blocking I/O

### 📊 Visualization (visualization.py)

- **EquityCurveChart**: Equity + Drawdown
- **CorrelationMatrixChart**: Correlation heatmap
- **Surface3DChart**: 3D optimization surface
- **TradingDashboard**: Комплексный dashboard

---

## 🆕 Новое в v2.3

### 📊 Order Book Simulation

- **L2 Order Book**: Реалистичная симуляция книги ордеров
- **Market Impact**: Almgren-Chriss модель влияния на цену
- **Liquidation Cascade**: Симуляция каскадных ликвидаций
- **Order Flow Analysis**: Анализ потока ордеров и дисбаланса

### ⚡ GPU Acceleration

- **CuPy Backend**: NVIDIA CUDA ускорение
- **Batch Backtesting**: Параллельный бэктестинг
- **Vectorized Indicators**: GPU-ускоренные RSI, MACD, BB
- **Automatic Fallback**: CPU fallback если GPU недоступен

### 🌐 Multi-Exchange Arbitrage

- **Spatial Arbitrage**: Межбиржевой арбитраж
- **Triangular Arbitrage**: Треугольный арбитраж
- **Funding Arbitrage**: Арбитраж фандинга
- **Latency Simulation**: Симуляция задержек

### 📡 Real-time Data Streaming

- **WebSocket Manager**: Унифицированный стриминг
- **Candle Aggregator**: Построение свечей из тиков
- **Order Book Stream**: Потоковое обновление стакана
- **Trade Stream**: Поток сделок

### 🧠 Advanced ML Signals

- **Feature Engine**: 50+ технических фич
- **MLP Classifier**: Нейросетевая классификация сигналов
- **Ensemble Predictor**: Ансамбль моделей
- **Adaptive Generator**: Самонастраивающиеся сигналы

## 🚀 Быстрый старт

### Одиночный бэктест

```python
from backend.backtesting.universal_engine import UniversalMathEngine

engine = UniversalMathEngine()

result = engine.run(
    candles=df,  # DataFrame with OHLCV
    strategy_type="rsi",
    strategy_params={"period": 14, "overbought": 70, "oversold": 30},
    initial_capital=10000,
    direction="both",
    stop_loss=0.02,
    take_profit=0.03,
    leverage=10,
)

print(f"Total trades: {result.metrics.total_trades}")
print(f"Net profit: {result.metrics.net_profit:.2f}")
print(f"Win rate: {result.metrics.win_rate:.2%}")
print(f"Sharpe: {result.metrics.sharpe_ratio:.2f}")
```

### Оптимизация

```python
from backend.backtesting.universal_engine import UniversalOptimizer

optimizer = UniversalOptimizer()

result = optimizer.optimize(
    candles=df,
    strategy_type="rsi",
    base_params={"strategy_params": {}},
    param_ranges={
        "period": [10, 14, 21],
        "overbought": [70, 75, 80],
        "oversold": [20, 25, 30],
    },
    initial_capital=10000,
    direction="both",
    leverage=10,
    optimize_metric="sharpe_ratio",
    filters={"min_trades": 5},
    method="grid",  # or "random"
    top_n=10,
)

print(f"Best params: {result.best_result.params}")
print(f"Best Sharpe: {result.best_result.score:.2f}")
```

### Quick Optimize

```python
result = optimizer.quick_optimize(
    candles=df,
    strategy_type="rsi",
    direction="both",
    optimize_metric="sharpe_ratio",
)
```

## 📊 Поддерживаемые стратегии

| Strategy         | Parameters                                       |
| ---------------- | ------------------------------------------------ |
| **RSI**          | period, overbought, oversold                     |
| **MACD**         | fast_period, slow_period, signal_period          |
| **Bollinger**    | period, std_dev                                  |
| **Stochastic**   | k_period, d_period, smooth, overbought, oversold |
| **MA Crossover** | fast_period, slow_period, ma_type                |
| **SuperTrend**   | atr_period, multiplier                           |
| **Custom**       | Через callback функцию                           |

## 🎛️ Поддерживаемые фильтры

- **MTF (Multi-Timeframe)**: HTF trend confirmation
- **BTC Correlation**: Фильтрация по корреляции с BTC
- **Volume**: Минимальный объём
- **Volatility**: ATR percentile range
- **Trend**: MA-based trend filter
- **Momentum**: RSI momentum filter
- **Time**: Session и weekend filters
- **Market Regime**: Bull/Bear/Ranging detection

## 💰 Position Sizing Modes

| Mode           | Description                      |
| -------------- | -------------------------------- |
| **Fixed**      | Фиксированный % от капитала      |
| **Risk**       | Размер на основе риска на сделку |
| **Kelly**      | Критерий Келли с fraction        |
| **Volatility** | ATR-based sizing                 |

## 🛡️ Risk Management

- `max_drawdown` - Максимальный допустимый drawdown
- `max_daily_trades` - Лимит сделок в день
- `max_consecutive_losses` - Макс. серия убытков
- `cooldown_bars` - Пауза после убыточной серии

## 📈 Метрики

```python
@dataclass
class EngineMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    net_profit: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    avg_trade_pnl: float
    avg_win: float
    avg_loss: float
    expectancy: float
    max_consecutive_wins: int
    max_consecutive_losses: int
```

## 🧪 Тестирование

```bash
# Запуск всех тестов Universal Engine
python -m pytest backend/backtesting/universal_engine/tests/ -v

# v2.4 тесты
python -m pytest backend/backtesting/universal_engine/tests/test_v24_features.py -v
# Результат: 61 tests passed

# Все тесты: ~120+ tests
```

## 🔄 История версий

| Version    | Features                                                      |
| ---------- | ------------------------------------------------------------- |
| v1.0.0     | Core modules: SignalGenerator, FilterEngine, PositionManager  |
| v2.0.0     | Advanced Features: Scale-in, Partial Close, Time Exit         |
| v2.1.0     | Realistic Simulation: Tick-by-tick, Liquidation, ML Interface |
| v2.2.0     | Trading Enhancements: Orders, Risk Management, Filters        |
| v2.3.0     | Order Book, GPU Acceleration, Multi-Exchange, ML Signals      |
| **v2.4.0** | **AI/ML Suite: Regime Detection, RL, Options, Live Trading**  |

## 📝 Версия

- **Version**: 2.4.0
- **Created**: 2025-01-27
- **Updated**: 2026-01-27
- **Author**: Universal Math Engine Team
- **Tests**: 120+ passing (61 for v2.4)
- **Exports**: 200+ classes

## 📚 Документация

- [UNIVERSAL_MATH_ENGINE_V24.md](../../.agent/docs/UNIVERSAL_MATH_ENGINE_V24.md) - Full v2.4 API
- [DECISIONS.md](../../.agent/docs/DECISIONS.md) - ADR-012: v2.4 decisions
- [CHANGELOG.md](../../CHANGELOG.md) - Version history
