# Progress — Статус проекта

## Последнее обновление: 2026-03-24

## ✅ Что работает (проверено)

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
  - Happy path, error paths (404/503/500), request forwarding, edge cases
  - datetime.utcnow() → datetime.now(UTC) deprecation fix

## ⚠️ Известные проблемы / Технический долг

- RSI Wilder smoothing: 4-trade divergence vs TradingView (warmup limit 500 баров) — ACCEPTABLE
- RSI Wilder smoothing: 4-trade divergence vs TradingView (warmup limit 500 баров) — ACCEPTABLE
- ~~commission=0.001 в optimize_tasks.py + ai_backtest_executor.py~~ — FIXED (2026-03-24), теперь COMMISSION_TV
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
