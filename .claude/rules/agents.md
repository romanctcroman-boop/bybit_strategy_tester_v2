---
paths:
  - "backend/agents/**/*.py"
  - "tests/backend/agents/**"
  - "tests/ai_agents/**"
---

# AI Agent System Rules

## Архитектура пайплайна (15 нод)
```
analyze_market → regime_classifier → [debate] → memory_recall
→ generate_strategies → parse → select_best → build_graph
→ backtest → backtest_analysis → [refine loop ≤3] → optimize
→ [wf_validation] → analysis_debate → ml_validation
→ [hitl] → memory_update → reflection → report
```

## Критические инварианты
- Pipeline timeout = 300s (`asyncio.wait_for`)
- Debate timeout = 150s (реальный debate 84–102s)
- WalkForward запускается ПОСЛЕ optimizer (использует `opt_result["best_sharpe"]`)
- WF проходит если `wf_sharpe/is_sharpe ≥ 0.5` ИЛИ `wf_sharpe ≥ 0.5` (абсолютный floor)
- `commission_rate = 0.0007` в TradingConfig (НЕ МЕНЯТЬ)

## Известные исправленные баги (не вводить повторно)
| Баг | Фикс | Расположение |
|-----|------|-------------|
| DIRECTION_MISMATCH ложное срабатывание | Использовать `sig_long`/`sig_short` (сигналы, НЕ сделки) | BacktestNode |
| WF до optimizer | Порядок: optimize → wf_validation | trading_strategy_graph.py |
| Debate timeout 90s | Поднят до 150s | DebateNode + AnalysisDebateNode |
| DeliberationResult wrong fields | `.decision`/`.confidence`/`.rounds` (НЕ `.consensus_answer`) | DebateNode |
| Memory хранит raw IS Sharpe | Использовать `opt_result["best_sharpe"]` если WF прошёл | MemoryUpdateNode |

## Паттерны тестирования
```python
# asyncio — Python 3.13 совместимо
asyncio.run(coro())          # ✅ OK
asyncio.get_event_loop().run_until_complete(coro())  # ❌ ЛОМАЕТСЯ в 3.13

# Lazy import patching
@patch("backend.agents.consensus.consensus_engine.ConsensusEngine.aggregate")  # ✅ источник
@patch("some_module.ConsensusEngine.aggregate")  # ❌ call-site

# _call_llm() требует state для отслеживания стоимости
await self._call_llm(prompt, state=state)  # ✅
await self._call_llm(prompt)               # ❌ нет cost tracking
```

## Память агентов
- SQLite timestamp: `"%Y-%m-%d %H:%M:%S"` (пробел, НЕ 'T') — ломает запросы
- `agent_namespace = "shared"` — виден ВСЕМ агентам; использовать имя агента для изоляции
- Retrieval: BM25 (keyword) + VectorStore (semantic) → hybrid score → Top-K
