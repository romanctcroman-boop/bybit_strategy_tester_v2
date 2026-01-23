# Technical Specifications for Bybit Strategy Tester v2

**Last Updated:** December 14, 2025

**Status:** All Features Implemented

---

## 1. Dashboard

**Functional requirements:**

- API endpoint returning summary metrics (active strategies, running backtests, PL, AI recommendations)
- Display metric cards, portfolio performance chart, recent activity feed

**Non-functional requirements:**

- Real-time updates via WebSocket every 5 seconds
- Responsive layout, dark-mode compatible

**Implementation:**

- backend/api/routers/dashboard.py
- backend/api/routers/dashboard_improvements.py
- frontend/dashboard.html

---

## 2. Strategies Management

**Functional requirements:**

- CRUD API for creating, reading, updating, deleting strategy definitions
- Store strategy code, parameters, and metadata
- Search and filter by name, type, performance

**Implementation:**

- backend/api/routers/strategies.py - Full CRUD
- backend/database/models/strategy.py - Persistence layer
- frontend/strategies.html

---

## 3. Backtest Results

**Functional requirements:**

- Run backtest engine on historical data, produce equity curve, trade log, risk metrics
- API returns detailed JSON

**Implementation:**

- backend/backtesting/engine.py (463 lines) - vectorbt integration
- backend/services/advanced_backtesting/ - Advanced engine with slippage, portfolio
- frontend/backtest-results.html

---

## 4. AI Studio

**Functional requirements:**

- Chat UI with selectable agents (DeepSeek, Perplexity)
- Thinking-Mode toggle for chain-of-thought reasoning
- Real-time streaming of AI output, statistics panel
- Tabbed interface and conversation history persistence

**Implementation:**

- backend/agents/unified_agent_interface.py
- backend/api/routers/chat_history.py
- frontend/streaming-chat.html

---

## 5. Market Data

**Functional requirements:**

- Fetch candles and trades from Bybit API, upload CSV, cache data
- Multi-timeframe aggregation
- Visual chart UI with TradingView Lightweight Charts

**Implementation:**

- backend/api/routers/marketdata.py
- backend/services/candle_cache.py
- frontend/market-chart.html

---

## 6. Analytics

**Functional requirements:**

- Risk dashboard (VaR, CVaR, Sharpe, Sortino)
- Alerts and monitoring via Prometheus

**Implementation:**

- backend/api/routers/risk.py
- backend/services/risk_dashboard.py
- frontend/analytics.html
- frontend/analytics-advanced.html

---

## 7. Live Trading

**Functional requirements:**

- WebSocket connection to Bybit V5 API
- Order placement, modification, cancellation
- Position tracking and PL
- Strategy execution

**Implementation:**

- backend/services/live_trading/bybit_websocket.py (756 lines)
- backend/services/live_trading/order_executor.py (848 lines)
- backend/services/live_trading/position_manager.py (681 lines)
- backend/services/live_trading/strategy_runner.py (848 lines)
- backend/api/routers/live_trading.py
- frontend/trading.html

---

## 8. Risk Management

**Functional requirements:**

- Position sizing (Kelly, fixed, volatility-adjusted)
- Stop-loss management (trailing, ATR-based)
- Exposure limits, drawdown controls
- Pre-trade validation

**Implementation:**

- backend/services/risk_management/ (5 modules)
- backend/api/routers/risk_management.py
- frontend/risk-management.html

---

## 9. Strategy Library

**Functional requirements:**

- Production-ready trading strategies
- Parameter specifications for optimization
- Strategy registration and discovery

**Strategies Implemented:**

- Momentum (RSI-based)
- Mean Reversion (Bollinger Bands)
- Breakout (Support/Resistance)
- Grid Trading
- DCA (Dollar Cost Averaging)
- Trend Following (EMA crossover)

**Implementation:**

- backend/services/strategies/ (6 strategy files plus base.py)
- backend/api/routers/strategy_library.py

---

## 10. AutoML Optimization

**Functional requirements:**

- Grid Search optimization
- Random Search optimization
- Bayesian optimization (Optuna/TPE)
- Walk-Forward validation

**Implementation:**

- backend/api/routers/optimizations.py (671 lines)
- backend/tasks/optimize_tasks.py (579 lines)
- backend/database/models/optimization.py

---

## 11. AI Strategy Generator

**Functional requirements:**

- Generate strategy code from natural language
- Pattern recognition prompts
- Code validation (static plus AI)
- Auto-backtesting

**Implementation:**

- backend/services/ai_strategy_generator.py (718 lines)
- backend/api/routers/ai_strategy_generator.py (533 lines)

---

## 12. Portfolio Management

**Functional requirements:**

- Multi-strategy orchestration
- Capital allocation
- Rebalancing

**Implementation:**

- Integrated with Risk Management modules
- frontend/portfolio.html

---

## Glossary

- AI: Artificial Intelligence agents integrated via DeepSeek V3.2 and Perplexity
- AutoML: Automated Machine Learning for strategy parameter optimization
- CRUD: Create, Read, Update, Delete operations
- DCA: Dollar Cost Averaging investment strategy
- VaR: Value at Risk metric
- CVaR: Conditional Value at Risk (Expected Shortfall)

---

Document updated based on Phase 5+ implementation (December 14, 2025)
