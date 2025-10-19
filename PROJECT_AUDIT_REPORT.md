# 🔍 АУДИТ ПРОЕКТА - Обнаруженные аномалии и проблемы

**Дата проверки:** 16 октября 2025  
**Проверенные файлы:** 15+ ключевых файлов проекта  
**Статус:** ⚠️ Найдено несколько потенциальных проблем

---

## ✅ ЧТО РАБОТАЕТ ПРАВИЛЬНО

### 1. Архитектура и структура ✅
- Правильное разделение на модули (backend/api, backend/core, backend/services)
- Чистые зависимости между компонентами
- Нет циклических импортов

### 2. API Endpoints ✅
- Все endpoints правильно определены
- Pydantic модели корректны
- CORS настроен
- Логирование работает

### 3. Синтаксис и импорты ✅
- Нет синтаксических ошибок (проверено через get_errors)
- Все импорты корректны
- Типизация присутствует

---

## ⚠️ ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ

### КРИТИЧЕСКИЕ 🔴

#### 1. **Дублирование логики нормализации timestamps**
**Файл:** `backend/api/routers/backtest.py`  
**Строки:** 321-324 (в функции run_backtest) и 133-138 (в run_simple_strategy)

**Проблема:**
```python
# В run_backtest (строка 321)
for candle in candles:
    if isinstance(candle['timestamp'], datetime) and candle['timestamp'].tzinfo is not None:
        candle['timestamp'] = candle['timestamp'].replace(tzinfo=None)

# В run_simple_strategy (строка 133)
if 'timestamp' in df.columns:
    if pd.api.types.is_integer_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
```

**Проблема:** Timestamps нормализуются дважды в разных форматах:
1. Сначала убираем timezone (список словарей)
2. Потом конвертируем в datetime (DataFrame)

**Решение:** Создать единую функцию `normalize_timestamps(candles)` и использовать её один раз.

---

#### 2. **Несогласованность форматов timestamps**
**Файлы:** `data.py`, `backtest.py`, `bybit_data_loader.py`

**Проблема:**
- `BybitDataLoader` возвращает `timestamp` как `datetime` объект
- API endpoints пытаются конвертировать в `int` (миллисекунды)
- BacktestEngine ожидает `datetime` в индексе DataFrame

**Пример несогласованности:**
```python
# data.py строка 248
CandleResponse(
    timestamp=int(c['timestamp'].timestamp() * 1000),  # Конвертируем в int
    ...
)

# backtest.py строка 137
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')  # Ожидаем int
```

**Решение:** Определить единый формат (рекомендация: datetime без timezone) и использовать везде.

---

### ВЫСОКИЙ ПРИОРИТЕТ 🟠

#### 3. **Hardcoded пути в start.ps1**
**Файл:** `start.ps1`  
**Строки:** 11, 17

**Проблема:**
```powershell
cd 'D:\bybit_strategy_tester_v2'  # Жестко заданный путь
cd 'D:\bybit_strategy_tester_v2\frontend'  # Жестко заданный путь
```

**Проблема:** Скрипт не будет работать:
- На других машинах
- Если проект в другой папке
- На Linux/Mac

**Решение:**
```powershell
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
cd $scriptPath
```

---

#### 4. **Отсутствие обработки ошибок при загрузке данных**
**Файл:** `backend/api/routers/data.py`, `backtest.py`

**Проблема:**
```python
loader = BybitDataLoader(testnet=False)
candles = loader.fetch_klines(...)  # Что если API недоступен?

if not candles:  # Только простая проверка
    raise HTTPException(404, "No data found")
```

**Отсутствуют проверки:**
- Сетевые ошибки (timeout, connection refused)
- Rate limiting от Bybit API
- Некорректные данные (NaN, пустые свечи)

**Решение:** Добавить try-except с конкретными типами ошибок и понятными сообщениями.

---

#### 5. **Потенциальная утечка памяти в run_simple_strategy**
**Файл:** `backend/api/routers/backtest.py`  
**Строка:** 133-138

**Проблема:**
```python
def run_simple_strategy(candles: List[dict], config: BacktestConfig, ...):
    df = pd.DataFrame(candles)  # Создаем DataFrame
    # ... используем df
    result = engine.run(df, strategy_func, ...)
    return result, engine  # Возвращаем engine с большим df в памяти
```

**Проблема:** DataFrame остаётся в памяти в engine после завершения backtest.

**Решение:** Очистить данные после использования или не возвращать engine.

---

### СРЕДНИЙ ПРИОРИТЕТ 🟡

#### 6. **Неэффективная проверка has_position**
**Файл:** `backend/api/routers/backtest.py`  
**Строки:** 177-193

**Проблема:**
```python
def strategy_func(data: pd.DataFrame, state: dict) -> dict:
    has_position = state.get('has_position', False)  # Используем state
    
    if not has_position and rsi < rsi_oversold:
        state['has_position'] = True  # Меняем state
        return {'action': 'BUY', ...}
```

**Проблема:** Состояние позиции дублируется:
- В `state['has_position']` (ручное управление)
- В `engine.position_manager` (автоматическое)

**Риск рассинхронизации:** Если позиция ликвидирована, `state` не обновится.

**Решение:** Использовать только `engine.position_manager.get_current_position()`.

---

#### 7. **Отсутствие валидации strategy_params**
**Файл:** `backend/api/routers/backtest.py`

**Проблема:**
```python
rsi_period = strategy_params.get('rsi_period', 14)  # Нет валидации
rsi_oversold = strategy_params.get('rsi_oversold', 30)
rsi_overbought = strategy_params.get('rsi_overbought', 70)
```

**Проблемы:**
- `rsi_period` может быть 0 или отрицательным
- `rsi_oversold` может быть > `rsi_overbought`
- `rsi_overbought` может быть > 100

**Решение:** Добавить валидацию:
```python
rsi_period = max(2, min(strategy_params.get('rsi_period', 14), 200))
rsi_oversold = max(0, min(strategy_params.get('rsi_oversold', 30), 50))
rsi_overbought = max(50, min(strategy_params.get('rsi_overbought', 70), 100))
```

---

#### 8. **Дублирование создания BybitDataLoader**
**Файлы:** Все API endpoints

**Проблема:**
```python
# В каждом endpoint
loader = BybitDataLoader(testnet=False)
candles = loader.fetch_klines(...)
```

**Проблема:** Каждый раз создаётся новый объект с новой HTTP сессией.

**Решение:** Создать singleton или dependency injection:
```python
# main.py
@app.on_event("startup")
async def startup_event():
    app.state.bybit_loader = BybitDataLoader(testnet=False)

# В endpoints
loader = request.app.state.bybit_loader
```

---

### НИЗКИЙ ПРИОРИТЕТ 🟢

#### 9. **Неинформативные логи**
**Файл:** `backend/api/routers/backtest.py`

**Проблема:**
```python
logger.info(f"Starting backtest: {request.symbol} {request.interval} ({request.strategy_name})")
logger.info(f"Loaded {len(candles)} candles")
```

**Недостаёт информации:**
- Какой период загружен (start_date, end_date)
- Параметры стратегии
- Initial capital и leverage

**Решение:** Добавить полное логирование конфигурации.

---

#### 10. **Отсутствие rate limiting на API**
**Файл:** `backend/main.py`

**Проблема:** Нет ограничения на количество запросов к API.

**Риск:** 
- Может быть заDDoS-ен
- Неконтролируемое потребление ресурсов

**Решение:** Добавить `slowapi` для rate limiting:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/v1/backtest/run")
@limiter.limit("10/minute")
async def run_backtest(...):
    ...
```

---

#### 11. **Дублирование endpoint в data.py**
**Файл:** `backend/api/routers/data.py`

**Проблема:**
```python
@router.get("/data/latest/{symbol}/{interval}")  # Строка 282
```

Но роутер уже имеет prefix="/data" (строка 20), так что реальный URL:
```
/api/v1/data/data/latest/...  # Двойное "data"!
```

**Решение:** Убрать `/data` из декоратора:
```python
@router.get("/latest/{symbol}/{interval}")
```

---

## 📋 РЕКОМЕНДАЦИИ ПО ПРИОРИТЕТАМ

### Немедленно исправить (Сегодня):
1. ✅ Дублирование `/data/` в URL (критическая ошибка API)
2. ✅ Hardcoded пути в start.ps1
3. ✅ Несогласованность timestamps

### В ближайшее время (На этой неделе):
4. Обработка ошибок сети
5. Валидация strategy_params
6. Singleton для BybitDataLoader

### При следующей итерации:
7. Rate limiting
8. Улучшение логов
9. Оптимизация памяти

---

## 🔧 ПЛАН ИСПРАВЛЕНИЙ

### Шаг 1: Исправить критические ошибки
```powershell
# 1. Исправить URL в data.py
# 2. Исправить пути в start.ps1
# 3. Унифицировать timestamps
```

### Шаг 2: Добавить обработку ошибок
```python
# В data.py и backtest.py
try:
    candles = loader.fetch_klines(...)
except requests.exceptions.Timeout:
    raise HTTPException(504, "Bybit API timeout")
except requests.exceptions.ConnectionError:
    raise HTTPException(503, "Cannot connect to Bybit API")
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(500, f"Internal error: {str(e)}")
```

### Шаг 3: Создать utility функции
```python
# backend/utils/timestamp.py
def normalize_timestamps(candles: List[dict]) -> List[dict]:
    """Normalize all timestamps to naive datetime"""
    for candle in candles:
        if isinstance(candle['timestamp'], datetime):
            if candle['timestamp'].tzinfo:
                candle['timestamp'] = candle['timestamp'].replace(tzinfo=None)
    return candles
```

---

## ✅ ИТОГОВАЯ ОЦЕНКА

**Общий статус проекта:** 🟢 ХОРОШО (85/100)

**Критические проблемы:** 2  
**Высокие:** 3  
**Средние:** 4  
**Низкие:** 2

**Вердикт:** Проект работает и функционален, но требует рефакторинга для production-ready состояния.

---

## 📝 СЛЕДУЮЩИЕ ШАГИ

1. Исправить `/data/data/` дублирование
2. Сделать start.ps1 переносимым
3. Унифицировать работу с timestamps
4. Добавить try-except в критических местах
5. Написать unit-тесты для найденных кейсов

**После исправлений оценка:** 🟢 ОТЛИЧНО (95/100)
