# backend/agents/ — Контекст модуля

## Структура

```
backend/agents/
├── trading_strategy_graph.py     # LangGraph pipeline (15 nodes) — MAIN ENTRY
├── unified_agent_interface.py    # Единая точка входа для всех AI вызовов
├── workflows/
│   └── builder_workflow.py       # AI Build workflow (graph → backtest → save)
├── integration/
│   └── graph_converter.py        # StrategyDefinition → strategy_graph dict
├── prompts/
│   ├── templates.py              # Prompt templates для всех nodes
│   └── response_parser.py        # Парсинг LLM ответов
├── memory/
│   ├── hierarchical_memory.py    # 4-tier cognitive memory (997 lines)
│   ├── sqlite_backend.py         # WAL mode, schema v2 (462 lines)
│   ├── vector_store.py           # ChromaDB + MiniLM-L6-v2 384-dim (602 lines)
│   └── bm25_ranker.py            # BM25 keyword fallback (203 lines)
├── consensus/
│   ├── consensus_engine.py       # 3 aggregation methods (896 lines)
│   ├── deliberation.py           # 4-phase multi-agent debate (1411 lines)
│   └── risk_veto_guard.py        # Post-consensus safety filter (297 lines)
├── self_improvement/
│   ├── feedback_loop.py          # backtest → reflect → improve (687 lines)
│   ├── strategy_evolution.py     # Evolution pipeline (772 lines)
│   ├── rlhf_module.py            # Preference learning (782 lines)
│   └── pattern_extractor.py      # Extract winning patterns (413 lines)
├── security/
│   ├── security_orchestrator.py  # Fusion policy (214 lines)
│   ├── prompt_guard.py           # Regex threat detection (235 lines)
│   └── semantic_guard.py         # 3-layer semantic analysis (258 lines)
├── llm/
│   ├── base_client.py            # Abstract base (551 lines) — aiohttp + rate limit
│   └── clients/                  # deepseek.py, qwen.py, perplexity.py, ollama.py
└── monitoring/
    ├── metrics_collector.py
    └── cost_tracker.py           # LLM API cost accumulation
```

## LangGraph Pipeline (trading_strategy_graph.py)

```
analyze_market → regime_classifier → [debate] → memory_recall
→ generate_strategies → parse → select_best → build_graph
→ backtest → backtest_analysis → [refine loop ≤3] → optimize
→ [wf_validation] → analysis_debate → ml_validation
→ [hitl] → memory_update → reflection → report
```

**Ключевые параметры запуска:**
```python
run_strategy_pipeline(
    pipeline_timeout=300.0,  # asyncio.wait_for wrapper
    max_cost_usd=0.5,        # BudgetExceededError если превышен
    hitl_enabled=False,      # HITLCheckNode перед memory_update
    run_wf_validation=True,  # WalkForwardValidationNode после optimizer
)
```

**AgentState поля:**
- `total_cost_usd`, `llm_call_count` — cost tracking
- `node_timing_s`, `slowest_node`, `total_wall_time_s` — performance
- `sig_long`, `sig_short` — signal counts (из BacktestNode, НЕ trade counts!)
- `opt_result["best_sharpe"]` — оптимизированный Sharpe (для WF и MemoryUpdate)

## Критические исправления (знай эти баги)

| Баг | Файл | Описание |
|-----|------|---------|
| DIRECTION_MISMATCH false positive | `BacktestNode` | Используй `sig_long`/`sig_short` (сигналы), НЕ trade counts |
| sparse_signals | `BacktestAnalysisNode` | `sig_long + sig_short < 10` → AND-gate over-filtering |
| poor_risk_reward skip | `_should_refine()` | Пропускает refinement если trades≥5 и sig≥50 — идёт в optimizer |
| WF ordering | graph order | Optimizer ПЕРЕД WF; WF использует `opt_result["best_sharpe"]` |
| Debate timeout | `DebateNode` | timeout=150s (реальный debate = 84-102s) |
| DeliberationResult | field names | `.decision`/`.confidence`/`.rounds` (НЕ `.consensus_answer`) |
| Memory stores raw Sharpe | `MemoryUpdateNode` | Используй `opt_result["best_sharpe"]` если WF прошёл |

## Memory System

**4-tier модель:**

| Tier | Тип | Max | TTL |
|------|-----|-----|-----|
| 1 | WORKING | 10 | Короткий |
| 2 | EPISODIC | 1,000 | Средний |
| 3 | SEMANTIC | 10,000 | Длинный |
| 4 | PROCEDURAL | 500 | Очень длинный |

**Retrieval:** BM25 (keyword) + VectorStore (semantic) → hybrid score → Top-K

**Ловушки:**
- `agent_namespace = "shared"` → доступно всем агентам; для изоляции используй имя агента
- `_SQLITE_TS_FMT = "%Y-%m-%d %H:%M:%S"` — space separator (НЕ 'T') — ломает запросы
- ChromaDB/sentence-transformers опциональны — fallback на BM25-only при ImportError
- `embedding = None` когда ChromaDB недоступен — ок, система деградирует gracefully

## Consensus & Debate

**ConsensusEngine.aggregate(strategies, method):**
- `"weighted_voting"` — по performance history агентов
- `"bayesian_aggregation"` — Prior × likelihood
- `"best_of"` — heuristic score ranking (fallback при ошибках engine)

**Deliberation:** 4 фазы (Initial → Cross-Examination → Refinement → Final Vote)
Voting strategies: `MAJORITY`, `WEIGHTED`, `UNANIMOUS`, `RANKED_CHOICE`, `SUPERMAJORITY`

**RiskVetoGuard** — MANDATORY post-filter (не рекомендация):
```python
# Veto если ANY из:
max_drawdown_pct = 5.0        # drawdown > 5%
daily_loss_limit_pct = 3.0    # дневной убыток > 3%
max_open_positions = 5         # слишком много позиций
min_agreement_score = 0.3     # агенты сильно расходятся
emergency_stop = False         # ручной kill switch
```

## Security Layer

**SecurityOrchestrator** — fusion policy: `BLOCK_ANY` / `BLOCK_ALL` / `WEIGHTED` (default)

**PromptGuard** — regex, 5 категорий угроз:
- `DIRECT_INJECTION`: "ignore all previous instructions"
- `ROLE_MANIPULATION`: "you are now a..."
- `DATA_EXFILTRATION`: "print your system prompt"
- `JAILBREAK`: известные паттерны
- `ENCODING_ATTACK`: base64, hex, unicode tricks

**SemanticGuard** — 3 слоя: regex → keyword density + role confusion → structure analysis

## LLM Client Architecture

**BaseLLMClient** (`llm/base_client.py`, 551 lines):
- aiohttp persistent sessions
- Token bucket rate limiting: 100K tokens/min, $5/hour, $50/day
- Retry с exponential backoff
- Circuit breaker (опционально)
- Usage stats: tokens, cost, latency

**Провайдеры:** DeepSeek V3.2 (strategy generation), Qwen/DashScope (alternative), Perplexity (market research), Ollama (local offline)

## Паттерны кода

**_call_llm() сигнатура:**
```python
async def _call_llm(self, prompt: str, state: AgentState | None = None) -> str:
    # state=state передавай для cost tracking
```

**Lazy import patch path:**
- `from X import Y` внутри функции → патчить source: `X.Y`, НЕ call site
- Пример: `ConsensusEngine` в `_consensus_node()` → `backend.agents.consensus.consensus_engine.ConsensusEngine`

**asyncio в тестах:**
- `asyncio.run()` — OK
- `asyncio.get_event_loop().run_until_complete()` — ЛОМАЕТСЯ в Python 3.13

## Тесты

```bash
pytest tests/backend/agents/ -v
pytest tests/test_agent_soul.py -v
pytest tests/test_memory_recall_and_analysis_nodes.py -v   # 43 теста
pytest tests/test_refinement_loop.py -v                    # 9 E2E тестов
pytest tests/test_p1_features.py -v                        # 35 тестов
pytest tests/test_p2_features.py -v                        # 45 тестов
pytest tests/test_pipeline_streaming_hitl.py -v            # 18 тестов
pytest tests/test_graph_converter.py -v                    # 28 тестов
```
