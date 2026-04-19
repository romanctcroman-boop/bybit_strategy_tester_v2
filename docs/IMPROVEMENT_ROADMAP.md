# Roadmap доработок Bybit Strategy Tester v2

**Дата:** 2026-02-19  
**Версия:** 2.12  
**Приоритизация:** P0 (критично) → P1 (важно) → P2 (желательно) → P3 (опционально)

---

## 🔴 P0 - Критичные (Security & Stability)

### 1. **Безопасность API ключей**
**Проблема:** API ключи в `.cursor/mcp.json` хранятся в открытом виде
```json
"DEEPSEEK_API_KEY": "sk-1630fbba63c64f88952c16ad33337242"
```

**Решение:**
- [ ] Переместить все ключи в `.env`
- [ ] Использовать `${env:DEEPSEEK_API_KEY}` в конфигах
- [ ] Добавить `.cursor/mcp.json` в `.gitignore`
- [ ] Создать `.cursor/mcp.json.example` без ключей

**Файлы:** `.cursor/mcp.json`, `.agent/mcp.json`

### 2. **Валидация startup конфигурации**
**Проблема:** Отсутствует централизованная проверка при запуске

**Решение:**
- [x] Создан `backend/agents/config_validator.py`
- [x] Создан `backend/agents/mcp_config.py`
- [ ] Интегрировать в `backend/api/app.py` startup
- [ ] Добавить fail-fast при отсутствии критичных ключей

**Код:**
```python
# backend/api/app.py
from backend.agents.config_validator import validate_startup_config

@app.on_event("startup")
async def startup_validation():
    errors = validate_startup_config()
    if errors:
        logger.critical("Startup validation failed!")
        raise RuntimeError(f"Config errors: {errors}")
```

### 3. **Error handling в MCP bridge**
**Проблема:** Timeout errors не логируются детально

**Решение:**
- [ ] Добавить structured logging для всех MCP ошибок
- [ ] Сохранять failed requests в DLQ (Dead Letter Queue)
- [ ] Алерты при превышении error rate

**Файл:** `backend/mcp/mcp_integration.py`

---

## 🟡 P1 - Важные (Performance & UX)

### 4. **Оптимизация startup времени**
**Текущее:** ~12-15 секунд (с FAST_DEV_MODE)  
**Цель:** <5 секунд

**Решение:**
- [ ] Lazy loading для тяжелых модулей (vectorbt, torch)
- [ ] Параллельный запуск сервисов
- [ ] Кэширование compiled Numba functions
- [ ] Отложенная инициализация MCP серверов

**Файлы:** `start_all.ps1`, `backend/api/app.py`

### 5. **Bar Magnifier автоматизация**
**Проблема:** Требует ручной загрузки 1m данных

**Решение:**
- [ ] Автоматическая загрузка 1m данных при включении Bar Magnifier
- [ ] Прогресс-бар в UI
- [ ] Кэширование в SQLite
- [ ] Фоновая синхронизация

**Файлы:** `backend/backtesting/intrabar_engine.py`, `frontend/js/pages/strategy_builder.js`

### 6. **Strategy Builder: Template система**
**Проблема:** Только 1 шаблон (RSI)

**Решение:**
- [ ] Добавить шаблоны: MACD, Bollinger, EMA Cross, Grid, DCA
- [ ] Import/Export стратегий (JSON)
- [ ] Marketplace для шаблонов
- [ ] Версионирование стратегий

**Файлы:** `frontend/js/data/templates.js`, `backend/api/routers/strategy_builder.py`

### 7. **Metrics Dashboard улучшения**
**Проблема:** 166 метрик сложно анализировать

**Решение:**
- [ ] Группировка метрик по категориям (Performance/Risk/Trades)
- [ ] Сравнение с бенчмарками (Buy & Hold, S&P500)
- [ ] Heatmap для корреляций метрик
- [ ] Export в Excel/CSV

**Файл:** `frontend/backtest-results.html`

### 8. **Walk-Forward визуализация**
**Проблема:** Результаты только в JSON

**Решение:**
- [ ] График equity по периодам (train/test)
- [ ] Таблица метрик по окнам
- [ ] Stability score (разброс метрик)
- [ ] Overfitting detection

**Файл:** `backend/backtesting/walk_forward.py`

---

## 🟢 P2 - Желательные (Features)

### 9. **Multi-symbol backtesting**
**Описание:** Портфельное тестирование

**Решение:**
- [ ] Поддержка списка символов в BacktestConfig
- [ ] Корреляционный анализ
- [ ] Portfolio rebalancing
- [ ] Risk parity allocation

**Файлы:** `backend/backtesting/portfolio_strategy.py` (существует, доработать)

### 10. **Genetic Algorithm оптимизация**
**Описание:** Альтернатива Grid Search

**Решение:**
- [ ] DEAP integration
- [ ] Multi-objective optimization (Sharpe + Win Rate)
- [ ] Adaptive mutation rates
- [ ] Elitism + Tournament selection

**Новый файл:** `backend/backtesting/genetic_optimizer.py`

### 11. **Live Trading интеграция**
**Описание:** Paper trading и real execution

**Решение:**
- [ ] Paper trading mode (симуляция на реальных данных)
- [ ] Bybit WebSocket для live prices
- [ ] Order execution через Bybit API
- [ ] Risk limits (max loss per day)

**Файлы:** `backend/trading/` (частично существует)

### 12. **Strategy Builder: Advanced блоки**
**Описание:** Расширение библиотеки блоков

**Решение:**
- [ ] Machine Learning блоки (LSTM predictions)
- [ ] Sentiment analysis (Twitter/Reddit)
- [ ] Order Flow Imbalance
- [ ] Volume Profile
- [ ] Market Microstructure

**Файл:** `frontend/js/data/block_library.js`

### 13. **Backtesting Reports**
**Описание:** Автоматические отчеты

**Решение:**
- [ ] PDF generation (ReportLab)
- [ ] HTML email reports
- [ ] Scheduled backtests (Celery)
- [ ] Slack/Telegram notifications

**Новый файл:** `backend/reports/generator.py`

---

## 🔵 P3 - Опциональные (Nice to Have)

### 14. **AI-powered strategy suggestions**
**Описание:** DeepSeek анализирует результаты и предлагает улучшения

**Решение:**
- [ ] Анализ equity curve через DeepSeek
- [ ] Предложения по параметрам
- [ ] Обнаружение паттернов в убыточных сделках
- [ ] Автоматическая генерация стратегий

**Интеграция:** `backend/agents/` + MCP

### 15. **Social Trading**
**Описание:** Sharing стратегий

**Решение:**
- [ ] Public/Private стратегии
- [ ] Leaderboard по метрикам
- [ ] Copy trading
- [ ] Rating system

**Новые файлы:** `backend/social/`, `frontend/marketplace.html`

### 16. **Mobile App**
**Описание:** iOS/Android приложение

**Решение:**
- [ ] React Native / Flutter
- [ ] Push notifications для алертов
- [ ] Simplified UI для мобильных
- [ ] Offline mode

**Новая директория:** `mobile/`

### 17. **Blockchain integration**
**Описание:** On-chain стратегии

**Решение:**
- [ ] DEX integration (Uniswap, PancakeSwap)
- [ ] MEV strategies
- [ ] Gas optimization
- [ ] Smart contract backtesting

**Новые файлы:** `backend/blockchain/`

---

## 📋 Быстрые победы (Quick Wins)

### Можно сделать за 1-2 часа:

1. **✅ MCP конфигурация** (P0)
   - Переместить ключи в `.env`
   - Обновить `.cursor/mcp.json`

2. **✅ Startup validation** (P0)
   - Интегрировать `validate_startup_config()` в app.py

3. **📊 Metrics grouping** (P1)
   - CSS accordion для категорий метрик
   - Collapse/Expand all

4. **📈 Export to CSV** (P1)
   - Кнопка "Export" в backtest-results.html
   - Pandas to_csv()

5. **🎨 UI polish** (P2)
   - Dark mode toggle
   - Tooltips для метрик
   - Loading spinners

---

## 🎯 Рекомендуемый план (Sprint 1-3)

### Sprint 1 (1 неделя) - Security & Stability
- [ ] P0.1: Безопасность API ключей
- [ ] P0.2: Startup validation
- [ ] P0.3: MCP error handling
- [ ] Quick Win: Metrics grouping

### Sprint 2 (1 неделя) - Performance
- [ ] P1.4: Startup optimization
- [ ] P1.5: Bar Magnifier automation
- [ ] P1.7: Metrics Dashboard
- [ ] Quick Win: Export to CSV

### Sprint 3 (2 недели) - Features
- [ ] P1.6: Strategy Builder templates
- [ ] P1.8: Walk-Forward visualization
- [ ] P2.9: Multi-symbol backtesting (базовая версия)
- [ ] Quick Win: Dark mode

---

## 📊 Метрики успеха

### Performance
- Startup time: <5s (сейчас ~12s)
- Backtest speed: >1000 trades/sec (Numba)
- API response time: <100ms p95

### Quality
- Test coverage: >80% (сейчас ~70%)
- Zero critical security issues
- <5 bugs per release

### UX
- Time to first backtest: <2 min (new user)
- Strategy Builder adoption: >50% users
- User satisfaction: >4.5/5

---

## 🔧 Технический долг

### Рефакторинг
1. **Consolidate engines** - Унифицировать интерфейсы всех движков
2. **Type hints** - Добавить везде (сейчас ~60% покрытие)
3. **Async/await** - Конвертировать sync код в async где возможно
4. **Tests** - Увеличить coverage до 90%

### Документация
1. **API docs** - OpenAPI/Swagger полное описание
2. **Architecture diagrams** - Mermaid диаграммы
3. **Video tutorials** - YouTube канал
4. **Changelog** - Автоматическая генерация

---

## 💡 Инновационные идеи

### AI/ML
- **AutoML** - Автоматический подбор стратегий
- **Reinforcement Learning** - RL-агенты для трейдинга
- **Sentiment Analysis** - NLP для новостей
- **Anomaly Detection** - Обнаружение манипуляций рынком

### Blockchain
- **NFT Strategies** - Торговля NFT
- **DeFi Yield** - Оптимизация yield farming
- **MEV** - Maximal Extractable Value стратегии

### Social
- **Copy Trading** - Автоматическое копирование сделок
- **Strategy Marketplace** - Покупка/продажа стратегий
- **Competitions** - Trading competitions с призами

---

## ✅ Заключение

**Приоритет на ближайший месяц:**
1. 🔴 P0: Security (API keys, validation)
2. 🟡 P1: Performance (startup, Bar Magnifier)
3. 🟡 P1: UX (templates, metrics dashboard)

**Долгосрочная цель:**
Превратить проект в **полноценную платформу** для алготрейдинга с AI-ассистентом, social features и live trading.

**Оценка текущего состояния:** 9.5/10  
**Потенциал после доработок:** 10/10 🚀
