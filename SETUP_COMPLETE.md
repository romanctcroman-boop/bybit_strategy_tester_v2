# Bybit Strategy Tester - Полная Установка ✅

## Статус: ГОТОВО К ИСПОЛЬЗОВАНИЮ

Система полностью настроена и работает с реальными данными Bybit API.

---

## 🚀 Быстрый Старт

### 1. Запуск Backend
```powershell
cd D:\bybit_strategy_tester_v2
python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

**Ожидаемый вывод:**
```
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### 2. Запуск Frontend (в отдельной консоли)
```powershell
cd D:\bybit_strategy_tester_v2\frontend
npm run dev
```

**Ожидаемый вывод:**
```
VITE v5.1.0  ready in XXX ms
➜  Local:   http://localhost:5173/
```

### 3. Открыть приложение в браузере

**Основная страница:** http://localhost:5173/

**Тестовая страница с графиком:** http://localhost:5173/#/test-chart

---

## 📊 API Endpoints

### Получить свечи BTCUSDT (реальные данные)
```
GET http://127.0.0.1:8000/api/v1/marketdata/bybit/klines/fetch?symbol=BTCUSDT&interval=60&limit=500
```

**Параметры:**
- `symbol` - Инструмент (BTCUSDT, ETHUSDT, и т.д.)
- `interval` - Timeframe в минутах ('1', '3', '5', '15', '60', '240', '1D')
- `limit` - Количество свечей (1-1000)
- `persist` - Сохранять ли в БД (0 - нет, 1 - да)

**Ответ:**
```json
[
  {
    "open_time": 1728902400000,
    "open": 111180.9,
    "high": 111259.4,
    "low": 110813.4,
    "close": 111259.4,
    "volume": 12345.67,
    "turnover": 1234567890.12
  },
  ...
]
```

---

## 🔐 API Credentials

**Файл:** `D:\bybit_strategy_tester_v2\.env`

```env
BYBIT_API_KEY=o40eJxo5zcRRIl7mnL
BYBIT_API_SECRET=LYXrFuN8sZjQyOBmkL8Th2sXQpN7LzTza293
```

Загружаются автоматически при старте backend.

---

## 🎨 Страницы приложения

### `/` - Strategies
Список торговых стратегий (пока пусто)

### `/optimizations` - Optimizations
Параметры оптимизации стратегий

### `/upload` - Data Upload
Загрузка исторических данных

### `/backtest/:id` - Backtest Detail (например `/backtest/1`)
Детали бэктеста с графиком:
- **Equity Curve** - Кривая капитала
- **Trades Table** - Таблица сделок
- **Chart** - График свечей с выбором режима:
  - **Lightweight Charts** - Встроенные свечи + SMA
  - **TradingView Widget** - Виджет TradingView

### `/test-chart` - Test Chart
Простая тестовая страница для проверки графиков (используется для отладки)

---

## 📈 Графики и Индикаторы

### Lightweight Charts Mode
✅ Свечи OHLCV  
✅ SMA 20 (опционально)  
✅ SMA 50 (опционально)  
✅ Маркеры сделок (Buy/Sell)  
✅ Автоматическое масштабирование  

### TradingView Widget Mode
✅ Встроенный TradingViewChart  
✅ Индикаторы MACD и RSI  
✅ Выбор символа и timeframe  
✅ Выбор темы (light/dark)  

---

## 🔧 Архитектура

```
Frontend (React + TypeScript + Vite)
        ↓
Vite Dev Server (localhost:5173)
        ↓ (HTTP Proxy: /api → backend)
        ↓
Backend (FastAPI + Uvicorn)
        ↓
Bybit API v5 (Реальные данные)
```

### Стек технологий

**Frontend:**
- React 18.2.0
- TypeScript 5.3.3
- Vite 5.1.0
- Material-UI 5.14.0
- lightweight-charts 5.0.9
- TradingView Lightweight Charts
- react-router-dom 6.18.0
- recharts 2.10.0

**Backend:**
- FastAPI
- Uvicorn (ASGI сервер)
- SQLAlchemy (ORM)
- PostgreSQL драйвер (psycopg2-binary)
- requests (HTTP клиент для Bybit API)

---

## 📝 Структура файлов

```
backend/
├── api/
│   ├── app.py                 # FastAPI приложение
│   └── routers/
│       ├── strategies.py
│       ├── backtests.py
│       └── marketdata.py      # Bybit API integration
├── services/
│   └── adapters/
│       └── bybit.py           # BybitAdapter class
├── database/                  # SQLAlchemy engine + sessions
├── models/                    # Database models
└── requirements.txt

frontend/
├── src/
│   ├── components/
│   │   ├── TradingViewChart.tsx     # Lightweight Charts
│   │   ├── SimpleChart.tsx          # Simplified test chart
│   │   ├── TradingViewWidget.tsx    # TradingView embedding
│   │   └── NotificationsProvider.tsx
│   ├── pages/
│   │   ├── BacktestDetailPage.tsx   # Main backtest page
│   │   ├── TestChartPage.tsx        # Test page
│   │   └── *.tsx                    # Other pages
│   ├── services/
│   │   └── api.ts                   # API client
│   ├── App.tsx                      # Main app + routes
│   └── main.tsx                     # Entry point
├── vite.config.ts                   # Vite proxy config
├── package.json
└── tsconfig.json

.env                            # API credentials (local development)
```

---

## ✅ Что работает

- [x] Backend запущен на http://127.0.0.1:8000
- [x] Frontend запущен на http://localhost:5173
- [x] Vite proxy правильно маршрутизирует /api → backend
- [x] Bybit API интегрирован с аутентификацией (API ключи из .env)
- [x] API возвращает реальные BTCUSDT свечи в формате OHLCV
- [x] Lightweight Charts отображает свечи и индикаторы
- [x] TradingView Widget встроен и работает
- [x] React.lazy() правильно настроен (ленивая загрузка компонентов)
- [x] Обработка ошибок на frontend и backend

---

## 🐛 Решенные проблемы

### TS2307: "Cannot find module './App'"
**Решение:** Заменена динамическая загрузка на статический импорт в `main.tsx`

### Runtime: "chart.addCandlestickSeries is not a function"
**Решение:** Добавлена compatibility layer в `TradingViewChart.tsx` для поддержки разных версий lightweight-charts

### Chart отображается пустым
**Решение:** 
1. Добавлена явная высота (height: 480) для контейнера div
2. Перемещена React.lazy() вызов за пределы render функции
3. Добавлено правильное преобразование времени (ms → seconds)

### Backend зависает при запросе к Bybit
**Решение:** Отключена персистентность свечей в БД по умолчанию (использовать `persist=0`)

---

## 🎯 Следующие шаги

1. **Добавить реальные данные в БД**
   ```powershell
   # Загрузить исторические данные BTCUSDT
   GET /api/v1/marketdata/bybit/klines/fetch?symbol=BTCUSDT&interval=60&limit=1000&persist=1
   ```

2. **Создать торговую стратегию**
   - Реализовать класс Strategy
   - Добавить правила entry/exit
   - Настроить параметры оптимизации

3. **Запустить бэктест**
   - Выбрать стратегию
   - Выбрать период данных
   - Запустить симуляцию

4. **Оптимизировать параметры**
   - Задать диапазоны параметров
   - Запустить grid search
   - Найти оптимальные значения

---

## 📞 Поддержка

**Основные логи:**
- Backend: консоль где запущен uvicorn
- Frontend: DevTools (F12) в браузере
- Логи Bybit API: `logs/bybit_kline_raw.jsonl`

**Тестирование API:**
```powershell
$ProgressPreference = 'SilentlyContinue'
$data = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/marketdata/bybit/klines/fetch?symbol=BTCUSDT&interval=60&limit=5" -TimeoutSec 30
$data.Content | ConvertFrom-Json | ConvertTo-Json -Depth 5
```

---

**Система готова к использованию! 🚀**

Запустите оба сервера (backend и frontend) и откройте http://localhost:5173 в браузере.
