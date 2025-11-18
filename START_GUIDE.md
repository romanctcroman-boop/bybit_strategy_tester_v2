# 🚀 Быстрый запуск Bybit Strategy Tester v2

## Предварительные требования

1. **Docker Desktop** - должен быть запущен
2. **Python 3.10+** - установлен и доступен в PATH
3. **Node.js 18+** - установлен и доступен в PATH
4. **PowerShell 5.1+** - встроен в Windows

## Первый запуск

### 1. Настройка окружения

Скопируйте файл `.env.example` в `.env`:

```powershell
Copy-Item .env.example .env
```

Откройте `.env` и добавьте реальные API ключи:

```bash
# Bybit API (получить на https://www.bybit.com/app/user/api-management)
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here

# Perplexity AI (получить на https://www.perplexity.ai/settings/api)
PERPLEXITY_API_KEY=pplx-your_api_key_here
```

**ВАЖНО:** Убедитесь, что в VS Code настроены переменные окружения:
- Откройте `.vscode/settings.json`
- Проверьте, что `perplexity-ai-assistant.apiKey` использует `${env:PERPLEXITY_API_KEY}`
- MCP сервер автоматически подхватит ключ из `.env`

### 2. Установка зависимостей (первый раз)

```powershell
# Установить Python зависимости
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

# Установить Node.js зависимости
cd frontend
npm install
cd ..
```

### 3. Запуск всех сервисов

```powershell
.\start.ps1
```

Этот скрипт автоматически:
- ✅ Запустит PostgreSQL (Docker, порт 5432)
- ✅ Запустит Redis (Docker, порт 6379)
- ✅ Запустит **MCP Server для Perplexity AI** (фоновый процесс)
- ✅ Выполнит миграции базы данных (Alembic)
- ✅ Запустит Backend API (FastAPI, порт 8000)
- ✅ Запустит Frontend (Vite, порт 5173)
- ✅ Подключится к реальному Bybit API
- ✅ Откроет браузер с приложением

**Схема работы AI Studio:**
```
Copilot (VS Code) ←→ MCP Server ←→ Perplexity AI ←→ MCP Server ←→ Copilot
```

MCP (Model Context Protocol) сервер обеспечивает двустороннюю связь между Copilot и Perplexity AI для расширенного поиска и анализа торговых стратегий.

### 4. Проверка работы

После запуска откроются страницы:

- **Frontend:** http://localhost:5173/
- **Backend API Docs:** http://127.0.0.1:8000/docs
- **Backend Health:** http://127.0.0.1:8000/api/v1/healthz

## Основные команды

### Запуск всех сервисов
```powershell
.\start.ps1
```

### Остановка всех сервисов (кроме баз данных)
```powershell
.\stop.ps1
```

### Остановка ВСЕХ сервисов (включая PostgreSQL и Redis)
```powershell
.\stop.ps1 -All
```

### Проверка статуса
```powershell
.\status.ps1
```

## Доступные страницы

После запуска доступны следующие страницы:

1. **Dashboard (Home)** - http://localhost:5173/
   - KPI карточки (P&L, Win Rate, Active Bots, Sharpe Ratio)
   - Quick Actions
   - Recent Activity feed

2. **AI Studio** - http://localhost:5173/#/ai-studio
   - Chat интерфейс Copilot ↔ Perplexity
   - Workflow History
   - Export функционал (JSON/TXT)

3. **ML Optimizer** - http://localhost:5173/#/optimizations
   - Parameter Grid (4 параметра с sliders)
   - ML Engine selector (CatBoost/XGBoost/LightGBM/Hybrid)
   - Plotly scatter plot (Return vs Sharpe)
   - Results table (Top 10 оптимизаций)

4. **Backtests** - http://localhost:5173/#/backtests
   - Список всех бэктестов
   - Детальные результаты
   - Equity curve
   - Trade list

5. **Strategies** - http://localhost:5173/#/strategies
   - Список стратегий
   - Редактор параметров
   - Strategy Wizard

6. **Charts** - http://localhost:5173/#/charts
   - Real-time графики (TradingView)
   - Индикаторы
   - Multi-timeframe анализ

## API Endpoints

### Health Checks
- `GET /healthz` - Basic health check
- `GET /readyz` - Ready check
- `GET /livez` - Liveness check
- `GET /api/v1/exchangez` - Bybit connectivity check

### Strategies
- `GET /api/v1/strategies` - Список стратегий
- `POST /api/v1/strategies` - Создать стратегию
- `GET /api/v1/strategies/{id}` - Получить стратегию
- `PUT /api/v1/strategies/{id}` - Обновить стратегию
- `DELETE /api/v1/strategies/{id}` - Удалить стратегию

### Backtests
- `GET /api/v1/backtests` - Список бэктестов
- `POST /api/v1/backtests` - Запустить бэктест
- `GET /api/v1/backtests/{id}` - Получить результаты

### Market Data
- `GET /api/v1/marketdata/bybit/klines` - Получить OHLCV данные
- `GET /api/v1/marketdata/bybit/symbols` - Список символов

### Optimizations
- `POST /api/v1/optimizations` - Запустить оптимизацию
- `GET /api/v1/optimizations/{id}` - Получить результаты

### Live Trading
- `WebSocket /ws/live` - Real-time данные (тики, ордера, позиции)

## Конфигурация

### Переменные окружения (.env)

**Bybit API:**
```bash
BYBIT_API_KEY=your_key
BYBIT_API_SECRET=your_secret
BYBIT_WS_ENABLED=1
BYBIT_WS_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT
BYBIT_WS_INTERVALS=1,5,15
BYBIT_PERSIST_KLINES=1
```

**Database:**
```bash
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/bybit
```

**Redis:**
```bash
REDIS_URL=redis://127.0.0.1:6379/0
```

**Perplexity AI:**
```bash
PERPLEXITY_API_KEY=pplx-your_key
```

## Логи

Все логи сохраняются в папке `logs/`:
- `logs/backend.log` - Backend API логи
- `logs/frontend.out.log` - Frontend stdout
- `logs/frontend.err.log` - Frontend stderr

## Troubleshooting

### Docker не запускается
```powershell
# Убедитесь, что Docker Desktop запущен
Get-Process Docker*

# Если не запущен, запустите Docker Desktop вручную
```

### Backend не подключается к PostgreSQL
```powershell
# Проверьте статус контейнера
docker ps

# Проверьте логи PostgreSQL
docker logs bybit_strategy_tester_v2-postgres-1

# Пересоздайте контейнер
docker compose down
docker compose up -d postgres redis
```

### Frontend показывает ошибки API
```powershell
# Проверьте статус Backend
Invoke-RestMethod http://127.0.0.1:8000/healthz

# Проверьте логи Backend
Get-Content logs\backend.log -Tail 50
```

### Bybit API не отвечает
```powershell
# Проверьте connectivity
Invoke-RestMethod http://127.0.0.1:8000/api/v1/exchangez

# Проверьте API ключи в .env
Get-Content .env | Select-String "BYBIT_API_KEY"
```

## Разработка

### Hot Reload

После запуска `.\start.ps1`:
- **Frontend:** Vite автоматически перезагружает страницы при изменении файлов
- **Backend:** Uvicorn перезагружает модули при изменении `.py` файлов

### Тестирование

```powershell
# Backend тесты
pytest tests/

# Frontend тесты
cd frontend
npm test
```

### Database Migrations

```powershell
# Создать миграцию
alembic revision --autogenerate -m "Description"

# Применить миграции
alembic upgrade head

# Откатить миграцию
alembic downgrade -1
```

## Архитектура

```
┌─────────────────────────────────────────────────────┐
│              FRONTEND (React + Vite)                │
│              http://localhost:5173                  │
└───────────────────┬─────────────────────────────────┘
                    │ HTTP/WebSocket
┌───────────────────▼─────────────────────────────────┐
│         BACKEND API (FastAPI + Uvicorn)             │
│         http://127.0.0.1:8000                       │
│  ┌──────────┬──────────┬──────────┬──────────┐     │
│  │Strategies│Backtests │Optimizer │MarketData│     │
│  └──────────┴──────────┴──────────┴──────────┘     │
└──────┬────────────────────────────────┬─────────────┘
       │                                │
       ▼                                ▼
┌────────────┐                   ┌────────────┐
│ PostgreSQL │                   │   Redis    │
│ (Docker)   │                   │  (Docker)  │
│ Port 5432  │                   │ Port 6379  │
└────────────┘                   └────────────┘
       │                                │
       └────────────┬───────────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  Bybit API    │
            │ (External)    │
            └───────────────┘
```

## Дополнительные ресурсы

- **Bybit API Docs:** https://bybit-exchange.github.io/docs/v5/intro
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **React Docs:** https://react.dev/
- **Vite Docs:** https://vitejs.dev/

## Поддержка

Если возникли проблемы:
1. Проверьте логи в `logs/`
2. Проверьте статус сервисов: `.\status.ps1`
3. Пересоздайте окружение: `.\stop.ps1 -All` → `.\start.ps1`
