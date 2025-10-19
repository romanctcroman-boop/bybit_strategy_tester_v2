-- ==============================================================================
-- BYBIT STRATEGY TESTER - DATABASE SCHEMA
-- ==============================================================================
-- Версия: 2.0
-- PostgreSQL: 16+
-- TimescaleDB: 2.18+
-- Создано: 2025-01-22
-- ==============================================================================

-- ==============================================================================
-- SETUP TIMESCALEDB
-- ==============================================================================
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ==============================================================================
-- USERS TABLE (optional для multi-user)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ==============================================================================
-- STRATEGIES TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS strategies (
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

CREATE INDEX IF NOT EXISTS idx_strategies_user_id ON strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_strategies_type ON strategies(strategy_type);
CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name);
-- GIN index для JSONB queries
CREATE INDEX IF NOT EXISTS idx_strategies_config ON strategies USING GIN(config);

-- ==============================================================================
-- BACKTESTS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS backtests (
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

CREATE INDEX IF NOT EXISTS idx_backtests_strategy_id ON backtests(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtests_user_id ON backtests(user_id);
CREATE INDEX IF NOT EXISTS idx_backtests_symbol ON backtests(symbol);
CREATE INDEX IF NOT EXISTS idx_backtests_status ON backtests(status);
CREATE INDEX IF NOT EXISTS idx_backtests_created_at ON backtests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtests_performance ON backtests(sharpe_ratio DESC, total_return DESC);

-- ==============================================================================
-- TRADES TABLE (Time-series data)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS trades (
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
CREATE INDEX IF NOT EXISTS idx_trades_backtest_id ON trades(backtest_id);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side);
CREATE INDEX IF NOT EXISTS idx_trades_exit_reason ON trades(exit_reason);

-- Continuous aggregate для быстрой статистики по дням
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.continuous_aggregates 
        WHERE view_name = 'trades_daily'
    ) THEN
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
        PERFORM add_continuous_aggregate_policy('trades_daily',
            start_offset => INTERVAL '1 month',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 hour');
    END IF;
END $$;

-- ==============================================================================
-- OPTIMIZATIONS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS optimizations (
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

CREATE INDEX IF NOT EXISTS idx_optimizations_strategy_id ON optimizations(strategy_id);
CREATE INDEX IF NOT EXISTS idx_optimizations_user_id ON optimizations(user_id);
CREATE INDEX IF NOT EXISTS idx_optimizations_status ON optimizations(status);
CREATE INDEX IF NOT EXISTS idx_optimizations_created_at ON optimizations(created_at DESC);

-- ==============================================================================
-- MARKET DATA CACHE (опционально, для локального хранения)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS market_data (
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
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_tf ON market_data(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON market_data(timestamp DESC);

-- Compression policy (данные старше 7 дней сжимаются)
DO $$
BEGIN
    ALTER TABLE market_data SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'symbol, timeframe'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.jobs 
        WHERE proc_name = 'policy_compression'
        AND hypertable_name = 'market_data'
    ) THEN
        PERFORM add_compression_policy('market_data', INTERVAL '7 days');
    END IF;
END $$;

-- Retention policy (удаляем данные старше 2 лет)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.jobs 
        WHERE proc_name = 'policy_retention'
        AND hypertable_name = 'market_data'
    ) THEN
        PERFORM add_retention_policy('market_data', INTERVAL '2 years');
    END IF;
END $$;

-- ==============================================================================
-- FUNCTIONS & TRIGGERS
-- ==============================================================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop triggers if exist and recreate
DROP TRIGGER IF EXISTS update_strategies_updated_at ON strategies;
CREATE TRIGGER update_strategies_updated_at
    BEFORE UPDATE ON strategies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- VIEWS
-- ==============================================================================

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

-- ==============================================================================
-- INITIAL DATA (опционально)
-- ==============================================================================

-- Создание тестового пользователя
INSERT INTO users (username, email, hashed_password, is_superuser)
VALUES ('admin', 'admin@example.com', 'changeme', TRUE)
ON CONFLICT (username) DO NOTHING;

-- Создание примера стратегии
INSERT INTO strategies (name, description, strategy_type, config, user_id)
VALUES (
    'Example RSI Strategy',
    'Simple RSI-based mean reversion strategy',
    'Indicator-Based',
    '{"rsi_period": 14, "oversold": 30, "overbought": 70, "timeframe": "15m"}'::jsonb,
    (SELECT id FROM users WHERE username = 'admin' LIMIT 1)
)
ON CONFLICT DO NOTHING;

-- ==============================================================================
-- VACUUM & ANALYZE
-- ==============================================================================

VACUUM ANALYZE users;
VACUUM ANALYZE strategies;
VACUUM ANALYZE backtests;
VACUUM ANALYZE trades;
VACUUM ANALYZE optimizations;
VACUUM ANALYZE market_data;

-- ==============================================================================
-- SUMMARY
-- ==============================================================================

\echo '================================================================================'
\echo 'DATABASE SCHEMA CREATED SUCCESSFULLY'
\echo '================================================================================'
\echo ''
\echo 'Tables created:'
\echo '  - users           (User management)'
\echo '  - strategies      (Trading strategies)'
\echo '  - backtests       (Backtest runs and results)'
\echo '  - trades          (Individual trades - TimescaleDB hypertable)'
\echo '  - optimizations   (Parameter optimization runs)'
\echo '  - market_data     (OHLCV cache - TimescaleDB hypertable)'
\echo ''
\echo 'Views created:'
\echo '  - top_strategies  (Performance ranking)'
\echo '  - recent_backtests (Latest results)'
\echo ''
\echo 'Continuous aggregates:'
\echo '  - trades_daily    (Daily trade statistics)'
\echo ''
\echo 'TimescaleDB policies:'
\echo '  - Compression: market_data (after 7 days)'
\echo '  - Retention:   market_data (delete after 2 years)'
\echo ''
\echo 'Initial data:'
\echo '  - User:     admin / changeme (CHANGE PASSWORD!)'
\echo '  - Strategy: Example RSI Strategy'
\echo ''
\echo 'Next steps:'
\echo '  1. Change admin password'
\echo '  2. Update .env file with connection string'
\echo '  3. Start backend: uvicorn main:app --reload'
\echo '================================================================================'
