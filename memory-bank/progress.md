# Progress — Статус проекта

## Последнее обновление: 2026-04-01

## ✅ Что работает (проверено, 2026-04-01)

- **Round 2 multi-agent audit & bugfixes** ✅ (2026-04-01 сессия 11)
  - **builder_optimizer.py**: (D) `calmar_ratio`/`payoff_ratio` для Numba DCA batch — были 0.0, теперь аналитически вычисляются из batch output; (E) WF OOS warmup в ОБОИХ batch методах (`_run_dca_pure_batch_numba` и `_run_dca_mixed_batch_numba`); (F) Fast RSI leverage default 1→10 (оптимизационный контекст)
  - **trading_strategy_graph.py**: BUG-AGENT-1 — `asyncio.wait_for(..., timeout=140.0)` вокруг `deliberate_with_llm()` в DebateNode + AnalysisDebateNode (LangGraph node-level timeout не гарантирован)
  - **deliberation.py**: BUG-AGENT-2 — `asyncio.wait_for(_ask_agent(), timeout=40.0)` в `refine_one()` внутри `_collect_refined_opinions()` — graceful fallback (keeps previous vote) on timeout
  - **Тесты**: 28 graph_converter ✅, 52 refinement_loop ✅, 115 real_llm_deliberation+p1+p2 ✅, 98 pipeline_streaming_hitl+consensus+langgraph ✅, ~1724 backend/agents (без real-API) ✅, ~426 backend/backtesting ✅, optimizer tests ✅
- **Multi-system audit & bugfixes** ✅ (2026-04-01 сессия 10)
  - **MetricsCalculator**: Win rate denominator → `total_trades` (TV standard); CAGR clip -100; recovery factor cap ±999
  - **formulas.py**: Monthly returns → `(end-start)/start_equity` (relative, TV-совместимо)
  - **service.py (backtest)**: `_drop_incomplete_last_bar()` — дропает неполный последний бар; `_validate_data_completeness()` — WARNING если < 70% ожидаемых свечей
  - **kline_repository.py**: `ON CONFLICT` добавлен `market_type`, `MIN_GAP_CANDLES` 2→1
  - **builder_optimizer.py**: (A) `math.isfinite(score_raw)` guard + clamp ±1e6 перед Optuna; (B) WF OOS warmup 200 баров (предотвращает data leakage); (C) Fast RSI DCA path → `_combo_sl`/`_combo_tp` вместо base block values
  - **test_pipeline_streaming_hitl.py**: hardcoded `created_at` → `datetime.now(UTC)` (TTL eviction fix)
  - **294/294 тестов** в targeted run (engine + parity + metrics + hitl + builder_optimizer), 0 регрессий

## ✅ Что работает (проверено, 2026-03-30)

- **Claude 4th agent integration** ✅ (2026-03-30 сессия 9)
  - `ClaudeClient` — нативный Anthropic Messages API (не OpenAI-compatible)
  - `_synthesis_critic()` — Claude первый, QWEN fallback, None если оба недоступны
  - `LLMClientFactory` регистрирует `ANTHROPIC → ClaudeClient`
  - `AGENT_SPECIALIZATIONS["claude"]` в templates.py
  - `ANTHROPIC_API_KEY` добавлен в `.env.example`
  - 18 новых тестов, 245/245 total — 0 регрессий
  - **Архитектура**: Claude как critic (автоматически) + как generator (opt-in через `agents=["deepseek","claude"]`)

## ✅ Что работает (проверено, 2026-03-29)

- **P3 AI Pipeline Performance** — 6 улучшений производительности ✅ (2026-03-29 сессия 8)
  - P3-1: `deliberation.py` `_collect_refined_opinions()` → `asyncio.gather` (~3× ускорение раунда)
  - P3-2: `EdgeType.PARALLEL` fan-out `regime_classifier → [debate, memory_recall]` (~60-90s экономия)
  - P3-3: SELF-RAG skip когда `async_load()` == 0 (первый run без истории)
  - P3-4: дедуп MemoryItem по `.id` внутри MemoryRecallNode
  - P3-5: `json_mode=True` для DeepSeek MoA + QWEN critic → детерминированный JSON output
  - P3-6: `N_TRIALS=100` (было 50), `n_jobs=2` (было 1) в OptimizationNode
  - **227/227 тестов** в targeted run, 0 регрессий в full suite
- **Test isolation fix** — async def + json_mode signatures ✅ (2026-03-29 сессия 8)
  - `test_wins_inject_memory_context` + `test_failures_inject_avoid_section` → native async def
  - `fake_call_llm` + `fake_critic_call` → добавлен `json_mode=False` в signatures
  - Root cause: pytest-asyncio Mode.AUTO + `asyncio.run()` sync helper конфликт

## ✅ Что работает (проверено, 2026-03-28)

- Claude Code инфраструктура расширена ✅ (2026-03-28 сессия 7)
  - `backend/agents/CLAUDE.md` + `backend/services/CLAUDE.md` + `backend/ml/CLAUDE.md` — on-demand context
  - `commission_guard.py` PreToolUse hook — блокирует случайный commission=0.001
  - `agent-system-expert` custom agent (`.claude/agents/`) — read-only AI-pipeline specialist
  - `CLAUDE.md §18` slim — 230 строк → 20 строк index table
  - `post_edit_tests.py` TEST_MAP — добавлены 3 entry для backend/services/ (19 targeted тестов)
  - `frontend/CLAUDE.md` — добавлены 3 bug entries (ConnectionsModule portId, AiBuildModule, SymbolSync)
- UI pipeline fixes завершены ✅ (2026-03-28 сессия 6)
  - ConnectionsModule `normalizeConnection()` portId fix — wires теперь рендерятся для AI-стратегий
  - GraphConverter orphan removal (`_remove_orphans()` BFS backward)
  - GraphConverter exit block (`_build_exit_block()` static_sltp из exit_conditions)
  - AI Build composite score display (Sharpe × Sortino × ln(1+trades) / (1+DD%))

## ✅ Что работает (проверено, 2026-03-27)

- FallbackEngineV4 — gold standard, TradingView parity ✅
- NumbaEngine — 100% parity с V4, 20-40x быстрее ✅
- DCAEngine — DCA/Grid/Martingale стратегии ✅
- Strategy Builder — блочный конструктор (50+ типов блоков) ✅
- MetricsCalculator — 166 метрик ✅
- Optuna optimizer — TPE/CMA-ES оптимизация ✅
- AI агенты (DeepSeek/Qwen/Perplexity) в direct API режиме ✅
- 179+ тестов проходят (214 файлов) ✅
- Port aliases (long↔bullish, short↔bearish) ✅
- Direction mismatch detection + warnings[] ✅
- commission=0.0007 — проверено в core-файлах ✅
- `backend/config/constants.py` создан (Phase 1.1) ✅
- `backend/backtesting/models.py` обновлён: константы + direction="both" (Phase 1.2) ✅
- Phase 3: `strategy_builder_adapter.py` (3575→1399 строк) разбит на пакет `strategy_builder/` ✅
- Phase 4: `backtests.py` (3171→пакет router.py+formatters.py+schemas.py) ✅
- Phase 5: `SymbolSyncModule.js` извлечён из `strategy_builder.js` (13378→7154 строк) ✅
- Phase 5: `blockLibrary.js` извлечён (каталог блоков, ~158 строк) ✅
- Agent pipeline BUG#1-3 fixes: PerformanceMetrics.model_dump(), analysis_warnings, None-safe RefinementNode ✅ (2026-03-24)
- ТЗ_ЭВОЛЮЦИЯ_ПАМЯТИ: все 5 фаз (P1-P5) реализованы и проверены, 286 тестов ✅ (2026-03-24)
- real_llm_deliberation.py: deprecated `connections` import → `backend.agents.llm` ✅
- 27 тестов: `test_agent_feedback_improvements.py` (все проходят) ✅
- 33 тестов: `test_refinement_loop.py` (все проходят) ✅
- P0 Agent Embodiment: MemoryRecallNode + BacktestAnalysisNode ✅ (2026-03-24)
  - MemoryRecallNode: читает HierarchicalMemory перед генерацией (wins/failures/regime)
  - BacktestAnalysisNode: severity + root_cause диагностика после backtest
  - Graph: analyze→[debate]→memory_recall→generate, backtest→backtest_analysis→[router]
  - 33 новых теста, 93 agent pipeline тестов проходят
- AI Agent system 10/10 readiness (unit-testable portion) ✅ (2026-03-25)
  - P1: PostRunReflectionNode, WalkForwardValidationNode, few-shot injection, SQLite checkpointer, cost budget
  - P2: RegimeClassifierNode, S²-MAD early stop, HITLCheckNode, pipeline event queue, composite_quality_score
  - P2 API: generate-hitl, pipeline/hitl, pipeline/hitl/approve, generate-stream, WS stream/{id}
  - 98 new tests (35 P1 + 45 P2 agent + 18 P2 API)
- AI Agent system 9.5/10 readiness ✅ (2026-03-24)
  - Global pipeline timeout (asyncio.wait_for, 300s default)
  - LLM cost observability: AgentState.total_cost_usd, llm_call_count, record_llm_cost()
  - Extended get_metrics(): node_timing_s, slowest_node, total_wall_time_s
  - Pipeline metrics in _report_node(), _backtest_passes() reads backtest_analysis
  - Module constants _MIN_TRADES=5, _MAX_DD_PCT=30.0 (single source of truth)
  - ConsensusNode fallback to best_of on engine exception
  - 25 new tests: refinement E2E + consensus fallback + cost accumulation + timeout
- generate-and-build endpoint: 25 integration tests ✅ (2026-03-24)
- Phases 1-6 (OptimizationNode top-20, AnalysisDebateNode, feedback loop, eval scripts) ✅ (2026-03-27)
  - eval_scenario_a: 4/4 criteria pass with real API keys, debate 84s (well within 150s new limit)
  - eval_regime_split: 3/3 regimes positive Sharpe, cross-regime debate success
  - SuperTrend filter type in graph_converter ✅ (was silently skipping, now produces supertrend block)
  - Debate timeout raised 90s → 150s (real measurements show 84-102s needed)
  - Happy path, error paths (404/503/500), request forwarding, edge cases
  - datetime.utcnow() → datetime.now(UTC) deprecation fix
- WF/optimizer ordering fix ✅ (2026-03-27 сессия 3)
  - WalkForwardValidationNode теперь ПОСЛЕ OptimizationNode: backtest_analysis → optimize → [wf →] analysis_debate
  - WF reads opt_result["best_sharpe"] → validates optimized params (not raw IS sharpe=-0.09)
  - 150 тестов проходят (43 refinement + 35 P1 + 27 feedback + 45 P2)
- MLValidationNode._run_strategy — 3 бага пофикшены ✅ (2026-03-27 сессия 4)
  - Bug 1: `timeframe=` → `interval=` (неверное поле BacktestConfig)
  - Bug 2: missing `start_date`/`end_date` → derive from `df.index[0]`/`df.index[-1]`
  - Bug 3: `engine.run(data=df, signals=…, config=cfg)` → `engine.run(cfg, df, silent=True, custom_strategy=adapter)`
  - Fix false "passed" log; return `result.metrics.model_dump()` (plain dict)
  - 141 тестов проходят
- MemoryItem.from_dict() — naive datetime из SQLite ✅ (2026-03-27 сессия 5)
  - `datetime.now(UTC) - naive_dt` → TypeError → memory recall падал на run 2+
  - Fix: `if tzinfo is None: replace(tzinfo=UTC)` для created_at и accessed_at
- MLValidationNode timeout ✅ (2026-03-27 сессия 5)
  - `use_bar_magnifier=True` → 200K 1m свечей × 17 backtests = 323s > 120s таймаут
  - Fix: `use_bar_magnifier=False` + таймаут узла 120.0 → 180.0s
- graph_converter `Highest/Lowest Bar` filter ✅ (2026-03-27, Run #22)
  - Тип не был в `_FILTER_BLOCK_MAP` → молча скипался
  - Fix: добавлен entry + 4 aliases (`Highest Lowest Bar`, `HighestLowest`, `Breakout Filter`, `New High/Low`)
- DebateNode `rounds` key missing ✅ (2026-03-27, Run #22)
  - `set_result` не сохранял `"rounds"` → debug script всегда показывал `Rounds: 0`
  - Fix: добавлен `"rounds": len(rounds_list)` в оба branch set_result

- **Multi-agent tech debt cleanup** ✅ (2026-04-10 сессия 13)
  - **consensus_engine.py**: `_SIGNAL_INCLUSION_THRESHOLD`, `_MAX_CONSENSUS_SIGNALS`, `_MAX_CONSENSUS_FILTERS` теперь конфигурируемы через конструктор; `_merge_filters` переведён в instance method
  - **hierarchical_memory.py**: DEBUG log при `agent_namespace="shared"` — предупреждает о cross-agent contamination
  - **templates.py**: `REGIME_INDICATOR_SECTIONS` + `_ALWAYS_INCLUDE_SECTIONS` + `filter_prompt_indicators()` — selective injection (~8K → ~2-3K токенов)
  - **prompt_engineer.py**: вызов `filter_prompt_indicators()` после форматирования промпта
  - **ai_pipeline.py**: SQLite persistence (`data/pipeline_jobs.db`, WAL) для pipeline jobs; `_create_job()`/`_update_job()` helpers; running jobs → "lost" при рестарте сервера
  - **Тесты**: exit_code=0 (p1_features, p2_features, pipeline_streaming_hitl, agents suite)

- **DeepSeek prefix caching + Optuna MedianPruner** ✅ (2026-04-10 сессия 14)
  - **`LLMResponse`**: поля `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` (DeepSeek KV cache)
  - **`estimated_cost`**: cache-aware ценообразование (hit=10% от нормальной цены → -90% экономии)
  - **`DeepSeekClient._parse_response()`**: извлекает cache метрики из `usage` + DEBUG лог экономии
  - **`builder_optimizer.py`**: `MedianPruner(n_startup_trials=10)` в single-objective `create_study()`; `trial.report()` + `trial.should_prune()` в objective; IS gate для OOS (skip OOS если `is_score < -1.0`)
  - **`test_prompt_ranges_match_optimizer_ranges`**: 27 passed (были уже зелёными из предыдущих сессий)
  - 9 новых тестов в `test_llm_clients.py`

## ⚠️ Известные проблемы / Технический долг

- RSI Wilder smoothing: 4-trade divergence vs TradingView (warmup limit 500 баров) — ACCEPTABLE
- ~~commission=0.001 в optimize_tasks.py + ai_backtest_executor.py~~ — FIXED (2026-03-24), теперь COMMISSION_TV
- **Bar Magnifier STUB**: `_bar_magnifier_index` строится (`engine:3101–3144`) но никогда не подписывается в main loop. Intrabar SL/TP check loop не существует. `use_bar_magnifier=True` молча не делает ничего — SL/TP по-прежнему проверяется только на закрытии бара. Задокументировано в CLAUDE.md `[UNIVERSAL_BAR_MAGNIFIER]` row.
- `sortino_ratio` в Numba DCA batch остаётся 0.0 — downside deviation недоступна из batch output. Не использовать `sortino` как `optimize_metric` для DCA стратегий.
- position_size: fraction (0-1) в engine vs percent в live trading — ADR-006, задокументировано
- leverage default: 10 в optimizer/UI vs 1.0 в live trading — задокументировано

## 📁 Крупные файлы требующие внимания

| Файл | Строк | Статус |
|------|-------|--------|
| strategy_builder/adapter.py | 1399 | ✅ Phase 3 рефакторинг завершён |
| indicator_handlers.py | wrapper | ✅ Phase 4: разбит на пакет indicators/ (trend/oscillators/volatility/volume/other) |
| strategy_builder.js | 7154 | ✅ Phase 5: SymbolSync + blockLibrary извлечены; canvas/block core остаётся |
| backtests/ (пакет) | router+formatters+schemas | ✅ Phase 4 завершён |

## 🚧 В процессе / Запланировано

- Deferred: real API integration tests (требует live keys + data), load tests (100+ requests)
- ~~Deferred: fix `test_prompt_ranges_match_optimizer_ranges`~~ — VERIFIED PASSING 27/27 (2026-04-10)
- Deferred: fix `test_workflow_with_iterations` (1 pre-existing) — ожидает 2 итерации, получает 3
- Deferred: multi-symbol validation (BTC+ETH+SOL параллельно)
- ~~Deferred: DeepSeek prefix caching~~ — DONE (2026-04-10)
- ~~Deferred: Optuna MedianPruner~~ — DONE (2026-04-10)

## 📊 Метрики кодовой базы

- Backend: ~50+ роутеров, 40+ индикаторов
- Tests: 214 файлов / 10 директорий
- Frontend: Vanilla JS, no build step

## 🚫 Что НЕЛЬЗЯ делать

- Менять commission с 0.0007 без явного согласования
- Использовать FallbackEngineV2/V3 для нового кода
- Хардкодить даты (импортировать DATA_START_DATE)
- Реализовывать метрики вне MetricsCalculator
- Вызывать реальный Bybit API в тестах
