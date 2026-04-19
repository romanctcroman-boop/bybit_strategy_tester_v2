# backend/services/ — Контекст модуля

## Структура

```
backend/services/
├── data_service.py           # DataService — Repository CRUD (OHLCV + ORM)
├── kline_manager.py          # KlineDataManager Singleton — 4-tier cache
├── kline_db_service.py       # FROZEN — не менять без крайней необходимости
├── smart_kline_service.py    # Умная агрегация klines
├── event_bus.py              (643 lines) # Redis + local pub/sub
├── monte_carlo.py            (561 lines) # MonteCarloSimulator
├── walk_forward.py           (525 lines) # WalkForwardOptimizer
├── adapters/
│   └── bybit.py              (1710 lines) # BybitAdapter — REST + WebSocket
├── live_trading/
│   ├── strategy_runner.py    (821 lines)  # Главный оркестратор live trading
│   ├── order_executor.py                   # Bybit REST, retry, partial fills
│   ├── position_manager.py                 # Open positions + unrealized PnL
│   ├── bybit_websocket.py                  # Real-time klines + trades stream
│   └── graceful_shutdown.py                # SIGTERM → close all positions
├── risk_management/
│   ├── risk_engine.py        (768 lines)  # Координатор (ExposureController + PositionSizer + StopLossManager + TradeValidator)
│   ├── exposure_controller.py (669 lines)
│   ├── position_sizing.py    (525 lines)  # 6 методов sizing
│   ├── stop_loss_manager.py  (548 lines)  # 7 типов SL
│   └── trade_validator.py    (688 lines)  # 18 RejectionReason
└── advanced_backtesting/     # Portfolio strategies
```

## KlineDataManager (Singleton) — 4-tier cache

```python
# backend/services/kline_manager.py
class KlineDataManager:
    _instance = None  # Singleton
    _cache: dict[tuple[str, str, str], pd.DataFrame]
    _locks: dict[tuple[str, str, str], asyncio.Lock]  # Per-key locks

    async def get_klines(self, symbol, interval, start, end, market_type="linear"):
        key = (symbol, interval, market_type)
        async with self._locks[key]:
            # L1 (in-process) → L2 (Redis) → L3 (SQLite) → L4 (Bybit REST)
```

| Level | Store | TTL |
|-------|-------|-----|
| L1 | In-process dict | session |
| L2 | Redis `kline:{symbol}:{interval}:{market_type}` | 5min (hot) / 1h (hist) |
| L3 | SQLite `bybit_klines_15m.db` | persistent |
| L4 | Bybit REST (200 candles/req, 120 req/min) | last resort |

**FROZEN:** `kline_db_service.py` — не трогать без крайней необходимости. Схема фиксирована.

## BybitAdapter (REST + WebSocket)

```python
# backend/services/adapters/bybit.py (1710 lines)

# REST:
async def get_historical_klines(symbol, interval, start, end) → dict
async def get_tickers(category) → list[dict]  # cached 30s TTL
async def get_instruments_info(category) → list[dict]

# WebSocket:
async def subscribe_kline(symbol, interval, callback)
async def subscribe_ticker(symbol, callback)
async def subscribe_orderbook(symbol, depth, callback)
# Auto-reconnect, ping/pong 30s, max 10 subscriptions per connection

# Safety:
# retCode != 0 → retry exponential backoff
# 429 → CircuitBreaker → wait
```

## Live Trading

**Signal flow:**
```
WebSocket → parse_kline → Strategy.generate_signals → RiskEngine.assess_trade
→ OrderExecutor.place_order → PositionManager.track → StopLossManager.monitor
```

**TradingConfig.commission_rate = 0.0007** — синхронизировать с BacktestConfig!

**Критические ловушки:**
- `paper_trading.py` — НЕ отправляет реальные ордера; проверь mode перед деплоем
- `position_size` в live = абсолютное qty; в engine = fraction 0-1 (ADR-006)
- `GracefulShutdown` при SIGTERM закрывает все открытые позиции перед выходом
- `leverage` default: live = 1.0, optimization/UI = 10 — не перепутать

## Risk Management

**RiskEngine** — центральный координатор:
```python
RiskEngine(config: RiskEngineConfig)
    ├── ExposureController   # max 20% equity/position, 200% total, 10x leverage
    ├── PositionSizer        # 6 методов: FIXED_PERCENTAGE, KELLY, HALF_KELLY, VOLATILITY, FIXED_FRACTIONAL, OPTIMAL_F
    ├── StopLossManager      # 7 типов: FIXED, TRAILING, TRAILING_PERCENT, BREAKEVEN, ATR_BASED, CHANDELIER, TIME_BASED
    └── TradeValidator       # 18 RejectionReason enum values
```

**Exposure defaults:**
```python
max_position_size_pct = 20.0    # Max 20% equity per position
max_total_exposure_pct = 200.0  # Max 200% total (2x leverage allowed)
max_leverage = 10.0
max_drawdown_pct = 20.0         # Auto-stop at 20% drawdown
daily_loss_limit_pct = 5.0
```

**Trade rejection** (`RejectionReason` enum, 18 причин):
`INSUFFICIENT_BALANCE`, `POSITION_SIZE_EXCEEDED`, `EXPOSURE_LIMIT_EXCEEDED`, `LEVERAGE_LIMIT_EXCEEDED`, `DAILY_LOSS_LIMIT`, `DRAWDOWN_LIMIT`, `CORRELATION_LIMIT`, `SYMBOL_BLOCKED`, `TRADING_PAUSED`, `INVALID_ORDER_PARAMS`, `MIN_ORDER_SIZE`, `MAX_ORDER_SIZE`, `PRICE_OUT_OF_RANGE`, `MARGIN_REQUIREMENT`, `RISK_REWARD_RATIO`, `STRATEGY_LIMIT`, `COOLDOWN_ACTIVE`, `MAX_TRADES_REACHED`

## Monte Carlo & Walk-Forward

```python
# MonteCarloSimulator (monte_carlo.py, 561 lines)
sim = MonteCarloSimulator(n_simulations=10000)
result = sim.analyze_strategy(backtest_results)
# Outputs: probability_of_return, drawdown_confidence_interval, VaR, CVaR

# WalkForwardOptimizer (walk_forward.py, 525 lines)
wfo = WalkForwardOptimizer(n_splits=5, train_ratio=0.7)
result = wfo.optimize(data, strategy_class, param_grid, initial_capital=10000)
# Outputs: stability_score (lower std=better), overfitting_ratio (train/test Sharpe)
```

**Ловушки:**
- Walk-forward `initial_capital=10000` — должен совпадать с engine default
- Monte Carlo на больших trade sets (~10000 симуляций) — может быть медленным

## Другие ключевые сервисы

| Сервис | Файл | Назначение |
|--------|------|-----------|
| `EventBus` | `event_bus.py` | Redis + local pub/sub (643 lines) |
| `MultiLevelCache` | `multi_level_cache.py` | L1 memory + L2 Redis |
| `DataQualityService` | `data_quality_service.py` | OHLCV quality checks + gap repair |
| `GracefulDegradation` | `graceful_degradation.py` | Fallback при недоступности сервисов |
| `DistributedLock` | `distributed_lock.py` | Redis-based distributed locking |

## Тесты

```bash
pytest tests/integration/ -v                      # Integration tests
pytest tests/integration/test_optimizer_real_data.py -v  # Real data (34 tests)
pytest tests/advanced_backtesting/ -v
```
