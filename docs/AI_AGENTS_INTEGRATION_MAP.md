# AI Agents — Карта интеграции с проектом

> **Создан:** 2026-03-21
> **Цель:** Зафиксировать текущее состояние интеграции AI агентов, что они видят, что не видят, и что нужно улучшить.

---

## 1. Архитектура агентного пайплайна

```
Пользователь → POST /api/ai/generate-strategy
                        ↓
           trading_strategy_graph.py (LangGraph)
                        ↓
    ┌───────────────────────────────────────────┐
    │  analyze_market → debate → generate       │
    │      ↓                                    │
    │  parse → select → build_graph → backtest  │
    │      ↓ (fail, iter<3)                     │
    │  refine_strategy → generate (loop)        │
    │      ↓ (pass)                             │
    │  optimize → ml_validation → memory_update │
    │      ↓                                    │
    │  report                                   │
    └───────────────────────────────────────────┘
```

**Агенты:** DeepSeek · Qwen · Perplexity (direct API, MCP disabled)
**Вход в LLM:** UnifiedAgentInterface → HTTP POST → LLM API
**Контекст передаётся:** только через строку промпта (без tool calls в production)

---

## 2. Что агенты ВИДЯТ ✅

### 2.1 Рыночный контекст (MarketContextBuilder)
Строится автоматически перед запросом к агенту:

| Данные | Откуда |
|--------|--------|
| Текущая цена, period high/low, change% | DataService |
| Режим рынка: trending_up/down, ranging, volatile | ATR + price momentum |
| Тренд: bullish/bearish/neutral + сила (strong/moderate/weak) | MA slope |
| Волатильность ATR%, исторический vol% | ATR |
| Объём: increasing/decreasing/stable | Volume MA |
| Уровни поддержки/сопротивления (топ-3) | Lookback peaks |

### 2.2 Платформенные ограничения (templates.py)
Агент явно получает:

```
- commission: 0.07% (display), real: 0.0007
- initial_capital: $10,000
- leverage: настраивается
- timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1D
- position type: long/short/both
- pyramiding: default 1
```

### 2.3 Индикаторы (templates.py, строки 39–62)
40+ индикаторов с документацией параметров. Примеры:

| Индикатор | Что видит агент |
|-----------|----------------|
| RSI | 3 режима: RANGE / CROSS / LEGACY, параметры: period, oversold, overbought |
| MACD | fast, slow, signal, combinable modes |
| SuperTrend | period, multiplier, entry/exit ports |
| Stochastic, QQE, StochRSI | полные параметры |
| ATR, Bollinger, Keltner, Donchian | period + деривативы |
| Divergence | → возвращает long/short + bullish/bearish |

### 2.4 Примеры стратегий (few-shot)
5 примеров в JSON-формате, **выбираются динамически по режиму**:
- trending → MACD
- ranging → Stochastic
- volatile → RSI
- bull/bear → SuperTrend / QQE momentum

### 2.5 Результаты бэктеста (через RefinementNode)
Когда стратегия не прошла:

```
=== REFINEMENT FEEDBACK (iteration N/3) ===
Failed: too few trades (2 < 5 required).
Metrics: trades=2, Sharpe=-0.15, MaxDD=18.5%, Return=0.8%
Suggestion: Use more sensitive signal conditions...
```

### 2.6 ML-валидация (через MLValidationNode)
В agent memory сохраняются предупреждения:
- `[OVERFIT] IS/OOS Sharpe gap=0.8`
- `[REGIME] strategy performs poorly in regimes: [volatile]`
- `[STABILITY] Sharpe drops below 0 when period perturbed ±20%`

---

## 3. Что агенты НЕ ВИДЯТ ❌

### 3.1 Внутренности StrategyBuilderAdapter

**Проблема:** Агент генерирует JSON-граф, адаптер тихо интерпретирует его. Агент не знает:

| Что происходит в адаптере | Агент в курсе? |
|--------------------------|---------------|
| Port aliases: `"long"` ↔ `"bullish"`, `"short"` ↔ `"bearish"` | ❌ Нет |
| Параметры зажаты в [1, 500] (`_clamp_period`) | ❌ Нет |
| `"Chart"` таймфрейм → резолвится в main_interval | ✅ Частично (в docs) |
| Топологическая сортировка блоков | ❌ Нет |
| Какие output ports у каждого блока | ❌ Частично |

**Последствие:** Агент пишет `"fromPort": "signal"` вместо `"fromPort": "long"` → 0 сделок → агент думает, что стратегия плохая.

### 3.2 Детали выполнения бэктеста

| Что происходит в движке | Агент получает? |
|------------------------|----------------|
| Отдельные сделки (вход, выход, PnL, длительность) | ❌ Нет |
| Equity curve | ❌ Нет |
| Breakdown комиссии и слиппажа | ❌ Нет |
| Причина 0 сделок: direction filter, SL/TP, bar magnifier | ❌ Нет |
| `[DIRECTION_MISMATCH]` warning из движка | ❌ Нет |
| `[NO_TRADES]` warning | ❌ Нет |
| DCA re-averaging поведение | ❌ Нет |

### 3.3 Ошибки валидации схемы

Когда ResponseParser отвергает JSON агента:
- Агент получает только: `"invalid strategy format"`
- НЕ получает: `"oversold=80 > overbought=30 — invalid range"` или `"unknown port name: 'go_long'"`

### 3.4 Оптимизация (чёрный ящик)

OptimizationNode выполняется **офлайн, без участия агентов**:
- 50 Optuna TPE trials
- Scoring: Sharpe 50% + Sortino 30% + ProfitFactor 20%
- Агенты не участвуют, не могут предлагать диапазоны параметров
- Получают только итог: `best_sharpe=1.2, best_params={...}`

### 3.5 Архитектурные знания о проекте

| Документ/контекст | Загружается в агента? |
|-------------------|----------------------|
| CLAUDE.md (главный) | ❌ Только для Claude Code |
| memory-bank/*.md | ❌ Только для Claude Code |
| docs/ документация | ❌ Только по явному tool call |
| backend/backtesting/CLAUDE.md | ❌ |
| Signal routing логика | ❌ |

---

## 4. Инструменты агентов (текущее состояние)

```python
# Доступные MCP tools (эмулированы локально, MCP disabled в prod):
mcp_read_project_file(path)      # Чтение файла (защита от path traversal)
mcp_list_project_structure(dir)  # Листинг директории
mcp_analyze_code_quality(path)   # Анализ качества кода

# НЕ ДОСТУПНО агентам:
- run_backtest()       # Нет прямого вызова
- get_metrics()        # Нет
- optimize()           # Нет
- query_memory()       # Нет семантического поиска
- validate_graph()     # Нет
```

**Реальность:** В production агенты вызывают инструменты **крайне редко** — основной поток через state passing в LangGraph, не через tool calls.

---

## 5. Память агентов

**Бэкенд:** SQLite (`data/agent_memory.db`) или JSON файлы

**Что сохраняется:**
- История сообщений (role, content, timestamp)
- ML validation warnings (overfitting, regime, stability)
- Оптимизированный граф в MemoryUpdateNode

**Что НЕ сохраняется:**
- ❌ Семантический поиск по прошлым стратегиям (vector store есть, но агенты его не запрашивают)
- ❌ Cross-conversation контекст (каждый запрос изолирован)
- ❌ Рейтинг агентов (AgentPerformanceTracker есть, ConsensusNode читает, но агенты не видят)

---

## 6. Специализация агентов

| Агент | Роль в системе |
|-------|----------------|
| **DeepSeek** | Expert system designer — технически сложные стратегии |
| **Qwen** | Conservative systematic trader — консервативные подходы |
| **Perplexity** | Research-oriented analyst — аналитика, обоснование |

Агенты **дебатируют** (DebateNode): каждый оценивает предложения других перед выбором лучшей стратегии (ConsensusNode).

---

## 7. Критические пробелы — приоритизированный список

### 🔴 ВЫСОКИЙ ПРИОРИТЕТ

**Пробел #1: Port alias blindness**
- Агент не знает, что `"long"` и `"bullish"` — одно и то же
- Нет документации output ports в подсказках
- **Фикс:** Добавить в `templates.py` секцию "PORT NAMES" с маппингом для каждого блока

**Пробел #2: Нет validation errors в refinement**
- Агент не знает почему стратегия невалидна
- **Фикс:** ResponseParser должен возвращать structured errors → RefinementNode → промпт

**Пробел #3: Direction trap невидима**
- Агент не знает, что `direction="long"` дропает все short сигналы
- **Фикс:** Добавить в refinement feedback `"[DIRECTION_MISMATCH] warning detected"`

### 🟡 СРЕДНИЙ ПРИОРИТЕТ

**Пробел #4: Слепота к деталям сделок**
- При < 10 сделок агент должен видеть entry/exit точки, чтобы понять проблему
- **Фикс:** RefinementNode передаёт `trades[:10]` при малом числе сделок

**Пробел #5: Оптимизация без участия агента**
- Агент не может предложить диапазоны параметров
- **Фикс:** Добавить в промпт секцию `"OPTIMIZATION HINTS"` перед OptimizationNode

**Пробел #6: Engine config непрозрачен**
- Агент не знает: `commission_on_margin=True`, `bar_magnifier=True`, `close_rule="ALL"`
- **Фикс:** Добавить engine_config summary в платформенные ограничения в templates.py

### 🟢 НИЗКИЙ ПРИОРИТЕТ

**Пробел #7: Нет semantic memory**
- Агент не может спросить "какие стратегии для BTCUSDT в trending работали раньше?"
- **Фикс:** ТЗ_ЭВОЛЮЦИЯ_ПАМЯТИ.md Phase 4 — BM25+vector hybrid search

**Пробел #8: Cross-conversation isolation**
- Каждый запрос с нуля
- **Фикс:** Session-level strategy cache в agent_memory.py

---

## 8. Схема information flow (полная)

```
User Request
    ↓
MarketContextBuilder
  price, regime, volatility, S/R levels
    ↓
templates.py → STRATEGY_GENERATION_TEMPLATE
  + indicators list (40+ с параметрами)
  + platform constraints (commission, capital, leverage)
  + few-shot examples (выбраны по режиму)
  + agent specialization role
    ↓
UnifiedAgentInterface → HTTP POST → LLM API
    ↓
LLM генерирует: strategy_graph JSON
    ↓
ResponseParser
  valid? → да → BuildGraphNode
  ❌ invalid? → агент получает только "invalid" (без деталей)
    ↓
StrategyBuilderAdapter
  (агент не видит что происходит здесь)
  - port alias resolution
  - period clamping [1, 500]
  - topological sort
  - indicator execution
    ↓
FallbackEngineV4
  (агент не видит что происходит здесь)
  - bar-by-bar simulation
  - commission=0.0007
  - SL/TP/bar magnifier
    ↓
BacktestResult
  trades=N, sharpe=X, maxdd=Y, return=Z
    ↓
RefinementNode (если failed)
  агент получает: summarized metrics + templated suggestions
  ❌ НЕ получает: individual trades, engine warnings, validation errors
    ↓
OptimizationNode (offline, 50 Optuna trials)
  агент не участвует
    ↓
MLValidationNode (offline)
  overfitting check, regime analysis, parameter stability
    ↓
MemoryUpdateNode → report
```

---

## 9. Файлы для изучения при работе с агентами

| Файл | Строк | Что важно |
|------|-------|-----------|
| `backend/agents/trading_strategy_graph.py` | 1657 | Весь LangGraph пайплайн |
| `backend/agents/prompts/templates.py` | ~300 | Все промпты, индикаторы, роли |
| `backend/agents/unified_agent_interface.py` | ~400 | HTTP клиент к LLM API |
| `backend/agents/prompts/response_parser.py` | ~200 | Парсинг JSON от агентов |
| `backend/agents/agent_memory.py` | ~300 | Memory backend |
| `backend/api/routers/ai_strategy_generator.py` | ~200 | Endpoint входа |

---

## 10. TODO для будущих улучшений

- [ ] **#1** `templates.py`: добавить секцию `PORT NAMES PER BLOCK TYPE` — маппинг output ports для каждого блока
- [ ] **#2** `response_parser.py`: возвращать structured validation errors (не просто "invalid")
- [ ] **#3** `RefinementNode`: передавать `warnings[]` из engine response (DIRECTION_MISMATCH, NO_TRADES)
- [ ] **#4** `RefinementNode`: при trades < 10 — добавлять `trades[:10]` в feedback
- [ ] **#5** `templates.py`: добавить engine_config в платформенные ограничения
- [ ] **#6** `OptimizationNode`: принимать hints от агента (parameter ranges)
- [ ] **#7** Semantic memory: ТЗ_ЭВОЛЮЦИЯ_ПАМЯТИ.md Phase 4
- [ ] **#8** Session-level strategy cache

> Эти улучшения превратят систему из **односторонней** (агент → движок → краткий ответ) в **диалоговую** (агент понимает что и почему не сработало на уровне движка).
