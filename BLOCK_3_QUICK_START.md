# 🚀 БЛОК 3: QUICK START GUIDE

Быстрое руководство по использованию Data Layer компонентов.

---

## 📦 УСТАНОВКА

### 1. Python Dependencies (уже установлены)
```bash
pip install sqlalchemy alembic requests websockets redis pandas numpy
```

### 2. Redis (для CacheService)
- **Windows**: https://github.com/tporadowski/redis/releases
- Скачать Redis-x64-5.0.14.1.msi
- Установить и запустить: `redis-server`

---

## 🎯 ИСПОЛЬЗОВАНИЕ

### 1️⃣ DataService - Работа с БД

```python
from backend.services.data_service import DataService
from datetime import datetime

# Context manager (рекомендуется)
with DataService() as ds:
    # Создать стратегию
    strategy = ds.create_strategy(
        name="RSI Strategy",
        description="Buy when RSI < 30",
        strategy_type="Indicator-Based",
        config={"rsi_period": 14, "oversold": 30}
    )
    
    # Создать бэктест
    backtest = ds.create_backtest(
        strategy_id=strategy.id,
        symbol="BTCUSDT",
        timeframe="15",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        initial_capital=10000.0
    )
    
    # Создать трейды (batch)
    trades = [
        {
            'backtest_id': backtest.id,
            'timestamp': datetime(2024, 1, 1, 10, 0),
            'side': 'LONG',
            'price': 50000.0,
            'quantity': 0.1,
            'pnl': 100.0
        },
        # ... еще трейды
    ]
    ds.create_trades_batch(trades)
    
    # Обновить результаты бэктеста
    ds.update_backtest_results(
        backtest_id=backtest.id,
        final_capital=12000.0,
        total_return=20.0,
        total_trades=50,
        win_rate=65.0,
        sharpe_ratio=1.85
    )
```

---

### 2️⃣ BybitDataLoader - Загрузка данных

```python
from backend.services.bybit_data_loader import BybitDataLoader, quick_load
from datetime import datetime, timedelta

# 🚀 БЫСТРЫЙ СПОСОБ
count = quick_load('BTCUSDT', '15', days_back=30)
print(f"Loaded {count} candles")

# 🔧 РУЧНОЙ СПОСОБ
loader = BybitDataLoader()

# Получить доступные символы
symbols = loader.get_available_symbols()
print(f"Available: {len(symbols)} USDT pairs")

# Загрузить последние 100 свечей
candles = loader.fetch_klines('BTCUSDT', '15', limit=100)

# Загрузить за период
start = datetime.utcnow() - timedelta(days=7)
end = datetime.utcnow()
candles = loader.fetch_klines_range('BTCUSDT', '15', start, end)

# Загрузить и сохранить в БД
count = loader.load_and_save('ETHUSDT', '15', days_back=30)
```

**Поддерживаемые таймфреймы**:
- Minutes: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720
- Daily: D
- Weekly: W
- Monthly: M

---

### 3️⃣ WebSocketManager - Real-time данные

```python
from backend.services.websocket_manager import WebSocketManager
import time

ws = WebSocketManager()

# 📡 СПОСОБ 1: Декораторы (рекомендуется)
@ws.on_kline('BTCUSDT', '1')
def handle_kline(data):
    if isinstance(data, list) and len(data) > 0:
        candle = data[0]
        print(f"🕯️ BTCUSDT 1m: Close={candle.get('close')}")

@ws.on_trade('BTCUSDT')
def handle_trade(data):
    if isinstance(data, list) and len(data) > 0:
        trade = data[0]
        print(f"💱 Trade: {trade.get('p')} x {trade.get('v')}")

@ws.on_ticker('BTCUSDT')
def handle_ticker(data):
    if isinstance(data, dict):
        print(f"📈 Last: {data.get('lastPrice')}, Vol: {data.get('volume24h')}")

# Запустить WebSocket
ws.start()

# Слушать 60 секунд
time.sleep(60)

# Статистика
stats = ws.get_stats()
print(f"Messages received: {stats['messages_received']}")

# Остановить
ws.stop()

# 📡 СПОСОБ 2: Callback functions
def my_kline_handler(data):
    print(f"Kline: {data}")

ws.subscribe_kline('ETHUSDT', '15', my_kline_handler)
ws.start()
```

**Доступные каналы**:
- `kline` - Candlesticks (1m, 3m, 5m, 15m, 30m, 1h, 4h, D)
- `trade` - Trade executions
- `ticker` - 24h ticker stats
- `orderbook` - Order book depth (1, 50, 200, 500)

---

### 4️⃣ CacheService - Redis кэширование

```python
from backend.services.cache_service import CacheService, get_cache

cache = CacheService()

if cache.is_available():
    # 💾 ПРОСТОЕ КЭШИРОВАНИЕ
    cache.set('my_key', {'data': 'value'}, ttl=300)
    value = cache.get('my_key')
    
    # 🗂️ NAMESPACE КЭШИРОВАНИЕ
    cache.cache_market_data('BTCUSDT', '15', candles, ttl=3600)
    candles = cache.get_market_data('BTCUSDT', '15')
    
    # ⏱️ TTL УПРАВЛЕНИЕ
    ttl = cache.ttl('my_key')  # Оставшееся время
    cache.expire('my_key', 600)  # Обновить TTL
    
    # 🎯 DECORATOR КЭШИРОВАНИЕ (самое удобное!)
    @cache.cached(ttl=300, key_prefix='backtest')
    def run_backtest(strategy_id, symbol):
        # Тяжелые вычисления...
        return result  # Автоматически кэшируется!
    
    # 📦 BACKTEST РЕЗУЛЬТАТЫ
    cache.cache_backtest_result(
        backtest_id=123,
        result={'profit': 15.5, 'sharpe': 1.8},
        ttl=3600
    )
    result = cache.get_backtest_result(123)
    
    # 📊 PUB/SUB
    def handle_update(message):
        print(f"Update: {message}")
    
    cache.subscribe('updates', handle_update)
    cache.publish('updates', {'event': 'new_candle'})
    
    # 🧹 ОЧИСТКА
    cache.flush_namespace('backtest')  # Очистить namespace
    cache.flush_all()  # Очистить всё

else:
    print("⚠️ Redis not available")
```

**Namespaces**:
- `market_data:` - OHLCV candles
- `backtest:` - Backtest results
- `optimization:` - Optimization results
- `strategy:` - Strategy configs
- `session:` - User sessions

---

### 5️⃣ DataPreprocessor - Очистка данных

```python
from backend.services.data_preprocessor import DataPreprocessor

preprocessor = DataPreprocessor()

# 🔍 ВАЛИДАЦИЯ
is_valid, errors = preprocessor.validate_ohlcv(candles)
if errors:
    for error in errors:
        print(f"Error: {error}")

# 🚨 ОБНАРУЖЕНИЕ АНОМАЛИЙ
# Price anomalies (резкие скачки)
anomalies = preprocessor.detect_price_anomalies(candles, threshold_pct=50)
for a in anomalies:
    print(f"Price spike: {a['description']}")

# Volume anomalies (всплески объема)
volume_anomalies = preprocessor.detect_volume_anomalies(candles, threshold_multiplier=100)

# 📊 OUTLIERS (выбросы)
outliers = preprocessor.detect_outliers(candles, method='iqr')
print(f"Outliers: {outliers}")

# 🧹 ОЧИСТКА ДАННЫХ
# Удалить дубликаты
cleaned = preprocessor.remove_duplicates(candles)

# Исправить OHLC relationships
fixed = preprocessor.fix_ohlc_relationships(candles)

# Сгладить выбросы
smoothed = preprocessor.smooth_outliers(candles, outliers, method='interpolate')

# 📈 ЗАПОЛНЕНИЕ ПРОПУСКОВ
filled = preprocessor.fill_missing_candles(
    candles,
    timeframe='15',
    method='forward_fill'  # или 'interpolate', 'zero'
)

# 📉 НОРМАЛИЗАЦИЯ
normalized = preprocessor.normalize_prices(candles, method='minmax')

# 🚀 ПОЛНЫЙ PIPELINE (все в одном)
processed, report = preprocessor.preprocess(
    candles,
    timeframe='15',
    fill_missing=True,
    detect_outliers=True,
    smooth_outliers=True,
    validate=True
)

print(f"Input: {report['input_count']} candles")
print(f"Output: {report['output_count']} candles")
print(f"Validation errors: {len(report['validation_errors'])}")
print(f"Outliers detected: {len(report['outliers'])}")
print(f"Anomalies found: {len(report['anomalies'])}")

# 📊 СТАТИСТИКА
stats = preprocessor.get_stats()
print(f"Total processed: {stats['total_processed']}")
print(f"Invalid candles: {stats['invalid_candles']}")
print(f"Missing filled: {stats['missing_filled']}")
```

---

## 🧪 ТЕСТИРОВАНИЕ

### Запустить core тесты
```bash
cd d:\bybit_strategy_tester_v2
python backend\test_block3_data_layer.py
```

### Запустить optional тесты
```bash
python backend\test_block3_optional.py
```

---

## 📚 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### Полный workflow: Загрузить и обработать данные

```python
from backend.services.bybit_data_loader import quick_load
from backend.services.data_service import DataService
from backend.services.data_preprocessor import DataPreprocessor
from backend.services.cache_service import get_cache

# 1. Загрузить данные с Bybit
count = quick_load('BTCUSDT', '15', days_back=30)
print(f"✅ Loaded {count} candles")

# 2. Получить из БД
with DataService() as ds:
    candles_dict = ds.get_market_data(
        symbol='BTCUSDT',
        timeframe='15',
        start_time=None,  # все данные
        end_time=None
    )

# 3. Обработать данные
preprocessor = DataPreprocessor()
processed, report = preprocessor.preprocess(
    candles_dict,
    timeframe='15',
    fill_missing=True,
    detect_outliers=True,
    smooth_outliers=True
)
print(f"✅ Processed: {report['output_count']} candles")

# 4. Кэшировать результат
cache = get_cache()
if cache.is_available():
    cache.cache_market_data('BTCUSDT', '15', processed, ttl=3600)
    print("✅ Cached data")

# 5. Использовать для бэктеста
# ... ваш код бэктеста
```

### Real-time мониторинг с WebSocket

```python
from backend.services.websocket_manager import WebSocketManager
from backend.services.cache_service import get_cache
import time

ws = WebSocketManager()
cache = get_cache()

# Сохранять last price в Redis
@ws.on_ticker('BTCUSDT')
def save_ticker(data):
    if isinstance(data, dict):
        last_price = data.get('lastPrice')
        if cache.is_available():
            cache.set('BTCUSDT:last_price', last_price, ttl=60)
        print(f"💰 BTCUSDT: ${last_price}")

ws.start()

# Мониторинг 5 минут
time.sleep(300)

# Получить последнюю цену
if cache.is_available():
    last_price = cache.get('BTCUSDT:last_price')
    print(f"Last cached price: ${last_price}")

ws.stop()
```

---

## 🔧 КОНФИГУРАЦИЯ

### Bybit API Rate Limits
- REST API: 10 req/sec (встроено в BybitDataLoader)
- WebSocket: Unlimited subscriptions

### Redis Configuration
```python
# По умолчанию
host = 'localhost'
port = 6379
db = 0
timeout = 5
default_ttl = 3600  # 1 час

# Изменить через __init__
cache = CacheService(host='192.168.1.100', port=6380, db=1)
```

### DataPreprocessor Thresholds
```python
# Price anomaly detection
threshold_pct = 50  # 50% change

# Volume anomaly detection
threshold_multiplier = 100  # 100x average

# Outlier detection
method = 'iqr'  # или 'zscore'
```

---

## ⚠️ TROUBLESHOOTING

### Redis not available
```python
# Проверить Redis
cache = CacheService()
if not cache.is_available():
    print("Redis unavailable - install and run redis-server")
    # Код продолжит работу без кэша
```

### WebSocket connection timeout
```python
# Обычно firewall/antivirus
# Проверить:
# 1. Windows Firewall
# 2. Antivirus settings
# 3. Network proxy
```

### Rate limit exceeded (Bybit)
```python
# BybitDataLoader автоматически ждет 100ms между запросами
# Если все равно ошибка - увеличить delay
loader = BybitDataLoader()
loader.rate_limit_delay = 0.2  # 200ms
```

---

## 📖 ПОЛНАЯ ДОКУМЕНТАЦИЯ

См. `docs/BLOCK_3_CERTIFICATE.md` для:
- Детальное описание всех методов
- Архитектурные решения
- Результаты тестирования
- Примеры использования

---

## 🎯 NEXT STEPS

### Block 4: Backtest Engine
После освоения Data Layer, переходите к:
1. **BacktestEngine** - Core backtesting logic
2. **OrderManager** - Order execution simulation
3. **PositionManager** - Position tracking
4. **MetricsCalculator** - Performance metrics (20+)

Все данные уже готовы для бэктестов! 🚀

---

**Created**: 2025-01-17  
**Author**: GitHub Copilot  
**Status**: ✅ Production Ready
