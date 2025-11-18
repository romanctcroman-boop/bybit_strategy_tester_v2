# План реализации ТЗ: Мультиагентная лаборатория

## 📋 Анализ текущего состояния

### ✅ Что УЖЕ реализовано:

#### 1. **MCP Server (Центральный оркестратор)** ✅
- **Статус**: Полностью реализован
- **Файл**: `mcp-server/server.py` (3978 lines)
- **Возможности**:
  - 51 AI-инструмент (Multi-Agent + Perplexity + Analysis + Utility)
  - FastMCP framework для MCP протокола
  - Multi-agent router (`multi_agent_router.py`)
  - LRU кэширование с TTL (Phase 3)
  - Streaming responses
  - Batch execution
  
**Соответствие ТЗ раздел 2.1**: ✅ 90%
- ✅ Многопоточная обработка (asyncio)
- ✅ Маршрутизация задач между агентами
- ✅ Приоритизация (task routing по типу)
- ❌ Нет очередей задач (Celery/Redis)
- ❌ Нет плагинов агентов (hardcoded)

#### 2. **Reasoning-агенты (Perplexity AI)** ✅
- **Статус**: Полностью интегрирован
- **Файл**: `multi_agent_router.py` → `SonarProClient`
- **Возможности**:
  - 27 Perplexity AI tools
  - Sonar Pro для reasoning
  - Search modes: web, academic, SEC
  - Citations и source tracking
  - Language preference support
  
**Соответствие ТЗ раздел 2.2**: ✅ 80%
- ✅ Генерация гипотез
- ✅ Объяснения reasoning
- ✅ AI-рефери (code review tools)
- ❌ Нет автоматической формализации бизнес-логики
- ❌ Нет интерпретации результатов бэктестов (Explainable AI)

#### 3. **Генерация кода (DeepSeek)** ✅
- **Статус**: Полностью интегрирован
- **Файл**: `multi_agent_router.py` → `DeepSeekClient`
- **Возможности**:
  - deepseek-coder model
  - Code generation
  - Refactoring
  - Batch operations
  - OpenAI-compatible API
  
**Соответствие ТЗ раздел 2.3**: ✅ 70%
- ✅ Генерация Python кода
- ✅ Retry с exponential backoff
- ❌ Нет автоматической коррекции по результатам тестов
- ❌ Нет автогенерации unit tests
- ❌ Нет документации и псевдокода

#### 4. **Pipeline выполнения** ✅
- **Статус**: Реализован базовый pipeline
- **Файл**: `multi_agent_router.py` → `execute_pipeline()`
- **Возможности**:
  - Multi-step execution
  - Context passing между шагами
  - Stop on error
  - Agent override
  
**Соответствие ТЗ раздел 3**: ✅ 60%
- ✅ Reasoning → codegen → review flow
- ❌ Нет ML-анализа в pipeline
- ❌ Нет sandbox execution
- ❌ Нет автоматических турниров стратегий

### ❌ Что ОТСУТСТВУЕТ:

#### 1. **ML-агенты / AutoML** ❌
**Статус**: НЕ РЕАЛИЗОВАНО
**Требуется по ТЗ раздел 2.4**:
- LSTM, CNN, RL модели
- Байесовская оптимизация (Optuna)
- Feature engineering
- Детекторы рыночных фаз (Вайкофф, волновой анализ)
- Tournament/Arena система для соревнований стратегий

**Критичность**: 🔴 ВЫСОКАЯ (core функционал)

#### 2. **Trader Psychology Agent** ❌
**Статус**: НЕ РЕАЛИЗОВАНО
**Требуется по ТЗ раздел 2.5**:
- Behavioral simulation (rabbit/wolf/speculator)
- Профили трейдеров (консерватор/агрессор)
- Психологические фильтры (стресс, паника)
- Адаптивность к форс-мажорам

**Критичность**: 🟡 СРЕДНЯЯ (enhancement)

#### 3. **Sandbox Execution** ❌
**Статус**: НЕ РЕАЛИЗОВАНО
**Требуется по ТЗ раздел 2.7**:
- Docker-контейнеры для изоляции
- Firejail/gVisor
- Resource limits (CPU/RAM/time)
- Audit trail

**Критичность**: 🔴 ВЫСОКАЯ (безопасность)

#### 4. **Knowledge Base (Reasoning Chains)** ❌
**Статус**: НЕ РЕАЛИЗОВАНО
**Требуется по ТЗ раздел 5**:
- trace-id для reasoning цепочек
- Chain-of-thought storage
- История изменений стратегий
- Auto-enrichment из прошлых итераций
- Full audit trail

**Критичность**: 🔴 ВЫСОКАЯ (explainability)

#### 5. **User Control Interface (WebUI)** ❌
**Статус**: ЧАСТИЧНО (есть frontend, но нет reasoning UI)
**Требуется по ТЗ раздел 2.6**:
- Просмотр reasoning логов
- Approve/reject/rollback actions
- Manual correction interface
- Feedback loop integration
- VS Code Extension (есть MCP, но нужен enhanced UI)

**Критичность**: 🟡 СРЕДНЯЯ (UX improvement)

#### 6. **Guardian Agents (Security)** ❌
**Статус**: НЕ РЕАЛИЗОВАНО
**Требуется по ТЗ раздел 5**:
- Агенты-брандмауэры
- Approval перед автоисполнением
- Risk assessment
- Automatic rollback

**Критичность**: 🟡 СРЕДНЯЯ (security enhancement)

---

## 🎯 Приоритизированный план реализации

### **Phase 1: MVP Enhancement (2-3 недели)**
**Цель**: Довести до минимально функционального состояния по ТЗ

#### 1.1 Knowledge Base System (5 дней)
- [ ] **Создать таблицы БД для reasoning chains**
  - `reasoning_traces`: id, request_id, task_type, agent, prompt, result, timestamp
  - `strategy_evolution`: strategy_id, version, parent_version, changes, reasoning_chain_id
  - `chain_of_thought`: trace_id, step_number, thought, decision, confidence
  
- [ ] **Реализовать logging middleware в MCP server**
  - Автоматическое логирование всех reasoning запросов
  - Связь между шагами pipeline (parent_id)
  - Timestamps и execution times
  
- [ ] **API для просмотра reasoning chains**
  - `GET /api/reasoning/trace/{request_id}`
  - `GET /api/reasoning/strategy/{strategy_id}/history`
  - `GET /api/reasoning/chains?filter=...`
  
**Файлы для создания**:
- `backend/database/models/reasoning_trace.py`
- `backend/services/reasoning_storage.py`
- `backend/api/routers/reasoning.py`

#### 1.2 Sandbox Execution System (7 дней)
- [ ] **Docker-based sandbox для стратегий**
  - Создать `Dockerfile.sandbox` с ограничениями
  - Network isolation (no internet access)
  - Resource limits (CPU: 2 cores, RAM: 4GB, time: 5min)
  
- [ ] **Sandbox executor service**
  - `backend/services/sandbox_executor.py`
  - Интеграция с docker-py
  - Monitoring и timeout handling
  - Cleanup после выполнения
  
- [ ] **Validation pipeline**
  - Проверка кода перед запуском (AST analysis)
  - Blacklist опасных операций (file I/O, network)
  - Security scoring (0-100)
  
**Файлы для создания**:
- `docker/Dockerfile.sandbox`
- `backend/services/sandbox_executor.py`
- `backend/core/code_validator.py`
- `scripts/test_sandbox.py`

#### 1.3 Enhanced Pipeline с ML Integration (3 дня)
- [ ] **Расширить `execute_pipeline()`**
  - Добавить шаг "ml-optimization"
  - Добавить шаг "sandbox-test"
  - Добавить шаг "reasoning-review"
  
- [ ] **Template pipelines**
  - `strategy_generation_pipeline.json`
  - `optimization_pipeline.json`
  - `tournament_pipeline.json`

**Файлы для обновления**:
- `mcp-server/multi_agent_router.py`
- `mcp-server/server.py` (добавить pipeline templates)

---

### **Phase 2: ML & AutoML (3-4 недели)**
**Цель**: Реализовать автоматическую оптимизацию и турниры

#### 2.1 AutoML Agent (10 дней)
- [ ] **Optuna integration для гиперпараметров**
  - `backend/ml/optuna_optimizer.py`
  - Objective functions для стратегий
  - Multi-objective optimization (Sharpe + Drawdown)
  
- [ ] **Feature Engineering Module**
  - `backend/ml/feature_engineer.py`
  - Technical indicators (TA-Lib)
  - Lag features, rolling statistics
  - Feature selection (mutual information, SHAP)
  
- [ ] **Market Regime Detection**
  - `backend/ml/market_regimes.py`
  - HMM для фаз рынка (trend/range/volatile)
  - Wyckoff method indicators
  - Adaptive strategy switching

**Файлы для создания**:
- `backend/ml/__init__.py`
- `backend/ml/optuna_optimizer.py`
- `backend/ml/feature_engineer.py`
- `backend/ml/market_regimes.py`
- `backend/ml/rl_agent.py` (опционально)

#### 2.2 Strategy Tournament System (5 дней)
- [ ] **Arena для соревнований стратегий**
  - `backend/services/strategy_arena.py`
  - Round-robin tournament
  - Scoring system (weighted metrics)
  - Automatic promotion/demotion
  
- [ ] **Batch backtesting**
  - Параллельный запуск стратегий
  - Multiprocessing pool
  - Result aggregation
  
**Файлы для создания**:
- `backend/services/strategy_arena.py`
- `backend/tasks/tournament_tasks.py`

---

### **Phase 3: Behavioral Testing (2 недели)**
**Цель**: Trader Psychology Agent

#### 3.1 Trader Profiles (7 дней)
- [ ] **Создать профили трейдеров**
  - `TraderProfile` class with risk preferences
  - Decision-making logic (enter/exit/hold)
  - Emotional states (fear/greed/neutral)
  
- [ ] **Behavioral simulator**
  - `backend/simulation/trader_psychology.py`
  - Stress scenarios (flash crash, pump, dump)
  - Risk tolerance curves
  - Panic exit triggers

**Файлы для создания**:
- `backend/simulation/__init__.py`
- `backend/simulation/trader_psychology.py`
- `backend/simulation/profiles.py`
- `tests/test_trader_psychology.py`

#### 3.2 Integration в Backtest (3 дня)
- [ ] **Расширить backtest engine**
  - Добавить `trader_profile` параметр
  - Simulate emotion-based decisions
  - Log behavioral events
  
**Файлы для обновления**:
- `backend/core/backtest_engine.py`
- `backend/core/vectorized_backtest.py`

---

### **Phase 4: User Control & Monitoring (2 недели)**
**Цель**: Интерактивность и прозрачность

#### 4.1 Reasoning UI (WebUI) (7 дней)
- [ ] **Frontend компоненты**
  - `ReasoningViewer.tsx` (просмотр chains)
  - `PipelineDebugger.tsx` (step-by-step analysis)
  - `StrategyEvolution.tsx` (timeline view)
  - `ApprovalPanel.tsx` (approve/reject/rollback)
  
- [ ] **Backend API endpoints**
  - `POST /api/reasoning/feedback` (user comments)
  - `POST /api/strategy/approve/{id}`
  - `POST /api/strategy/rollback/{id}`
  
**Файлы для создания**:
- `frontend/src/pages/ReasoningLab.tsx`
- `frontend/src/components/Reasoning/ReasoningViewer.tsx`
- `frontend/src/components/Reasoning/PipelineDebugger.tsx`
- `backend/api/routers/reasoning.py` (expand)

#### 4.2 Monitoring & Alerts (3 дня)
- [ ] **Prometheus metrics**
  - Strategy success rate
  - Agent response times
  - Pipeline failure rates
  
- [ ] **Alert system**
  - Email/Telegram notifications
  - Threshold-based alerts
  - Anomaly detection

**Файлы для создания**:
- `backend/monitoring/metrics.py`
- `backend/monitoring/alerts.py`
- `docker-compose.monitoring.yml`

---

### **Phase 5: Guardian Agents & Security (1 неделя)**
**Цель**: Безопасность автоматизации

#### 5.1 Guardian Agent (5 дней)
- [ ] **Risk assessment module**
  - `backend/security/risk_assessor.py`
  - Analyze generated code for risks
  - Analyze strategy parameters (leverage, position size)
  - Auto-approval threshold (risk score < 30)
  
- [ ] **Approval workflow**
  - Automatic for low-risk (< 30 score)
  - Manual review for medium-risk (30-70)
  - Auto-reject for high-risk (> 70)

**Файлы для создания**:
- `backend/security/risk_assessor.py`
- `backend/security/guardian_agent.py`

---

## 📊 Метрики успеха (по ТЗ раздел 6)

### Текущие метрики:
- ✅ MCP Server: 51 tools, Grade A+ (95/100)
- ✅ Multi-agent routing: Copilot + DeepSeek + Sonar Pro
- ✅ Backtest engine: Vectorized, MTF support
- ✅ Tests: 28/28 passing

### Целевые метрики после реализации ТЗ:
- **% автоматических успешных стратегий**: Target > 60%
- **Доля стратегий, прошедших full pipeline**: Target > 80%
- **Среднее время цикла "гипотеза→deploy"**: Target < 30 минут
- **Глубина reasoning**: Target > 5 steps в chain
- **Adaptive performance**: Test на 3+ market regimes

---

## 🚀 Quick Wins (можно начать сразу)

### Quick Win #1: Knowledge Base MVP (1 день)
**Цель**: Начать логировать reasoning chains прямо сейчас

```bash
# 1. Создать таблицу
alembic revision --autogenerate -m "Add reasoning_traces table"
alembic upgrade head

# 2. Добавить logging в MCP server
# Файл: mcp-server/server.py
# Добавить decorator для автоматического логирования
```

### Quick Win #2: Simple Sandbox (1 день)
**Цель**: Базовая изоляция для генерированного кода

```bash
# 1. Создать Docker image
docker build -f docker/Dockerfile.sandbox -t bybit-sandbox .

# 2. Test sandbox
python scripts/test_sandbox.py
```

### Quick Win #3: Tournament MVP (2 дня)
**Цель**: Запустить первый турнир из 5 стратегий

```python
# backend/services/strategy_arena.py (minimal version)
class StrategyArena:
    def run_tournament(self, strategies: List[Strategy]):
        results = []
        for strategy in strategies:
            result = run_backtest(strategy)
            results.append(result)
        return sorted(results, key=lambda x: x['sharpe_ratio'])
```

---

## 📁 Новые файлы для создания

### Backend:
```
backend/
├── ml/
│   ├── __init__.py
│   ├── optuna_optimizer.py
│   ├── feature_engineer.py
│   ├── market_regimes.py
│   └── rl_agent.py (optional)
├── simulation/
│   ├── __init__.py
│   ├── trader_psychology.py
│   └── profiles.py
├── security/
│   ├── risk_assessor.py
│   └── guardian_agent.py
├── monitoring/
│   ├── metrics.py
│   └── alerts.py
├── database/models/
│   └── reasoning_trace.py
├── services/
│   ├── reasoning_storage.py
│   ├── sandbox_executor.py
│   └── strategy_arena.py
└── api/routers/
    └── reasoning.py
```

### Frontend:
```
frontend/src/
├── pages/
│   └── ReasoningLab.tsx
└── components/Reasoning/
    ├── ReasoningViewer.tsx
    ├── PipelineDebugger.tsx
    ├── StrategyEvolution.tsx
    └── ApprovalPanel.tsx
```

### Docker:
```
docker/
├── Dockerfile.sandbox
└── docker-compose.monitoring.yml
```

### Scripts:
```
scripts/
├── test_sandbox.py
├── run_tournament.py
└── export_reasoning_chains.py
```

---

## 🔄 Итерационный подход (по ТЗ раздел 7)

**Рекомендация из ТЗ**:
> "Стартовать с минимально жизнеспособного pipeline (reasoning→codegen→test→ручной review), расширять блоки по спринтам."

### Спринт 1 (2 недели): Foundation
- Knowledge Base MVP
- Sandbox MVP
- Enhanced Pipeline

### Спринт 2 (3 недели): ML Core
- AutoML Agent
- Market Regime Detection
- Tournament System

### Спринт 3 (2 недели): Behavioral
- Trader Psychology
- Stress scenarios
- Backtest integration

### Спринт 4 (2 недели): UX
- Reasoning UI
- Approval workflow
- Monitoring dashboard

### Спринт 5 (1 неделя): Security
- Guardian Agent
- Risk assessment
- Auto-approval logic

---

## ✅ Следующие шаги (ACTION ITEMS)

1. **Создать Knowledge Base структуру** (начать с Quick Win #1)
2. **Создать Sandbox executor** (начать с Quick Win #2)
3. **Реализовать AutoML optimizer** (Optuna integration)
4. **Создать Trader Psychology profiles**
5. **Построить Reasoning UI в frontend**

---

**Статус**: План готов к исполнению
**Общая оценка работ**: 10-12 недель full-time development
**MVP оценка**: 3-4 недели (Phase 1)
