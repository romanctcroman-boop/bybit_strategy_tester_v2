# 📈 P1-11: Live Trading Integration — План

**Дата:** 2026-02-26
**Статус:** ⏳ В работе
**Оценка:** 5 дней (40 часов)

---

## 🎯 Цель

Реализовать live trading интеграцию:
- WebSocket подключение к Bybit
- Real-time data streaming
- Order execution (market/limit)
- Paper trading mode
- Risk limits
- Position tracking

---

## 🏗️ Архитектура

```
backend/trading/
├── __init__.py
├── live_trading_engine.py    # LiveTradingEngine
├── websocket_client.py       # BybitWebSocketClient
├── order_executor.py         # OrderExecutor
├── paper_trading.py          # PaperTradingEngine
├── risk_limits.py            # RiskLimits
├── position_tracker.py       # PositionTracker
└── tests/
    ├── test_websocket.py
    ├── test_orders.py
    ├── test_paper_trading.py
    └── test_risk_limits.py
```

---

## 📝 План работ

### День 1: WebSocket (8 часов)
- [ ] BybitWebSocketClient
- [ ] Real-time data stream
- [ ] Reconnection logic
- [ ] Heartbeat/ping

### День 2: Order Execution (8 часов)
- [ ] OrderExecutor
- [ ] Market/Limit orders
- [ ] Order status tracking
- [ ] Fill handling

### День 3: Paper Trading (8 часов)
- [ ] PaperTradingEngine
- [ ] Simulation logic
- [ ] Performance tracking

### День 4: Risk Management (8 часов)
- [ ] RiskLimits
- [ ] Max loss per day
- [ ] Position limits
- [ ] Circuit breakers

### День 5: API & Tests (8 часов)
- [ ] API endpoints
- [ ] Тесты
- [ ] Документация

---

## 🔧 Зависимости

### requirements-live.txt

```txt
# WebSocket
websockets>=12.0
aiohttp>=3.9.0

# Trading
ccxt>=4.0.0
```

---

## 📊 Ожидаемые результаты

### WebSocket

**Возможности:**
- Real-time kline/candlestick data
- Real-time trades
- Real-time ticker
- Order book updates

**API:**
- `WS /ws/live/kline/{symbol}/{timeframe}`
- `WS /ws/live/trades/{symbol}`
- `WS /ws/live/ticker/{symbol}`

### Order Execution

**Возможности:**
- Market orders
- Limit orders
- Stop-loss/Take-profit
- Order cancellation
- Order status

**API:**
- `POST /api/v1/live/order`
- `GET /api/v1/live/order/{id}`
- `DELETE /api/v1/live/order/{id}`
- `GET /api/v1/live/positions`

### Paper Trading

**Возможности:**
- Simulation на real-time данных
- Virtual balance
- Performance metrics
- Trade history

---

## ✅ Критерии приёмки

- [ ] WebSocket подключение работает
- [ ] Real-time data streaming
- [ ] Order execution реализован
- [ ] Paper trading mode работает
- [ ] Risk limits enforce
- [ ] API endpoints созданы
- [ ] Тесты проходят (>80%)

---

*План создан: 2026-02-26*
