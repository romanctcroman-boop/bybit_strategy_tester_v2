# 📊 P1-9 + P1-11 + P2-5: Комплексная реализация

**Дата:** 2026-02-26
**Задачи:**
- P1-9: Multi-symbol backtesting (3 дня)
- P1-11: Live Trading интеграция (5 дней)
- P2-5: Backtesting Reports PDF (3 дня)

**Общая оценка:** 11 дней (~88 часов)
**Статус:** ⏳ В работе

---

## 🎯 Цель

Реализовать три взаимосвязанные функции:

### P1-9: Multi-symbol backtesting
- Портфельное тестирование стратегий
- Корреляционный анализ между символами
- Portfolio rebalancing стратегии
- Risk parity allocation

### P1-11: Live Trading интеграция
- Paper trading mode (симуляция на реальных данных)
- Bybit WebSocket для live prices
- Order execution через Bybit API
- Risk limits (max loss per day)

### P2-5: Backtesting Reports PDF
- Автоматическая генерация PDF отчётов
- 166 метрик с графиками
- Email рассылка отчётов
- Scheduled backtests (Celery)

---

## 🏗️ Архитектура

### P1-9: Multi-symbol

```
backend/backtesting/portfolio/
├── __init__.py
├── portfolio_engine.py       # PortfolioBacktestEngine
├── correlation_analysis.py   # Корреляции, коинтеграция
├── risk_parity.py            # Risk parity allocation
├── rebalancing.py            # Rebalancing стратегии
└── tests/
    ├── test_portfolio.py
    ├── test_correlation.py
    └── test_risk_parity.py
```

### P1-11: Live Trading

```
backend/trading/
├── __init__.py
├── live_trading_engine.py    # LiveTradingEngine
├── websocket_client.py       # Bybit WebSocket
├── order_executor.py         # Order execution
├── paper_trading.py          # Paper trading simulator
├── risk_limits.py            # Risk management
└── tests/
    ├── test_websocket.py
    ├── test_orders.py
    └── test_paper_trading.py
```

### P2-5: Reports

```
backend/reports/
├── __init__.py
├── generator.py              # ReportGenerator
├── pdf_generator.py          # ReportLab integration
├── email_sender.py           # Email reports
├── templates/
│   ├── backtest_report.html
│   └── optimization_report.html
└── tests/
    ├── test_generator.py
    └── test_pdf.py
```

---

## 📝 План работ

### Этап 1: Multi-symbol backtesting (3 дня)

**День 1: Portfolio Engine**
- [ ] PortfolioBacktestEngine
- [ ] Multi-symbol data loading
- [ ] Equity curve aggregation

**День 2: Correlation & Risk**
- [ ] CorrelationAnalysis
- [ ] RiskParityAllocator
- [ ] Diversification ratio

**День 3: API & Tests**
- [ ] API endpoints
- [ ] Тесты
- [ ] Документация

### Этап 2: Live Trading (5 дней)

**День 4: WebSocket**
- [ ] BybitWebSocketClient
- [ ] Real-time data stream
- [ ] Reconnection logic

**День 5: Order Execution**
- [ ] OrderExecutor
- [ ] Market/Limit orders
- [ ] Order status tracking

**День 6: Paper Trading**
- [ ] PaperTradingEngine
- [ ] Simulation logic
- [ ] Performance tracking

**День 7: Risk Management**
- [ ] RiskLimits
- [ ] Max loss per day
- [ ] Position limits

**День 8: Integration & Tests**
- [ ] API endpoints
- [ ] Тесты
- [ ] Документация

### Этап 3: Reports PDF (3 дня)

**День 9: Generator**
- [ ] ReportGenerator
- [ ] HTML templates
- [ ] Metrics visualization

**День 10: PDF & Email**
- [ ] PDF generation (ReportLab)
- [ ] Email integration
- [ ] Scheduled reports

**День 11: Tests & Docs**
- [ ] Тесты
- [ ] Документация
- [ ] Примеры

---

## 🔧 Зависимости

### requirements-reports.txt

```txt
# PDF Generation
reportlab>=4.0.0
weasyprint>=59.0

# Email
aiosmtplib>=3.0.0
email-validator>=2.1.0

# Scheduling
celery>=5.3.0
redis>=5.0.0
```

### requirements-live.txt

```txt
# WebSocket
websockets>=12.0
aiohttp>=3.9.0

# Live trading
ccxt>=4.0.0  # Crypto exchange library
```

---

## 📊 Ожидаемые результаты

### P1-9: Multi-symbol

**Метрики:**
- Portfolio Sharpe ratio
- Portfolio Sortino ratio
- Diversification ratio
- Correlation matrix
- Efficient frontier

**API:**
- `POST /api/v1/portfolio/optimize`
- `GET /api/v1/portfolio/correlation`
- `GET /api/v1/portfolio/efficient-frontier`

### P1-11: Live Trading

**Возможности:**
- Real-time data streaming
- Market/Limit orders
- Paper trading mode
- Risk limits enforcement
- Position tracking

**API:**
- `POST /api/v1/live/order`
- `GET /api/v1/live/positions`
- `WS /ws/live`

### P2-5: Reports

**Функции:**
- PDF отчёты (166 метрик)
- Email рассылка
- Scheduled backtests
- HTML export

**API:**
- `POST /api/v1/reports/generate`
- `POST /api/v1/reports/email`
- `GET /api/v1/reports/{id}`

---

## ✅ Критерии приёмки

### P1-9

- [ ] PortfolioBacktestEngine работает
- [ ] Correlation analysis реализован
- [ ] Risk parity allocation работает
- [ ] API endpoints созданы
- [ ] Тесты проходят (>80%)

### P1-11

- [ ] WebSocket подключение работает
- [ ] Order execution реализован
- [ ] Paper trading mode работает
- [ ] Risk limits enforce
- [ ] Тесты проходят (>80%)

### P2-5

- [ ] PDF generation работает
- [ ] Email integration работает
- [ ] Scheduled reports работают
- [ ] Тесты проходят (>80%)

---

*План создан: 2026-02-26*
*Начало реализации: День 1 — Portfolio Engine*
