# 📐 ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ: Bybit Strategy Tester

**Дата:** 16 октября 2025  
**Версия:** 1.0  
**Статус:** Production-Ready Prototype  

---

## 🎯 1. АРХИТЕКТУРА СИСТЕМЫ

### 1.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      ELECTRON DESKTOP APP                         │
│                     (Windows 11 Native)                           │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              RENDERER PROCESS (React)                       │  │
│  │                                                              │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │  │
│  │  │Dashboard │  │Backtest  │  │Strategies│  │Live      │  │  │
│  │  │Page      │  │Page      │  │Page      │  │Trading   │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │  │
│  │                                                              │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │         TradingView Lightweight Charts               │  │  │
│  │  │  • Candlestick                                       │  │  │
│  │  │  • Indicators (20+ built-in)                         │  │  │
│  │  │  • Real-time updates                                 │  │  │
│  │  │  • Markers & Price lines                             │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                               │                                     │
│                               │ IPC (Inter-Process Communication)  │
│                               │                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  MAIN PROCESS (Node.js)                      │  │
│  │                                                              │  │
│  │  • Window Management                                        │  │
│  │  • Native OS Integration                                    │  │
│  │  • File System Access                                       │  │
│  │  • Auto-updates                                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────────────┘
                     │
                     │ HTTP/WebSocket
                     │
┌────────────────────▼─────────────────────────────────────────────┐
│                    BACKEND SERVER (FastAPI)                       │
│                    localhost:8000 (Development)                   │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    REST API LAYER                           │  │
│  │                                                              │  │
│  │  GET  /api/v1/data/candles                                 │  │
│  │  GET  /api/v1/strategies                                   │  │
│  │  POST /api/v1/backtest/run                                 │  │
│  │  GET  /api/v1/backtest/{id}/results                        │  │
│  │  POST /api/v1/optimize/grid                                │  │
│  │  WS   /api/v1/live/candles/{symbol}                        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  BUSINESS LOGIC LAYER                       │  │
│  │                                                              │  │
│  │  • BacktestService                                          │  │
│  │  • StrategyService                                          │  │
│  │  • OptimizationService                                      │  │
│  │  • DataService                                              │  │
│  │  • LiveDataService                                          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  BACKTEST ENGINE CORE                       │  │
│  │                                                              │  │
│  │  • Order Execution                                          │  │
│  │  • Position Management                                      │  │
│  │  • PnL Calculation                                          │  │
│  │  • Margin Calculation                                       │  │
│  │  • Commission Handling                                      │  │
│  │  • Slippage Simulation                                      │  │
│  └────────────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────────────┘
                     │
          ┌──────────┴───────────┬──────────────┐
          │                      │               │
          ▼                      ▼               ▼
┌─────────────────┐  ┌──────────────────┐  ┌─────────────┐
│   PostgreSQL    │  │      Redis       │  │  RabbitMQ   │
│   + TimescaleDB │  │                  │  │             │
│                 │  │  • Cache         │  │  • Tasks    │
│  • Strategies   │  │  • Live Data     │  │  • Jobs     │
│  • Backtests    │  │  • Sessions      │  │  • Workers  │
│  • Trades       │  │  • Pub/Sub       │  │             │
│  • Optimizations│  │                  │  │             │
└─────────────────┘  └──────────────────┘  └─────────────┘
          │
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│                  BACKGROUND WORKERS                      │
│                      (Celery)                            │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Bybit WS     │  │ Backtest     │  │ Optimization │ │
│  │ Worker       │  │ Worker       │  │ Worker       │ │
│  │              │  │              │  │              │ │
│  │ • Live data  │  │ • Run tests  │  │ • Grid       │ │
│  │ • Multi-TF   │  │ • Parallel   │  │ • Walk-fwd   │ │
│  │ • Redis pub  │  │ • Queue      │  │ • Bayesian   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Architecture

```
USER ACTION → RENDERER → MAIN → API → SERVICE → DATABASE → RESPONSE
     ↓                                   ↓                      ↑
     └──── WebSocket ────────────────→ REDIS ──────────────────┘
                                         ↑
                                         │
                                    WS WORKER
                                         ↑
                                         │
                                    BYBIT API
```

### 1.3 Component Interaction Matrix

| Component | Communicates With | Protocol | Purpose |
|-----------|------------------|----------|---------|
| **Renderer Process** | Main Process | IPC | UI events, Native APIs |
| **Renderer Process** | Backend API | HTTP/WS | Data operations |
| **Main Process** | OS | Native | File system, Windows integration |
| **Backend API** | PostgreSQL | TCP/5432 | Data persistence |
| **Backend API** | Redis | TCP/6379 | Cache, Pub/Sub |
| **Backend API** | RabbitMQ | AMQP/5672 | Task queue |
| **Celery Workers** | RabbitMQ | AMQP | Task execution |
| **Celery Workers** | Redis | TCP | Result backend |
| **WS Worker** | Bybit API | WebSocket | Live market data |
| **WS Worker** | Redis | TCP | Live data storage |

---

## 🛠️ 2. ТЕХНОЛОГИЧЕСКИЙ СТЕК

### 2.1 Frontend Stack (100% FREE)

```typescript
// package.json (Frontend dependencies)

{
  "name": "bybit-strategy-tester",
  "version": "1.0.0",
  "description": "Professional Trading Strategy Backtester",
  
  // CORE FRAMEWORK
  "dependencies": {
    // Desktop framework
    "electron": "^28.0.0",              // Desktop wrapper
    "electron-builder": "^24.0.0",      // Build & package
    "electron-updater": "^6.1.0",       // Auto-updates
    
    // UI Framework
    "react": "^18.2.0",                 // UI library
    "react-dom": "^18.2.0",             // DOM rendering
    "react-router-dom": "^6.20.0",      // Routing
    
    // State Management
    "zustand": "^4.4.0",                // State management (lighter than Redux)
    "immer": "^10.0.0",                 // Immutability
    
    // Charts & Visualization
    "lightweight-charts": "^5.0.0",     // TradingView charts (FREE)
    "recharts": "^2.10.0",              // Additional charts
    "d3": "^7.8.0",                     // Custom visualizations
    
    // UI Components
    "@mui/material": "^5.15.0",         // Material-UI (FREE)
    "@mui/icons-material": "^5.15.0",   // Icons
    "@mui/x-data-grid": "^6.18.0",      // Data grid (FREE version)
    
    // Tables
    "@tanstack/react-table": "^8.10.0", // Powerful tables (FREE)
    
    // Forms & Validation
    "react-hook-form": "^7.48.0",       // Form handling
    "zod": "^3.22.0",                   // Validation
    
    // API Communication
    "axios": "^1.6.0",                  // HTTP client
    "socket.io-client": "^4.6.0",       // WebSocket client
    "rxjs": "^7.8.0",                   // Reactive programming
    
    // Data Processing
    "apache-arrow": "^14.0.0",          // Columnar data format
    "papaparse": "^5.4.0",              // CSV parsing
    "date-fns": "^2.30.0",              // Date utilities
    
    // Styling
    "tailwindcss": "^3.3.0",            // Utility-first CSS
    "styled-components": "^6.1.0",      // CSS-in-JS
    
    // Development
    "typescript": "^5.3.0",             // Type safety
    "vite": "^5.0.0",                   // Build tool
    "vitest": "^1.0.0",                 // Testing
    "playwright": "^1.40.0"             // E2E testing
  },
  
  // Scripts
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "electron:dev": "concurrently \"npm run dev\" \"wait-on http://localhost:5173 && electron .\"",
    "electron:build": "electron-builder",
    "test": "vitest",
    "test:e2e": "playwright test"
  },
  
  // Electron Builder Config
  "build": {
    "appId": "com.bybit.strategytester",
    "productName": "Bybit Strategy Tester",
    "win": {
      "target": ["nsis", "portable"],
      "icon": "assets/icon.ico"
    },
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true
    },
    "files": [
      "dist/**/*",
      "electron/**/*",
      "package.json"
    ]
  }
}
```

### 2.2 Backend Stack (100% FREE)

```python
# requirements.txt (Backend dependencies)

# ============================================================================
# CORE FRAMEWORK
# ============================================================================
fastapi==0.109.0               # REST API framework
uvicorn[standard]==0.27.0      # ASGI server
pydantic==2.5.0                # Data validation
pydantic-settings==2.1.0       # Settings management

# ============================================================================
# DATABASE
# ============================================================================
psycopg2-binary==2.9.9         # PostgreSQL driver
asyncpg==0.29.0                # Async PostgreSQL driver
sqlalchemy==2.0.25             # ORM
alembic==1.13.0                # Migrations

# TimescaleDB (extension для PostgreSQL)
# Установка: CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

# ============================================================================
# CACHE & MESSAGE QUEUE
# ============================================================================
redis==5.0.1                   # Redis client
aioredis==2.0.1                # Async Redis client
celery==5.3.4                  # Task queue
kombu==5.3.4                   # Celery message transport

# ============================================================================
# DATA PROCESSING
# ============================================================================
pandas==2.1.4                  # Data analysis
numpy==1.26.2                  # Numerical computing
polars==0.20.0                 # Fast dataframes (Rust-based)
numba==0.58.1                  # JIT compilation
pyarrow==14.0.2                # Columnar data format
ta-lib==0.4.28                 # Technical analysis (optional)

# ============================================================================
# API CLIENTS
# ============================================================================
pybit==5.7.0                   # Bybit API client
aiohttp==3.9.1                 # Async HTTP client
websocket-client==1.7.0        # WebSocket client

# ============================================================================
# TESTING
# ============================================================================
pytest==7.4.3                  # Testing framework
pytest-asyncio==0.23.2         # Async tests
pytest-cov==4.1.0              # Coverage
httpx==0.26.0                  # Test client for FastAPI

# ============================================================================
# MONITORING & LOGGING
# ============================================================================
prometheus-client==0.19.0      # Prometheus metrics
loguru==0.7.2                  # Advanced logging
sentry-sdk==1.39.1             # Error tracking (optional)

# ============================================================================
# UTILITIES
# ============================================================================
python-dotenv==1.0.0           # Environment variables
python-jose[cryptography]==3.3.0  # JWT tokens
passlib[bcrypt]==1.7.4         # Password hashing
python-multipart==0.0.6        # File uploads
```

### 2.3 Database Schema (PostgreSQL + TimescaleDB)

```sql
-- ============================================================================
-- SETUP TIMESCALEDB
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ============================================================================
-- USERS TABLE (optional для multi-user)
-- ============================================================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- ============================================================================
-- STRATEGIES TABLE
-- ============================================================================
CREATE TABLE strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    strategy_type VARCHAR(50) NOT NULL,  -- 'Indicator-Based', 'Pattern-Based', etc.
    config JSONB NOT NULL,                -- Полная конфигурация стратегии
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_strategies_user_id ON strategies(user_id);
CREATE INDEX idx_strategies_type ON strategies(strategy_type);
CREATE INDEX idx_strategies_name ON strategies(name);
-- GIN index для JSONB queries
CREATE INDEX idx_strategies_config ON strategies USING GIN(config);

-- ============================================================================
-- BACKTESTS TABLE
-- ============================================================================
CREATE TABLE backtests (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    -- Market data parameters
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    
    -- Trading parameters
    initial_capital NUMERIC(18, 2) NOT NULL,
    leverage INTEGER DEFAULT 1,
    commission NUMERIC(5, 4) DEFAULT 0.0006,  -- 0.06% taker fee
    
    -- Results
    final_capital NUMERIC(18, 2),
    total_return NUMERIC(10, 4),              -- %
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    win_rate NUMERIC(5, 2),                   -- %
    
    -- Performance metrics
    sharpe_ratio NUMERIC(10, 4),
    sortino_ratio NUMERIC(10, 4),
    calmar_ratio NUMERIC(10, 4),
    max_drawdown NUMERIC(10, 4),              -- %
    max_drawdown_duration INTEGER,            -- days
    profit_factor NUMERIC(10, 4),
    
    -- Additional metrics
    avg_trade_return NUMERIC(10, 4),          -- %
    avg_win NUMERIC(10, 4),
    avg_loss NUMERIC(10, 4),
    largest_win NUMERIC(18, 2),
    largest_loss NUMERIC(18, 2),
    avg_trade_duration INTEGER,               -- minutes
    
    -- Execution details
    config JSONB,                             -- Параметры запуска
    results JSONB,                            -- Детальные результаты
    error_message TEXT,
    status VARCHAR(20) DEFAULT 'pending',     -- 'pending', 'running', 'completed', 'failed'
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    CONSTRAINT positive_capital CHECK (initial_capital > 0),
    CONSTRAINT valid_leverage CHECK (leverage >= 1 AND leverage <= 100),
    CONSTRAINT valid_commission CHECK (commission >= 0 AND commission < 1)
);

CREATE INDEX idx_backtests_strategy_id ON backtests(strategy_id);
CREATE INDEX idx_backtests_user_id ON backtests(user_id);
CREATE INDEX idx_backtests_symbol ON backtests(symbol);
CREATE INDEX idx_backtests_status ON backtests(status);
CREATE INDEX idx_backtests_created_at ON backtests(created_at DESC);
CREATE INDEX idx_backtests_performance ON backtests(sharpe_ratio DESC, total_return DESC);

-- ============================================================================
-- TRADES TABLE (Time-series data)
-- ============================================================================
CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    backtest_id INTEGER NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    
    -- Trade details
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    side VARCHAR(10) NOT NULL CHECK(side IN ('LONG', 'SHORT')),
    
    -- Prices
    entry_price NUMERIC(18, 8) NOT NULL,
    exit_price NUMERIC(18, 8),
    
    -- Quantities
    quantity NUMERIC(18, 8) NOT NULL,
    position_size NUMERIC(18, 2) NOT NULL,      -- USDT value
    
    -- Results
    pnl NUMERIC(18, 8),                         -- Profit/Loss (USDT)
    pnl_pct NUMERIC(10, 4),                     -- Profit/Loss (%)
    commission NUMERIC(18, 8),
    
    -- Exit details
    exit_reason VARCHAR(50),                    -- 'signal', 'take_profit', 'stop_loss', etc.
    
    -- Metadata
    metadata JSONB,
    
    CONSTRAINT positive_quantity CHECK (quantity > 0),
    CONSTRAINT positive_position_size CHECK (position_size > 0)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('trades', 'entry_time', if_not_exists => TRUE);

-- Indexes
CREATE INDEX idx_trades_backtest_id ON trades(backtest_id);
CREATE INDEX idx_trades_entry_time ON trades(entry_time DESC);
CREATE INDEX idx_trades_side ON trades(side);
CREATE INDEX idx_trades_exit_reason ON trades(exit_reason);

-- Continuous aggregate для быстрой статистики по дням
CREATE MATERIALIZED VIEW trades_daily
WITH (timescaledb.continuous) AS
SELECT 
    backtest_id,
    time_bucket('1 day', entry_time) AS day,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) AS losing_trades,
    SUM(pnl) AS total_pnl,
    AVG(pnl_pct) AS avg_return_pct,
    MAX(pnl) AS best_trade,
    MIN(pnl) AS worst_trade
FROM trades
GROUP BY backtest_id, day;

-- Refresh policy для continuous aggregate
SELECT add_continuous_aggregate_policy('trades_daily',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 hour');

-- ============================================================================
-- OPTIMIZATIONS TABLE
-- ============================================================================
CREATE TABLE optimizations (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    -- Optimization parameters
    optimization_type VARCHAR(20) NOT NULL,   -- 'grid', 'walkforward', 'bayesian'
    param_space JSONB NOT NULL,               -- Пространство параметров
    
    -- Results
    best_params JSONB,
    best_score NUMERIC(10, 4),
    metric VARCHAR(50),                       -- 'sharpe_ratio', 'total_return', etc.
    
    -- All results
    results JSONB,                            -- Все комбинации и их результаты
    
    -- Execution details
    total_combinations INTEGER,
    completed_combinations INTEGER,
    failed_combinations INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_optimizations_strategy_id ON optimizations(strategy_id);
CREATE INDEX idx_optimizations_user_id ON optimizations(user_id);
CREATE INDEX idx_optimizations_status ON optimizations(status);
CREATE INDEX idx_optimizations_created_at ON optimizations(created_at DESC);

-- ============================================================================
-- MARKET DATA CACHE (опционально, для локального хранения)
-- ============================================================================
CREATE TABLE market_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    
    -- OHLCV
    open NUMERIC(18, 8) NOT NULL,
    high NUMERIC(18, 8) NOT NULL,
    low NUMERIC(18, 8) NOT NULL,
    close NUMERIC(18, 8) NOT NULL,
    volume NUMERIC(18, 8) NOT NULL,
    
    -- Metadata
    turnover NUMERIC(18, 8),
    
    UNIQUE(symbol, timeframe, timestamp)
);

-- Convert to hypertable
SELECT create_hypertable('market_data', 'timestamp', if_not_exists => TRUE);

-- Indexes
CREATE INDEX idx_market_data_symbol_tf ON market_data(symbol, timeframe);
CREATE INDEX idx_market_data_timestamp ON market_data(timestamp DESC);

-- Compression policy (данные старше 7 дней сжимаются)
ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe'
);

SELECT add_compression_policy('market_data', INTERVAL '7 days');

-- Retention policy (удаляем данные старше 2 лет)
SELECT add_retention_policy('market_data', INTERVAL '2 years');

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_strategies_updated_at
    BEFORE UPDATE ON strategies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View для топ стратегий
CREATE OR REPLACE VIEW top_strategies AS
SELECT 
    s.id,
    s.name,
    s.strategy_type,
    COUNT(b.id) AS total_backtests,
    AVG(b.sharpe_ratio) AS avg_sharpe,
    AVG(b.total_return) AS avg_return,
    MAX(b.total_return) AS best_return,
    AVG(b.win_rate) AS avg_win_rate
FROM strategies s
LEFT JOIN backtests b ON s.id = b.strategy_id AND b.status = 'completed'
WHERE s.is_active = TRUE
GROUP BY s.id, s.name, s.strategy_type
HAVING COUNT(b.id) > 0
ORDER BY avg_sharpe DESC, avg_return DESC;

-- View для последних бэктестов
CREATE OR REPLACE VIEW recent_backtests AS
SELECT 
    b.id,
    b.strategy_id,
    s.name AS strategy_name,
    b.symbol,
    b.timeframe,
    b.total_return,
    b.sharpe_ratio,
    b.max_drawdown,
    b.win_rate,
    b.total_trades,
    b.status,
    b.created_at,
    b.completed_at,
    EXTRACT(EPOCH FROM (b.completed_at - b.started_at)) AS duration_seconds
FROM backtests b
JOIN strategies s ON b.strategy_id = s.id
WHERE b.status = 'completed'
ORDER BY b.created_at DESC
LIMIT 100;
```

---

## 🚀 3. API ENDPOINTS

### 3.1 REST API Specification

```python
# backend/api/routers/data.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/data", tags=["data"])

# ============================================================================
# MODELS
# ============================================================================

class CandleResponse(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
class SymbolInfo(BaseModel):
    symbol: str
    base_currency: str
    quote_currency: str
    min_order_qty: float
    max_order_qty: float
    tick_size: float
    is_active: bool

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/symbols", response_model=List[SymbolInfo])
async def get_symbols(
    category: str = Query("linear", description="bybit category"),
    is_active: bool = Query(True, description="Only active symbols")
):
    """
    Получить список доступных торговых пар
    
    Example response:
    [
        {
            "symbol": "BTCUSDT",
            "base_currency": "BTC",
            "quote_currency": "USDT",
            "min_order_qty": 0.001,
            "max_order_qty": 100.0,
            "tick_size": 0.01,
            "is_active": true
        }
    ]
    """
    # Implementation
    pass

@router.get("/candles/{symbol}", response_model=List[CandleResponse])
async def get_candles(
    symbol: str,
    timeframe: str = Query(..., regex="^(1|3|5|15|30|60|120|240|360|720|D|W|M)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(1000, le=10000)
):
    """
    Получить исторические свечи
    
    Parameters:
    - symbol: Торговая пара (BTCUSDT, ETHUSDT, etc.)
    - timeframe: Таймфрейм (1, 5, 15, 30, 60, 240, D, W, M)
    - start_date: Начальная дата (ISO 8601)
    - end_date: Конечная дата (ISO 8601)
    - limit: Максимум свечей (default: 1000, max: 10000)
    
    Example:
    GET /api/v1/data/candles/BTCUSDT?timeframe=15&limit=1000
    
    Response:
    [
        {
            "timestamp": "2025-01-01T00:00:00Z",
            "open": 50000.0,
            "high": 50100.0,
            "low": 49900.0,
            "close": 50050.0,
            "volume": 123.45
        }
    ]
    """
    # Implementation
    pass

@router.post("/download")
async def download_data(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime
):
    """
    Скачать и кэшировать исторические данные
    
    Запускает background task для скачивания данных
    """
    # Implementation
    pass
```

```python
# backend/api/routers/strategies.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])

# ============================================================================
# MODELS
# ============================================================================

class StrategyCreate(BaseModel):
    name: str
    description: Optional[str]
    strategy_type: str
    config: dict
    
class StrategyUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    config: Optional[dict]
    is_active: Optional[bool]

class StrategyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    strategy_type: str
    config: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    total_backtests: int
    avg_sharpe: Optional[float]
    avg_return: Optional[float]

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/", response_model=List[StrategyResponse])
async def list_strategies(
    strategy_type: Optional[str] = None,
    is_active: bool = True,
    skip: int = 0,
    limit: int = 100
):
    """Список всех стратегий"""
    pass

@router.post("/", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(strategy: StrategyCreate):
    """Создать новую стратегию"""
    pass

@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: int):
    """Получить стратегию по ID"""
    pass

@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(strategy_id: int, strategy: StrategyUpdate):
    """Обновить стратегию"""
    pass

@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(strategy_id: int):
    """Удалить стратегию"""
    pass

@router.post("/{strategy_id}/duplicate", response_model=StrategyResponse)
async def duplicate_strategy(strategy_id: int):
    """Дублировать стратегию"""
    pass

@router.post("/validate")
async def validate_strategy(config: dict):
    """Валидация конфигурации стратегии"""
    pass
```

```python
# backend/api/routers/backtest.py

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])

# ============================================================================
# MODELS
# ============================================================================

class BacktestRequest(BaseModel):
    strategy_id: int
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    leverage: int = 1
    commission: float = 0.0006

class BacktestResponse(BaseModel):
    id: int
    strategy_id: int
    status: str  # 'pending', 'running', 'completed', 'failed'
    symbol: str
    timeframe: str
    
    # Results (if completed)
    final_capital: Optional[float]
    total_return: Optional[float]
    sharpe_ratio: Optional[float]
    max_drawdown: Optional[float]
    total_trades: Optional[int]
    win_rate: Optional[float]
    
    created_at: datetime
    completed_at: Optional[datetime]

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/run", response_model=BacktestResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks
):
    """
    Запустить бэктест (асинхронно)
    
    Returns:
    - id: ID бэктеста (для отслеживания статуса)
    - status: 'pending' (добавлен в очередь)
    """
    # Implementation
    pass

@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(backtest_id: int):
    """Получить результаты бэктеста"""
    pass

@router.get("/{backtest_id}/trades")
async def get_backtest_trades(
    backtest_id: int,
    skip: int = 0,
    limit: int = 1000
):
    """Получить список сделок бэктеста"""
    pass

@router.get("/{backtest_id}/equity")
async def get_equity_curve(backtest_id: int):
    """Получить кривую капитала"""
    pass

@router.delete("/{backtest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backtest(backtest_id: int):
    """Удалить бэктест"""
    pass
```

```python
# backend/api/routers/optimize.py

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/optimize", tags=["optimization"])

# ============================================================================
# MODELS
# ============================================================================

class OptimizationRequest(BaseModel):
    strategy_id: int
    optimization_type: str  # 'grid', 'walkforward', 'bayesian'
    param_space: dict
    metric: str = 'sharpe_ratio'
    
    # Backtest parameters
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime

class OptimizationResponse(BaseModel):
    id: int
    strategy_id: int
    optimization_type: str
    status: str
    best_params: Optional[dict]
    best_score: Optional[float]
    progress: float  # 0.0 - 1.0
    created_at: datetime

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/grid", response_model=OptimizationResponse)
async def run_grid_search(request: OptimizationRequest):
    """Запустить Grid Search оптимизацию"""
    pass

@router.post("/walkforward", response_model=OptimizationResponse)
async def run_walkforward(request: OptimizationRequest):
    """Запустить Walk-Forward оптимизацию"""
    pass

@router.get("/{optimization_id}", response_model=OptimizationResponse)
async def get_optimization(optimization_id: int):
    """Получить статус оптимизации"""
    pass

@router.get("/{optimization_id}/results")
async def get_optimization_results(optimization_id: int):
    """Получить детальные результаты оптимизации"""
    pass
```

```python
# backend/api/routers/live.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/live", tags=["live"])

# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@router.websocket("/candles/{symbol}")
async def websocket_candles(
    websocket: WebSocket,
    symbol: str,
    timeframe: str = "15"
):
    """
    WebSocket для получения live свечей
    
    Client → Server:
    {
        "action": "subscribe",
        "symbol": "BTCUSDT",
        "timeframe": "15"
    }
    
    Server → Client:
    {
        "type": "candle_update",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "timestamp": "2025-01-01T12:00:00Z",
        "open": 50000.0,
        "high": 50100.0,
        "low": 49900.0,
        "close": 50050.0,
        "volume": 123.45
    }
    """
    await websocket.accept()
    
    try:
        # Subscribe to Redis pub/sub
        # Send updates to client
        while True:
            message = await websocket.receive_text()
            # Handle message
    except WebSocketDisconnect:
        # Cleanup
        pass

@router.websocket("/ticks/{symbol}")
async def websocket_ticks(websocket: WebSocket, symbol: str):
    """WebSocket для получения live тиков (trades)"""
    pass
```

### 3.2 API Authentication (JWT)

```python
# backend/api/auth.py

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta

security = HTTPBearer()

SECRET_KEY = "your-secret-key"  # из .env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    """Создать JWT токен"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получить текущего пользователя из JWT"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Usage в endpoints:
# @router.get("/protected")
# async def protected_route(user_id: int = Depends(get_current_user)):
#     return {"user_id": user_id}
```

---

## 🧠 4. BACKEND SERVICES LAYER

### 4.1 BacktestService (Основной сервис бэктестирования)

```python
# backend/services/backtest_service.py

from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from loguru import logger

from backend.models.backtest import Backtest, Trade
from backend.models.strategy import Strategy
from backend.core.backtest_engine import BacktestEngine
from backend.services.data_service import DataService
from backend.core.metrics import calculate_metrics

class BacktestService:
    """
    Сервис для выполнения бэктестов
    
    Responsibilities:
    - Запуск бэктестов
    - Сохранение результатов
    - Валидация параметров
    - Вычисление метрик
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.data_service = DataService(db)
        
    async def run_backtest(
        self,
        strategy_id: int,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 10000.0,
        leverage: int = 1,
        commission: float = 0.0006,
        user_id: Optional[int] = None
    ) -> Backtest:
        """
        Запустить бэктест стратегии
        
        Args:
            strategy_id: ID стратегии
            symbol: Торговая пара (BTCUSDT)
            timeframe: Таймфрейм (1, 5, 15, 30, 60, 240, D)
            start_date: Начальная дата
            end_date: Конечная дата
            initial_capital: Начальный капитал (USDT)
            leverage: Плечо (1-100)
            commission: Комиссия (0.0006 = 0.06%)
            user_id: ID пользователя (optional)
            
        Returns:
            Backtest: Объект с результатами бэктеста
        """
        
        # 1. Валидация параметров
        self._validate_parameters(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            leverage=leverage,
            commission=commission
        )
        
        # 2. Загрузка стратегии
        strategy = self.db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")
            
        logger.info(f"Running backtest for strategy: {strategy.name}")
        
        # 3. Создание записи в БД
        backtest = Backtest(
            strategy_id=strategy_id,
            user_id=user_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            leverage=leverage,
            commission=commission,
            status='running',
            started_at=datetime.utcnow()
        )
        self.db.add(backtest)
        self.db.commit()
        self.db.refresh(backtest)
        
        try:
            # 4. Загрузка данных
            logger.info(f"Loading data: {symbol} {timeframe} from {start_date} to {end_date}")
            df = await self.data_service.get_candles(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            if df.empty:
                raise ValueError("No data available for specified period")
                
            logger.info(f"Loaded {len(df)} candles")
            
            # 5. Инициализация движка бэктестирования
            engine = BacktestEngine(
                initial_capital=initial_capital,
                leverage=leverage,
                commission=commission,
                strategy_config=strategy.config
            )
            
            # 6. Запуск бэктеста
            logger.info("Running backtest engine...")
            results = engine.run(df)
            
            # 7. Сохранение сделок
            logger.info(f"Saving {len(results['trades'])} trades...")
            self._save_trades(backtest.id, results['trades'])
            
            # 8. Вычисление метрик
            logger.info("Calculating metrics...")
            metrics = calculate_metrics(
                trades=results['trades'],
                equity_curve=results['equity_curve'],
                initial_capital=initial_capital
            )
            
            # 9. Обновление записи бэктеста
            backtest.final_capital = metrics['final_capital']
            backtest.total_return = metrics['total_return']
            backtest.total_trades = metrics['total_trades']
            backtest.winning_trades = metrics['winning_trades']
            backtest.losing_trades = metrics['losing_trades']
            backtest.win_rate = metrics['win_rate']
            backtest.sharpe_ratio = metrics['sharpe_ratio']
            backtest.sortino_ratio = metrics['sortino_ratio']
            backtest.calmar_ratio = metrics['calmar_ratio']
            backtest.max_drawdown = metrics['max_drawdown']
            backtest.max_drawdown_duration = metrics['max_drawdown_duration']
            backtest.profit_factor = metrics['profit_factor']
            backtest.avg_trade_return = metrics['avg_trade_return']
            backtest.avg_win = metrics['avg_win']
            backtest.avg_loss = metrics['avg_loss']
            backtest.largest_win = metrics['largest_win']
            backtest.largest_loss = metrics['largest_loss']
            backtest.avg_trade_duration = metrics['avg_trade_duration']
            
            backtest.results = {
                'equity_curve': results['equity_curve'].to_dict(),
                'drawdown_curve': results['drawdown_curve'].to_dict(),
                'metrics': metrics
            }
            
            backtest.status = 'completed'
            backtest.completed_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(backtest)
            
            logger.success(f"Backtest completed: {backtest.id}")
            logger.info(f"Total Return: {metrics['total_return']:.2f}%")
            logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
            logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
            
            return backtest
            
        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}")
            backtest.status = 'failed'
            backtest.error_message = str(e)
            backtest.completed_at = datetime.utcnow()
            self.db.commit()
            raise
            
    def _validate_parameters(self, **kwargs):
        """Валидация параметров бэктеста"""
        
        if kwargs['initial_capital'] <= 0:
            raise ValueError("Initial capital must be positive")
            
        if not (1 <= kwargs['leverage'] <= 100):
            raise ValueError("Leverage must be between 1 and 100")
            
        if not (0 <= kwargs['commission'] < 1):
            raise ValueError("Commission must be between 0 and 1")
            
        if kwargs['start_date'] >= kwargs['end_date']:
            raise ValueError("Start date must be before end date")
            
        valid_timeframes = ['1', '3', '5', '15', '30', '60', '120', '240', '360', '720', 'D', 'W', 'M']
        if kwargs['timeframe'] not in valid_timeframes:
            raise ValueError(f"Invalid timeframe. Must be one of: {valid_timeframes}")
            
    def _save_trades(self, backtest_id: int, trades: List[Dict]):
        """Сохранить сделки в БД"""
        
        trade_objects = []
        for trade_data in trades:
            trade = Trade(
                backtest_id=backtest_id,
                entry_time=trade_data['entry_time'],
                exit_time=trade_data.get('exit_time'),
                side=trade_data['side'],
                entry_price=trade_data['entry_price'],
                exit_price=trade_data.get('exit_price'),
                quantity=trade_data['quantity'],
                position_size=trade_data['position_size'],
                pnl=trade_data.get('pnl'),
                pnl_pct=trade_data.get('pnl_pct'),
                commission=trade_data['commission'],
                exit_reason=trade_data.get('exit_reason'),
                metadata=trade_data.get('metadata', {})
            )
            trade_objects.append(trade)
            
        self.db.bulk_save_objects(trade_objects)
        self.db.commit()
        
    async def get_backtest_results(self, backtest_id: int) -> Dict:
        """Получить результаты бэктеста"""
        
        backtest = self.db.query(Backtest).filter(Backtest.id == backtest_id).first()
        if not backtest:
            raise ValueError(f"Backtest {backtest_id} not found")
            
        # Загрузка сделок
        trades = self.db.query(Trade).filter(Trade.backtest_id == backtest_id).all()
        
        return {
            'backtest': backtest,
            'trades': [self._trade_to_dict(t) for t in trades],
            'metrics': backtest.results.get('metrics', {}),
            'equity_curve': backtest.results.get('equity_curve', {})
        }
        
    def _trade_to_dict(self, trade: Trade) -> Dict:
        """Конвертация Trade в dict"""
        return {
            'id': trade.id,
            'entry_time': trade.entry_time.isoformat(),
            'exit_time': trade.exit_time.isoformat() if trade.exit_time else None,
            'side': trade.side,
            'entry_price': float(trade.entry_price),
            'exit_price': float(trade.exit_price) if trade.exit_price else None,
            'quantity': float(trade.quantity),
            'position_size': float(trade.position_size),
            'pnl': float(trade.pnl) if trade.pnl else None,
            'pnl_pct': float(trade.pnl_pct) if trade.pnl_pct else None,
            'commission': float(trade.commission),
            'exit_reason': trade.exit_reason
        }
```

### 4.2 DataService (Управление данными)

```python
# backend/services/data_service.py

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from pybit.unified_trading import HTTP
import redis
import json
from loguru import logger

from backend.models.market_data import MarketData
from backend.core.cache import redis_client

class DataService:
    """
    Сервис для управления рыночными данными
    
    Responsibilities:
    - Загрузка данных из Bybit API
    - Кэширование в Redis
    - Сохранение в PostgreSQL (TimescaleDB)
    - Предоставление данных для бэктестов
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.bybit = HTTP(testnet=False)
        self.redis = redis_client
        
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Получить свечи для бэктеста
        
        Strategy:
        1. Check Redis cache
        2. Check PostgreSQL (TimescaleDB)
        3. Download from Bybit API
        4. Save to cache and DB
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
            start_date: Начальная дата
            end_date: Конечная дата
            use_cache: Использовать кэш
            
        Returns:
            pd.DataFrame с колонками: timestamp, open, high, low, close, volume
        """
        
        cache_key = f"candles:{symbol}:{timeframe}:{start_date.date()}:{end_date.date()}"
        
        # 1. Проверка Redis cache
        if use_cache:
            cached = self.redis.get(cache_key)
            if cached:
                logger.debug(f"Cache HIT: {cache_key}")
                df = pd.read_json(cached)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
                
        logger.debug(f"Cache MISS: {cache_key}")
        
        # 2. Проверка PostgreSQL
        df = self._load_from_db(symbol, timeframe, start_date, end_date)
        
        if not df.empty:
            logger.info(f"Loaded {len(df)} candles from database")
            
            # Проверка полноты данных
            expected_candles = self._calculate_expected_candles(
                start_date, end_date, timeframe
            )
            
            if len(df) >= expected_candles * 0.95:  # 95% coverage
                # Кэшируем на 1 час
                self.redis.setex(cache_key, 3600, df.to_json())
                return df
            else:
                logger.warning(f"Incomplete data in DB: {len(df)}/{expected_candles}")
                
        # 3. Загрузка с Bybit API
        logger.info(f"Downloading from Bybit: {symbol} {timeframe}")
        df = await self._download_from_bybit(symbol, timeframe, start_date, end_date)
        
        # 4. Сохранение в БД
        if not df.empty:
            self._save_to_db(symbol, timeframe, df)
            
            # Кэширование
            self.redis.setex(cache_key, 3600, df.to_json())
            
        return df
        
    def _load_from_db(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Загрузка данных из PostgreSQL"""
        
        query = self.db.query(MarketData).filter(
            MarketData.symbol == symbol,
            MarketData.timeframe == timeframe,
            MarketData.timestamp >= start_date,
            MarketData.timestamp <= end_date
        ).order_by(MarketData.timestamp)
        
        rows = query.all()
        
        if not rows:
            return pd.DataFrame()
            
        data = [{
            'timestamp': row.timestamp,
            'open': float(row.open),
            'high': float(row.high),
            'low': float(row.low),
            'close': float(row.close),
            'volume': float(row.volume)
        } for row in rows]
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df
        
    async def _download_from_bybit(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Загрузка данных с Bybit API"""
        
        # Конвертация timeframe
        interval_map = {
            '1': 1, '3': 3, '5': 5, '15': 15, '30': 30,
            '60': 60, '120': 120, '240': 240, '360': 360,
            '720': 720, 'D': 'D', 'W': 'W', 'M': 'M'
        }
        
        interval = interval_map.get(timeframe)
        if not interval:
            raise ValueError(f"Invalid timeframe: {timeframe}")
            
        all_data = []
        current_start = start_date
        
        # Bybit API limit: 200 candles per request
        while current_start < end_date:
            try:
                response = self.bybit.get_kline(
                    category="linear",
                    symbol=symbol,
                    interval=str(interval),
                    start=int(current_start.timestamp() * 1000),
                    end=int(end_date.timestamp() * 1000),
                    limit=200
                )
                
                if response['retCode'] != 0:
                    logger.error(f"Bybit API error: {response['retMsg']}")
                    break
                    
                klines = response['result']['list']
                
                if not klines:
                    break
                    
                for kline in klines:
                    all_data.append({
                        'timestamp': pd.to_datetime(int(kline[0]), unit='ms'),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    })
                    
                # Обновляем start для следующей итерации
                last_timestamp = pd.to_datetime(int(klines[-1][0]), unit='ms')
                current_start = last_timestamp + timedelta(minutes=int(interval) if isinstance(interval, int) else 1440)
                
                # Rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error downloading data: {str(e)}")
                break
                
        if not all_data:
            logger.warning(f"No data downloaded from Bybit")
            return pd.DataFrame()
            
        df = pd.DataFrame(all_data)
        df = df.sort_values('timestamp').drop_duplicates('timestamp')
        
        logger.success(f"Downloaded {len(df)} candles from Bybit")
        
        return df
        
    def _save_to_db(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """Сохранение данных в PostgreSQL"""
        
        objects = []
        for _, row in df.iterrows():
            obj = MarketData(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=row['timestamp'],
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume']
            )
            objects.append(obj)
            
        # Bulk insert с игнорированием дубликатов
        try:
            self.db.bulk_save_objects(objects)
            self.db.commit()
            logger.info(f"Saved {len(objects)} candles to database")
        except Exception as e:
            logger.error(f"Error saving to DB: {str(e)}")
            self.db.rollback()
            
    def _calculate_expected_candles(
        self,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> int:
        """Вычислить ожидаемое количество свечей"""
        
        minutes_map = {
            '1': 1, '3': 3, '5': 5, '15': 15, '30': 30,
            '60': 60, '120': 120, '240': 240, '360': 360,
            '720': 720, 'D': 1440, 'W': 10080, 'M': 43200
        }
        
        minutes = minutes_map.get(timeframe, 15)
        total_minutes = (end_date - start_date).total_seconds() / 60
        
        return int(total_minutes / minutes)
```

### 4.3 StrategyService (Управление стратегиями)

```python
# backend/services/strategy_service.py

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from backend.models.strategy import Strategy
from backend.schemas.strategy import StrategyCreate, StrategyUpdate

class StrategyService:
    """
    Сервис для управления стратегиями
    """
    
    def __init__(self, db: Session):
        self.db = db
        
    def create_strategy(
        self,
        strategy: StrategyCreate,
        user_id: Optional[int] = None
    ) -> Strategy:
        """Создать новую стратегию"""
        
        # Валидация конфигурации
        self._validate_config(strategy.config)
        
        db_strategy = Strategy(
            name=strategy.name,
            description=strategy.description,
            strategy_type=strategy.strategy_type,
            config=strategy.config,
            user_id=user_id
        )
        
        self.db.add(db_strategy)
        self.db.commit()
        self.db.refresh(db_strategy)
        
        return db_strategy
        
    def get_strategy(self, strategy_id: int) -> Optional[Strategy]:
        """Получить стратегию по ID"""
        return self.db.query(Strategy).filter(Strategy.id == strategy_id).first()
        
    def list_strategies(
        self,
        user_id: Optional[int] = None,
        strategy_type: Optional[str] = None,
        is_active: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> List[Strategy]:
        """Список стратегий с фильтрацией"""
        
        query = self.db.query(Strategy)
        
        if user_id:
            query = query.filter(Strategy.user_id == user_id)
            
        if strategy_type:
            query = query.filter(Strategy.strategy_type == strategy_type)
            
        if is_active is not None:
            query = query.filter(Strategy.is_active == is_active)
            
        return query.offset(skip).limit(limit).all()
        
    def update_strategy(
        self,
        strategy_id: int,
        strategy_update: StrategyUpdate
    ) -> Strategy:
        """Обновить стратегию"""
        
        db_strategy = self.get_strategy(strategy_id)
        if not db_strategy:
            raise ValueError(f"Strategy {strategy_id} not found")
            
        update_data = strategy_update.dict(exclude_unset=True)
        
        if 'config' in update_data:
            self._validate_config(update_data['config'])
            
        for field, value in update_data.items():
            setattr(db_strategy, field, value)
            
        self.db.commit()
        self.db.refresh(db_strategy)
        
        return db_strategy
        
    def delete_strategy(self, strategy_id: int):
        """Удалить стратегию"""
        
        db_strategy = self.get_strategy(strategy_id)
        if not db_strategy:
            raise ValueError(f"Strategy {strategy_id} not found")
            
        self.db.delete(db_strategy)
        self.db.commit()
        
    def duplicate_strategy(self, strategy_id: int) -> Strategy:
        """Дублировать стратегию"""
        
        original = self.get_strategy(strategy_id)
        if not original:
            raise ValueError(f"Strategy {strategy_id} not found")
            
        duplicate = Strategy(
            name=f"{original.name} (Copy)",
            description=original.description,
            strategy_type=original.strategy_type,
            config=original.config.copy(),
            user_id=original.user_id
        )
        
        self.db.add(duplicate)
        self.db.commit()
        self.db.refresh(duplicate)
        
        return duplicate
        
    def _validate_config(self, config: dict):
        """Валидация конфигурации стратегии"""
        
        required_fields = ['entry_conditions', 'exit_conditions']
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
                
        # Дополнительная валидация в зависимости от типа стратегии
        # TODO: Implement detailed validation
```

---

## ⚙️ 5. BACKTEST ENGINE CORE

### 5.1 Основной движок бэктестирования

```python
# backend/core/backtest_engine.py

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from backend.core.indicators import IndicatorCalculator
from backend.core.signals import SignalGenerator
from backend.core.position import Position, PositionSide

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

@dataclass
class BacktestConfig:
    """Конфигурация бэктеста"""
    initial_capital: float
    leverage: int
    commission: float
    slippage: float = 0.0
    use_margin: bool = True

class BacktestEngine:
    """
    Движок бэктестирования
    
    Features:
    - Margin trading с leverage
    - Long/Short позиции
    - Take Profit / Stop Loss
    - Commission & Slippage
    - Partial fills
    - Position sizing
    """
    
    def __init__(
        self,
        initial_capital: float,
        leverage: int,
        commission: float,
        strategy_config: dict,
        slippage: float = 0.0
    ):
        self.config = BacktestConfig(
            initial_capital=initial_capital,
            leverage=leverage,
            commission=commission,
            slippage=slippage
        )
        
        self.strategy_config = strategy_config
        
        # State
        self.capital = initial_capital
        self.position: Optional[Position] = None
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = []
        
        # Modules
        self.indicator_calc = IndicatorCalculator()
        self.signal_gen = SignalGenerator(strategy_config)
        
    def run(self, df: pd.DataFrame) -> Dict:
        """
        Запустить бэктест
        
        Args:
            df: DataFrame с OHLCV данными
            
        Returns:
            Dict с результатами:
            - trades: List[Dict]
            - equity_curve: pd.Series
            - drawdown_curve: pd.Series
        """
        
        logger.info("Starting backtest engine...")
        
        # 1. Вычисление индикаторов
        logger.info("Calculating indicators...")
        df = self.indicator_calc.calculate_all(df, self.strategy_config)
        
        # 2. Генерация сигналов
        logger.info("Generating signals...")
        df = self.signal_gen.generate_signals(df)
        
        # 3. Основной цикл бэктеста
        logger.info(f"Running backtest on {len(df)} candles...")
        
        for i in range(len(df)):
            current_candle = df.iloc[i]
            
            # Обновление equity
            current_equity = self._calculate_equity(current_candle['close'])
            self.equity_curve.append(current_equity)
            
            # Проверка открытой позиции
            if self.position:
                self._check_exit_conditions(current_candle, i)
                
            # Проверка новых сигналов
            if not self.position:
                self._check_entry_signals(current_candle, i)
                
        # Закрытие позиции в конце
        if self.position:
            self._close_position(
                df.iloc[-1],
                len(df) - 1,
                reason='end_of_data'
            )
            
        # 4. Формирование результатов
        results = {
            'trades': self.trades,
            'equity_curve': pd.Series(self.equity_curve, index=df.index),
            'drawdown_curve': self._calculate_drawdown_curve()
        }
        
        logger.success(f"Backtest completed: {len(self.trades)} trades")
        
        return results
        
    def _check_entry_signals(self, candle: pd.Series, index: int):
        """Проверка сигналов на вход"""
        
        # LONG signal
        if candle.get('signal') == 1:
            self._open_position(
                side=PositionSide.LONG,
                candle=candle,
                index=index
            )
            
        # SHORT signal
        elif candle.get('signal') == -1:
            self._open_position(
                side=PositionSide.SHORT,
                candle=candle,
                index=index
            )
            
    def _open_position(
        self,
        side: PositionSide,
        candle: pd.Series,
        index: int
    ):
        """Открыть позицию"""
        
        entry_price = candle['close']
        
        # Apply slippage
        if self.config.slippage > 0:
            if side == PositionSide.LONG:
                entry_price *= (1 + self.config.slippage)
            else:
                entry_price *= (1 - self.config.slippage)
                
        # Calculate position size
        position_size = self.capital * self.config.leverage
        quantity = position_size / entry_price
        
        # Calculate commission
        commission = position_size * self.config.commission
        
        # Deduct commission from capital
        self.capital -= commission
        
        # Create position
        self.position = Position(
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=candle['timestamp'],
            entry_index=index,
            commission=commission
        )
        
        logger.debug(f"Opened {side.value} position at {entry_price:.2f}, size: {position_size:.2f} USDT")
        
    def _check_exit_conditions(self, candle: pd.Series, index: int):
        """Проверка условий выхода"""
        
        if not self.position:
            return
            
        current_price = candle['close']
        should_exit = False
        exit_reason = None
        
        # 1. Check Take Profit
        if self.strategy_config.get('take_profit'):
            tp_pct = self.strategy_config['take_profit']
            
            if self.position.side == PositionSide.LONG:
                tp_price = self.position.entry_price * (1 + tp_pct / 100)
                if current_price >= tp_price:
                    should_exit = True
                    exit_reason = 'take_profit'
            else:
                tp_price = self.position.entry_price * (1 - tp_pct / 100)
                if current_price <= tp_price:
                    should_exit = True
                    exit_reason = 'take_profit'
                    
        # 2. Check Stop Loss
        if self.strategy_config.get('stop_loss') and not should_exit:
            sl_pct = self.strategy_config['stop_loss']
            
            if self.position.side == PositionSide.LONG:
                sl_price = self.position.entry_price * (1 - sl_pct / 100)
                if current_price <= sl_price:
                    should_exit = True
                    exit_reason = 'stop_loss'
            else:
                sl_price = self.position.entry_price * (1 + sl_pct / 100)
                if current_price >= sl_price:
                    should_exit = True
                    exit_reason = 'stop_loss'
                    
        # 3. Check Exit Signal
        if candle.get('exit_signal') and not should_exit:
            should_exit = True
            exit_reason = 'signal'
            
        if should_exit:
            self._close_position(candle, index, exit_reason)
            
    def _close_position(self, candle: pd.Series, index: int, reason: str):
        """Закрыть позицию"""
        
        if not self.position:
            return
            
        exit_price = candle['close']
        
        # Apply slippage
        if self.config.slippage > 0:
            if self.position.side == PositionSide.LONG:
                exit_price *= (1 - self.config.slippage)
            else:
                exit_price *= (1 + self.config.slippage)
                
        # Calculate PnL
        if self.position.side == PositionSide.LONG:
            pnl = (exit_price - self.position.entry_price) * self.position.quantity
        else:
            pnl = (self.position.entry_price - exit_price) * self.position.quantity
            
        # Exit commission
        position_value = exit_price * self.position.quantity
        exit_commission = position_value * self.config.commission
        
        # Net PnL
        net_pnl = pnl - exit_commission
        pnl_pct = (net_pnl / (self.position.entry_price * self.position.quantity)) * 100
        
        # Update capital
        self.capital += net_pnl
        
        # Record trade
        trade = {
            'entry_time': self.position.entry_time,
            'exit_time': candle['timestamp'],
            'side': self.position.side.value,
            'entry_price': self.position.entry_price,
            'exit_price': exit_price,
            'quantity': self.position.quantity,
            'position_size': self.position.entry_price * self.position.quantity,
            'pnl': net_pnl,
            'pnl_pct': pnl_pct,
            'commission': self.position.commission + exit_commission,
            'exit_reason': reason,
            'duration_candles': index - self.position.entry_index
        }
        
        self.trades.append(trade)
        
        logger.debug(
            f"Closed {self.position.side.value} position at {exit_price:.2f}, "
            f"PnL: {net_pnl:.2f} USDT ({pnl_pct:.2f}%), reason: {reason}"
        )
        
        # Clear position
        self.position = None
        
    def _calculate_equity(self, current_price: float) -> float:
        """Вычислить текущий капитал"""
        
        if not self.position:
            return self.capital
            
        # Unrealized PnL
        if self.position.side == PositionSide.LONG:
            unrealized_pnl = (current_price - self.position.entry_price) * self.position.quantity
        else:
            unrealized_pnl = (self.position.entry_price - current_price) * self.position.quantity
            
        return self.capital + unrealized_pnl
        
    def _calculate_drawdown_curve(self) -> pd.Series:
        """Вычислить кривую просадки"""
        
        equity = pd.Series(self.equity_curve)
        rolling_max = equity.expanding().max()
        drawdown = (equity - rolling_max) / rolling_max * 100
        
        return drawdown
```

### 5.2 Position Management

```python
# backend/core/position.py

from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

@dataclass
class Position:
    """
    Открытая позиция
    """
    side: PositionSide
    entry_price: float
    quantity: float
    entry_time: datetime
    entry_index: int
    commission: float
    
    # Optional
    take_profit: float = None
    stop_loss: float = None
    trailing_stop: float = None
    
    def unrealized_pnl(self, current_price: float) -> float:
        """Вычислить нереализованный PnL"""
        if self.side == PositionSide.LONG:
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity
            
    def unrealized_pnl_pct(self, current_price: float) -> float:
        """Вычислить нереализованный PnL в процентах"""
        pnl = self.unrealized_pnl(current_price)
        position_value = self.entry_price * self.quantity
        return (pnl / position_value) * 100
```

### 5.3 Indicator Calculator

```python
# backend/core/indicators.py

import pandas as pd
import numpy as np
from typing import Dict

class IndicatorCalculator:
    """
    Калькулятор технических индикаторов
    
    Supported indicators:
    - Moving Averages (SMA, EMA, WMA)
    - RSI (Relative Strength Index)
    - MACD (Moving Average Convergence Divergence)
    - Bollinger Bands
    - ATR (Average True Range)
    - Stochastic Oscillator
    - ADX (Average Directional Index)
    """
    
    def calculate_all(self, df: pd.DataFrame, config: dict) -> pd.DataFrame:
        """Вычислить все индикаторы из конфигурации"""
        
        df = df.copy()
        
        # Extract indicator configs
        indicators = config.get('indicators', [])
        
        for indicator in indicators:
            ind_type = indicator['type']
            params = indicator.get('params', {})
            
            if ind_type == 'MA':
                df = self.calculate_ma(df, **params)
            elif ind_type == 'RSI':
                df = self.calculate_rsi(df, **params)
            elif ind_type == 'MACD':
                df = self.calculate_macd(df, **params)
            elif ind_type == 'BB':
                df = self.calculate_bollinger_bands(df, **params)
            elif ind_type == 'ATR':
                df = self.calculate_atr(df, **params)
            elif ind_type == 'STOCH':
                df = self.calculate_stochastic(df, **params)
            elif ind_type == 'ADX':
                df = self.calculate_adx(df, **params)
                
        return df
        
    def calculate_ma(
        self,
        df: pd.DataFrame,
        period: int = 20,
        ma_type: str = 'SMA',
        source: str = 'close'
    ) -> pd.DataFrame:
        """
        Moving Average
        
        Args:
            period: Период MA
            ma_type: Тип MA ('SMA', 'EMA', 'WMA')
            source: Источник данных ('close', 'open', 'high', 'low')
        """
        
        column_name = f'{ma_type}_{period}'
        
        if ma_type == 'SMA':
            df[column_name] = df[source].rolling(window=period).mean()
        elif ma_type == 'EMA':
            df[column_name] = df[source].ewm(span=period, adjust=False).mean()
        elif ma_type == 'WMA':
            weights = np.arange(1, period + 1)
            df[column_name] = df[source].rolling(period).apply(
                lambda x: np.dot(x, weights) / weights.sum(), raw=True
            )
            
        return df
        
    def calculate_rsi(
        self,
        df: pd.DataFrame,
        period: int = 14,
        source: str = 'close'
    ) -> pd.DataFrame:
        """
        Relative Strength Index
        
        Formula:
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        """
        
        delta = df[source].diff()
        
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        df[f'RSI_{period}'] = 100 - (100 / (1 + rs))
        
        return df
        
    def calculate_macd(
        self,
        df: pd.DataFrame,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        source: str = 'close'
    ) -> pd.DataFrame:
        """
        MACD (Moving Average Convergence Divergence)
        
        Components:
        - MACD Line = EMA(fast) - EMA(slow)
        - Signal Line = EMA(MACD, signal_period)
        - Histogram = MACD - Signal
        """
        
        ema_fast = df[source].ewm(span=fast_period, adjust=False).mean()
        ema_slow = df[source].ewm(span=slow_period, adjust=False).mean()
        
        df['MACD'] = ema_fast - ema_slow
        df['MACD_Signal'] = df['MACD'].ewm(span=signal_period, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        return df
        
    def calculate_bollinger_bands(
        self,
        df: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0,
        source: str = 'close'
    ) -> pd.DataFrame:
        """
        Bollinger Bands
        
        Components:
        - Middle Band = SMA(period)
        - Upper Band = Middle + (std_dev * standard deviation)
        - Lower Band = Middle - (std_dev * standard deviation)
        """
        
        df['BB_Middle'] = df[source].rolling(window=period).mean()
        rolling_std = df[source].rolling(window=period).std()
        
        df['BB_Upper'] = df['BB_Middle'] + (rolling_std * std_dev)
        df['BB_Lower'] = df['BB_Middle'] - (rolling_std * std_dev)
        df['BB_Width'] = df['BB_Upper'] - df['BB_Lower']
        
        return df
        
    def calculate_atr(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Average True Range
        
        TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
        ATR = SMA(TR, period)
        """
        
        df['prev_close'] = df['close'].shift(1)
        
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        
        df['TR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df[f'ATR_{period}'] = df['TR'].rolling(window=period).mean()
        
        # Cleanup temp columns
        df = df.drop(['prev_close', 'tr1', 'tr2', 'tr3', 'TR'], axis=1)
        
        return df
        
    def calculate_stochastic(
        self,
        df: pd.DataFrame,
        k_period: int = 14,
        d_period: int = 3
    ) -> pd.DataFrame:
        """
        Stochastic Oscillator
        
        %K = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
        %D = SMA(%K, d_period)
        """
        
        df['lowest_low'] = df['low'].rolling(window=k_period).min()
        df['highest_high'] = df['high'].rolling(window=k_period).max()
        
        df['STOCH_K'] = (
            (df['close'] - df['lowest_low']) / 
            (df['highest_high'] - df['lowest_low'])
        ) * 100
        
        df['STOCH_D'] = df['STOCH_K'].rolling(window=d_period).mean()
        
        # Cleanup temp columns
        df = df.drop(['lowest_low', 'highest_high'], axis=1)
        
        return df
        
    def calculate_adx(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Average Directional Index
        
        Components:
        - +DI (Positive Directional Indicator)
        - -DI (Negative Directional Indicator)
        - ADX = SMA(DX, period)
        """
        
        # Calculate True Range
        df = self.calculate_atr(df, period)
        
        # Directional Movement
        df['up_move'] = df['high'] - df['high'].shift(1)
        df['down_move'] = df['low'].shift(1) - df['low']
        
        df['plus_dm'] = np.where(
            (df['up_move'] > df['down_move']) & (df['up_move'] > 0),
            df['up_move'],
            0
        )
        
        df['minus_dm'] = np.where(
            (df['down_move'] > df['up_move']) & (df['down_move'] > 0),
            df['down_move'],
            0
        )
        
        # Smoothed DM and TR
        df['plus_dm_smooth'] = df['plus_dm'].rolling(window=period).sum()
        df['minus_dm_smooth'] = df['minus_dm'].rolling(window=period).sum()
        df['tr_smooth'] = df[f'ATR_{period}'] * period
        
        # Directional Indicators
        df['plus_di'] = (df['plus_dm_smooth'] / df['tr_smooth']) * 100
        df['minus_di'] = (df['minus_dm_smooth'] / df['tr_smooth']) * 100
        
        # DX and ADX
        df['dx'] = (
            abs(df['plus_di'] - df['minus_di']) / 
            (df['plus_di'] + df['minus_di'])
        ) * 100
        
        df[f'ADX_{period}'] = df['dx'].rolling(window=period).mean()
        
        # Cleanup
        temp_cols = ['up_move', 'down_move', 'plus_dm', 'minus_dm',
                     'plus_dm_smooth', 'minus_dm_smooth', 'tr_smooth', 'dx']
        df = df.drop(temp_cols, axis=1)
        
        return df
```

### 5.4 Signal Generator

```python
# backend/core/signals.py

import pandas as pd
import numpy as np
from typing import Dict, List

class SignalGenerator:
    """
    Генератор торговых сигналов
    
    Supports:
    - Indicator-based conditions
    - Multiple conditions with AND/OR logic
    - Long/Short signals
    - Exit signals
    """
    
    def __init__(self, config: dict):
        self.config = config
        
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Генерация сигналов на основе условий
        
        Returns:
            DataFrame с колонками:
            - signal: 1 (LONG), -1 (SHORT), 0 (no signal)
            - exit_signal: True/False
        """
        
        df = df.copy()
        
        # Entry signals
        df['signal'] = 0
        
        # LONG conditions
        long_conditions = self.config.get('entry_conditions', {}).get('long', [])
        if long_conditions:
            long_mask = self._evaluate_conditions(df, long_conditions)
            df.loc[long_mask, 'signal'] = 1
            
        # SHORT conditions
        short_conditions = self.config.get('entry_conditions', {}).get('short', [])
        if short_conditions:
            short_mask = self._evaluate_conditions(df, short_conditions)
            df.loc[short_mask, 'signal'] = -1
            
        # Exit signals
        exit_conditions = self.config.get('exit_conditions', [])
        if exit_conditions:
            df['exit_signal'] = self._evaluate_conditions(df, exit_conditions)
        else:
            df['exit_signal'] = False
            
        return df
        
    def _evaluate_conditions(
        self,
        df: pd.DataFrame,
        conditions: List[Dict]
    ) -> pd.Series:
        """
        Оценка списка условий
        
        Args:
            df: DataFrame с данными
            conditions: Список условий
            
        Example conditions:
        [
            {
                "indicator": "RSI_14",
                "operator": "<",
                "value": 30,
                "logic": "AND"
            },
            {
                "indicator": "close",
                "operator": ">",
                "value": "SMA_20",
                "logic": "OR"
            }
        ]
        
        Returns:
            Boolean Series
        """
        
        if not conditions:
            return pd.Series([False] * len(df), index=df.index)
            
        # Start with first condition
        result = self._evaluate_single_condition(df, conditions[0])
        
        # Apply remaining conditions with logic operators
        for i in range(1, len(conditions)):
            condition = conditions[i]
            mask = self._evaluate_single_condition(df, condition)
            
            logic = condition.get('logic', 'AND')
            
            if logic == 'AND':
                result = result & mask
            elif logic == 'OR':
                result = result | mask
                
        return result
        
    def _evaluate_single_condition(
        self,
        df: pd.DataFrame,
        condition: Dict
    ) -> pd.Series:
        """Оценка одного условия"""
        
        indicator = condition['indicator']
        operator = condition['operator']
        value = condition['value']
        
        # Get indicator values
        if indicator not in df.columns:
            raise ValueError(f"Indicator '{indicator}' not found in dataframe")
            
        indicator_values = df[indicator]
        
        # Get comparison value
        if isinstance(value, str):
            # Compare with another indicator
            if value not in df.columns:
                raise ValueError(f"Indicator '{value}' not found in dataframe")
            compare_values = df[value]
        else:
            # Compare with constant
            compare_values = value
            
        # Apply operator
        if operator == '>':
            return indicator_values > compare_values
        elif operator == '<':
            return indicator_values < compare_values
        elif operator == '>=':
            return indicator_values >= compare_values
        elif operator == '<=':
            return indicator_values <= compare_values
        elif operator == '==':
            return indicator_values == compare_values
        elif operator == '!=':
            return indicator_values != compare_values
        elif operator == 'crosses_above':
            return self._crosses_above(indicator_values, compare_values)
        elif operator == 'crosses_below':
            return self._crosses_below(indicator_values, compare_values)
        else:
            raise ValueError(f"Unknown operator: {operator}")
            
    def _crosses_above(self, series1: pd.Series, series2: pd.Series) -> pd.Series:
        """Проверка пересечения вверх"""
        prev_below = series1.shift(1) < series2.shift(1)
        curr_above = series1 > series2
        return prev_below & curr_above
        
    def _crosses_below(self, series1: pd.Series, series2: pd.Series) -> pd.Series:
        """Проверка пересечения вниз"""
        prev_above = series1.shift(1) > series2.shift(1)
        curr_below = series1 < series2
        return prev_above & curr_below
```

### 5.5 Metrics Calculator

```python
# backend/core/metrics.py

import pandas as pd
import numpy as np
from typing import Dict, List

def calculate_metrics(
    trades: List[Dict],
    equity_curve: pd.Series,
    initial_capital: float
) -> Dict:
    """
    Вычисление метрик производительности
    
    Args:
        trades: Список сделок
        equity_curve: Кривая капитала
        initial_capital: Начальный капитал
        
    Returns:
        Dict с метриками:
        - total_return: Общая доходность (%)
        - sharpe_ratio: Коэффициент Шарпа
        - sortino_ratio: Коэффициент Сортино
        - max_drawdown: Максимальная просадка (%)
        - win_rate: Процент прибыльных сделок
        - profit_factor: Отношение прибыли к убыткам
        - и многое другое...
    """
    
    if not trades:
        return _empty_metrics()
        
    trades_df = pd.DataFrame(trades)
    
    # Basic metrics
    final_capital = equity_curve.iloc[-1]
    total_return = ((final_capital - initial_capital) / initial_capital) * 100
    
    total_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df['pnl'] > 0])
    losing_trades = len(trades_df[trades_df['pnl'] < 0])
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # PnL metrics
    total_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
    total_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
    
    profit_factor = (total_profit / total_loss) if total_loss > 0 else float('inf')
    
    avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
    avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
    
    avg_trade_return = trades_df['pnl_pct'].mean()
    
    largest_win = trades_df['pnl'].max()
    largest_loss = trades_df['pnl'].min()
    
    # Duration metrics
    if 'duration_candles' in trades_df.columns:
        avg_trade_duration = trades_df['duration_candles'].mean()
    else:
        avg_trade_duration = 0
        
    # Drawdown metrics
    rolling_max = equity_curve.expanding().max()
    drawdown = (equity_curve - rolling_max) / rolling_max * 100
    
    max_drawdown = drawdown.min()
    
    # Calculate drawdown duration
    in_drawdown = drawdown < 0
    drawdown_periods = (in_drawdown != in_drawdown.shift()).cumsum()
    max_drawdown_duration = in_drawdown.groupby(drawdown_periods).sum().max()
    
    # Risk-adjusted returns
    returns = equity_curve.pct_change().dropna()
    
    # Sharpe Ratio (annualized)
    if len(returns) > 0 and returns.std() > 0:
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
    else:
        sharpe_ratio = 0
        
    # Sortino Ratio (annualized)
    negative_returns = returns[returns < 0]
    if len(negative_returns) > 0 and negative_returns.std() > 0:
        sortino_ratio = (returns.mean() / negative_returns.std()) * np.sqrt(252)
    else:
        sortino_ratio = 0
        
    # Calmar Ratio
    if max_drawdown < 0:
        calmar_ratio = total_return / abs(max_drawdown)
    else:
        calmar_ratio = 0
        
    # Expectancy
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
    
    return {
        'final_capital': float(final_capital),
        'total_return': float(total_return),
        'total_trades': int(total_trades),
        'winning_trades': int(winning_trades),
        'losing_trades': int(losing_trades),
        'win_rate': float(win_rate),
        'profit_factor': float(profit_factor),
        'avg_win': float(avg_win),
        'avg_loss': float(avg_loss),
        'avg_trade_return': float(avg_trade_return),
        'largest_win': float(largest_win),
        'largest_loss': float(largest_loss),
        'avg_trade_duration': float(avg_trade_duration),
        'max_drawdown': float(max_drawdown),
        'max_drawdown_duration': int(max_drawdown_duration) if not pd.isna(max_drawdown_duration) else 0,
        'sharpe_ratio': float(sharpe_ratio),
        'sortino_ratio': float(sortino_ratio),
        'calmar_ratio': float(calmar_ratio),
        'expectancy': float(expectancy)
    }

def _empty_metrics() -> Dict:
    """Пустые метрики (когда нет сделок)"""
    return {
        'final_capital': 0,
        'total_return': 0,
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'win_rate': 0,
        'profit_factor': 0,
        'avg_win': 0,
        'avg_loss': 0,
        'avg_trade_return': 0,
        'largest_win': 0,
        'largest_loss': 0,
        'avg_trade_duration': 0,
        'max_drawdown': 0,
        'max_drawdown_duration': 0,
        'sharpe_ratio': 0,
        'sortino_ratio': 0,
        'calmar_ratio': 0,
        'expectancy': 0
    }
```

---

## 🎨 6. FRONTEND ARCHITECTURE (Electron + React)

### 6.1 Electron Main Process

```typescript
// electron/main.ts

import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';
import { autoUpdater } from 'electron-updater';

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1920,
    height: 1080,
    minWidth: 1280,
    minHeight: 720,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    titleBarStyle: 'hidden',
    frame: false,
    backgroundColor: '#1e1e1e'
  });

  // Load app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // Window events
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Auto-updater
  autoUpdater.checkForUpdatesAndNotify();
}

// App lifecycle
app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC Handlers
ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('minimize-window', () => {
  mainWindow?.minimize();
});

ipcMain.handle('maximize-window', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});

ipcMain.handle('close-window', () => {
  mainWindow?.close();
});

// File system operations
ipcMain.handle('export-backtest-results', async (event, data) => {
  const { dialog } = require('electron');
  const fs = require('fs');
  
  const result = await dialog.showSaveDialog({
    title: 'Export Backtest Results',
    defaultPath: 'backtest_results.json',
    filters: [
      { name: 'JSON Files', extensions: ['json'] },
      { name: 'CSV Files', extensions: ['csv'] }
    ]
  });

  if (!result.canceled && result.filePath) {
    fs.writeFileSync(result.filePath, JSON.stringify(data, null, 2));
    return { success: true, path: result.filePath };
  }

  return { success: false };
});
```

```typescript
// electron/preload.ts

import { contextBridge, ipcRenderer } from 'electron';

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Window controls
  minimizeWindow: () => ipcRenderer.invoke('minimize-window'),
  maximizeWindow: () => ipcRenderer.invoke('maximize-window'),
  closeWindow: () => ipcRenderer.invoke('close-window'),
  
  // App info
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  
  // File operations
  exportBacktestResults: (data: any) => 
    ipcRenderer.invoke('export-backtest-results', data),
});

// Type definitions for TypeScript
declare global {
  interface Window {
    electronAPI: {
      minimizeWindow: () => Promise<void>;
      maximizeWindow: () => Promise<void>;
      closeWindow: () => Promise<void>;
      getAppVersion: () => Promise<string>;
      exportBacktestResults: (data: any) => Promise<{ success: boolean; path?: string }>;
    };
  }
}
```

### 6.2 React Application Structure

```
frontend/
├── src/
│   ├── main.tsx                    # Entry point
│   ├── App.tsx                     # Root component
│   ├── vite-env.d.ts              # Vite types
│   │
│   ├── components/                 # Reusable components
│   │   ├── Layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── TitleBar.tsx       # Custom window controls
│   │   │
│   │   ├── Charts/
│   │   │   ├── CandlestickChart.tsx   # TradingView wrapper
│   │   │   ├── EquityCurveChart.tsx
│   │   │   ├── DrawdownChart.tsx
│   │   │   └── ChartToolbar.tsx
│   │   │
│   │   ├── Tables/
│   │   │   ├── TradesTable.tsx
│   │   │   ├── StrategiesTable.tsx
│   │   │   └── BacktestsTable.tsx
│   │   │
│   │   ├── Forms/
│   │   │   ├── StrategyForm.tsx
│   │   │   ├── BacktestForm.tsx
│   │   │   └── OptimizationForm.tsx
│   │   │
│   │   └── Cards/
│   │       ├── MetricCard.tsx
│   │       ├── SummaryCard.tsx
│   │       └── PerformanceCard.tsx
│   │
│   ├── pages/                      # Page components
│   │   ├── Dashboard.tsx
│   │   ├── Backtest.tsx
│   │   ├── Strategies.tsx
│   │   ├── Optimization.tsx
│   │   ├── LiveTrading.tsx
│   │   └── Settings.tsx
│   │
│   ├── hooks/                      # Custom React hooks
│   │   ├── useBacktest.ts
│   │   ├── useStrategy.ts
│   │   ├── useLiveData.ts
│   │   └── useWebSocket.ts
│   │
│   ├── store/                      # State management (Zustand)
│   │   ├── backtestStore.ts
│   │   ├── strategyStore.ts
│   │   ├── dataStore.ts
│   │   └── uiStore.ts
│   │
│   ├── services/                   # API services
│   │   ├── api.ts                 # Axios instance
│   │   ├── backtestService.ts
│   │   ├── strategyService.ts
│   │   ├── dataService.ts
│   │   └── websocketService.ts
│   │
│   ├── types/                      # TypeScript types
│   │   ├── backtest.ts
│   │   ├── strategy.ts
│   │   ├── trade.ts
│   │   └── api.ts
│   │
│   └── utils/                      # Utility functions
│       ├── formatters.ts
│       ├── calculations.ts
│       └── validators.ts
│
├── public/                         # Static assets
│   └── assets/
│
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

### 6.3 Main App Component

```typescript
// src/App.tsx

import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material';
import CssBaseline from '@mui/material/CssBaseline';

// Layout
import Layout from './components/Layout/Layout';
import TitleBar from './components/Layout/TitleBar';

// Pages
import Dashboard from './pages/Dashboard';
import Backtest from './pages/Backtest';
import Strategies from './pages/Strategies';
import Optimization from './pages/Optimization';
import LiveTrading from './pages/LiveTrading';
import Settings from './pages/Settings';

// Dark theme (trading terminal style)
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#0a0e27',
      paper: '#131722',
    },
    success: {
      main: '#26a69a',  // Green for profit
    },
    error: {
      main: '#ef5350',  // Red for loss
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    fontSize: 13,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
        },
      },
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <BrowserRouter>
        <div className="app">
          {/* Custom window title bar (Electron) */}
          <TitleBar />
          
          {/* Main layout with sidebar */}
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/backtest" element={<Backtest />} />
              <Route path="/strategies" element={<Strategies />} />
              <Route path="/optimization" element={<Optimization />} />
              <Route path="/live" element={<LiveTrading />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Layout>
        </div>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
```

### 6.4 Custom Title Bar (Windows Integration)

```typescript
// src/components/Layout/TitleBar.tsx

import React from 'react';
import { Box, IconButton, Typography } from '@mui/material';
import MinimizeIcon from '@mui/icons-material/Minimize';
import CropSquareIcon from '@mui/icons-material/CropSquare';
import CloseIcon from '@mui/icons-material/Close';

const TitleBar: React.FC = () => {
  const handleMinimize = () => {
    window.electronAPI.minimizeWindow();
  };

  const handleMaximize = () => {
    window.electronAPI.maximizeWindow();
  };

  const handleClose = () => {
    window.electronAPI.closeWindow();
  };

  return (
    <Box
      sx={{
        height: '32px',
        width: '100%',
        backgroundColor: '#131722',
        borderBottom: '1px solid #2a2e39',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        WebkitAppRegion: 'drag',  // Makes title bar draggable
        userSelect: 'none',
      }}
    >
      {/* App title */}
      <Box sx={{ display: 'flex', alignItems: 'center', px: 2 }}>
        <Typography variant="caption" sx={{ fontWeight: 500 }}>
          Bybit Strategy Tester
        </Typography>
      </Box>

      {/* Window controls */}
      <Box sx={{ display: 'flex', WebkitAppRegion: 'no-drag' }}>
        <IconButton
          size="small"
          onClick={handleMinimize}
          sx={{
            borderRadius: 0,
            width: '46px',
            height: '32px',
            '&:hover': { backgroundColor: '#2a2e39' }
          }}
        >
          <MinimizeIcon fontSize="small" />
        </IconButton>

        <IconButton
          size="small"
          onClick={handleMaximize}
          sx={{
            borderRadius: 0,
            width: '46px',
            height: '32px',
            '&:hover': { backgroundColor: '#2a2e39' }
          }}
        >
          <CropSquareIcon fontSize="small" />
        </IconButton>

        <IconButton
          size="small"
          onClick={handleClose}
          sx={{
            borderRadius: 0,
            width: '46px',
            height: '32px',
            '&:hover': { backgroundColor: '#e81123', color: 'white' }
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>
    </Box>
  );
};

export default TitleBar;
```

---

## 📊 7. TRADINGVIEW LIGHTWEIGHT CHARTS INTEGRATION

### 7.1 Candlestick Chart Component

```typescript
// src/components/Charts/CandlestickChart.tsx

import React, { useEffect, useRef, useState } from 'react';
import { Box } from '@mui/material';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  LineData,
  Time,
  UTCTimestamp
} from 'lightweight-charts';

interface Trade {
  entry_time: string;
  exit_time?: string;
  entry_price: number;
  exit_price?: number;
  side: 'LONG' | 'SHORT';
  pnl?: number;
}

interface CandlestickChartProps {
  data: CandlestickData[];
  trades?: Trade[];
  indicators?: {
    name: string;
    data: LineData[];
    color: string;
  }[];
  height?: number;
}

const CandlestickChart: React.FC<CandlestickChartProps> = ({
  data,
  trades = [],
  indicators = [],
  height = 600
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const indicatorSeriesRefs = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: '#0a0e27' },
        textColor: '#9598a1',
      },
      grid: {
        vertLines: { color: '#1e222d' },
        horzLines: { color: '#1e222d' },
      },
      crosshair: {
        mode: 1,  // Normal crosshair
        vertLine: {
          color: '#758696',
          width: 1,
          style: 3,  // Dashed
          labelBackgroundColor: '#1976d2',
        },
        horzLine: {
          color: '#758696',
          width: 1,
          style: 3,
          labelBackgroundColor: '#1976d2',
        },
      },
      rightPriceScale: {
        borderColor: '#2a2e39',
      },
      timeScale: {
        borderColor: '#2a2e39',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // Add candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    candlestickSeriesRef.current = candlestickSeries;

    // Set data
    if (data.length > 0) {
      candlestickSeries.setData(data);
    }

    // Add indicators
    indicators.forEach((indicator) => {
      const lineSeries = chart.addLineSeries({
        color: indicator.color,
        lineWidth: 2,
        title: indicator.name,
      });
      lineSeries.setData(indicator.data);
      indicatorSeriesRefs.current.set(indicator.name, lineSeries);
    });

    // Add trade markers
    if (trades.length > 0) {
      const markers = trades.flatMap((trade) => {
        const markers = [];

        // Entry marker
        const entryTime = new Date(trade.entry_time).getTime() / 1000 as UTCTimestamp;
        markers.push({
          time: entryTime,
          position: trade.side === 'LONG' ? 'belowBar' : 'aboveBar',
          color: trade.side === 'LONG' ? '#26a69a' : '#ef5350',
          shape: trade.side === 'LONG' ? 'arrowUp' : 'arrowDown',
          text: trade.side === 'LONG' ? 'LONG' : 'SHORT',
        });

        // Exit marker
        if (trade.exit_time && trade.exit_price) {
          const exitTime = new Date(trade.exit_time).getTime() / 1000 as UTCTimestamp;
          const isProfit = trade.pnl && trade.pnl > 0;

          markers.push({
            time: exitTime,
            position: trade.side === 'LONG' ? 'aboveBar' : 'belowBar',
            color: isProfit ? '#26a69a' : '#ef5350',
            shape: 'circle',
            text: `${isProfit ? '+' : ''}${trade.pnl?.toFixed(2) || '0'} USDT`,
          });

          // Price line from entry to exit
          candlestickSeries.createPriceLine({
            price: trade.entry_price,
            color: trade.side === 'LONG' ? '#26a69a80' : '#ef535080',
            lineWidth: 1,
            lineStyle: 2,  // Dashed
            axisLabelVisible: false,
          });
        }

        return markers;
      });

      candlestickSeries.setMarkers(markers as any);
    }

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data, trades, indicators, height]);

  // Update data when it changes
  useEffect(() => {
    if (candlestickSeriesRef.current && data.length > 0) {
      candlestickSeriesRef.current.setData(data);
    }
  }, [data]);

  return (
    <Box
      ref={chartContainerRef}
      sx={{
        width: '100%',
        height: `${height}px`,
        position: 'relative',
        backgroundColor: '#0a0e27',
        borderRadius: 1,
      }}
    />
  );
};

export default CandlestickChart;
```

### 7.2 Equity Curve Chart

```typescript
// src/components/Charts/EquityCurveChart.tsx

import React, { useEffect, useRef } from 'react';
import { Box } from '@mui/material';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  LineData,
  UTCTimestamp
} from 'lightweight-charts';

interface EquityCurveChartProps {
  data: { time: string; value: number }[];
  initialCapital: number;
  height?: number;
}

const EquityCurveChart: React.FC<EquityCurveChartProps> = ({
  data,
  initialCapital,
  height = 300
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: '#0a0e27' },
        textColor: '#9598a1',
      },
      grid: {
        vertLines: { color: '#1e222d' },
        horzLines: { color: '#1e222d' },
      },
      rightPriceScale: {
        borderColor: '#2a2e39',
      },
      timeScale: {
        borderColor: '#2a2e39',
        timeVisible: true,
      },
    });

    // Add equity line series
    const equitySeries = chart.addLineSeries({
      color: '#1976d2',
      lineWidth: 2,
      title: 'Equity',
    });

    // Convert data
    const lineData: LineData[] = data.map((point) => ({
      time: new Date(point.time).getTime() / 1000 as UTCTimestamp,
      value: point.value,
    }));

    equitySeries.setData(lineData);

    // Add initial capital line
    if (lineData.length > 0) {
      equitySeries.createPriceLine({
        price: initialCapital,
        color: '#9598a180',
        lineWidth: 1,
        lineStyle: 2,  // Dashed
        title: 'Initial Capital',
        axisLabelVisible: true,
      });
    }

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data, initialCapital, height]);

  return (
    <Box
      ref={chartContainerRef}
      sx={{
        width: '100%',
        height: `${height}px`,
        backgroundColor: '#0a0e27',
        borderRadius: 1,
      }}
    />
  );
};

export default EquityCurveChart;
```

### 7.3 Live Data Integration

```typescript
// src/hooks/useLiveData.ts

import { useEffect, useState } from 'react';
import { CandlestickData, UTCTimestamp } from 'lightweight-charts';
import { websocketService } from '../services/websocketService';

interface UseLiveDataProps {
  symbol: string;
  timeframe: string;
  enabled: boolean;
}

export const useLiveData = ({ symbol, timeframe, enabled }: UseLiveDataProps) => {
  const [candles, setCandles] = useState<CandlestickData[]>([]);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!enabled) return;

    // Connect to WebSocket
    websocketService.connect();

    // Subscribe to candles
    websocketService.subscribe('candle_update', (data: any) => {
      if (data.symbol === symbol && data.timeframe === timeframe) {
        const newCandle: CandlestickData = {
          time: new Date(data.timestamp).getTime() / 1000 as UTCTimestamp,
          open: data.open,
          high: data.high,
          low: data.low,
          close: data.close,
        };

        setCandles((prev) => {
          const lastCandle = prev[prev.length - 1];

          // Update last candle or add new one
          if (lastCandle && lastCandle.time === newCandle.time) {
            return [...prev.slice(0, -1), newCandle];
          } else {
            return [...prev, newCandle];
          }
        });

        setLastUpdate(new Date());
      }
    });

    // Connection status
    websocketService.on('connect', () => setIsConnected(true));
    websocketService.on('disconnect', () => setIsConnected(false));

    // Send subscription message
    websocketService.send({
      action: 'subscribe',
      symbol,
      timeframe,
    });

    return () => {
      websocketService.send({
        action: 'unsubscribe',
        symbol,
        timeframe,
      });
      websocketService.disconnect();
    };
  }, [symbol, timeframe, enabled]);

  return { candles, lastUpdate, isConnected };
};
```

---

## 🔌 8. WEBSOCKET SERVICE (Real-time Data)

### 8.1 Frontend WebSocket Client

```typescript
// src/services/websocketService.ts

import { io, Socket } from 'socket.io-client';

class WebSocketService {
  private socket: Socket | null = null;
  private listeners: Map<string, Set<Function>> = new Map();

  connect(url: string = 'http://localhost:8000') {
    if (this.socket?.connected) {
      console.log('WebSocket already connected');
      return;
    }

    this.socket = io(url, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.emit('connect');
    });

    this.socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      this.emit('disconnect');
    });

    this.socket.on('error', (error: any) => {
      console.error('WebSocket error:', error);
      this.emit('error', error);
    });

    // Handle all incoming messages
    this.socket.onAny((event, ...args) => {
      this.emit(event, ...args);
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  send(event: string, data?: any) {
    if (!this.socket?.connected) {
      console.warn('WebSocket not connected');
      return;
    }

    this.socket.emit(event, data);
  }

  subscribe(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }

    this.listeners.get(event)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.listeners.get(event)?.delete(callback);
    };
  }

  on(event: string, callback: Function) {
    return this.subscribe(event, callback);
  }

  private emit(event: string, ...args: any[]) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach((callback) => callback(...args));
    }
  }

  get isConnected(): boolean {
    return this.socket?.connected || false;
  }
}

export const websocketService = new WebSocketService();
```

### 8.2 Backend WebSocket Server (FastAPI + Socket.IO)

```python
# backend/api/websocket.py

from fastapi import FastAPI
from fastapi_socketio import SocketManager
import asyncio
from loguru import logger
from typing import Dict, Set

from backend.services.redis_manager import RedisManager

# Initialize Socket.IO
socket_manager = SocketManager(app=FastAPI(), cors_allowed_origins='*')

# Track subscriptions
subscriptions: Dict[str, Set[str]] = {}  # {sid: {subscription_keys}}

@socket_manager.on('connect')
async def handle_connect(sid, environ):
    """Handle client connection"""
    logger.info(f"Client connected: {sid}")
    subscriptions[sid] = set()
    await socket_manager.emit('connected', {'status': 'ok'}, to=sid)

@socket_manager.on('disconnect')
async def handle_disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {sid}")
    
    # Cleanup subscriptions
    if sid in subscriptions:
        del subscriptions[sid]

@socket_manager.on('subscribe')
async def handle_subscribe(sid, data):
    """
    Subscribe to live data stream
    
    Request:
    {
        "action": "subscribe",
        "symbol": "BTCUSDT",
        "timeframe": "15"
    }
    """
    symbol = data.get('symbol')
    timeframe = data.get('timeframe')
    
    if not symbol or not timeframe:
        await socket_manager.emit('error', {
            'message': 'Missing symbol or timeframe'
        }, to=sid)
        return
        
    subscription_key = f"{symbol}:{timeframe}"
    
    # Add subscription
    subscriptions[sid].add(subscription_key)
    
    logger.info(f"Client {sid} subscribed to {subscription_key}")
    
    await socket_manager.emit('subscribed', {
        'symbol': symbol,
        'timeframe': timeframe
    }, to=sid)

@socket_manager.on('unsubscribe')
async def handle_unsubscribe(sid, data):
    """Unsubscribe from data stream"""
    symbol = data.get('symbol')
    timeframe = data.get('timeframe')
    
    subscription_key = f"{symbol}:{timeframe}"
    
    if sid in subscriptions:
        subscriptions[sid].discard(subscription_key)
        
    logger.info(f"Client {sid} unsubscribed from {subscription_key}")

# Background task to broadcast updates
async def broadcast_candle_updates():
    """
    Listen to Redis pub/sub and broadcast to WebSocket clients
    """
    redis = RedisManager()
    pubsub = redis.client.pubsub()
    
    # Subscribe to Redis channel
    await pubsub.subscribe('candle_updates')
    
    logger.info("Started broadcasting candle updates")
    
    async for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'])
            
            symbol = data['symbol']
            timeframe = data['timeframe']
            subscription_key = f"{symbol}:{timeframe}"
            
            # Broadcast to subscribed clients
            for sid, subs in subscriptions.items():
                if subscription_key in subs:
                    await socket_manager.emit('candle_update', data, to=sid)
```

### 8.3 Redis Pub/Sub Manager

```python
# backend/services/redis_manager.py

import redis
import json
from typing import Optional
from loguru import logger

class RedisManager:
    """
    Redis manager for caching and pub/sub
    """
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )
        
    def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None
            
    def set(self, key: str, value: str, expire: int = 3600):
        """Set value in cache with expiration"""
        try:
            self.client.setex(key, expire, value)
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            
    def publish(self, channel: str, message: dict):
        """Publish message to channel"""
        try:
            self.client.publish(channel, json.dumps(message))
        except Exception as e:
            logger.error(f"Redis PUBLISH error: {e}")
            
    def subscribe(self, *channels):
        """Subscribe to channels"""
        pubsub = self.client.pubsub()
        pubsub.subscribe(*channels)
        return pubsub
        
    def delete(self, *keys):
        """Delete keys"""
        try:
            self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return False

# Singleton instance
redis_manager = RedisManager()
```

---

## ⚙️ 9. CELERY WORKERS (Background Tasks)

### 9.1 Celery Configuration

```python
# backend/celery_app.py

from celery import Celery
from backend.core.config import settings

# Initialize Celery
celery_app = Celery(
    'bybit_strategy_tester',
    broker=f'amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASS}@{settings.RABBITMQ_HOST}:5672/',
    backend=f'redis://{settings.REDIS_HOST}:6379/1',
    include=[
        'backend.tasks.backtest_tasks',
        'backend.tasks.optimization_tasks',
        'backend.tasks.data_tasks',
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'backend.tasks.backtest_tasks.*': {'queue': 'backtest'},
        'backend.tasks.optimization_tasks.*': {'queue': 'optimization'},
        'backend.tasks.data_tasks.*': {'queue': 'data'},
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    
    # Result backend settings
    result_expires=3600,
    
    # Task settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

@celery_app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
```

### 9.2 Backtest Tasks

```python
# backend/tasks/backtest_tasks.py

from celery import Task
from sqlalchemy.orm import Session
from loguru import logger

from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.services.backtest_service import BacktestService
from backend.models.backtest import Backtest

class BacktestTask(Task):
    """Base task with database session"""
    
    def __call__(self, *args, **kwargs):
        with SessionLocal() as db:
            return self.run(db, *args, **kwargs)

@celery_app.task(base=BacktestTask, bind=True, name='run_backtest')
def run_backtest_task(
    self,
    db: Session,
    strategy_id: int,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    leverage: int,
    commission: float,
    user_id: int = None
):
    """
    Celery task для запуска бэктеста
    
    This task runs in background and updates progress
    """
    
    try:
        logger.info(f"Starting backtest task: strategy={strategy_id}, symbol={symbol}")
        
        # Update task state
        self.update_state(state='PROGRESS', meta={'progress': 0, 'status': 'Initializing...'})
        
        # Run backtest
        service = BacktestService(db)
        
        from datetime import datetime
        backtest = await service.run_backtest(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=datetime.fromisoformat(start_date),
            end_date=datetime.fromisoformat(end_date),
            initial_capital=initial_capital,
            leverage=leverage,
            commission=commission,
            user_id=user_id
        )
        
        logger.success(f"Backtest completed: {backtest.id}")
        
        return {
            'status': 'completed',
            'backtest_id': backtest.id,
            'total_return': float(backtest.total_return),
            'sharpe_ratio': float(backtest.sharpe_ratio),
            'max_drawdown': float(backtest.max_drawdown)
        }
        
    except Exception as e:
        logger.error(f"Backtest task failed: {str(e)}")
        
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        
        raise

@celery_app.task(name='run_multiple_backtests')
def run_multiple_backtests_task(backtest_configs: list):
    """
    Run multiple backtests in parallel
    
    Args:
        backtest_configs: List of backtest configurations
    """
    
    from celery import group
    
    # Create group of tasks
    job = group(
        run_backtest_task.s(**config)
        for config in backtest_configs
    )
    
    # Execute in parallel
    result = job.apply_async()
    
    return {
        'task_id': result.id,
        'total_tasks': len(backtest_configs)
    }
```

### 9.3 WebSocket Worker (Bybit Live Data)

```python
# backend/workers/websocket_worker.py

import asyncio
import json
from datetime import datetime
from pybit.unified_trading import WebSocket
from loguru import logger

from backend.services.redis_manager import redis_manager

class BybitWebSocketWorker:
    """
    Worker для получения live данных с Bybit через WebSocket
    
    Features:
    - Real-time candles (multiple timeframes)
    - Trade updates
    - Orderbook updates
    - Redis pub/sub broadcasting
    """
    
    def __init__(self, symbols: list, timeframes: list):
        self.symbols = symbols
        self.timeframes = timeframes
        self.ws = None
        self.candle_buffers = {}  # Buffer для построения свечей
        
    def start(self):
        """Start WebSocket connection"""
        
        self.ws = WebSocket(
            testnet=False,
            channel_type="linear"
        )
        
        # Subscribe to kline (candles)
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                topic = f"kline.{timeframe}.{symbol}"
                self.ws.kline_stream(
                    interval=timeframe,
                    symbol=symbol,
                    callback=self.handle_candle_update
                )
                logger.info(f"Subscribed to {topic}")
                
        # Subscribe to trades
        for symbol in self.symbols:
            self.ws.trade_stream(
                symbol=symbol,
                callback=self.handle_trade_update
            )
            
        logger.success("WebSocket worker started")
        
        # Keep running
        try:
            while True:
                asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping WebSocket worker...")
            self.stop()
            
    def handle_candle_update(self, message):
        """Handle candle update"""
        
        try:
            data = message['data'][0]
            
            symbol = message['topic'].split('.')[-1]
            timeframe = message['topic'].split('.')[1]
            
            candle_data = {
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': datetime.fromtimestamp(data['start'] / 1000).isoformat(),
                'open': float(data['open']),
                'high': float(data['high']),
                'low': float(data['low']),
                'close': float(data['close']),
                'volume': float(data['volume']),
                'is_closed': data['confirm']
            }
            
            # Cache в Redis
            cache_key = f"candle:{symbol}:{timeframe}:latest"
            redis_manager.set(cache_key, json.dumps(candle_data), expire=60)
            
            # Broadcast via Redis pub/sub
            redis_manager.publish('candle_updates', candle_data)
            
            logger.debug(f"Candle update: {symbol} {timeframe} @ {candle_data['close']}")
            
        except Exception as e:
            logger.error(f"Error handling candle update: {e}")
            
    def handle_trade_update(self, message):
        """Handle trade update"""
        
        try:
            data = message['data'][0]
            
            trade_data = {
                'symbol': data['s'],
                'price': float(data['p']),
                'quantity': float(data['v']),
                'side': data['S'],
                'timestamp': datetime.fromtimestamp(data['T'] / 1000).isoformat()
            }
            
            # Broadcast
            redis_manager.publish('trade_updates', trade_data)
            
        except Exception as e:
            logger.error(f"Error handling trade update: {e}")
            
    def stop(self):
        """Stop WebSocket connection"""
        if self.ws:
            self.ws.exit()
            logger.info("WebSocket worker stopped")

# Run worker
if __name__ == '__main__':
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    timeframes = ['1', '5', '15', '30', '60', '240']
    
    worker = BybitWebSocketWorker(symbols, timeframes)
    worker.start()
```

---

## 📦 10. DEPLOYMENT STRATEGY

### 10.1 Windows 11 Desktop Application

```json
// electron-builder configuration
// package.json (build section)

{
  "build": {
    "appId": "com.bybit.strategytester",
    "productName": "Bybit Strategy Tester",
    "copyright": "Copyright © 2025",
    
    "directories": {
      "output": "dist/electron",
      "buildResources": "build"
    },
    
    "files": [
      "dist/**/*",
      "electron/**/*",
      "!**/*.map",
      "!**/node_modules/**/*",
      "package.json"
    ],
    
    "win": {
      "target": [
        {
          "target": "nsis",
          "arch": ["x64"]
        },
        {
          "target": "portable",
          "arch": ["x64"]
        }
      ],
      "icon": "build/icon.ico",
      "artifactName": "${productName}-${version}-${os}-${arch}.${ext}",
      "publisherName": "Bybit Strategy Tester",
      "verifyUpdateCodeSignature": false
    },
    
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true,
      "allowElevation": true,
      "createDesktopShortcut": true,
      "createStartMenuShortcut": true,
      "shortcutName": "Bybit Strategy Tester",
      "perMachine": false,
      "installerIcon": "build/icon.ico",
      "uninstallerIcon": "build/icon.ico",
      "installerHeader": "build/installerHeader.bmp",
      "installerSidebar": "build/installerSidebar.bmp",
      "license": "LICENSE.txt"
    },
    
    "portable": {
      "artifactName": "${productName}-${version}-portable.exe"
    },
    
    "publish": {
      "provider": "github",
      "owner": "your-username",
      "repo": "bybit-strategy-tester",
      "releaseType": "release"
    }
  },
  
  "scripts": {
    "build": "tsc && vite build",
    "electron:dev": "concurrently \"npm run dev\" \"wait-on http://localhost:5173 && electron .\"",
    "electron:build": "npm run build && electron-builder",
    "electron:build:portable": "npm run build && electron-builder --win portable",
    "electron:publish": "npm run build && electron-builder --publish always"
  }
}
```

### 10.2 Backend Deployment (Windows Service)

```python
# backend/service_installer.py

"""
Install backend as Windows Service using NSSM (Non-Sucking Service Manager)

Installation:
1. Download NSSM: https://nssm.cc/download
2. Run: python service_installer.py install
3. Start service: nssm start BybitBackend
"""

import os
import subprocess
import sys
from pathlib import Path

NSSM_PATH = "nssm.exe"  # Add to PATH or use full path
SERVICE_NAME = "BybitBackend"

def install_service():
    """Install backend as Windows service"""
    
    # Get paths
    backend_dir = Path(__file__).parent
    python_exe = sys.executable
    uvicorn_script = f"{python_exe} -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
    
    commands = [
        # Install service
        f'{NSSM_PATH} install {SERVICE_NAME} {python_exe}',
        
        # Set application parameters
        f'{NSSM_PATH} set {SERVICE_NAME} AppParameters "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000"',
        
        # Set working directory
        f'{NSSM_PATH} set {SERVICE_NAME} AppDirectory {backend_dir}',
        
        # Set display name
        f'{NSSM_PATH} set {SERVICE_NAME} DisplayName "Bybit Strategy Tester Backend"',
        
        # Set description
        f'{NSSM_PATH} set {SERVICE_NAME} Description "FastAPI backend for Bybit Strategy Tester"',
        
        # Set startup type (auto)
        f'{NSSM_PATH} set {SERVICE_NAME} Start SERVICE_AUTO_START',
        
        # Set output/error logs
        f'{NSSM_PATH} set {SERVICE_NAME} AppStdout {backend_dir}/logs/service.log',
        f'{NSSM_PATH} set {SERVICE_NAME} AppStderr {backend_dir}/logs/service_error.log',
        
        # Rotate logs
        f'{NSSM_PATH} set {SERVICE_NAME} AppStdoutCreationDisposition 4',
        f'{NSSM_PATH} set {SERVICE_NAME} AppStderrCreationDisposition 4',
        f'{NSSM_PATH} set {SERVICE_NAME} AppRotateFiles 1',
        f'{NSSM_PATH} set {SERVICE_NAME} AppRotateOnline 1',
        f'{NSSM_PATH} set {SERVICE_NAME} AppRotateBytes 1048576',  # 1 MB
    ]
    
    for cmd in commands:
        print(f"Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)
        
    print(f"\n✅ Service '{SERVICE_NAME}' installed successfully!")
    print(f"Start service: nssm start {SERVICE_NAME}")
    print(f"Stop service: nssm stop {SERVICE_NAME}")
    print(f"Remove service: nssm remove {SERVICE_NAME} confirm")

def uninstall_service():
    """Uninstall service"""
    subprocess.run(f'{NSSM_PATH} remove {SERVICE_NAME} confirm', shell=True)
    print(f"✅ Service '{SERVICE_NAME}' removed")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python service_installer.py [install|uninstall]")
        sys.exit(1)
        
    action = sys.argv[1]
    
    if action == 'install':
        install_service()
    elif action == 'uninstall':
        uninstall_service()
    else:
        print(f"Unknown action: {action}")
```

### 10.3 Docker Compose (Development)

```yaml
# docker-compose.yml

version: '3.8'

services:
  # PostgreSQL + TimescaleDB
  postgres:
    image: timescale/timescaledb:latest-pg16
    container_name: bybit_postgres
    environment:
      POSTGRES_USER: bybit
      POSTGRES_PASSWORD: bybit_password
      POSTGRES_DB: bybit_strategy_tester
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - bybit_network
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    container_name: bybit_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - bybit_network
    restart: unless-stopped
    command: redis-server --appendonly yes

  # RabbitMQ
  rabbitmq:
    image: rabbitmq:3-management-alpine
    container_name: bybit_rabbitmq
    environment:
      RABBITMQ_DEFAULT_USER: bybit
      RABBITMQ_DEFAULT_PASS: bybit_password
    ports:
      - "5672:5672"   # AMQP
      - "15672:15672" # Management UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    networks:
      - bybit_network
    restart: unless-stopped

  # FastAPI Backend
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: bybit_backend
    environment:
      DATABASE_URL: postgresql://bybit:bybit_password@postgres:5432/bybit_strategy_tester
      REDIS_HOST: redis
      REDIS_PORT: 6379
      RABBITMQ_HOST: rabbitmq
      RABBITMQ_USER: bybit
      RABBITMQ_PASS: bybit_password
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - ./logs:/app/logs
    networks:
      - bybit_network
    depends_on:
      - postgres
      - redis
      - rabbitmq
    restart: unless-stopped
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

  # Celery Worker (Backtest)
  celery_backtest:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: bybit_celery_backtest
    environment:
      DATABASE_URL: postgresql://bybit:bybit_password@postgres:5432/bybit_strategy_tester
      REDIS_HOST: redis
      RABBITMQ_HOST: rabbitmq
    volumes:
      - ./backend:/app
    networks:
      - bybit_network
    depends_on:
      - postgres
      - redis
      - rabbitmq
    restart: unless-stopped
    command: celery -A backend.celery_app worker -Q backtest -c 4 --loglevel=info

  # Celery Worker (Optimization)
  celery_optimization:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: bybit_celery_optimization
    environment:
      DATABASE_URL: postgresql://bybit:bybit_password@postgres:5432/bybit_strategy_tester
      REDIS_HOST: redis
      RABBITMQ_HOST: rabbitmq
    volumes:
      - ./backend:/app
    networks:
      - bybit_network
    depends_on:
      - postgres
      - redis
      - rabbitmq
    restart: unless-stopped
    command: celery -A backend.celery_app worker -Q optimization -c 2 --loglevel=info

  # WebSocket Worker
  websocket_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: bybit_websocket_worker
    environment:
      REDIS_HOST: redis
    volumes:
      - ./backend:/app
    networks:
      - bybit_network
    depends_on:
      - redis
    restart: unless-stopped
    command: python backend/workers/websocket_worker.py

  # Flower (Celery monitoring)
  flower:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: bybit_flower
    environment:
      CELERY_BROKER_URL: amqp://bybit:bybit_password@rabbitmq:5672/
      CELERY_RESULT_BACKEND: redis://redis:6379/1
    ports:
      - "5555:5555"
    networks:
      - bybit_network
    depends_on:
      - rabbitmq
      - redis
    restart: unless-stopped
    command: celery -A backend.celery_app flower --port=5555

  # Prometheus (metrics)
  prometheus:
    image: prom/prometheus:latest
    container_name: bybit_prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - bybit_network
    restart: unless-stopped
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  # Grafana (dashboards)
  grafana:
    image: grafana/grafana:latest
    container_name: bybit_grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_INSTALL_PLUGINS: grafana-clock-panel
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    ports:
      - "3000:3000"
    networks:
      - bybit_network
    depends_on:
      - prometheus
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  rabbitmq_data:
  prometheus_data:
  grafana_data:

networks:
  bybit_network:
    driver: bridge
```

```dockerfile
# backend/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 10.4 Installation Script

```powershell
# install.ps1

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Bybit Strategy Tester Installer   " -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "❌ Please run this script as Administrator" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Running as Administrator" -ForegroundColor Green

# Check Python installation
Write-Host "`n📦 Checking Python installation..." -ForegroundColor Yellow

$pythonVersion = python --version 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python not found. Please install Python 3.11+" -ForegroundColor Red
    Write-Host "Download: https://www.python.org/downloads/" -ForegroundColor Cyan
    exit 1
}

Write-Host "✅ Python installed: $pythonVersion" -ForegroundColor Green

# Check Node.js installation
Write-Host "`n📦 Checking Node.js installation..." -ForegroundColor Yellow

$nodeVersion = node --version 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Node.js not found. Please install Node.js 18+" -ForegroundColor Red
    Write-Host "Download: https://nodejs.org/" -ForegroundColor Cyan
    exit 1
}

Write-Host "✅ Node.js installed: $nodeVersion" -ForegroundColor Green

# Install backend dependencies
Write-Host "`n📦 Installing backend dependencies..." -ForegroundColor Yellow

Set-Location backend
python -m pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install backend dependencies" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Backend dependencies installed" -ForegroundColor Green

Set-Location ..

# Install frontend dependencies
Write-Host "`n📦 Installing frontend dependencies..." -ForegroundColor Yellow

Set-Location frontend
npm install

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install frontend dependencies" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Frontend dependencies installed" -ForegroundColor Green

Set-Location ..

# Initialize database
Write-Host "`n🗄️  Initializing database..." -ForegroundColor Yellow

# Check if PostgreSQL is running
$pgService = Get-Service -Name postgresql* -ErrorAction SilentlyContinue

if ($null -eq $pgService) {
    Write-Host "❌ PostgreSQL service not found" -ForegroundColor Red
    Write-Host "Please install PostgreSQL 16+ and TimescaleDB extension" -ForegroundColor Yellow
    exit 1
}

if ($pgService.Status -ne 'Running') {
    Write-Host "⚠️  Starting PostgreSQL service..." -ForegroundColor Yellow
    Start-Service $pgService.Name
}

Write-Host "✅ PostgreSQL is running" -ForegroundColor Green

# Run migrations
Set-Location backend
python -m alembic upgrade head

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to run database migrations" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Database initialized" -ForegroundColor Green

Set-Location ..

# Build Electron app
Write-Host "`n🔨 Building Electron application..." -ForegroundColor Yellow

Set-Location frontend
npm run electron:build

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to build Electron app" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Electron app built successfully" -ForegroundColor Green

Set-Location ..

# Create desktop shortcut
Write-Host "`n🔗 Creating desktop shortcut..." -ForegroundColor Yellow

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Bybit Strategy Tester.lnk")
$Shortcut.TargetPath = "$PWD\frontend\dist\electron\Bybit Strategy Tester.exe"
$Shortcut.WorkingDirectory = "$PWD"
$Shortcut.Save()

Write-Host "✅ Desktop shortcut created" -ForegroundColor Green

# Final message
Write-Host "`n=====================================" -ForegroundColor Cyan
Write-Host "  Installation Complete! 🎉          " -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the application:" -ForegroundColor Yellow
Write-Host "  1. Run: .\start_all.ps1" -ForegroundColor White
Write-Host "  2. Or double-click desktop shortcut" -ForegroundColor White
Write-Host ""
Write-Host "Backend API: http://localhost:8000" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Flower (Celery): http://localhost:5555" -ForegroundColor Cyan
Write-Host ""
```

---

## 🧪 11. TESTING STRATEGY

### 11.1 Backend Unit Tests

```python
# tests/test_backtest_engine.py

import pytest
import pandas as pd
from datetime import datetime, timedelta

from backend.core.backtest_engine import BacktestEngine
from backend.core.position import PositionSide

@pytest.fixture
def sample_data():
    """Generate sample OHLCV data"""
    dates = pd.date_range(start='2025-01-01', periods=100, freq='15T')
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + pd.Series(range(100)) * 10,
        'high': 50000 + pd.Series(range(100)) * 10 + 50,
        'low': 50000 + pd.Series(range(100)) * 10 - 50,
        'close': 50000 + pd.Series(range(100)) * 10 + 25,
        'volume': 100
    })
    
    return df

@pytest.fixture
def strategy_config():
    """Sample strategy configuration"""
    return {
        'indicators': [
            {
                'type': 'MA',
                'params': {'period': 20, 'ma_type': 'SMA'}
            },
            {
                'type': 'RSI',
                'params': {'period': 14}
            }
        ],
        'entry_conditions': {
            'long': [
                {
                    'indicator': 'close',
                    'operator': '>',
                    'value': 'SMA_20',
                    'logic': 'AND'
                },
                {
                    'indicator': 'RSI_14',
                    'operator': '<',
                    'value': 30
                }
            ]
        },
        'exit_conditions': [],
        'take_profit': 2.0,  # 2%
        'stop_loss': 1.0     # 1%
    }

class TestBacktestEngine:
    
    def test_initialization(self, strategy_config):
        """Test engine initialization"""
        engine = BacktestEngine(
            initial_capital=10000,
            leverage=1,
            commission=0.0006,
            strategy_config=strategy_config
        )
        
        assert engine.capital == 10000
        assert engine.config.leverage == 1
        assert engine.position is None
        
    def test_indicator_calculation(self, sample_data, strategy_config):
        """Test indicator calculation"""
        engine = BacktestEngine(
            initial_capital=10000,
            leverage=1,
            commission=0.0006,
            strategy_config=strategy_config
        )
        
        df = engine.indicator_calc.calculate_all(sample_data, strategy_config)
        
        # Check indicators exist
        assert 'SMA_20' in df.columns
        assert 'RSI_14' in df.columns
        
        # Check calculations
        assert not df['SMA_20'].isna().all()
        assert df['RSI_14'].between(0, 100).all()
        
    def test_backtest_execution(self, sample_data, strategy_config):
        """Test full backtest execution"""
        engine = BacktestEngine(
            initial_capital=10000,
            leverage=1,
            commission=0.0006,
            strategy_config=strategy_config
        )
        
        results = engine.run(sample_data)
        
        # Check results structure
        assert 'trades' in results
        assert 'equity_curve' in results
        assert 'drawdown_curve' in results
        
        # Check equity curve
        assert len(results['equity_curve']) == len(sample_data)
        assert results['equity_curve'].iloc[0] == 10000
        
    def test_long_position(self, sample_data, strategy_config):
        """Test LONG position logic"""
        engine = BacktestEngine(
            initial_capital=10000,
            leverage=2,
            commission=0.0006,
            strategy_config=strategy_config
        )
        
        candle = sample_data.iloc[0]
        
        engine._open_position(
            side=PositionSide.LONG,
            candle=candle,
            index=0
        )
        
        # Check position created
        assert engine.position is not None
        assert engine.position.side == PositionSide.LONG
        assert engine.position.entry_price == candle['close']
        
        # Check capital deducted (commission)
        assert engine.capital < 10000
        
    def test_short_position(self, sample_data, strategy_config):
        """Test SHORT position logic"""
        engine = BacktestEngine(
            initial_capital=10000,
            leverage=2,
            commission=0.0006,
            strategy_config=strategy_config
        )
        
        candle = sample_data.iloc[0]
        
        engine._open_position(
            side=PositionSide.SHORT,
            candle=candle,
            index=0
        )
        
        assert engine.position.side == PositionSide.SHORT
        
    def test_take_profit_exit(self, sample_data, strategy_config):
        """Test take profit exit"""
        engine = BacktestEngine(
            initial_capital=10000,
            leverage=1,
            commission=0.0006,
            strategy_config=strategy_config
        )
        
        # Open position
        entry_candle = sample_data.iloc[0]
        engine._open_position(
            side=PositionSide.LONG,
            candle=entry_candle,
            index=0
        )
        
        # Create exit candle with 2%+ gain
        exit_candle = entry_candle.copy()
        exit_candle['close'] = entry_candle['close'] * 1.025  # 2.5% gain
        
        engine._check_exit_conditions(exit_candle, 1)
        
        # Position should be closed
        assert engine.position is None
        assert len(engine.trades) == 1
        assert engine.trades[0]['exit_reason'] == 'take_profit'
        assert engine.trades[0]['pnl'] > 0
        
    def test_stop_loss_exit(self, sample_data, strategy_config):
        """Test stop loss exit"""
        engine = BacktestEngine(
            initial_capital=10000,
            leverage=1,
            commission=0.0006,
            strategy_config=strategy_config
        )
        
        # Open position
        entry_candle = sample_data.iloc[0]
        engine._open_position(
            side=PositionSide.LONG,
            candle=entry_candle,
            index=0
        )
        
        # Create exit candle with 1%+ loss
        exit_candle = entry_candle.copy()
        exit_candle['close'] = entry_candle['close'] * 0.985  # 1.5% loss
        
        engine._check_exit_conditions(exit_candle, 1)
        
        # Position should be closed
        assert engine.position is None
        assert len(engine.trades) == 1
        assert engine.trades[0]['exit_reason'] == 'stop_loss'
        assert engine.trades[0]['pnl'] < 0
        
    def test_commission_calculation(self):
        """Test commission deduction"""
        engine = BacktestEngine(
            initial_capital=10000,
            leverage=1,
            commission=0.001,  # 0.1%
            strategy_config={'indicators': [], 'entry_conditions': {}}
        )
        
        initial_capital = engine.capital
        
        candle = pd.Series({
            'timestamp': datetime.now(),
            'close': 50000,
            'open': 50000,
            'high': 50000,
            'low': 50000
        })
        
        engine._open_position(
            side=PositionSide.LONG,
            candle=candle,
            index=0
        )
        
        # Commission = position_size * commission
        # position_size = 10000 * 1 = 10000
        # commission = 10000 * 0.001 = 10
        
        expected_capital = initial_capital - 10
        assert abs(engine.capital - expected_capital) < 0.01
```

### 11.2 API Integration Tests

```python
# tests/test_api.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create tables
Base.metadata.create_all(bind=engine)

client = TestClient(app)

class TestStrategiesAPI:
    
    def test_create_strategy(self):
        """Test strategy creation"""
        response = client.post("/api/v1/strategies/", json={
            "name": "Test Strategy",
            "description": "Test description",
            "strategy_type": "Indicator-Based",
            "config": {
                "indicators": [],
                "entry_conditions": {}
            }
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Strategy"
        assert "id" in data
        
    def test_list_strategies(self):
        """Test listing strategies"""
        response = client.get("/api/v1/strategies/")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_strategy(self):
        """Test getting single strategy"""
        # Create strategy first
        create_response = client.post("/api/v1/strategies/", json={
            "name": "Get Test",
            "strategy_type": "Indicator-Based",
            "config": {}
        })
        
        strategy_id = create_response.json()["id"]
        
        # Get strategy
        response = client.get(f"/api/v1/strategies/{strategy_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == strategy_id
        assert data["name"] == "Get Test"
        
    def test_update_strategy(self):
        """Test strategy update"""
        # Create strategy
        create_response = client.post("/api/v1/strategies/", json={
            "name": "Update Test",
            "strategy_type": "Indicator-Based",
            "config": {}
        })
        
        strategy_id = create_response.json()["id"]
        
        # Update
        response = client.put(f"/api/v1/strategies/{strategy_id}", json={
            "name": "Updated Name"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        
    def test_delete_strategy(self):
        """Test strategy deletion"""
        # Create strategy
        create_response = client.post("/api/v1/strategies/", json={
            "name": "Delete Test",
            "strategy_type": "Indicator-Based",
            "config": {}
        })
        
        strategy_id = create_response.json()["id"]
        
        # Delete
        response = client.delete(f"/api/v1/strategies/{strategy_id}")
        
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/api/v1/strategies/{strategy_id}")
        assert get_response.status_code == 404

class TestBacktestAPI:
    
    def test_run_backtest(self):
        """Test backtest execution"""
        # Create strategy first
        strategy_response = client.post("/api/v1/strategies/", json={
            "name": "Backtest Strategy",
            "strategy_type": "Indicator-Based",
            "config": {
                "indicators": [
                    {"type": "MA", "params": {"period": 20}}
                ],
                "entry_conditions": {}
            }
        })
        
        strategy_id = strategy_response.json()["id"]
        
        # Run backtest
        response = client.post("/api/v1/backtest/run", json={
            "strategy_id": strategy_id,
            "symbol": "BTCUSDT",
            "timeframe": "15",
            "start_date": "2025-01-01T00:00:00",
            "end_date": "2025-01-31T23:59:59",
            "initial_capital": 10000,
            "leverage": 1,
            "commission": 0.0006
        })
        
        assert response.status_code == 202
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
```

### 11.3 Frontend E2E Tests (Playwright)

```typescript
// frontend/tests/e2e/backtest.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Backtest Flow', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
  });

  test('should create new strategy and run backtest', async ({ page }) => {
    // Navigate to Strategies page
    await page.click('text=Strategies');
    await expect(page).toHaveURL(/.*strategies/);

    // Create new strategy
    await page.click('button:has-text("New Strategy")');
    
    // Fill form
    await page.fill('input[name="name"]', 'E2E Test Strategy');
    await page.fill('textarea[name="description"]', 'Created by E2E test');
    
    // Add indicator
    await page.click('button:has-text("Add Indicator")');
    await page.selectOption('select[name="indicator_type"]', 'MA');
    await page.fill('input[name="period"]', '20');
    
    // Save strategy
    await page.click('button:has-text("Save Strategy")');
    
    // Verify success
    await expect(page.locator('text=Strategy created successfully')).toBeVisible();

    // Navigate to Backtest page
    await page.click('text=Backtest');
    await expect(page).toHaveURL(/.*backtest/);

    // Select strategy
    await page.selectOption('select[name="strategy"]', { label: 'E2E Test Strategy' });

    // Fill backtest parameters
    await page.fill('input[name="symbol"]', 'BTCUSDT');
    await page.selectOption('select[name="timeframe"]', '15');
    await page.fill('input[name="start_date"]', '2025-01-01');
    await page.fill('input[name="end_date"]', '2025-01-31');
    await page.fill('input[name="initial_capital"]', '10000');

    // Run backtest
    await page.click('button:has-text("Run Backtest")');

    // Wait for completion (with timeout)
    await expect(page.locator('text=Backtest completed')).toBeVisible({ timeout: 60000 });

    // Verify results displayed
    await expect(page.locator('[data-testid="total-return"]')).toBeVisible();
    await expect(page.locator('[data-testid="sharpe-ratio"]')).toBeVisible();
    await expect(page.locator('[data-testid="max-drawdown"]')).toBeVisible();

    // Verify chart rendered
    await expect(page.locator('[data-testid="candlestick-chart"]')).toBeVisible();
  });

  test('should display trades table', async ({ page }) => {
    await page.goto('http://localhost:5173/backtest');

    // Assume backtest already run
    await page.click('text=View Trades');

    // Verify trades table
    await expect(page.locator('table')).toBeVisible();
    await expect(page.locator('th:has-text("Entry Time")')).toBeVisible();
    await expect(page.locator('th:has-text("Exit Time")')).toBeVisible();
    await expect(page.locator('th:has-text("PnL")')).toBeVisible();

    // Check pagination
    if (await page.locator('button:has-text("Next")').isVisible()) {
      await page.click('button:has-text("Next")');
      await expect(page.locator('table tbody tr')).toHaveCount(10);
    }
  });

  test('should export backtest results', async ({ page }) => {
    await page.goto('http://localhost:5173/backtest');

    // Click export button
    const downloadPromise = page.waitForEvent('download');
    await page.click('button:has-text("Export Results")');
    
    const download = await downloadPromise;
    
    // Verify file downloaded
    expect(download.suggestedFilename()).toContain('backtest_results');
  });
});
```

---

## ⚡ 12. PERFORMANCE OPTIMIZATION

### 12.1 Database Optimization

```sql
-- performance_indexes.sql

-- ============================================================================
-- CRITICAL INDEXES FOR PERFORMANCE
-- ============================================================================

-- Backtests: Most common queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtests_strategy_status 
ON backtests(strategy_id, status) WHERE status = 'completed';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtests_performance 
ON backtests(sharpe_ratio DESC, total_return DESC) 
WHERE status = 'completed' AND sharpe_ratio IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtests_created_desc 
ON backtests(created_at DESC);

-- Trades: Time-based queries (already hypertable, but additional indexes)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_backtest_time 
ON trades(backtest_id, entry_time DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_pnl 
ON trades(backtest_id, pnl) WHERE pnl IS NOT NULL;

-- Strategies: Active strategies
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_strategies_active_type 
ON strategies(is_active, strategy_type) WHERE is_active = TRUE;

-- Market data: Symbol + timeframe queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_market_data_lookup 
ON market_data(symbol, timeframe, timestamp DESC);

-- ============================================================================
-- PARTITIONING (for large datasets)
-- ============================================================================

-- Partition backtests by month (if dataset grows large)
-- ALTER TABLE backtests DETACH PARTITION;  -- Remove default partition
-- CREATE TABLE backtests_2025_01 PARTITION OF backtests
-- FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- ============================================================================
-- MATERIALIZED VIEWS FOR FAST AGGREGATIONS
-- ============================================================================

-- Strategy performance summary
CREATE MATERIALIZED VIEW IF NOT EXISTS strategy_performance_summary AS
SELECT 
    s.id AS strategy_id,
    s.name AS strategy_name,
    s.strategy_type,
    COUNT(b.id) AS total_backtests,
    COUNT(CASE WHEN b.status = 'completed' THEN 1 END) AS completed_backtests,
    AVG(b.sharpe_ratio) FILTER (WHERE b.status = 'completed') AS avg_sharpe,
    AVG(b.total_return) FILTER (WHERE b.status = 'completed') AS avg_return,
    MAX(b.total_return) FILTER (WHERE b.status = 'completed') AS best_return,
    MIN(b.total_return) FILTER (WHERE b.status = 'completed') AS worst_return,
    AVG(b.win_rate) FILTER (WHERE b.status = 'completed') AS avg_win_rate,
    AVG(b.max_drawdown) FILTER (WHERE b.status = 'completed') AS avg_max_drawdown,
    MAX(b.created_at) AS last_backtest_at
FROM strategies s
LEFT JOIN backtests b ON s.id = b.strategy_id
WHERE s.is_active = TRUE
GROUP BY s.id, s.name, s.strategy_type;

-- Refresh strategy (call periodically)
CREATE INDEX ON strategy_performance_summary(avg_sharpe DESC);
-- REFRESH MATERIALIZED VIEW CONCURRENTLY strategy_performance_summary;

-- ============================================================================
-- VACUUM & ANALYZE (maintenance)
-- ============================================================================

-- Run weekly
-- VACUUM ANALYZE backtests;
-- VACUUM ANALYZE trades;
-- VACUUM ANALYZE market_data;

-- ============================================================================
-- QUERY OPTIMIZATION EXAMPLES
-- ============================================================================

-- BAD: Sequential scan
-- SELECT * FROM backtests WHERE total_return > 10 ORDER BY created_at DESC;

-- GOOD: Index scan
-- SELECT * FROM backtests 
-- WHERE status = 'completed' AND total_return > 10 
-- ORDER BY created_at DESC LIMIT 100;

-- BAD: Count all rows
-- SELECT COUNT(*) FROM trades;

-- GOOD: Approximate count (fast)
-- SELECT reltuples::BIGINT AS approximate_count 
-- FROM pg_class WHERE relname = 'trades';
```

### 12.2 Backend Caching Strategy

```python
# backend/core/cache_manager.py

from functools import wraps
import hashlib
import json
from typing import Any, Callable
from loguru import logger

from backend.services.redis_manager import redis_manager

class CacheManager:
    """
    Intelligent caching layer
    
    Features:
    - Function result caching
    - Cache invalidation
    - TTL management
    - Cache warming
    """
    
    DEFAULT_TTL = 3600  # 1 hour
    
    @staticmethod
    def cache_key(prefix: str, *args, **kwargs) -> str:
        """Generate cache key from function arguments"""
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    @staticmethod
    def cached(
        prefix: str,
        ttl: int = DEFAULT_TTL,
        key_builder: Callable = None
    ):
        """
        Decorator for caching function results
        
        Usage:
        @CacheManager.cached(prefix='backtest_results', ttl=3600)
        def get_backtest_results(backtest_id: int):
            # expensive operation
            return results
        """
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    cache_key = CacheManager.cache_key(prefix, *args, **kwargs)
                
                # Try to get from cache
                cached_value = redis_manager.get(cache_key)
                
                if cached_value:
                    logger.debug(f"Cache HIT: {cache_key}")
                    return json.loads(cached_value)
                
                # Cache MISS - execute function
                logger.debug(f"Cache MISS: {cache_key}")
                result = func(*args, **kwargs)
                
                # Store in cache
                redis_manager.set(cache_key, json.dumps(result), expire=ttl)
                
                return result
            
            return wrapper
        
        return decorator
    
    @staticmethod
    def invalidate(prefix: str, *args, **kwargs):
        """Invalidate cached result"""
        cache_key = CacheManager.cache_key(prefix, *args, **kwargs)
        redis_manager.delete(cache_key)
        logger.info(f"Cache invalidated: {cache_key}")
    
    @staticmethod
    def invalidate_pattern(pattern: str):
        """Invalidate all keys matching pattern"""
        # Note: Use with caution in production
        keys = redis_manager.client.keys(pattern)
        if keys:
            redis_manager.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys matching: {pattern}")

# Usage examples
@CacheManager.cached(prefix='strategy', ttl=3600)
def get_strategy(strategy_id: int):
    """Cached strategy retrieval"""
    # Database query
    pass

@CacheManager.cached(prefix='candles', ttl=300)  # 5 minutes
def get_candles(symbol: str, timeframe: str, start: str, end: str):
    """Cached candle data"""
    pass
```

### 12.3 Frontend Performance

```typescript
// src/utils/performance.ts

/**
 * Performance optimization utilities
 */

// Debounce function calls
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };

    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Throttle function calls
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean;

  return function executedFunction(...args: Parameters<T>) {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

// Memoize expensive calculations
export function memoize<T extends (...args: any[]) => any>(
  func: T
): (...args: Parameters<T>) => ReturnType<T> {
  const cache = new Map<string, ReturnType<T>>();

  return function memoized(...args: Parameters<T>): ReturnType<T> {
    const key = JSON.stringify(args);

    if (cache.has(key)) {
      return cache.get(key)!;
    }

    const result = func(...args);
    cache.set(key, result);

    return result;
  };
}

// Virtual scrolling for large lists
export function useVirtualScroll<T>(
  items: T[],
  itemHeight: number,
  containerHeight: number
): { visibleItems: T[]; scrollTop: number; totalHeight: number } {
  const [scrollTop, setScrollTop] = useState(0);

  const startIndex = Math.floor(scrollTop / itemHeight);
  const endIndex = Math.min(
    startIndex + Math.ceil(containerHeight / itemHeight),
    items.length
  );

  const visibleItems = items.slice(startIndex, endIndex);
  const totalHeight = items.length * itemHeight;

  return { visibleItems, scrollTop, totalHeight };
}

// Lazy load components
export const LazyBacktestPage = lazy(() => import('../pages/Backtest'));
export const LazyOptimizationPage = lazy(() => import('../pages/Optimization'));
```

### 12.4 Parallel Processing

```python
# backend/core/parallel_backtest.py

from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict
import multiprocessing
from loguru import logger

from backend.core.backtest_engine import BacktestEngine

def run_single_backtest(config: Dict) -> Dict:
    """
    Run single backtest (used in parallel execution)
    
    This function must be picklable (no nested functions)
    """
    engine = BacktestEngine(
        initial_capital=config['initial_capital'],
        leverage=config['leverage'],
        commission=config['commission'],
        strategy_config=config['strategy_config']
    )
    
    results = engine.run(config['data'])
    
    return {
        'config': config,
        'results': results
    }

class ParallelBacktestRunner:
    """
    Run multiple backtests in parallel
    
    Uses multiprocessing for CPU-intensive tasks
    """
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or multiprocessing.cpu_count()
        
    def run_backtests(self, configs: List[Dict]) -> List[Dict]:
        """
        Run multiple backtests in parallel
        
        Args:
            configs: List of backtest configurations
            
        Returns:
            List of results
        """
        
        logger.info(f"Running {len(configs)} backtests in parallel with {self.max_workers} workers")
        
        results = []
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_config = {
                executor.submit(run_single_backtest, config): config
                for config in configs
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_config):
                config = future_to_config[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"Completed backtest {len(results)}/{len(configs)}")
                except Exception as e:
                    logger.error(f"Backtest failed: {e}")
                    results.append({'config': config, 'error': str(e)})
        
        logger.success(f"Completed {len(results)} backtests")
        
        return results

# Usage example
"""
configs = [
    {
        'initial_capital': 10000,
        'leverage': 1,
        'commission': 0.0006,
        'strategy_config': {...},
        'data': df1
    },
    {
        'initial_capital': 10000,
        'leverage': 2,
        'commission': 0.0006,
        'strategy_config': {...},
        'data': df2
    }
]

runner = ParallelBacktestRunner(max_workers=4)
results = runner.run_backtests(configs)
"""
```

---

## 📊 13. MONITORING & LOGGING

### 13.1 Prometheus Metrics

```python
# backend/core/metrics.py

from prometheus_client import Counter, Histogram, Gauge, Summary
import time
from functools import wraps

# ============================================================================
# METRICS DEFINITIONS
# ============================================================================

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Backtest metrics
backtests_total = Counter(
    'backtests_total',
    'Total backtests run',
    ['status']
)

backtest_duration_seconds = Histogram(
    'backtest_duration_seconds',
    'Backtest execution duration'
)

backtest_trades_count = Histogram(
    'backtest_trades_count',
    'Number of trades per backtest'
)

# System metrics
active_backtests = Gauge(
    'active_backtests',
    'Currently running backtests'
)

celery_task_queue_length = Gauge(
    'celery_task_queue_length',
    'Number of tasks in Celery queue',
    ['queue']
)

# Database metrics
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['query_type']
)

# ============================================================================
# DECORATORS
# ============================================================================

def track_request(func):
    """Track HTTP request metrics"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            status = 200
            return result
        except Exception as e:
            status = 500
            raise
        finally:
            duration = time.time() - start_time
            
            http_requests_total.labels(
                method='POST',
                endpoint=func.__name__,
                status=status
            ).inc()
            
            http_request_duration_seconds.labels(
                method='POST',
                endpoint=func.__name__
            ).observe(duration)
    
    return wrapper

def track_backtest(func):
    """Track backtest execution metrics"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        active_backtests.inc()
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            
            backtests_total.labels(status='completed').inc()
            
            # Track trades count
            if 'trades' in result:
                backtest_trades_count.observe(len(result['trades']))
            
            return result
            
        except Exception as e:
            backtests_total.labels(status='failed').inc()
            raise
        finally:
            active_backtests.dec()
            
            duration = time.time() - start_time
            backtest_duration_seconds.observe(duration)
    
    return wrapper
```

### 13.2 Structured Logging

```python
# backend/core/logging_config.py

from loguru import logger
import sys
import json
from datetime import datetime

# Remove default logger
logger.remove()

# Console handler (development)
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG",
    colorize=True
)

# File handler (production)
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    compression="gz",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO"
)

# JSON handler (for log aggregation)
def json_formatter(record):
    """Format log record as JSON"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"]
    }
    
    if record["exception"]:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__,
            "value": str(record["exception"].value),
            "traceback": record["exception"].traceback
        }
    
    return json.dumps(log_entry)

logger.add(
    "logs/app_json_{time:YYYY-MM-DD}.log",
    format=json_formatter,
    rotation="00:00",
    retention="30 days",
    level="INFO"
)

# Error handler (separate file)
logger.add(
    "logs/errors_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="90 days",
    level="ERROR",
    backtrace=True,
    diagnose=True
)
```

### 13.3 Grafana Dashboard (JSON)

```json
{
  "dashboard": {
    "title": "Bybit Strategy Tester - System Monitoring",
    "panels": [
      {
        "id": 1,
        "title": "Active Backtests",
        "type": "graph",
        "targets": [
          {
            "expr": "active_backtests",
            "legendFormat": "Active Backtests"
          }
        ]
      },
      {
        "id": 2,
        "title": "Backtest Success Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(rate(backtests_total{status='completed'}[5m])) / sum(rate(backtests_total[5m])) * 100",
            "legendFormat": "Success Rate"
          }
        ]
      },
      {
        "id": 3,
        "title": "Average Backtest Duration",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(backtest_duration_seconds_bucket[5m]))",
            "legendFormat": "p95"
          },
          {
            "expr": "histogram_quantile(0.50, rate(backtest_duration_seconds_bucket[5m]))",
            "legendFormat": "p50"
          }
        ]
      },
      {
        "id": 4,
        "title": "HTTP Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(http_requests_total[1m])) by (endpoint)",
            "legendFormat": "{{endpoint}}"
          }
        ]
      },
      {
        "id": 5,
        "title": "Celery Queue Length",
        "type": "graph",
        "targets": [
          {
            "expr": "celery_task_queue_length",
            "legendFormat": "{{queue}}"
          }
        ]
      },
      {
        "id": 6,
        "title": "Database Query Performance",
        "type": "heatmap",
        "targets": [
          {
            "expr": "rate(db_query_duration_seconds_bucket[5m])",
            "legendFormat": "{{query_type}}"
          }
        ]
      }
    ]
  }
}
```

---

## 🎯 14. ФИНАЛЬНЫЕ РЕКОМЕНДАЦИИ

### 14.1 Roadmap Implementation (Приоритеты)

```
ФАЗА 1: FOUNDATION (Недели 1-4)
├── Backend API
│   ├── FastAPI setup
│   ├── PostgreSQL + TimescaleDB
│   ├── Redis + RabbitMQ
│   └── Базовые endpoints
├── Core Engine
│   ├── Backtest engine
│   ├── Indicator calculator
│   ├── Signal generator
│   └── Metrics calculator
└── Testing
    ├── Unit tests (>80% coverage)
    └── Integration tests

ФАЗА 2: FRONTEND (Недели 5-8)
├── Electron + React setup
├── TradingView Charts integration
├── Strategy builder UI
├── Backtest results visualization
└── State management (Zustand)

ФАЗА 3: REAL-TIME (Недели 9-10)
├── WebSocket integration
├── Bybit live data worker
├── Redis pub/sub
└── Live chart updates

ФАЗА 4: OPTIMIZATION (Недели 11-12)
├── Grid optimization
├── Walk-forward analysis
├── Parallel processing
└── Result caching

ФАЗА 5: PRODUCTION (Недели 13-14)
├── Windows packaging
├── Performance tuning
├── Monitoring setup
├── Documentation
└── User testing
```

### 14.2 Best Practices

**🔒 Security:**
- ✅ Use environment variables for secrets (.env)
- ✅ Never commit API keys to git
- ✅ Implement rate limiting (FastAPI middleware)
- ✅ Validate all user inputs (Pydantic)
- ✅ Use HTTPS in production
- ✅ Implement JWT authentication
- ✅ Regular dependency updates (Dependabot)

**⚡ Performance:**
- ✅ Database indexes on all foreign keys
- ✅ Cache frequently accessed data (Redis)
- ✅ Use TimescaleDB for time-series data
- ✅ Implement pagination (limit/offset)
- ✅ Background tasks for expensive operations (Celery)
- ✅ Virtual scrolling for large tables (React)
- ✅ Code splitting and lazy loading (Vite)

**🧪 Testing:**
- ✅ Aim for >80% code coverage
- ✅ Write tests before fixing bugs
- ✅ Use fixtures for test data
- ✅ Mock external APIs (Bybit)
- ✅ E2E tests for critical flows (Playwright)
- ✅ CI/CD pipeline (GitHub Actions)

**📝 Code Quality:**
- ✅ Type hints everywhere (Python)
- ✅ TypeScript strict mode (Frontend)
- ✅ Linting (pylint, eslint)
- ✅ Formatting (black, prettier)
- ✅ Pre-commit hooks (husky)
- ✅ Code reviews before merge

**📊 Monitoring:**
- ✅ Prometheus metrics for all critical paths
- ✅ Grafana dashboards for visualization
- ✅ Structured logging (JSON)
- ✅ Error tracking (Sentry optional)
- ✅ Health check endpoints
- ✅ Performance profiling (py-spy)

### 14.3 Upgrade Path (FREE → PAID)

```
ТЕКУЩАЯ ВЕРСИЯ (FREE):
├── TradingView Lightweight Charts (Apache 2.0)
├── Electron (MIT)
├── FastAPI (MIT)
├── PostgreSQL + TimescaleDB (Open Source)
└── COST: $0/month

PROFESSIONAL VERSION ($29/month):
├── Enhanced UI components
├── Advanced indicators (proprietary)
├── AI-powered optimization
├── Priority support
├── Cloud sync
└── Multi-user workspace

ENTERPRISE VERSION ($99/month):
├── TradingView Pro API ($1,500/year)
├── AG Grid Enterprise (€999/year)
├── Dedicated servers
├── White-label branding
├── API access
└── SLA guarantee

INFRASTRUCTURE COSTS (если SaaS):
├── AWS/Azure hosting: ~$200/month
├── Database (managed): ~$50/month
├── CDN: ~$20/month
├── Monitoring: ~$25/month
└── TOTAL: ~$295/month
```

### 14.4 Performance Benchmarks (Expected)

```
BACKTEST PERFORMANCE:
├── 1,000 candles: ~0.5 seconds
├── 10,000 candles: ~2 seconds
├── 100,000 candles: ~15 seconds
└── Parallel (4 cores): 4x speedup

DATABASE QUERIES:
├── Simple SELECT: <10ms
├── Complex JOIN: <50ms
├── Aggregations (TimescaleDB): <100ms
└── Full table scan: <1s (with indexes)

API RESPONSE TIMES:
├── GET /strategies: <50ms
├── POST /backtest/run: <100ms (queued)
├── GET /backtest/{id}: <50ms
└── WebSocket latency: <20ms

FRONTEND RENDERING:
├── Initial load: <2s
├── Chart render (1k candles): <100ms
├── Table render (100 rows): <50ms
└── State update: <16ms (60 FPS)
```

### 14.5 Common Pitfalls (Избегать)

**❌ НЕ ДЕЛАТЬ:**
1. **Overfitting** - Не оптимизировать на всех исторических данных
2. **Look-ahead bias** - Не использовать будущие данные в расчетах
3. **Survivorship bias** - Учитывать делистинг токенов
4. **Blocking operations** - Не блокировать UI долгими операциями
5. **No error handling** - Всегда обрабатывать исключения
6. **Hardcoded values** - Использовать конфигурационные файлы
7. **No logging** - Логировать все критические операции
8. **Premature optimization** - Сначала работающий код, потом оптимизация

**✅ ПРАВИЛЬНО:**
1. Walk-forward optimization (out-of-sample testing)
2. Асинхронная обработка (Celery для бэктестов)
3. Кэширование частых запросов (Redis)
4. Graceful degradation (fallback UI)
5. Progressive enhancement
6. Environment-based configuration
7. Structured logging с уровнями
8. Profile first, optimize later

---

## 📚 15. ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

### 15.1 Документация

**Официальные документы:**
- TradingView Lightweight Charts: https://tradingview.github.io/lightweight-charts/
- Electron: https://www.electronjs.org/docs
- FastAPI: https://fastapi.tiangolo.com/
- PostgreSQL: https://www.postgresql.org/docs/
- TimescaleDB: https://docs.timescale.com/
- Redis: https://redis.io/documentation
- RabbitMQ: https://www.rabbitmq.com/documentation.html
- Celery: https://docs.celeryq.dev/

**Туториалы:**
- Electron + React: https://www.electronjs.org/docs/latest/tutorial/tutorial-prerequisites
- FastAPI Best Practices: https://github.com/zhanymkanov/fastapi-best-practices
- TimescaleDB Time-series: https://docs.timescale.com/timescaledb/latest/tutorials/
- TradingView Integration: https://github.com/tradingview/lightweight-charts/tree/master/docs

### 15.2 Инструменты разработки

**Backend:**
- VSCode + Python extension
- Postman / Insomnia (API testing)
- pgAdmin / DBeaver (database GUI)
- RedisInsight (Redis GUI)
- Flower (Celery monitoring)

**Frontend:**
- VSCode + React extensions
- Chrome DevTools
- React Developer Tools
- Redux DevTools (если используется)

**DevOps:**
- Docker Desktop
- Prometheus
- Grafana
- NSSM (Windows Service Manager)

### 15.3 Community & Support

**GitHub Repositories:**
- Lightweight Charts Examples: https://github.com/tradingview/lightweight-charts/tree/master/plugin-examples
- FastAPI Boilerplates: https://github.com/topics/fastapi-boilerplate
- Electron Apps: https://github.com/topics/electron-app

**Forums:**
- TradingView Community: https://www.tradingview.com/community/
- FastAPI Discord: https://discord.com/invite/VQjSZaeJmf
- PostgreSQL Mailing List: https://www.postgresql.org/list/

---

## ✅ 16. CHECKLIST (Перед релизом)

### Development
- [ ] Все unit tests проходят (>80% coverage)
- [ ] Все integration tests проходят
- [ ] E2E tests для критических путей
- [ ] Нет критических warning'ов в логах
- [ ] Code review пройден
- [ ] Документация обновлена

### Performance
- [ ] Database indexes созданы
- [ ] Redis caching настроен
- [ ] Celery workers запущены
- [ ] Backtest < 2s для 10k candles
- [ ] API response time < 100ms
- [ ] Frontend render < 16ms (60 FPS)

### Security
- [ ] API keys в .env (не в коде)
- [ ] CORS настроен правильно
- [ ] Rate limiting включен
- [ ] Input validation везде
- [ ] SQL injection защита (Pydantic)
- [ ] XSS protection (React)

### Monitoring
- [ ] Prometheus metrics работают
- [ ] Grafana dashboards настроены
- [ ] Logging в файлы и JSON
- [ ] Error tracking настроен
- [ ] Health check endpoints
- [ ] Alerts настроены

### Deployment
- [ ] Docker Compose работает
- [ ] Windows Service устанавливается
- [ ] Electron app собирается
- [ ] Auto-updater настроен
- [ ] Backup strategy есть
- [ ] Rollback plan есть

### Documentation
- [ ] README.md с инструкциями
- [ ] API documentation (OpenAPI)
- [ ] Architecture diagram
- [ ] Deployment guide
- [ ] User manual
- [ ] Changelog

---

## 🎊 ЗАКЛЮЧЕНИЕ

Эта техническая спецификация содержит **полный план** для разработки профессионального Bybit Strategy Tester:

**✅ Что покрыто:**
- **Архитектура**: 3-tier (Frontend/Backend/Database) с микросервисами
- **Технологии**: 100% FREE open-source стек ($0/month)
- **Backend**: FastAPI + PostgreSQL + TimescaleDB + Redis + Celery
- **Frontend**: Electron + React + TradingView Lightweight Charts
- **Database**: Полная схема с hypertables и indexes
- **API**: REST + WebSocket с полными спецификациями
- **Testing**: Unit + Integration + E2E (pytest + Playwright)
- **Performance**: Caching, indexes, parallel processing
- **Deployment**: Docker + Windows Service + Electron packaging
- **Monitoring**: Prometheus + Grafana + Structured logging

**📊 Объём работы:**
- **Backend**: ~5,000 строк кода
- **Frontend**: ~8,000 строк кода
- **Tests**: ~2,000 строк кода
- **Total**: ~15,000 строк кода
- **Timeline**: 10-14 недель (1 разработчик)

**💰 Финансовая модель:**
- **Development**: $0/month (FREE tools)
- **SaaS Infrastructure**: ~$295/month (опционально)
- **Potential Revenue**: $300K+ ARR (800 PRO + 50 Enterprise users)

**🚀 Следующие шаги:**
1. Setup development environment
2. Initialize Git repository
3. Create project structure
4. Start with backend foundation
5. Implement core backtest engine
6. Build frontend UI
7. Integrate TradingView charts
8. Add optimization features
9. Performance testing
10. Production deployment

**Успехов в разработке! 🎯**

---

**Автор:** GitHub Copilot  
**Версия:** 1.0  
**Дата:** 16 октября 2025  
**Лицензия:** MIT (рекомендуется)
