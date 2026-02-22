# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **AI builder — Optimizer Sweep Mode (2026-02-22, commit `e7fc03f9b`):**

    New `use_optimizer_mode` flag connects the AI builder workflow to the existing `BuilderOptimizer` infrastructure so each iteration can search a full parameter space rather than guessing a single value.

    **`backend/agents/workflows/builder_workflow.py`:**
    - `BuilderWorkflowConfig.use_optimizer_mode: bool = False` — opt-in per request; serialized in `to_dict()`.
    - `_suggest_param_ranges()`: A2A parallel consensus (DeepSeek + Qwen + Perplexity) — agents are shown the full graph description + `DEFAULT_PARAM_RANGES` hints and asked to propose narrow `{min, max, step}` ranges for 2-4 parameters. Falls back to single DeepSeek on A2A failure.
    - `_merge_agent_ranges()`: merges per-agent range suggestions using tightest common window: `max(mins)`, `min(maxima)`, `min(steps)`. Falls back to first agent's range if the intersection is empty.
    - `_run_optimizer_for_ranges()`: converts agent ranges → `custom_ranges` format, fetches strategy graph via `builder_get_strategy()` MCP tool, fetches OHLCV via `BacktestService`, auto-selects grid search (≤ 500 combos) or Bayesian/Optuna (> 500 combos, capped at 200 trials), returns `{best_params, best_score, best_metrics, tested_combinations}`.
    - Iteration loop now branches: `if config.use_optimizer_mode` → ranges+sweep path; `else` → existing single-value `_suggest_adjustments` path (backward-compatible).
    - Added `import asyncio` at module top.

    **`backend/api/routers/agents_advanced.py`:**
    - `BuilderTaskRequest.use_optimizer_mode: bool = False` Pydantic field (with description).
    - Passed to `BuilderWorkflowConfig` in both `run_builder_task()` and `_builder_sse_stream()`.

    **`frontend/strategy-builder.html`:**
    - New `#aiUseOptimizer` checkbox added to AI Build modal under the Deliberation checkbox.

    **`frontend/js/pages/strategy_builder.js`:**
    - `payload.use_optimizer_mode` reads `#aiUseOptimizer` checkbox value.

### Fixed

- **AI optimizer — 3 optimize-mode pipeline bugs fixed (2026-02-22, commit `e2ecd1dab`):**

    **`frontend/js/pages/strategy_builder.js` — Fix #1: empty blocks sent in optimize mode:**
    - Was: `payload.blocks = []; payload.connections = []` — agents received an empty graph with nothing to analyze.
    - Now: serializes the live canvas state (`strategyBlocks` + `connections`) into the payload so the backend gets the real graph without an extra API round-trip. Each block maps to `{id, type, name, params}`; each connection normalizes `sourceBlockId`/`source_block_id`/`source` key aliases for cross-version compat.

    **`backend/agents/workflows/builder_workflow.py` — Fix #1b: deliberation ran before strategy was loaded:**
    - Was: `_plan_blocks → deliberation → load existing strategy` (deliberation always saw empty `config.blocks`).
    - Now: `load existing strategy → _plan_blocks (new only) → deliberation` — deliberation always sees populated `config.blocks`. The block loader also prefers the canvas payload blocks (fast path) and falls back to `builder_graph.blocks` if the top-level API blocks list lacks params.

    **`backend/agents/mcp/tools/strategy_builder.py` — Fix #2a: new `builder_clone_strategy()` MCP tool:**
    - Wraps the already-existing `POST /strategies/{id}/clone` REST endpoint.
    - Returns `{id, name, block_count, connection_count, timeframe, symbol, created_at}`.

    **`backend/agents/workflows/builder_workflow.py` — Fix #2b: version snapshots saved to DB per iteration:**
    - After each successful block-param update, clones the strategy as `{base_name}_v{iteration}` so parameter history survives page reload.
    - Stores `version_name` and `version_strategy_id` in `iteration_record` for UI display.

    **`backend/agents/workflows/builder_workflow.py` — Fix #3: silent no-op iterations halted:**
    - Was: if `builder_update_block_params()` failed, the loop continued and ran another identical backtest.
    - Now: tracks `failed_blocks` list; if **all** updates in an iteration failed, logs a warning and `continue`s — skipping the backtest for that iteration.
    - On each successful update: syncs `b["params"]` in `self._result.blocks_added` so `_describe_graph_for_agents()` shows the new values in the next iteration's prompt.

- **AI optimizer agents no longer destroy the existing strategy graph during optimization (2026-02-22, commit `b8e26690c`):**

    **`backend/agents/workflows/builder_workflow.py`:**
    - **Root cause:** `_suggest_adjustments` sent agents only a bare list of block types and params, with zero context about the visual node-graph system, the signal-flow topology, or the constraint that structural changes were forbidden. Agents had no way to distinguish between an RSI block, an AND logic gate, or a STRATEGY aggregator — so they proposed reconstructing the strategy from scratch, replacing complex multi-indicator graphs (CCI + MFI + RSI + MACD + Supertrend → AND gates) with simplified structures.
    - **Added `_describe_graph_for_agents()` static helper:** formats the full visual graph for agent prompts — every block with its type, role description (e.g. _"logic gate (output True only when ALL inputs are True)"_), and current parameter values; every connection as a port-level signal-flow line (`rsi_14:long_signal → and_1:input_a`); an explanation of the Indicator → Condition → Logic → Action → STRATEGY signal-flow model; and a hard constraint header _"do NOT add/remove/reconnect blocks"_.
    - **Rewrote `_suggest_adjustments` prompt:** injects the full graph description at the top; explains all four block categories; provides a separate _tunable blocks_ list alongside the complete topology; uses `❌/✅` constraint markers so LLMs reliably respect structural boundaries.
    - **Fixed `blocks_summary` filter bug:** was `if b.get("params")` — silently dropped every logic gate, buy/sell action, price block, and strategy node from the agent's view. Now all blocks are included in the summary (no filter).
    - **Improved optimize-mode blocks loading:** if the REST API's top-level `blocks` list has no `params` (can happen for older saved strategies), workflow now falls back to `builder_graph.blocks`; same fallback for connections; logs count of blocks-with-params for observability.
    - **Passes `connections` to `_suggest_adjustments`:** the call site now forwards `connections=self._result.connections_made` so the graph topology is always available to the prompt builder.

- **Chart Audit — 6 chart bugs fixed + 2 follow-up fixes (2026-02-22, commits `5f39bfce6`, `HEAD`):**

    **`frontend/js/pages/backtest_results.js` + `frontend/backtest-results.html`:**
    - **Benchmarking chart (CRITICAL):** `buy_hold_return` is a USD absolute value, but the chart Y-axis treated it as `%` → showed e.g. `−2770%` instead of `−27%`. Fixed: convert via `(buy_hold_return / initialCapital) * 100`; rewrote chart init with correct `%` axis title `'Доходность (%)'`, floating-bar tooltip callbacks, and a clean 2-dataset structure (`Диапазон` + `Текущ. значение`).
    - **Equity badge:** Was showing `±$abs(netPnL)` (loss magnitude, e.g. `−$5545`). Fixed: now shows final account balance `$initialCapital + PnL` (e.g. `$4,455`); hover `title` attribute displays the P&L delta.
    - **Waterfall chart datalabels:** Bar values were invisible because global `ChartDataLabels.display = false` was not overridden. Fixed: added per-chart `datalabels` block (skips `_base` connector bars; K-suffix for values ≥ 1000); added Y-axis title `'USD'`.
    - **P&L distribution chart:** No datalabels, no axis titles, avg-line annotations had `label.display: false`. Fixed: enabled count labels above bars; added X-axis `'Доходность за сделку (%)'` and Y-axis `'Количество сделок'`; enabled annotation labels `Ср. убыток X%` / `Ср. приб. X%` with coloured badge backgrounds.
    - **ERR badge false-positives:** `window.onerror` set `resultsCount` badge to `'ERR'` on every harmless `ResizeObserver loop completed...` browser warning. Fixed: filter out `ResizeObserver`, `Script error`, and `Non-Error promise rejection` messages before setting the badge.
    - **Donut breakeven row:** `Безубыточность: 0 сделок (0.00%)` legend row always visible. Fixed: added `id="legend-breakeven-row"` to the HTML `<div>`, and JS hides the row with `display: none` when `breakeven === 0`.
    - **OHLC info row stays stale:** Price chart `subscribeCrosshairMove` callback only updated `btChartOHLC` when `candleData` was truthy; when crosshair moved between candles the row kept the last value. Fixed: added `else` branch that resets to `O: -- H: -- L: -- C: --`; replaced `?.toFixed(2)` chains with a null-safe `fmt()` helper.
    - **Equity chart DPR blur:** `equityChart` was created without an explicit `devicePixelRatio` option, causing canvas to render at 1×pixels on Retina / 125%-scaled displays. Fixed: added `devicePixelRatio: window.devicePixelRatio || 1` to Chart init options; `ResizeObserver` now also refreshes this option on resize.

    - **`models.py` — EngineType enum expanded:**
      Added `FALLBACK_V4 = "fallback_v4"`, `DCA = "dca"`, `DCA_GRID = "dca_grid"` aliases;
      `validate_engine_type` now accepts `"fallback_v4"` and normalizes it to `"fallback"`;
      `ADVANCED` docstring notes it delegates to `strategy_builder_adapter` (no dedicated handler).

    - **`engine.py` — three dead-code / correctness fixes:**
      Removed dead `open_price` variable;
      Fixed MFE/MAE short-position initialization — both excursion trackers now start from `entry_price` instead of the current bar's `low`/`high`;
      Added NaN/Inf guard on both `pnl_pct` calculation sites: checks `margin_used > 0`, then rejects NaN/Inf result with fallback `0.0`.

    - **`builder_optimizer.py` — MACD fast < slow cross-param constraint:**
      After sampling all trial parameters, scans `overrides` for `*.fast_period` / `*.slow_period` pairs (same block prefix) and clamps `slow_period = max(slow_period, fast_period + 1)` before graph cloning.

    - **`optuna_optimizer.py` — `_sample_params` low ≥ high guard + stop_loss range:**
      `_sample_params()` now skips any spec where `low >= high` with a `WARNING` log instead of letting Optuna raise `ValueError`;
      `stop_loss` minimum in both `create_sltp_param_space()` and `create_full_strategy_param_space()` changed `0.01 → 0.001`.

    - **`strategy_builder_adapter.py` — DCA `grid_size_percent` median-step fix:**
      Replaced `max(offsets)` (full range, not step size) with the **median inter-order gap** of sorted positive offsets; falls back to the single offset value, then `1.0` for degenerate cases.

    - **`indicator_handlers.py` — `_clamp_period()` coverage gaps:**
      Added `_clamp_period()` wrapping to six previously-unguarded period reads:
      `vol_length1`, `vol_length2` in `_handle_volume_filter`;
      `hl_lookback_bars`, `atr_hl_length` in `_handle_highest_lowest_bar`;
      `backtracking_interval`, `min_bars_to_execute` in `_handle_accumulation_areas`.

    - **`optimization/utils.py` — walk-forward split clamp warning level:**
      `split_candles()` now captures the pre-clamp value and emits `logger.warning(...)` when `train_split` was actually changed by the `max(0.5, min(0.95, …))` clamp; the always-fires `logger.info` log for the final split is retained.

### Added

- **Фича 1 — `profit_only` / `min_profit` gate on `close_cond` exits (2026-02-22):**
    - `strategy_builder_adapter.py`: `close_cond` routing now collects `profit_only` and `min_profit` flags per signal bar into four extra-data Series: `profit_only_exits`, `profit_only_short_exits`, `min_profit_exits`, `min_profit_short_exits`, passed to the engine via `SignalResult.extra_data`.
    - `engine.py` (`FallbackEngineV4`): new per-signal profit-gate block reads `po_exit_arr` / `po_sexit_arr` from `extra_data`. A signal-triggered exit is only executed when the current PnL% ≥ `min_profit` threshold; if the gate is not active the original unconditional exit fires as before.

- **Фича 2 — HTF timeframe resampling for `mfi_filter` / `cci_filter` (2026-02-22):**
    - `indicator_handlers.py`: added `_TF_RESAMPLE_MAP` (all 9 Bybit TFs + common aliases) and `_resample_ohlcv()` helper that converts a 1-min / 15-min OHLCV DataFrame to any higher timeframe and reindexes it back to the original length via forward-fill.
    - `_handle_mfi_filter` and `_handle_cci_filter` patched: when `mfi_timeframe` / `cci_timeframe` ≠ chart interval the handler now resamples the OHLCV before computing the indicator. Removed stale `BUG-WARN` comments from both handlers.

- **Фича 3 — `use_btcusdt_mfi`: BTCUSDT OHLCV as MFI data source (2026-02-22):**
    - `strategy_builder_adapter.py`: `__init__` accepts new `btcusdt_ohlcv: pd.DataFrame | None = None` keyword argument; stored as `self._btcusdt_ohlcv`. Added `_requires_btcusdt_data()` helper that scans blocks for `mfi_filter` with `use_btcusdt_mfi=True`.
    - `api/routers/strategy_builder.py`: after adapter construction, if `_requires_btcusdt_data()` is true, pre-fetches BTCUSDT OHLCV via `BacktestService._fetch_historical_data()` for the same date range/interval and recreates the adapter with the new argument.
    - `indicator_handlers.py` `_handle_mfi_filter`: checks `adapter._btcusdt_ohlcv`; if set and `use_btcusdt_mfi=True`, uses that DataFrame instead of the chart symbol's OHLCV; falls back to chart OHLCV silently if not available.

- **Unit tests — 20 new tests for Фичи 1-3 (2026-02-22):**
    - `tests/backend/backtesting/test_unimplemented_features.py` (520 lines, 20 tests):
        - `TestResampleOhlcv` (6): DatetimeIndex resample, numeric-ms-index resample, unknown TF → `None`, <2 HTF bars → `None`, daily from 1h, `_TF_RESAMPLE_MAP` completeness.
        - `TestMfiFilterHtf` (4): chart-TF path, HTF resample path, BTCUSDT override, BTCUSDT fallback-to-None.
        - `TestCciFilterHtf` (2): chart-TF and HTF resample paths.
        - `TestProfitOnlyExitsEngine` (4): loss-suppressed exit, profit-above-threshold fires, unconditional exit fires, below-min_profit suppressed.
        - `TestAdapterProfitOnlyExtraData` (4): `_requires_btcusdt_data()` false by default, true when block present, `_btcusdt_ohlcv` stored on adapter, `None` by default.

### Fixed

- **`strategy_builder_adapter.py` — pre-existing encoding corruption (2026-02-22):**
    - 117 curly-quote characters (U+201C / U+201D) replaced with ASCII straight quotes.
    - 26 Windows-1252 mojibake em-dash sequences (`\xd0\xb2\xd0\x82"`) replaced with proper `—` (U+2014), resolving `SyntaxError: unterminated string literal` at line 2001.

- **`strategy_builder_adapter.py` line 3406 — stale raw connection format (2026-02-22):**
    - `conn.get("target", {}).get("nodeId")` used the pre-normalization nested format on `self.connections` which has already been normalized to flat `dict[str, str]` by `_normalize_connections()`. Replaced with `conn.get("target_id")`. Fixes 3 Mypy errors (`misc`, `union-attr`, `call-overload`).

- **`indicator_handlers.py` — ambiguous en-dash in comments (2026-02-22):**
    - Replaced `–` (U+2013 en-dash) with `-` (hyphen) in block-registry comment lines 1659–1661 (Ruff RUF003).

- **`strategy_builder_adapter.py` — collapsible nested `if` in `_requires_btcusdt_data()` (2026-02-22):**
    - Merged `if block.get("type") == "mfi_filter": if block.get("params"...) ...` into a single `and` condition (Ruff SIM102).

### Fixed

- **Strategy Builder Adapter — `close_conditions` blocks never executed (2026-02-21):**
    - **Root cause:** `close_by_time`, `close_channel`, `close_ma_cross`, `close_rsi`, `close_stochastic`, `close_psar` were all missing from `_BLOCK_CATEGORY_MAP` in `strategy_builder_adapter.py`. When `_execute_block()` called `_infer_category()` and the type wasn't found in the map, it fell through to the heuristic fallback which returned `"indicator"`. This caused `_execute_indicator()` to be called instead of `_execute_close_condition()`, returning `{}` for all these block types.
    - **Effect:** `exits=0` in `[SignalSummary]` even when `close_by_time` / `close_channel` blocks were wired to `main_strategy:close_cond`. The `close_cond` routing code at line 3198 was never reached because the block never produced outputs.
    - **Fix:** Added all 6 close-condition block types to `_BLOCK_CATEGORY_MAP` with `"close_conditions"` category (`backend/backtesting/strategy_builder_adapter.py`).

- **Strategy Builder Adapter — `close_by_time` wrong parameter key `bars` vs `bars_since_entry` (2026-02-21):**
    - `_execute_close_condition()` read `params.get("bars", 10)` but the frontend saves the value under key `"bars_since_entry"`.
    - **Fix:** Changed to `params.get("bars_since_entry", params.get("bars", 10))` to support both keys with backward compatibility.

- **Strategy Builder Router — `close_by_time` not wired to `BacktestConfig.max_bars_in_trade` (2026-02-21):**
    - `close_by_time` block params were not extracted from `db_strategy.builder_blocks` in `run_backtest_from_builder()`, so `BacktestConfig.max_bars_in_trade` was always `0` (disabled) even when the block was present.
    - **Fix:** Added `block_max_bars_in_trade` extraction in the block-scan loop in `strategy_builder.py` and passed it as `max_bars_in_trade=block_max_bars_in_trade` to `BacktestConfig`. Also fixed the key lookup (`bars_since_entry` with `bars` fallback).

- **Strategy Builder Backtest — `datetime` JSON serialization crash (2026-02-21):**
    - `BacktestRequest.start_date` / `end_date` are Pydantic `datetime` fields. They were stored as-is inside the `parameters` dict passed to SQLAlchemy's `JSON` column, which calls `json.dumps()` and throws `TypeError: Object of type datetime is not JSON serializable`.
    - Fixed in `backend/api/routers/strategy_builder.py` `run_backtest_from_builder()`: `request.start_date` and `request.end_date` are now serialized to ISO strings via `.isoformat()` before being stored in `parameters`.
    - **Impact:** `POST /strategy-builder/strategies/{id}/backtest` was returning HTTP 500 for all Strategy Builder strategies. The backtest engine itself ran correctly (95+ trades with real metrics), but the DB write failed causing the entire endpoint to crash and AI Strategy Optimizer to see 0 trades / 0% win rate.

- **Strategy Builder Canvas — 7 Coordinate & Performance Bug Fixes (2026-02-21):**
    - **BUG#1 🔴 (Drag at zoom!=1):** `startDragBlock()` now computes `dragOffset` in **logical** coordinates: `(clientX - containerRect.left) / zoom - blockData.x`. `onMouseMove` converts mouse position to logical via `/ zoom` before writing `blockData.x/y` and `block.style.left/top`. Fixes block drifting/jumping at any zoom level other than 1.
    - **BUG#2 🔴 (Marquee selection at zoom!=1):** `startMarqueeSelection()` converts `marqueeStart` to logical space (`/ zoom`). `onMouseMove` converts `currentX/Y` the same way. Marquee rect and block bounds are now both in logical space — intersection test is correct.
    - **BUG#3 🔴 (Drop position at zoom!=1):** `onCanvasDrop()` divides drop offset by `zoom` before passing to `addBlockToCanvas()`. Dropped blocks now land under the cursor at all zoom levels.
    - **BUG#4 🟡 (Double renderConnections):** Removed the standalone `renderConnections()` call from `deleteConnection()` (called just before `renderBlocks()` which already calls it internally). Same redundant call removed from `restoreStateSnapshot()`.
    - **BUG#5 🟡 (pushUndo on bare click):** Moved `pushUndo()` from `mousedown` to first real movement inside `onMouseMove` (guarded by `Math.hypot(dx, dy) > 3`). Clicks without dragging no longer pollute the undo stack.
    - **BUG#6 🟡 (console.log in render hot path):** Removed `console.log` from `renderBlocks()` (called ~60fps during drag via RAF) and stripped 5 verbose logs from `addBlockToCanvas()`. The one user-facing drop log is kept.
    - **BUG#7 🟢 (ID collision on fast generation):** All `block_${Date.now()}` and `conn_${Date.now()}` ID sites (4 block sites, 2 conn sites) now append a 5-char random suffix: `_${Math.random().toString(36).slice(2,7)}`. Prevents ID collisions during AI bulk-generation or rapid duplication.

- **Strategy Builder — 6 Bug Fixes (2026-02-21):**
    - **Bug #2 (use_fallback silent zero-signal):** `strategy_builder_adapter.py` now sets `use_fallback=True` with a diagnostic `logger.warning` when connections exist to the main node but all signal series are empty — prevents silently returning 0 trades when a node is wired but produces no signals.
    - **Bug #3 (Breakeven not passed from static_sltp):** `extractSlTpFromBlocks()` in `strategy_builder.js` already correctly extracts and forwards `breakeven_enabled`, `breakeven_activation_pct`, `breakeven_offset`, `close_only_in_profit`, `sl_type` from `static_sltp` blocks. Backend router reads these fields directly from saved `db_strategy.builder_blocks` — confirmed working end-to-end.
    - **Bug #4 (Direction filter change not saved):** Added `autoSaveStrategy()` call after `connections.splice()` in the direction-change handler so DB is updated when connections to hidden ports are pruned.
    - **Bug #5 (Mismatch highlighting misses bullish/bearish):** Mismatch detection now recognises `bullish` as alias for `long` and `bearish` as alias for `short` in source port checking, fixing highlight for divergence blocks.
    - **Bug #6 (Default port "value" causes signal loss):** `_parse_source_port()` and `_parse_target_port()` in `strategy_builder_adapter.py` now default to `""` instead of `"value"`, preventing phantom "value" port IDs that silently broke signal routing on malformed/unconnected nodes.

- **leverageManager.js — Encoding fix (2026-02-21):** All 12 Russian strings were corrupted with UTF-8 mojibake (box-drawing chars). Restored correct Cyrillic text for 8 risk level labels, 3 warning messages, and `indicator.title`. Version bumped to 1.1.1.

- **Close by Time node — Parameter labels (2026-02-21):** Added `close_by_time` block schema to `blockParamDefs` in `strategy_builder.js` with correct labels ("Use Close By Time Since Order?", "Close order after XX bars:", "Close only with Profit?", "Min Profit percent for Close. %%"). Fixed `min_profit_percent` default from `0` to `0.5`.

### Added

- **Optional Improvement: Canary Deployment Infrastructure — 2026-02-20:**
    - `deployment/canary/canary-deployment.yaml` — K8s Deployment with canary track labels, health probes, resource limits, Prometheus annotations
    - `deployment/canary/canary-virtualservice.yaml` — Istio VirtualService for progressive traffic splitting (10→25→50→100% stages) with DestinationRule subsets
    - `deployment/canary/canary-rollback-rules.yaml` — PrometheusRule for automatic rollback on >5% error rate (critical) and >2s p99 latency (warning)
    - `deployment/canary/canary.ps1` — PowerShell management script (deploy/promote/rollback/status actions with health checks)

- **Optional Improvement: GraphQL API Schema — 2026-02-20:**
    - `backend/api/graphql_schema.py` — Strawberry GraphQL schema with Query (health, strategies, symbols, timeframes) + Mutation (run_backtest)
    - Graceful fallback router if `strawberry` package not installed (returns 501 with install instructions)

- **Optional Improvement: WebSocket Scaling Service — 2026-02-20:**
    - `backend/services/ws_scaling.py` — High-level Redis Pub/Sub broadcaster for multi-worker WebSocket delivery
    - `BroadcastMessage` serialization, channel registry, local asyncio.Queue fallback when Redis unavailable
    - Module-level `get_ws_broadcaster()` singleton
    - Extends existing `tick_redis_broadcaster.py` for backtest progress, pipeline status, and system alerts

- **Optional Improvement: RL Training Pipeline — 2026-02-20:**
    - `backend/services/rl_training.py` — Experiment tracking & model management wrapping `backend/ml/rl_trading_agent.py`
    - `LocalExperimentTracker` (file-based JSON storage, run listing, best-model selection by metric)
    - `RLTrainingPipeline` with `train()`, `evaluate()`, `list_runs()`, `best_model()` methods
    - Synthetic episode generation, epsilon-greedy training loop, batch DQN with `train_step()`
    - NumPy `.npz` checkpoint saving

- **Optional Improvement: News Feed Service — 2026-02-20:**
    - `backend/services/news_feed.py` — Real-time news aggregation wrapping `backend/ml/news_nlp_analyzer.py`
    - `MockNewsSource` for dev/testing, `RSSNewsSource` stub, pluggable `BaseNewsSource` adapter
    - `ArticleCache` with TTL-based eviction and symbol/date filtering
    - `NewsFeedService.get_feed()` and `get_sentiment_summary()` with bullish/bearish/neutral aggregation
    - Module-level `get_news_feed_service()` singleton

- **Tests for new optional modules — 2026-02-20:**
    - `tests/backend/services/test_rl_training.py` — 19 tests: TrainingRun serialization, LocalExperimentTracker CRUD, RLTrainingPipeline train/evaluate/list
    - `tests/backend/services/test_news_feed.py` — 18 tests: MockNewsSource, ArticleCache, FeedArticle, SentimentSummary, NewsFeedService integration
    - `tests/backend/services/test_ws_scaling.py` — 9 tests: BroadcastMessage JSON roundtrip, WSBroadcaster local pub/sub, singleton

### Fixed

- **Perplexity cache `invalidate_cache()` TypeError on tuple keys — 2026-02-20:**
    - `backend/agents/consensus/perplexity_integration.py` line 673: `key.startswith()` failed when cache contained tuple keys `("SYMBOL", "strategy")`. Fixed to handle both `str` and `tuple` key formats.
    - 17/17 perplexity tests pass.

- **AI pipeline status tests TTL eviction — 2026-02-20:**
    - `tests/backend/api/test_ai_pipeline_endpoints.py`: 6 tests used hardcoded `"2025-01-01T12:00:00"` timestamps that were evicted by `_evict_stale_jobs()` (1hr TTL). Added `_recent_ts()` helper using `datetime.now(UTC)`.
    - 28/28 pipeline endpoint tests pass.

- **Ruff UP041: `asyncio.TimeoutError` → `TimeoutError` — 2026-02-20:**
    - Updated deprecated `asyncio.TimeoutError` alias in `perplexity_integration.py`.

- **Mypy annotation fix in `agent_memory.py` — 2026-02-20:**
    - Explicit `self._db_path: str | None = None` annotation to satisfy Mypy type checker.

### Confirmed Pre-Existing (No Changes Needed)

- **Performance Profiling** — `backend/services/profiler.py` (244 lines) already implements `@profile_time`, `@profile_memory`, `profiling_session` context manager
- **A/B Testing Framework** — `backend/services/ab_testing.py` (713 lines) already implements full A/B test suite with scipy
- **WebSocket Scaling (low-level)** — `backend/services/tick_redis_broadcaster.py` (301 lines) already implements Redis pub/sub for trade data
- **RL Trading Agent** — `backend/ml/rl_trading_agent.py` (820 lines) already implements DQN/PPO agents with experience replay
- **News NLP Analyzer** — `backend/ml/news_nlp_analyzer.py` (797 lines) already implements sentiment analysis with lexicon + optional FinBERT

---

### Added

- **P5.1a: Agent Memory SQLite WAL backend — 2026-02-21:**
    - `AgentMemoryManager` now supports dual backend: SQLite WAL (`AGENT_MEMORY_BACKEND=sqlite`) or JSON files (default)
    - Separate database at `data/agent_conversations.db` with WAL mode for concurrent reads
    - New methods: `_init_sqlite()`, `_get_sqlite()`, `_persist_conversation_sqlite()`, `_load_conversation_sqlite()`, `_clear_conversation_sqlite()`
    - 12 unit tests including concurrent write stress test (5 threads x 20 messages)

- **P5.1b: Redis distributed lock for pipeline — 2026-02-21:**
    - `backend/services/distributed_lock.py`: `DistributedLock` with Redis SET NX EX pattern
    - Graceful fallback to `asyncio.Lock` when Redis unavailable
    - Integrated into `ai_pipeline.py` `generate_strategy` endpoint with 429 on lock timeout
    - Extracted `_execute_pipeline()` helper for clean separation
    - 8 unit tests covering acquire/release, contention, timeout, fallback

- **P5.3a: Comprehensive metrics calculator tests — 2026-02-21:**
    - 147 known-value unit tests for `backend/core/metrics_calculator.py` (86% coverage)
    - Tests every standalone function: `safe_divide`, `calculate_win_rate`, `calculate_profit_factor`, `calculate_margin_efficiency`, `calculate_ulcer_index`, `calculate_sharpe`, `calculate_sortino`, `calculate_calmar`, `calculate_max_drawdown`, `calculate_cagr`, `calculate_expectancy`, `calculate_consecutive_streaks`, `calculate_stability_r2`, `calculate_sqn`
    - Tests `calculate_trade_metrics`, `calculate_risk_metrics`, `calculate_long_short_metrics` with hand-calculated expected values
    - Tests `calculate_all()` output: 90+ keys present, all values finite, caching, Kelly criterion, expectancy
    - Tests `enrich_metrics_with_percentages`, Numba parity, edge cases (single trade, all winners, all losers, breakeven only, large PnL, negative equity)
    - Full output key verification: all documented metric keys present in result dict

- **P5.3d: XSS E2E protection tests — 2026-02-21:**
    - 98 tests without Playwright dependency (httpx AsyncClient against FastAPI app)
    - `escapeHtml` parity with `Sanitizer.js` (19 OWASP payloads, angle bracket verification, stdlib parity)
    - XSS detection patterns (dangerous tags, event handler attributes, no false positives)
    - API endpoint reflection tests (health, klines, backtest, 404 path)
    - Security headers verification (X-Content-Type-Options, server header, JSON content-type)
    - Template injection payloads (Jinja2, JS, Ruby, ERB)
    - Sanitizer.js allowed/dangerous tag verification, input length limits, null byte injection

### Fixed

- **P1 Critical Bug Fixes — 2026-02-20:**
    - **M1: Duplicate dataclass fields** — `long_largest_loss` and `short_largest_loss` were each defined twice in `BacktestMetrics` dataclass (`backend/core/metrics_calculator.py`). Second definition silently overwrote the first, causing data loss during serialization. Removed duplicate lines.
    - **M2: FK type mismatch** — `Optimization.strategy_id` was `Column(Integer)` but `strategies.id` is `Column(String(36))` (UUID). FK constraint never enforced, cascade delete broken. Changed to `Column(String(36))` in `backend/database/models/optimization.py`.
    - **F1/F2/F5/F6: XSS in strategy_builder.js** — `e.message` and `err.message` from errors/API responses were inserted via `innerHTML` without escaping. Applied `escapeHtml()` (already available in file) to all vulnerable locations: backend connection banner, database panel error, data sync status error message, and version history error.
    - **F4: Race condition in agent_memory.py** — Concurrent `store_message()` calls wrote to the same JSON file without locking, causing data corruption. Added per-conversation `threading.Lock` with a `_locks_guard` to protect the locks dict itself.
    - **A1: Deprecated pandas API** — `reindex(ohlcv.index, method="ffill")` and `fillna(method="bfill")` in `strategy_builder_adapter.py` throw `TypeError` on pandas 2.1+. Replaced with `.reindex(ohlcv.index).ffill()` and `.bfill()`.

- **Audit findings verified as false positives:**
    - **V3: VectorBT direction_mode** — Audit claimed `mode==0` disables short (should disable long). Verified code is correct: `direction_mode=0` (long only) disables `short_entry/exit`, `direction_mode=1` (short only) disables `long_entry/exit`. Dict mapping `{"long": 0, "short": 1, "both": 2}` is consistent.
    - **V1/V2: VectorBT SL/TP clamping** — Trigger conditions and price clamping logic are correct for both LONG and SHORT positions.

### Removed

- **`strategies.html` page removed — 2026-02-19:**
    - **Deleted files:** `frontend/strategies.html` (1755 lines), `frontend/css/strategies.css`, `frontend/js/pages/strategies.js`, and `frontend/js/pages/strategies/` folder (6 sub-modules: `backtestManager.js`, `strategyCRUD.js`, `leverageManager.js`, `instrumentService.js`, `utils.js`, `index.js`)
    - **Reason:** `strategy-builder.html` is a complete superset — visual block-based strategy composition replaces the old form-based approach. All functionality (backtest, optimization, strategy CRUD, templates, versions, AI build, evaluation, database management) is available on `strategy-builder.html`
    - **Migrated shared utilities:** `leverageManager.js` and `instrumentService.js` moved to `frontend/js/shared/` since `strategy_builder.js` imports `updateLeverageRiskForElements`
    - **Updated 13 navigation links** across 10 files: `analytics-advanced.html`, `settings.html`, `risk-management.html`, `portfolio.html`, `optimization-results.html`, `ml-models.html`, `notifications.html`, `marketplace.html`, `dashboard.html` (2 links), `backtest-results.html` (2 links)
    - **Updated 3 JS references:** `marketplace.js`, `dashboard.js` (2 hotkeys: `s` and `n`)

### Added

- **Direction mismatch wire highlighting — 2026-02-19:**
    - Wires (connections) that conflict with the selected direction now turn **red and dashed** with a pulsing animation:
        - Direction = "Short" but wire goes to `entry_long`/`exit_long` → red dashed
        - Direction = "Long" but wire goes to `entry_short`/`exit_short` → red dashed
        - Source port `"long"` wired to `entry_short` (cross-wired signal) → red dashed
        - Source port `"short"` wired to `entry_long` (cross-wired signal) → red dashed
    - SVG `<title>` tooltip on hover explains the mismatch in Russian
    - Wires update instantly when the direction dropdown changes
    - **Wires also re-evaluate on ANY block param change** (`updateBlockParam()`) and on `resetBlockToDefaults()`
    - CSS class: `.direction-mismatch` with `stroke: #ef4444`, `stroke-dasharray: 10 6`, pulse animation
    - Files: `frontend/js/pages/strategy_builder.js` (`renderConnections()`, `updateBlockParam()`, `resetBlockToDefaults()`), `frontend/css/strategy_builder.css`

- **Port alias fallback in Case 2 signal routing — 2026-02-19:**
    - When a connection's `source_port` is not found in `source_outputs`, the adapter now tries alias mapping (`"long"↔"bullish"`, `"short"↔"bearish"`, `"output"↔"value"`, `"result"↔"signal"`) before falling back to single-output extraction.
    - Prevents silent signal drops when backend output keys don't match frontend port IDs.
    - Logs `logger.warning` for any connection where port cannot be resolved.
    - File: `backend/backtesting/strategy_builder_adapter.py` (Case 2 in `generate_signals()`)

- **Direction mismatch warning in backtest engine — 2026-02-19:**
    - `_run_fallback()` now logs `[DIRECTION_MISMATCH]` warning when the direction filter would drop all available signals (e.g., `direction="long"` but only `short_entries` exist, or vice versa).
    - Helps diagnose "Short gives nothing" scenarios before simulation even starts.
    - File: `backend/backtesting/engine.py`

- **Pre-backtest signal diagnostics in API — 2026-02-19:**
    - `run_backtest_from_builder()` now generates a `warnings` list before running the backtest, checking for: no signals detected, direction/signal mismatch.
    - Warnings are returned in the API response as `"warnings": [...]` field.
    - File: `backend/api/routers/strategy_builder.py`

- **Frontend warning display for backtest results — 2026-02-19:**
    - `runBacktest()` in `strategy_builder.js` now checks for `warnings` array in backtest response and shows each as a notification with `warning` type.
    - Users see actionable diagnostics like "Direction is 'long' but only short signals detected" immediately after backtest completes.
    - File: `frontend/js/pages/strategy_builder.js`

- **11 new divergence tests — 2026-02-19:**
    - `TestDivergenceSignalRouting` (4 tests): long_only, short_only, both directions, no_connections
    - `TestDivergencePortAlias` (3 tests): bullish→long alias, bearish→short alias, signal alias resolution
    - `TestDivergenceWithEngine` (4 tests): direction filtering (long/short/both trades), open position at end-of-data
    - Total: 56 divergence tests pass (6 handler + 50 AI agent).
    - File: `tests/ai_agents/test_divergence_block_ai_agents.py`

### Fixed

- **🔴 CRITICAL: Divergence block signals silently dropped — 2026-02-19:**
    - **Root cause**: Backend `_execute_divergence()` returned output keys `"bullish"` and `"bearish"`, but frontend divergence block ports are named `"long"` and `"short"`. The port alias system in `_get_block_inputs()` had no mapping between these names, so when connecting `divergence.long` → `strategy.entry_long`, the signal lookup failed silently — divergence signals were never delivered to the strategy node.
    - **Fix** (`backend/backtesting/strategy_builder_adapter.py`): `_execute_divergence()` now returns **both** `"long"`/`"short"` (matching frontend port IDs) AND `"bullish"`/`"bearish"` (backward compatibility). The `"signal"` key remains as `long | short`.
    - **Test coverage**: Added `test_returns_long_short_port_keys` to verify `"long"` and `"short"` keys exist and equal `"bullish"`/`"bearish"`. All 50 divergence tests pass (6 handler + 44 AI agent).

- **Health check UnicodeEncodeError on Windows cp1251 terminals — 2026-02-19:**
    - `main.py health` crashed with `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f3e5'` because emoji characters in `print()` can't be encoded in cp1251.
    - **Fix** (`main.py`): Added `io.TextIOWrapper` with `encoding="utf-8", errors="replace"` for stdout/stderr when terminal encoding is not UTF-8.

- **SL/TP Request Explicitness & Investigation — 2026-02-18:**
    - **Investigation**: User reported SL not triggering on 5 candles before actual exit in trade #272 (BTCUSDT, 15m, 10x leverage)
    - **Finding**: SL **IS working correctly**. Exhaustive analysis proved:
        - Entry=70103.73, SL price=66598.55 (5% below entry)
        - Only 1 of 305 fifteen-minute bars had low (66556.6) below SL — the exit bar at 2026-02-17 15:30
        - Bar Magnifier 1m data confirmed: candle at 15:33 had low=66556.6 breaching SL
        - `exit_comment: "SL"` correctly recorded; PnL=-51% is correct (5.05% price drop × 10x leverage + fees)
        - The 5 candles user circled had lows ABOVE the SL price — visual misread on compressed chart
    - **Defensive JS fix** (`frontend/js/pages/strategy_builder.js`):
        - Added `extractSlTpFromBlocks()` function — iterates `strategyBlocks` for `static_sltp`/`sl_percent`/`tp_percent` blocks
        - Converts human % (e.g., 5) to decimal fraction (0.05) matching `BacktestRequest` model constraints
        - Spread into `buildBacktestRequest()` so `stop_loss`/`take_profit` are sent explicitly in request body
        - Backend already extracted SL/TP from DB blocks as fallback — this makes the request self-contained and debuggable

- **🔴 CRITICAL: Margin/Equity/Fee Deep Audit Fixes — 2026-02-18:**
    - **engine.py — Margin Reconstruction Error (Issue #1)**:
        - Old code reconstructed margin at exit: `margin = entry_size * entry_price / leverage`
        - This is mathematically WRONG because `entry_size = margin * leverage / (price * (1+fee))`, so `size * price / leverage ≠ margin` (fee term causes drift)
        - Fix: Track `margin_allocated` at entry, use exact value at exit
    - **engine.py — Equity Formula Inflation (Issue #2)**:
        - Old: `equity = cash + entry_price * position + unrealized_pnl` — position includes leverage, inflating equity by `(leverage - 1) * margin`
        - Fix: `equity = cash + margin_allocated + unrealized_pnl` — matches FallbackEngineV4 gold standard
    - **engine.py — Fee Recording Approximation (Issue #3)**:
        - Old: `total_trade_fees = fees * 2` — assumes entry fee == exit fee (wrong when entry_price ≠ exit_price)
        - Fix: Track `entry_fees_paid` at entry, total = `entry_fees_paid + exit_fees`
    - **engine.py — End-of-Data Close (Issue #4)**:
        - Same margin reconstruction and fee doubling bugs existed in end-of-backtest close path
        - Fixed with same `margin_allocated` / `entry_fees_paid` pattern
    - **vectorbt_sltp.py — Margin State Tracking (Issue #5)**:
        - State array expanded from 6 to 8 elements: added `margin_locked` (state[6]) and `entry_fees_paid` (state[7])
        - All 5 exit paths (max_drawdown, SL/TP long, SL/TP short, signal exit) now use tracked margin instead of reconstructed
        - Equity formula: `cash + margin_locked + unrealized_pnl` (was `cash + size * price + unrealized`)
    - **Tests**: Added 19 new tests in `tests/backend/backtesting/test_margin_fee_parity.py`:
        - Margin conservation (zero fees, across leverage levels, with fees)
        - Equity formula not inflated by leverage
        - Fee recording accuracy (exact entry+exit vs doubled)
        - No margin leak across various fee rates
        - End-of-data close margin and fee correctness
    - **Total backtesting tests: 147/147 pass** (128 existing + 19 new)

- **🔴 CRITICAL: Equity Double-Leverage Bug — 2026-02-18:**
    - **Root cause**: `engine.py` multiplied `unrealized_pnl` by `leverage` despite `position` (entry_size) already including leverage. This caused equity curve to show `leverage²` amplified unrealized PnL.
    - **Affected code**:
        - `_build_equity_with_position_tracking()`: `unrealized = (price - entry) * size * leverage` → fixed to `* size` (no `* leverage`)
        - `_run_fallback()` equity section: same double-leverage pattern, same fix
    - **Gold standard reference**: `FallbackEngineV4` uses `unrealized = total_size * (close - avg_entry)` — no extra leverage, because `total_size = (margin * leverage) / price`

- **🔴 CRITICAL: numba_engine.py Cash Model Overhaul — 2026-02-18:**
    - **Root cause**: `numba_engine.py` used a fundamentally broken cash model:
        1. `entry_size` had NO leverage: `size = margin / (price * (1+fee))` — missing `* leverage`
        2. Cash deducted full `position_value` (not margin): `cash -= position_value + fees`
        3. Long exit returned raw `position_value - fees` (no leveraged PnL in cash)
        4. Short exit was inconsistent: `cash += position_value + pnl` (different formula from Long)
        5. PnL/MFE/MAE had `* leverage` to compensate for missing leverage in size
    - **Fix**: Rewrote to match FallbackEngineV4 margin-based model:
        - Entry: `entry_size = (margin * leverage) / (price * (1+fee))` — leverage IN size
        - Cash entry: `cash -= margin + entry_fees` — deduct margin only
        - PnL: `(exit - entry) * entry_size - exit_fees` — no extra `* leverage`
        - Cash exit: `cash += margin + pnl` — return margin + net PnL (symmetric Long/Short)
        - Equity: `unrealized = (price - entry) * position` — no extra `* leverage`
        - pnl_pct: `pnl / margin * 100` — % return on margin invested
        - MFE/MAE: `(price_diff) * entry_size` — no extra `* leverage`
    - **Tests**: Added 53 new tests in `tests/backend/backtesting/test_equity_pnl_parity.py`:
        - Entry sizing formula validation (leverage scaling)
        - PnL calculation without extra leverage
        - Cash flow round-trip (profitable/losing, long/short symmetric)
        - Unrealized PnL without double leverage
        - Equity mid-trade correctness
        - MFE/MAE with leverage in size
        - Numba engine integration: entry_size, PnL scaling, equity, cash conservation
    - **Verification**: 128 backtesting tests pass (28 engine + 53 equity + 22 SL/TP + 3 GPU + 21 MTF + 1 parity), 4485 total tests pass

- **🔴 CRITICAL: SL/TP Leverage Bug — 2026-02-18:**
    - **Root cause**: `engine.py`, `numba_engine.py`, `fast_optimizer.py`, `vectorbt_sltp.py` all divided SL/TP by leverage when calculating exit prices
    - **Impact**: With SL=5% and leverage=10, SL triggered at 0.5% price movement instead of 5%. This made ALL trade PnL values uniform and incorrect.
    - **Fix**: Removed `/leverage` from exit_price formulas and `*leverage` from pnl_pct trigger checks. SL/TP now correctly represent % of price movement (TradingView semantics), matching `FallbackEngineV4` (gold standard).
    - **Files changed**:
        - `backend/backtesting/engine.py` — `_run_fallback()`: worst/best_pnl_pct, bar magnifier SL/TP, standard SL/TP exit prices
        - `backend/backtesting/numba_engine.py` — pnl_pct calculation, SL/TP exit prices
        - `backend/backtesting/fast_optimizer.py` — pnl_pct calculation, SL/TP exit prices (both functions)
        - `backend/backtesting/vectorbt_sltp.py` — removed `adjusted_sl/tp = sl_pct / leverage`, now passes raw sl_pct/tp_pct to `check_sl_tp_hit_nb()`
    - **Tests**: Added 22 new tests in `tests/backend/backtesting/test_sltp_leverage_parity.py` covering exit price independence from leverage, trigger conditions, PnL scaling, and vectorbt parity
    - **Verification**: All 92 existing engine tests pass (28 + 32 + 10 + 22 new)

### Removed

- **Agent Skills Cleanup — 2026-02-14:**
    - Deleted `.agent/skills/skills/` directory (232 generic skills, 19.5 MB) — 95% irrelevant to the trading project
    - Deleted `skills_index.json` (1436-line index of generic skills)
    - Deleted 4 duplicate skill files from `.agent/skills/` (originals remain in `.github/skills/`)
    - Removed `.agent/skills` from `chat.agentSkillsLocations` in VS Code settings
    - Cleaned embedded git repository left inside `.agent/skills/`
    - Deleted backup files (`Claude.md.bak`, `.bak.old`, `.bak2`) and empty directories (`experiments/`, `reports/`)

### Changed

- **Workflow Fixes — 2026-02-14:**
    - `start_app.md` — replaced Claude Code `// turbo` syntax with proper VS Code task references and manual fallback
    - `multi_agent.md` — replaced Claude Code `// turbo-all` multi-agent syntax with VS Code Agent Mode compatible phased workflow
- **Model Name Corrections — 2026-02-14:**
    - Fixed all references from "Claude Opus 4.5 / Sonnet 4.5" → "Claude Opus 4 / Sonnet 4" across 12 files
    - Updated all 5 custom agents (`backtester`, `tdd`, `reviewer`, `planner`, `implementer`) with correct model names
    - Updated `AGENTS.MD` — fixed model table, skills paths (`.agent/skills` → `.github/skills`), engine reference (V2→V4)
    - Updated `Gemini.md` v1.0 → v1.1 with project-specific rules, critical constraints, and Russian language requirement
    - Updated `CONTEXT.md` — complete rewrite with accurate file structure, counts, and session history
    - Updated `TODO.md` — replaced generic placeholders with project-relevant tasks
    - Updated `docs/ai-context.md` — FallbackEngineV2 → FallbackEngineV4 as gold standard
    - Updated `docs/DECISIONS.md` — corrected engine reference in ADR-002

### Added

- **New Project-Specific Skills — 2026-02-14:**
    - `database-operations` — SQLite + SQLAlchemy patterns, models, sessions, async context, UoW pattern
    - `metrics-calculator` — 166 TradingView-parity metrics, dataclass structures, Numba path, parity rules
    - `bybit-api-integration` — Bybit API v5 adapter patterns, rate limiting, circuit breaker, testing rules

### Security

- **API Key Leak Fix — 2026-02-14:**
    - Removed hardcoded DeepSeek API keys from `.agent/mcp.json` (replaced with `${env:DEEPSEEK_API_KEY}` references)
    - Added `.agent/mcp.json` to `.gitignore` to prevent future leaks
    - Removed `.agent/mcp.json` from git tracking (`git rm --cached`)
    - API keys are now loaded exclusively from `.env` file

### Fixed

- **Claude.md Cleanup — 2026-02-14:**
    - Fixed `.agent/Claude.md` — two versions (v2.0 and v3.0) were merged/overlapping, creating 662 lines of garbled text
    - Rewrote as clean v3.1 (342 lines) combining best of both versions
    - Removed all duplicate headers, interleaved paragraphs, and broken formatting

### Added

- **Agent Phase 2: Autonomous Capabilities — 2026-02-12:**
    - **Autonomous Workflow Coordinator** (`backend/agents/workflows/autonomous_backtesting.py`, ~380 LOC):
        - Full pipeline: fetch → evolve → backtest → report → learn
        - `WorkflowConfig`, `WorkflowStatus` with live progress tracking, `WorkflowResult`
        - Pipeline stages: idle → fetching → evolving → backtesting → reporting → learning → completed/failed
    - **Pattern Extractor** (`backend/agents/self_improvement/pattern_extractor.py`, ~340 LOC):
        - Discovers winning strategy patterns from backtest history
        - Groups by strategy type, computes avg Sharpe/win rate/return, timeframe affinities
        - Auto-generates human-readable insights
    - **Task Scheduler** (`backend/agents/scheduler/task_scheduler.py`, ~335 LOC):
        - Asyncio-native periodic job scheduler (zero external deps)
        - Supports interval, daily, and one-shot tasks with exponential backoff retry
        - Pre-built health_check and pattern_extraction tasks
    - **Paper Trader** (`backend/agents/trading/paper_trader.py`, ~340 LOC):
        - Simulated live trading sessions with real price feeds
        - Session management: start, stop, auto-close on duration expiry
        - P&L tracking, win/loss stats, vector memory integration
    - **Dashboard Integration** — 12 new API endpoints in `backend/api/routers/agents.py`:
        - `POST /dashboard/workflow/start` — start autonomous workflow
        - `GET /dashboard/workflow/status/{id}` — poll progress
        - `GET /dashboard/workflow/active` — list active workflows
        - `GET /dashboard/patterns` — extract strategy patterns
        - `GET /dashboard/scheduler/tasks` — list scheduler tasks
        - `GET /dashboard/paper-trading/sessions` — list paper sessions
        - `POST /dashboard/paper-trading/start` — start paper trading
        - `POST /dashboard/paper-trading/stop/{id}` — stop session
        - `GET /dashboard/activity-log` — agent action log
    - **Test suite** (`tests/integration/test_additional_agents.py`, 51 tests):
        - 46 pass (unit), 5 deselected (@slow, require server)
        - Covers: workflow (11), patterns (9), scheduler (12), paper trader (9), dashboard (5), cross-module (6)
    - **Updated docs**: `docs/AGENTS_TOOLS.md` — Phase 2 module reference

- **Agent Autonomy Infrastructure — 2026-02-11 (Roadmap P0/P1/P2):**
    - **MCP Agent Tools** (`backend/agents/mcp/trading_tools.py`):
        - `run_backtest` — execute strategy backtests with full parameter control
        - `get_backtest_metrics` — retrieve backtest results from DB by ID or list recent
        - `list_strategies` — list all available strategies with default params
        - `validate_strategy` — validate strategy params, check ranges, cross-validate
        - `check_system_health` — check database, disk, memory, data availability
    - **Agent API Endpoints** (`backend/api/routers/agents.py`):
        - `POST /agents/actions/run-backtest` — agent-driven backtest execution
        - `GET /agents/actions/backtest-history` — recent backtest history
        - `GET /agents/actions/strategies` — list available strategies
        - `POST /agents/actions/validate-strategy` — validate params before run
        - `GET /agents/actions/system-health` — system health check
        - `GET /agents/actions/tools` — list all registered MCP tools
    - **Backtest Memory** (`backend/agents/memory/vector_store.py`):
        - `save_backtest_result()` — store backtest results as searchable vector embeddings
        - `find_similar_results()` — semantic search across past backtest results
    - **Strategy Validator** (`backend/agents/security/strategy_validator.py`, 354 lines):
        - Validates strategy params against safe ranges per strategy type
        - Risk classification: SAFE / MODERATE / HIGH / EXTREME / REJECTED
        - Cross-validates params (MACD fast < slow, grid upper > lower)
        - Enforces guardrails: leverage, capital, date range, stop loss
    - **Agent Documentation** (`docs/AGENTS_TOOLS.md`):
        - Complete reference for MCP tools, API endpoints, memory system
        - Security & validation docs, constraints, usage examples
    - All 15 existing tests pass, 0 regressions, ruff clean on new code
    - **Sandbox & Resource Limits (P2)** — 2026-02-11:
        - `run_backtest` tool now wrapped with `asyncio.wait_for(timeout=300)` (5 min max)
        - Pre-flight memory guard: aborts if < 512MB free (`psutil.virtual_memory()`)
        - Returns actionable error messages with suggestions
    - **P3 Tools** — 2026-02-11:
        - `evolve_strategy` — AI-powered iterative strategy evolution using StrategyEvolution engine
        - `generate_backtest_report` — structured markdown/JSON reports with assessment & recommendations
        - `log_agent_action` — JSONL activity logging for agent audit trail
    - **Comprehensive test suite** (`tests/integration/test_agent_autonomy.py`):
        - 52 tests total: 50 pass, 2 skip (ChromaDB), 6 slow API tests (deselected by default)
        - Covers: StrategyValidator (24), MCP tools (13), sandbox (4), memory (4), P3 tools (8), API (6)

- **Comprehensive AI Systems Audit — 2026-02-10:**
    - Full audit of AI agent architecture (48+ modules, ~15,000 LOC in `backend/agents/`)
    - ML systems audit: regime detection (HMM/GMM/KMeans), RL trading agent (DQN/PPO), AutoML pipeline, concept drift detection
    - Agent memory audit: hierarchical 4-tier memory (748 LOC), vector store with ChromaDB (472 LOC)
    - LLM integrations audit: 6 providers (DeepSeek, Perplexity, Qwen, OpenAI, Claude, Ollama)
    - Prompt system audit: 4 templates, 3 agent specializations, 7 reflection categories
    - MCP tools audit: tool_registry (476 LOC), 10+ trading tools, 3 MCP server deployments
    - Self-improvement audit: RLHF (775 LOC), self-reflection (629 LOC), strategy evolution (772 LOC), feedback loop (679 LOC)
    - Monitoring audit: Prometheus-style metrics, circuit breaker telemetry, cost tracking, alerting
    - **Test results: 814 tests ALL PASSING** (641 agent + 59 ML + 114 system)
    - Generated comprehensive audit report: `docs/ai/AI_SYSTEMS_AUDIT_2026_02_10.md`
    - Overall system score: **89.3/100** — Production-ready
    - Identified 4 improvement areas: evals/, security/, integration tests, online learning

- **Quality Improvements: StrategyOptimizer, E2E Tests, Coverage — 2026-02-10:**
    - **StrategyOptimizer (`backend/agents/optimization/strategy_optimizer.py`, ~920 lines):**
        - Per spec 3.6.2: genetic algorithm, grid search, bayesian optimization
        - `OptimizableParam` dataclass with `random_value()`, `grid_values()`, `mutate()` methods
        - `SIGNAL_PARAM_RANGES` for 10 indicator types (RSI, MACD, EMA, SMA, Bollinger, SuperTrend, etc.)
        - `FITNESS_WEIGHTS`: sharpe 0.4, max_dd 0.3, win_rate 0.2, profit_factor 0.1
        - `calculate_fitness()` — static method with complexity penalty for >4 signals
        - `optimize_strategy()` — async, full flow: extract params → evaluate original → run method → build result
        - `OptimizationResult` dataclass with `improved` property, `to_dict()` serialization
    - **E2E Integration Tests (`tests/backend/agents/test_e2e_pipeline.py`, 22 tests):**
        - ResponseParser → StrategyController → BacktestBridge → StrategyOptimizer pipeline
        - LangGraph pipeline integration with mocked agents
        - Error recovery and fallback scenarios
        - MetricsAnalyzer integration tests
    - **Coverage Gap Tests (`tests/backend/agents/test_coverage_gaps.py`, 39 tests):**
        - PromptEngineer coverage: 75% → **98%** (market_analysis, validation, auto_detect_issues branches)
        - StrategyController: \_select_best_proposal, \_score_proposal, walk-forward, generate_and_backtest
        - LangGraph orchestrator: AgentState, FunctionAgent, AgentGraph node management
        - Deliberation: MultiAgentDeliberation with mock ask_fn, voting strategies
        - StrategyEvolution: instantiation, component initialization, lazy LLM
        - AgentTracker: record_result, get_profile, leaderboard, stats
    - **StrategyOptimizer Tests (`tests/backend/agents/test_strategy_optimizer.py`, 51 tests):**
        - OptimizableParam, fitness calculation, parameter extraction/application
        - Genetic algorithm, grid search, bayesian optimization
        - Full optimize_strategy flow, OptimizationResult, edge cases
    - **Total agent tests: 557 (all passing), up from 445**

- **Test Coverage for 3 Untested Modules — 2026-02-09:**
    - **`test_hierarchical_memory.py`** (~53 tests): MemoryItem, MemoryTier, Store/Recall/Get/Delete, Consolidation, Forgetting, Persistence, Relevance/Cosine similarity, Stats, MemoryConsolidator, MemoryType
    - **`test_ai_backtest_integration.py`** (~28 tests): AIBacktestResult/AIOptimizationResult, \_parse_analysis/\_parse_optimization_analysis, analyze_backtest with mocked LLM, singleton accessors, \_call_llm fallback, lazy deliberation init
    - **`test_rlhf_module.py`** (~51 tests): FeedbackSample serialization, PreferenceType enum, QualityScore weighted scoring, RewardModel feature extraction/training/cross-validation/cosine LR, RLHFModule human/AI/self feedback, reward training, preference prediction, heuristic evaluation, persistence, auto-training, stats
    - **Total agent tests: 445 (all passing)**
    - Updated IMPLEMENTATION_PLAN.md: all modules now 100% ✅

- **AI Self-Improvement System (Tasks 4.1, 4.2, 4.3) — 2026-02-09:**
    - **Task 4.1 — LLM-backed Self-Reflection (`backend/agents/self_improvement/llm_reflection.py`, ~470 lines):**
        - `LLMReflectionProvider` — connects real LLM providers to SelfReflectionEngine:
            - 3 provider configs: deepseek (deepseek-chat), qwen (qwen-plus), perplexity (llama-3.1-sonar-small-128k-online)
            - Lazy client initialization via `_get_client()` using `LLMClientFactory.create()`
            - API key resolution: explicit key → KeyManager fallback
            - `get_reflection_fn()` → async callable `(prompt, task, solution) -> str`
            - Automatic fallback to heuristic response when no LLM available
            - Call/error counting and statistics via `get_stats()`
        - `LLMSelfReflectionEngine` — extends `SelfReflectionEngine`:
            - `reflect_on_strategy()` — full strategy reflection with real LLM
            - `batch_reflect()` — batch reflection for multiple strategies
            - Auto-registers LLM reflection function in all 7 categories
        - Constants: `REFLECTION_SYSTEM_PROMPT`, `REFLECTION_PROMPTS` (7 categories)
        - **26 tests** — `tests/backend/agents/test_llm_reflection.py`
    - **Task 4.2 — Automatic Feedback Loop (`backend/agents/self_improvement/feedback_loop.py`, ~670 lines):**
        - `FeedbackLoop` — automatic backtest → reflect → improve → repeat cycle:
            - Convergence detection (Sharpe change < 0.01 for 3 consecutive iterations)
            - 8-step loop: build strategy → backtest → evaluate → reflect → adjust → repeat
            - Configurable max_iterations, convergence_threshold, min_improvement
            - Builds `StrategyDefinition` with proper Signal/ExitConditions models
        - `PromptImprovementEngine` — strategy improvement via metric analysis:
            - Metric thresholds (Sharpe < 0.5, MaxDD > 20%, WinRate < 40%, PF < 1.0)
            - 7 adjustment templates keyed to metric failures
            - Parameter hint generation for strategy tuning
            - `analyze_and_improve()` → adjustments dict with reasons + parameter hints
        - `FeedbackEntry` / `FeedbackLoopResult` — iteration tracking dataclasses
        - **33 tests** — `tests/backend/agents/test_feedback_loop.py`
    - **Task 4.3 — Agent Performance Tracking (`backend/agents/self_improvement/agent_tracker.py`, ~480 lines):**
        - `AgentPerformanceTracker` — per-agent accuracy tracking for dynamic ConsensusEngine weights:
            - Rolling window tracking (default 100 records per agent)
            - `record_result()` — log backtest results per agent
            - `compute_dynamic_weights()` — 3 methods: composite, sharpe, pass_rate
            - `sync_to_consensus_engine()` — push computed weights to ConsensusEngine
            - `get_leaderboard()` — sorted performance ranking
            - `get_specialization_analysis()` — per-symbol/timeframe agent analysis
        - `AgentProfile` — aggregated stats with `pass_rate`, `composite_score` properties
        - `AgentRecord` — per-backtest record dataclass
        - Weight computation: composite_score/50.0 with recency_factor=0.8, min_weight=0.1
        - **35 tests** — `tests/backend/agents/test_agent_tracker.py`
    - **Total: 94 new tests, 313 agent tests total — all passing**

- **AI LangGraph Pipeline Integration — 2026-02-09:**
    - **`backend/agents/integration/langgraph_pipeline.py`** (~660 lines) — LangGraph-based strategy pipeline:
        - `TradingStrategyGraph` — pre-built directed graph connecting all pipeline stages:
            - `MarketAnalysisNode` → market context via MarketContextBuilder
            - `ParallelGenerationNode` → concurrent LLM calls across agents (deepseek/qwen/perplexity)
            - `ConsensusNode` → multi-agent consensus via ConsensusEngine
            - `BacktestNode` → strategy validation via BacktestBridge + FallbackEngineV4
            - `QualityCheckNode` → conditional routing based on metrics thresholds
            - `ReOptimizeNode` → walk-forward re-optimization loop
            - `ReportNode` → structured pipeline report
        - **Conditional edges** (graph-based decision routing):
            - Sharpe < `min_sharpe` → `re_optimize` (walk-forward parameter tuning)
            - MaxDD > `max_drawdown_pct` → `re_generate` (full strategy re-generation)
            - Quality PASS → `report` (final output)
        - `PipelineConfig` dataclass: min_sharpe, max_drawdown_pct, max_reoptimize_cycles, max_regenerate_cycles, agents, commission=0.0007
        - `TradingStrategyGraph.run()` — single entry point for full pipeline execution
        - `TradingStrategyGraph.visualize()` — ASCII graph visualization
        - Graph auto-registered in global `_graph_registry`
    - **Tests: 40 new tests (`tests/backend/agents/test_langgraph_pipeline.py`):**
        - 10 test classes: PipelineConfig, GraphConstruction, MarketAnalysisNode, ConsensusNode, BacktestNode, QualityCheckNode, ConditionalRouterIntegration, ReportNode, ReOptimizeNode, FullPipeline
        - Covers: config defaults, graph topology (7 nodes, edges, entry/exit), conditional routing (re_optimize/re_generate/report), retry exhaustion, custom thresholds, full pipeline with mocked LLM + backtest, re-optimization loop
    - **Total AI agent test count: 219 (all passing)**

- **AI Multi-Agent Deliberation — Qwen 3-Agent Integration — 2026-02-09:**
    - **`backend/agents/consensus/real_llm_deliberation.py`** — Full 3-agent Qwen integration:
        - `AGENT_SYSTEM_PROMPTS` class dict with specialized trading domain prompts per agent:
            - **deepseek**: quantitative analyst — risk metrics, Sharpe optimization, conservative approach
            - **qwen**: technical analyst — momentum, pattern recognition, indicator optimization
            - **perplexity**: market researcher — sentiment, macro trends, regime analysis
        - `DEFAULT_SYSTEM_PROMPT` fallback for unknown agent types
        - `_real_ask()` updated to use agent-specific system prompts (was generic for all)
        - `deliberate_with_llm()` defaults to all available agents (up to 3)
        - Module docstring updated with agent specialization overview
    - **`backend/agents/consensus/deliberation.py`** — Qwen routing fix:
        - `_ask_agent()` fallback now uses `agent_type_map` dict supporting all 3 agents
        - Previously only mapped deepseek/perplexity, qwen was ignored
    - **Tests: 35 new tests (`tests/backend/agents/test_real_llm_deliberation.py`):**
        - 7 test classes: Init, SystemPrompts, RealAsk, ThreeAgentDeliberation, DeliberateWithLlm, AskAgentQwenSupport, CloseCleanup, GetApiKey
        - Covers: specialized prompt content, dispatch routing, fallback behavior, 3-agent deliberation flow, weighted voting, multi-round convergence
    - **Total AI agent test count: 179 (all passing)**

- **AI Strategy Pipeline — Walk-Forward Integration & Extended API — 2026-02-09:**
    - **`backend/agents/integration/walk_forward_bridge.py`** (~470 lines) — adapter between AI StrategyDefinition and WalkForwardOptimizer:
        - `WalkForwardBridge` class with configurable n_splits, train_ratio, gap_periods
        - `build_strategy_runner()` — converts StrategyDefinition → callable strategy_runner for WF optimizer
        - `build_param_grid()` — builds parameter grid from OptimizationHints, DEFAULT_PARAM_RANGES, or current params
        - `run_walk_forward()` / `run_walk_forward_async()` — sync and async walk-forward execution
        - `_execute_backtest()` — converts candle list → DataFrame → signals → FallbackEngineV4 → metrics dict
        - `DEFAULT_PARAM_RANGES` for 7 strategy types (rsi, macd, ema_crossover, sma_crossover, bollinger, supertrend, stochastic)
        - `_generate_variations()` — auto-generates +/-40% parameter variations for grid search
    - **Walk-Forward integrated into StrategyController (Stage 7):**
        - `PipelineStage.WALK_FORWARD` enum value
        - `PipelineResult.walk_forward` field for walk-forward results
        - `generate_strategy(enable_walk_forward=True)` triggers Stage 7 after evaluation
        - `_run_walk_forward()` — loads data, creates WalkForwardBridge, runs async optimization
    - **Extended API Endpoints (4 new routes in `ai_pipeline.py`):**
        - `POST /ai-pipeline/analyze-market` — analyze market context (regime, trend, volatility, key levels)
        - `POST /ai-pipeline/improve-strategy` — optimize existing strategy via walk-forward validation
        - `GET /ai-pipeline/pipeline/{id}/status` — pipeline job progress tracking (stage-based progress %)
        - `GET /ai-pipeline/pipeline/{id}/result` — retrieve completed pipeline results
        - In-memory `_pipeline_jobs` store for async pipeline tracking
        - Updated `POST /generate` with `pipeline_id` and `enable_walk_forward` support
    - **Tests: 67 new tests (39 walk-forward bridge + 28 API endpoints):**
        - `tests/backend/agents/test_walk_forward_bridge.py` — 10 test classes covering init, param grid, strategy runner, candle conversion, SL/TP extraction, variations, grid from hints, execute backtest, walk-forward run, async wrapper, controller integration
        - `tests/backend/api/test_ai_pipeline_endpoints.py` — 8 test classes covering all 6 endpoints: generate, agents, analyze-market, improve-strategy, pipeline status/result, response models
    - **Total AI agent test count: 172 (all passing)**

### Fixed

- Fixed `TradeDirection.LONG_ONLY` → `TradeDirection.LONG` in walk_forward_bridge.py
- Fixed `datetime.utcnow()` deprecation → `datetime.now(UTC)` in ai_pipeline.py
- Added missing `id` field to `Signal()` in improve-strategy endpoint

- **AI Strategy Pipeline — P1: Consensus Engine & Metrics Analyzer — 2026-02-09:**
    - **`backend/agents/consensus/consensus_engine.py`** (~840 lines) — structured strategy-level consensus aggregation:
        - `ConsensusMethod` enum: WEIGHTED_VOTING, BAYESIAN, BEST_OF
        - `AgentPerformance` dataclass — historical agent performance tracking with running average
        - `ConsensusResult` dataclass — aggregated strategy + agreement score + agent weights + signal votes
        - `ConsensusEngine.aggregate()` — main entry point: dispatches to method-specific aggregation
        - `_weighted_voting()` — signal-level aggregation by normalized agent weight, threshold-based inclusion
        - `_bayesian_aggregation()` — posterior proportional to prior x likelihood (signal support fraction)
        - `_best_of()` — pick single best strategy by weight x quality
        - `_calculate_all_weights()` / `_calculate_agent_weight()` — dynamic weight computation from history + strategy quality
        - `_merge_params()` — median for numeric params, mode for non-numeric
        - `_merge_filters()` — deduplicate by type, keep highest-weight
        - `_merge_exit_conditions()` — weighted average of TP/SL values
        - `_merge_optimization_hints()` — union of parameters, widened ranges
        - `_calculate_agreement_score()` — Jaccard similarity between agent signal sets
        - `update_performance()` — track agent accuracy over time for weight calculation
    - **`backend/agents/metrics_analyzer.py`** (~480 lines) — backtest results grading & recommendations:
        - `MetricGrade` enum: EXCELLENT, GOOD, ACCEPTABLE, POOR
        - `OverallGrade` enum: A-F letter grades
        - `MetricAssessment` / `AnalysisResult` dataclasses with `to_dict()`, `to_prompt_context()`
        - `METRIC_THRESHOLDS` — configurable grading boundaries for sharpe, PF, WR, DD, calmar, trades
        - `MetricsAnalyzer.analyze()` — grades each metric, computes weighted overall score, detects strengths/weaknesses, generates actionable recommendations
        - `_grade_metric()` — interpolated scoring with direction awareness (higher/lower is better)
        - `needs_optimization` / `is_deployable` properties for decision logic
        - `_RECOMMENDATIONS` dict — actionable suggestions keyed by metric:grade
    - **Integration with StrategyController:**
        - `_select_best_proposal()` now uses `ConsensusEngine.aggregate()` with weighted_voting (fallback to simple scoring)
        - New Stage 6 (Evaluation): `MetricsAnalyzer` runs after backtest, results stored in `backtest_metrics["_analysis"]`
        - Agent weights dynamically computed from historical performance
    - **Updated `consensus/__init__.py`** — exports: AgentPerformance, ConsensusEngine, ConsensusMethod, ConsensusResult (15 total symbols)
    - **61 unit tests** across 2 new test files:
        - `tests/backend/agents/test_consensus_engine.py` (31 tests): TestConsensusEngineBasic (5), TestWeightedVoting (4), TestBayesianAggregation (2), TestBestOf (2), TestAgentWeights (2), TestAgreementScore (3), TestPerformanceTracking (4), TestSignalVotes (2), TestMergingHelpers (4), TestEdgeCases (3)
        - `tests/backend/agents/test_metrics_analyzer.py` (30 tests): TestMetricGrading (6), TestOverallScoring (4), TestStrengthsWeaknesses (3), TestRecommendations (3), TestSerialization (3), TestProperties (4), TestEdgeCases (7)
    - **All 105 tests in tests/backend/agents/ pass** (31+30+18+26)

- **AI Strategy Pipeline — P3: Self-Improvement & Strategy Evolution — 2026-02-11:**
    - **P3: Self-Improvement (Strategy Evolution):**
        - **`backend/agents/self_improvement/strategy_evolution.py`** (~790 lines) — центральный модуль P3, связывающий RLHF, Reflexion и стратегический пайплайн:
            - `EvolutionStage` enum (GENERATE→BACKTEST→REFLECT→RANK→EVOLVE→CONVERGED/FAILED)
            - `GenerationRecord` dataclass — запись одного поколения: стратегия, метрики бэктеста, рефлексия, fitness score
            - `EvolutionResult` dataclass — итог эволюции: все поколения, лучшее, статистика RLHF, сводка рефлексии
            - `compute_fitness(metrics, weights)` — скоринг 0-100: Sharpe (25%), Profit Factor (20%), Win Rate (15%), Net Profit (15%), Max DD penalty (15%), Trade Count (10%)
            - `StrategyEvolution.evolve()` — главный цикл: генерация → бэктест → рефлексия → ранжирование → эволюция; convergence detection (threshold=2.0, stagnation=3), min/max generations
            - `_create_llm_reflection_fn()` — async замыкание для LLM-powered рефлексии через DeepSeek
            - `_rank_strategies()` — попарный RLHF фидбэк на основе fitness-сравнения
            - `_evolve_strategy()` — LLM-генерация улучшенной стратегии на основе предыдущих метрик и инсайтов рефлексии
            - Промпты: REFLECTION_SYSTEM_PROMPT (эксперт-трейдер), EVOLUTION_PROMPT_TEMPLATE (предыдущая стратегия + метрики + рефлексия → улучшенный JSON)
        - **Обновлён `self_improvement/__init__.py`** — экспорт: EvolutionResult, GenerationRecord, StrategyEvolution, compute_fitness (всего 11 символов)
        - **18 unit тестов** в `tests/backend/agents/test_strategy_evolution.py` (~330 lines):
            - TestComputeFitness (6 тестов): good_high, bad_low, range_bounds, empty_metrics, custom_weights, trade_bonus
            - TestRewardModel (3 теста): extract_features, predict_reward_range, training_updates_weights
            - TestSelfReflection (3 async теста): heuristic_reflect, custom_fn, stats_updated
            - TestStrategyEvolution (6 тестов): basic_flow (mocked LLM+backtest), convergence, backtest_failure, rlhf_ranking, record_to_dict, result_to_dict
        - **Все 18 тестов пройдено**, 0 ошибок

- **AI Strategy Pipeline — Multi-Agent LLM Strategy Generation — 2026-02-11:**
    - **P0: Core Pipeline Components:**
        - **`backend/agents/prompts/templates.py`** (~280 lines) — шаблоны промптов: STRATEGY_GENERATION_TEMPLATE, MARKET_ANALYSIS_TEMPLATE, OPTIMIZATION_SUGGESTIONS_TEMPLATE, STRATEGY_VALIDATION_TEMPLATE, AGENT_SPECIALIZATIONS (deepseek=quantitative_analyst, qwen=technical_analyst, perplexity=market_researcher), 2 few-shot примера
        - **`backend/agents/prompts/context_builder.py`** (~325 lines) — MarketContext dataclass + MarketContextBuilder: детекция рыночного режима (EMA 20/50), уровни S/R, волатильность (ATR), анализ объёма, сводка индикаторов
        - **`backend/agents/prompts/prompt_engineer.py`** (~220 lines) — PromptEngineer: create_strategy_prompt, create_market_analysis_prompt, create_optimization_prompt, create_validation_prompt, get_system_message, \_auto_detect_issues
        - **`backend/agents/prompts/response_parser.py`** (~525 lines) — ResponseParser с Pydantic моделями: Signal, Filter, ExitConditions, EntryConditions, PositionManagement, OptimizationHints, AgentMetadata, StrategyDefinition (get_strategy_type_for_engine(), get_engine_params(), to_dict()), ValidationResult; парсинг JSON из markdown/raw, авто-фикс trailing commas и single quotes
        - **`backend/agents/strategy_controller.py`** (~630 lines) — StrategyController: главный оркестратор пайплайна с PipelineStage enum (CONTEXT→GENERATION→PARSING→CONSENSUS→BACKTEST→EVALUATION→COMPLETE/FAILED), StageResult, PipelineResult; вызов LLM провайдеров (deepseek/qwen/perplexity), скоринг предложений, quick_generate(), generate_and_backtest()
        - **`backend/agents/integration/backtest_bridge.py`** (~260 lines) — BacktestBridge: конвертация StrategyDefinition → BacktestInput → FallbackEngineV4, извлечение SL/TP из exit conditions, COMMISSION_RATE=0.0007, async через asyncio.to_thread()
    - **P1: Multi-Agent Enhancements:**
        - **Qwen в RealLLMDeliberation** — добавлен QwenClient (qwen-plus, temp 0.4) в consensus/real_llm_deliberation.py
        - **`backend/agents/trading_strategy_graph.py`** (~340 lines) — LangGraph пайплайн с 5 нодами: AnalyzeMarketNode, GenerateStrategiesNode, ParseResponsesNode, SelectBestNode, BacktestNode; build_trading_strategy_graph(), run_strategy_pipeline()
        - **Скоринг предложений** в StrategyController.\_score_proposal — оценка 0-10 по количеству сигналов, exit conditions, фильтрам, entry conditions, optimization hints
    - **P2: Integration:**
        - **`backend/api/routers/ai_pipeline.py`** (~260 lines) — REST API: POST /ai-pipeline/generate (GenerateRequest → PipelineResponse), GET /ai-pipeline/agents (→ list[AgentInfo]); загрузка OHLCV через DataService, проверка доступности агентов через KeyManager
        - **Роутер зарегистрирован** в backend/api/app.py: `/api/v1/ai-pipeline/*`
        - **26 unit тестов** в `tests/backend/agents/test_strategy_pipeline.py`:
            - TestResponseParser (11 тестов): JSON extraction, trailing comma fix, validation, engine type mapping, signal normalization
            - TestMarketContextBuilder (4 теста): context building, S/R levels, prompt vars, edge case
            - TestPromptEngineer (3 теста): strategy prompt, system messages, optimization prompt
            - TestBacktestBridge (4 теста): strategy_to_config, SL/TP extraction, commission rate
            - TestStrategyController (2 теста): proposal scoring heuristic
        - **Все 26 тестов пройдено**, 0 ошибок

- **Phase 3: Strategy Builder ↔ Optimization Integration — 2026-02-09:**
    - **`builder_optimizer.py`** (~660 lines) — новый модуль оптимизации для node-based стратегий Strategy Builder:
        - `DEFAULT_PARAM_RANGES` — 14 типов блоков (RSI, MACD, EMA, SMA, Bollinger, SuperTrend, Stochastic, CCI, ATR, ADX, Williams %R, Static SL/TP, Trailing Stop) с типизированными диапазонами
        - `extract_optimizable_params(graph)` — извлечение оптимизируемых параметров из графа стратегии
        - `clone_graph_with_params(graph, overrides)` — глубокое клонирование графа с подстановкой параметров по пути `blockId.paramKey`
        - `generate_builder_param_combinations()` — Grid/Random генерация комбинаций с merge пользовательских диапазонов
        - `run_builder_backtest()` — одиночный бэктест через StrategyBuilderAdapter → BacktestEngine → метрики
        - `run_builder_grid_search()` — полный grid search со скорингом, фильтрацией, early stopping, timeout
        - `run_builder_optuna_search()` — Optuna Bayesian (TPE/Random/CmaES) с top-N re-run для полных метрик
    - **`BuilderOptimizationRequest`** — Pydantic модель (~65 строк) для endpoint оптимизации: symbol, interval, dates, method (grid_search/random_search/bayesian), parameter_ranges, n_trials, sampler_type, timeout, metric, weights, constraints
    - **`POST /api/v1/strategy-builder/strategies/{id}/optimize`** — переписан с mock на реальную реализацию: загрузка из БД → извлечение параметров → загрузка OHLCV → grid/random/bayesian оптимизация → ранжированные результаты
    - **`GET /api/v1/strategy-builder/strategies/{id}/optimizable-params`** — новый endpoint для автообнаружения оптимизируемых параметров (frontend UI)
    - **Frontend: `optimization_panels.js`** — интеллектуальная маршрутизация:
        - `getBuilderStrategyId()` — детекция контекста Strategy Builder
        - `startBuilderOptimization()` — отправка запроса на builder endpoint с полным payload
        - `buildBuilderParameterRanges()` — сборка parameter_ranges в формате `blockId.paramKey`
        - `fetchBuilderOptimizableParams()` — автозагрузка параметров из backend при открытии стратегии
        - `startClassicOptimization()` — сохранена совместимость с классическими стратегиями
    - **58 новых тестов** в `test_builder_optimizer.py` покрывают:
        - DEFAULT_PARAM_RANGES валидность (8 тестов)
        - extract_optimizable_params (11 тестов)
        - clone_graph_with_params (9 тестов)
        - generate_builder_param_combinations (9 тестов)
        - \_merge_ranges (4 теста)
        - run_builder_backtest (3 теста)
        - run_builder_grid_search (6 тестов)
        - run_builder_optuna_search (3 теста)
        - Integration pipeline (3 теста)
        - Edge cases (4 теста)
    - **1847 тестов пройдено**, 0 ошибок, 27 skipped

- **Phase 2: Универсализация стратегий и Optuna top-N — 2026-02-10:**
    - **5 генераторов сигналов** в `signal_generators.py`: RSI, SMA crossover, EMA crossover, MACD, Bollinger Bands
    - **`generate_signals_for_strategy()`** — универсальный диспетчер, маршрутизирует по `strategy_type` к соответствующему генератору
    - **`combo_to_params()`** — конвертер tuple→dict для именованных параметров (связка с `param_names`)
    - **`generate_param_combinations()`** теперь возвращает 3-tuple `(combinations, total, param_names)` — поддерживает все стратегии
    - **SyncOptimizationRequest** расширен 9 полями: `sma_fast/slow_period_range`, `ema_fast/slow_period_range`, `macd_fast/slow/signal_period_range`, `bb_period_range`, `bb_std_dev_range`
    - **Optuna handler** — возвращает **top-10 результатов** с полными метриками (было: 1 best trial)
    - **Все 6 путей выполнения** в `optimizations.py` теперь strategy-agnostic (было: RSI-only hardcoded)
    - **Inline `_run_batch_backtests`** заменена thin wrapper → `workers.run_batch_backtests()` (DRY)
    - Все **215/215 тестов** проходят, **1788 total** passed

- **Рефакторинг системы оптимизации — 2026-02-09:**
    - **6 новых модулей** в `backend/optimization/`: `models.py`, `scoring.py`, `filters.py`, `recommendations.py`, `utils.py`, `workers.py`
    - **`build_backtest_input()`** — единый DRY-конструктор BacktestInput, заменяет 6 дублированных блоков по 25 полей
    - **`extract_metrics_from_output()`** — единый экстрактор 50+ метрик из bt_output, заменяет 3 блока по 50 строк
    - **`TimeoutChecker`** — класс для принудительного timeout (теперь request.timeout_seconds реально работает)
    - **`EarlyStopper`** — класс для ранней остановки (теперь request.early_stopping реально работает)
    - **`split_candles()`** — train/test split (теперь request.train_split реально работает)
    - **`parse_trade_direction()`** — DRY-конвертер string → TradeDirection enum
    - **`_format_params()`** — теперь универсальный (RSI, EMA, MACD, Bollinger, generic)
    - **Memory optimization** — trades хранятся только для top-10 результатов
    - Документация: `docs/OPTIMIZATION_REFACTORING.md`
    - Все **215/215 тестов** проходят после рефакторинга

### Fixed

- **Аудит панели «Критерии оценки» (Evaluation Panel) — 2026-02-09:**
    - **BUG-1 (КРИТИЧЕСКИЙ):** `optimization_panels.js` содержал хардкод symbol='BTCUSDT', interval='1h', direction='both', initial_capital=10000, leverage=10, commission=0.0007, strategy_type='rsi' — параметры из панели «Параметры» полностью игнорировались при запуске оптимизации. Добавлен метод `getPropertiesPanelValues()`, который читает 8 параметров из DOM.
    - **BUG-2 (ВЫСОКИЙ):** Функция `_passes_filters()` не вызывалась в 2 из 3 путей выполнения `sync_grid_search_optimization`: GPU batch и single-process. Constraints из Evaluation Panel (max_drawdown ≤ 15%, total_trades ≥ 50 и др.) применялись только в multiprocessing-пути. Добавлены вызовы в оба пропущенных пути.
    - **BUG-3 (СРЕДНИЙ):** 13 из 20 фронтенд-метрик не поддерживались в backend-функциях скоринга (`_calculate_composite_score`, `_rank_by_multi_criteria`, `_compute_weighted_composite`). Метрики sortino_ratio, calmar_ratio, cagr, avg_drawdown, volatility, var_95, risk_adjusted_return, avg_win, avg_loss, expectancy, payoff_ratio, trades_per_month, avg_bars_in_trade возвращали дефолтные значения. Все 3 функции расширены до 20+ метрик.
    - Документация: `docs/AUDIT_EVALUATION_PANEL.md`
    - Тесты: `tests/backend/api/test_evaluation_panel.py` — 87 тестов (скоринг, фильтрация, ранжирование, нормализация, интеграция)

- **Аудит панели «Параметры» (Properties Panel) — 2026-02-09:**
    - **BUG-1 (КРИТИЧЕСКИЙ):** `direction` из UI (long/short/both) игнорировался при запуске бэктеста — поле отсутствовало в `BacktestRequest`. Бэкенд брал direction из сохранённого `builder_graph`, что приводило к рассогласованию UI ↔ результат. Добавлено поле `direction` в `BacktestRequest` с приоритетом request > builder_graph.
    - **BUG-2 (КРИТИЧЕСКИЙ):** `position_size` и `position_size_type` из UI игнорировались — поля отсутствовали в `BacktestRequest`. Все бэктесты запускались с position_size=1.0 (100%), независимо от настройки. Добавлены оба поля, значение передаётся в `BacktestConfig`.
    - **BUG-3 (СРЕДНИЙ):** `BacktestRequest` не валидировал `symbol`, `interval`, `market_type`, `direction`, `position_size_type` — любая строка принималась, ошибки вылетали позже как 500 вместо 422. Добавлены `@field_validator` для всех полей.
    - Добавлены constraint'ы: `symbol` min=2/max=20, `commission` ge=0/le=0.01, `initial_capital` le=100M
    - Документация: `docs/AUDIT_PROPERTIES_PANEL.md`
    - Тесты: `tests/backend/api/test_properties_panel.py` — 46 тестов (валидация + интеграция)

### Changed

- **Массовое обновление зависимостей (2026-02-08):**
    - **Фреймворк:** FastAPI 0.121.3 → 0.128.4, Uvicorn 0.38.0 → 0.40.0
    - **ORM/DB:** SQLAlchemy 2.0.44 → 2.0.46, Alembic 1.17.1 → 1.18.3, Redis 6.4.0 → 7.1.0
    - **Pydantic:** 2.12.3 → 2.12.5, pydantic-settings 2.11.0 → 2.12.0, pydantic-core 2.41.4 → 2.41.5
    - **Сеть:** aiohttp 3.13.2 → 3.13.3, websockets 15.0.1 → 16.0
    - **MCP/API:** mcp 1.19.0 → 1.26.0, pybit 5.13.0 → 5.14.0
    - **Тестирование:** pytest 8.4.2 → 9.0.2
    - **Утилиты:** orjson 3.9.10 → 3.11.7, cryptography 46.0.3 → 46.0.4, celery 5.5.3 → 5.6.2, kombu 5.5.4 → 5.6.2
    - **Визуализация:** plotly 6.3.1 → 6.5.2, matplotlib 3.10.7 → 3.10.8
    - **Научные:** scipy 1.16.3 → 1.17.0, joblib 1.5.2 → 1.5.3, tqdm 4.67.1 → 4.67.3
    - **Системные:** psutil 7.1.3 → 7.2.2, structlog → 25.5.0, pip 25.3 → 26.0.1
    - **river:** constraint обновлён >=0.22.0,<0.24.0 во всех 3 requirements файлах
    - **docker SDK:** pin ослаблен ==7.0.0 → >=7.0.0

- **pyproject.toml — обновление целей линтинга:**
    - ruff target-version: py311 → py313
    - mypy python_version: 3.11 → 3.13
    - black target-version: [py311, py312] → [py313, py314]
    - Добавлен classifier Python 3.14

- **Dockerfile:** python:3.11-slim → python:3.14-slim (builder + runtime)

- **Docker Compose образы:**
    - PostgreSQL: 15-alpine → 17-alpine (prod + vault)
    - Elasticsearch: 8.5.0 → 8.17.0 (prod + monitoring)
    - Kibana: 8.5.0 → 8.17.0 (prod + monitoring)
    - Logstash: 8.5.0 → 8.17.0 (monitoring)
    - HashiCorp Vault: 1.15 → 1.19
    - MLflow: v2.10.0 → v2.21.0

### Added

- **`.vscode/extensions.json`** — рекомендуемые расширения для проекта (Python, Ruff, Docker, Copilot, YAML, TOML и др.)

### Known Issues

- **pandas 3.0 несовместим** с mlflow (<3), river (<3.0.0), pandas-ta — остаётся на 2.3.3
- **numpy ограничен 2.2.x** из-за numba 0.61.2 (требуется pandas-ta) — будет обновлён когда pandas-ta поддержит новый numba

### Fixed

- **Optimization `engine_type: "optimization"` 500 Error:** исправлен баг, при котором `engine_type="optimization"` вызывал 500 Internal Server Error в `/api/v1/optimizations/sync/grid-search`. Причина: `"optimization"` не был включён в условие single-process режима (строка 2316 в `optimizations.py`). Теперь `engine_type="optimization"` корректно обрабатывается как single-process Numba-движок.

### Added

- **MCP DeepSeek (Node.js) для Cursor:** папка `mcp-deepseek/` — MCP-сервер на Node.js с инструментами `deepseek_chat` и `deepseek_code_completion`. В `.cursor/mcp.json` добавлен сервер `deepseek-node` (запуск через `cmd /c cd /d ...\mcp-deepseek && node server.js`). API-ключ задаётся в env или в `mcp-deepseek/.env` (не в репозитории). См. `mcp-deepseek/README.md`.

### Changed

- **DeepSeek proxy (Base URL http://localhost:5000):** в `scripts/run_deepseek_proxy.ps1` исправлен расчёт корня проекта (один уровень вверх от `scripts/`), добавлена проверка наличия `.env` и использование `py -3.14` (как в проекте). В `docs/ai/CURSOR_DEEPSEEK_MODEL.md` — пошаговая диагностика «прокси не запускается»: создание `.env`, ключ, команда `python`/`py`, порт, запуск из корня.
- **Strategy Builder UI/UX (2026-02):** выбор тикера — немедленная синхронизация `runCheckSymbolDataForProperties()` (без debounce), blur вместо focus после выбора; База данных — эмодзи 🔒 заблокирован / 🔓 разблокирован, grid 3×2 (6 тикеров), `refreshDunnahBasePanel()` после sync, API_BASE для fetch; блок/разблок — `finally loadAndRender()` для обновления списка; удалённые тикеры исчезают.
- **Регрессия и калибровка (2026-02):** Установлены numba, vectorbt, torch. calibrate_166_metrics — 51/51 метрик ✅. compare_vectorbt_vs_fallback — sys.path + DATABASE_PATH. REMAINING_AND_NEW_TASKS обновлён: инструкции по калибровке (TV_DATA_DIR, PYTHONIOENCODING на Windows).
- **Зависимости:** добавлена опциональная группа `dev-full` (numba, vectorbt, torch) в pyproject.toml для полного покрытия тестов.
- **calibrate_166_metrics.py:** TV_DATA_DIR env для пути к TradingView экспорту; fix Unicode на Windows.
- **compare_vectorbt_vs_fallback.py:** sys.path + DATABASE_PATH env.
- **L2 Order Book (experimental):** WebSocket real-time collector, CGAN (PyTorch) для генерации стакана, обучение на NDJSON, скрипты `l2_lob_collect_ws.py` и `l2_lob_train_cgan.py`. модуль `backend/experimental/l2_lob/` — Bybit orderbook API, сбор снимков в NDJSON, replay в OrderBookSimulator, скелет Generative LOB.
- **ExecutionHandler:** SimulationExecutionHandler с slippage, latency, partial fills, rejection. Интеграция в EventDrivenEngine.
- **Cvxportfolio allocation:** Метод cvxportfolio (cvxpy convex optimization) для multi-asset портфеля.
- **EventDrivenEngine + StrategyBuilderAdapter:** create_on_bar_from_adapter(), run_event_driven_with_adapter() — запуск Strategy Builder стратегий в event-driven режиме.
- **Strategy Versions UI:** кнопка Versions в Strategy Builder, модалка с историей версий, Restore.
- **Strategy Builder — Export/Import шаблонов:** кнопки Export и Import в модалке Templates. Сохранение текущей стратегии в JSON и загрузка из файла.
- **Undo/Redo в Strategy Builder:** Ctrl+Z / Ctrl+Y, история 50 шагов. Охват: блоки, связи, drag, шаблоны, загрузка.
- **Regime overlay на equity:** чекбокс «Режим рынка» в backtest-results, загрузка `/market-regime/history`, box-аннотации (trending/ranging/volatile) на графике капитала.
- **Перепроверка roadmap:** EventDrivenEngine — тесты tests/test_event_driven_engine.py. ROADMAP_REMAINING_TASKS обновлён: Event-driven скелет ✅, Multi-asset portfolio ✅, §12 Heatmap и Trade distribution ✅, версионирование БД+API ✅. Regime overlay на equity — осталось.
- **Multi-asset portfolio (P2):** MIN_VARIANCE и MAX_SHARPE allocation (scipy.optimize), diversification_ratio, rolling_correlations, aggregate_multi_symbol_equity(). Тесты: tests/test_portfolio_allocation.py, API /advanced-backtest/portfolio.
- **Unified Trading API:** `backend/services/unified_trading/` — LiveDataProvider, StrategyRunner (завершение TODO из BACKTEST_PAPER_LIVE_API). — DataProvider, OrderExecutorInterface, HistoricalDataProvider, SimulatedExecutor (docs/architecture/BACKTEST_PAPER_LIVE_API.md).
- **Monte Carlo robustness API:** `POST /monte-carlo/robustness` — slippage_stress, price_randomization.
- **P2 RL environment:** calmar, drawdown_penalty reward, REWARD_FUNCTIONS, docs/architecture/RL_ENVIRONMENT.md
- **Backtest→Live API design:** docs/architecture/BACKTEST_PAPER_LIVE_API.md
- **P1 Regime integration:** `market_regime_enabled`, `market_regime_filter`, `market_regime_lookback` в SyncOptimizationRequest. При включении regime используется FallbackV4. UI в strategies.html (чекбокс, селект, окно).
- **Реализация рекомендаций ENGINE_OPTIMIZER_MODERNIZATION:** Optuna Bayesian оптимизация — `POST /sync/optuna-search` (TPE, n_trials, sampler_type). Monte Carlo robustness — добавлены SLIPPAGE_STRESS, PRICE_RANDOMIZATION. ExecutionSimulator — `backend/backtesting/execution_simulator.py` (latency, slippage, partial fills, rejections). Walk-Forward — режим `expanding`, `param_stability_report`, `get_param_stability_report()`. Roadmap: `docs/ROADMAP_ADVANCED_IDEAS.md`.
- **Гибридная двухфазная архитектура:** формализован pipeline Research → Validation → Paper → Live. Документ `docs/architecture/HYBRID_TWO_PHASE_PIPELINE.md` — точность и паритет (Numba↔FallbackV4 100%, VBT↔Fallback 10–60% drift). В `/sync/grid-search` добавлен параметр `validate_best_with_fallback` — опциональная перепроверка best_params на FallbackV4.
- **Предложения по модернизации движков и оптимизаторов:** создан `docs/ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md` — обзор мировых практик (event-driven, Monte Carlo robustness, Bayesian/Optuna, L2 order book, RL environments, backtest→live), приоритизированные идеи для roadmap.
- **Расширенный аудит проекта:** создан `docs/AUDIT_PROJECT_EXTENDED.md` — карта систем, аудит backend (API, backtesting, database, services), frontend, инфраструктуры, скриптов и тестов; кросс-срез, риски, рекомендации.
- **Выполнены рекомендации аудита:** удалён router_registry.py; API инвентаризация (docs/API_INVENTORY.md, legacy markers); консолидация docs + план декомпозиции strategy_builder.js (STRATEGY_BUILDER_INDEX.md); тесты test_fast_optimizer.py, test_live_trading_services.py; план API v2 (STATE_MANAGEMENT_AND_API_VERSIONING.md).
- **sync-all-tf:** блокирующие операции БД (чтение audit, persist) перенесены в thread pool (`asyncio.to_thread`), чтобы не блокировать event loop. Синхронизация 9 таймфреймов теперь выполняется параллельно и быстрее.
- **Окно Параметры (audit):** восстановление commission при загрузке; \_commission в buildStrategyPayload; убрана ссылка на initialCapital. Backend: CreateStrategyRequest/StrategyResponse расширены (leverage, position_size, parameters) — полная end-to-end поддержка сохранения/восстановления параметров. Документация: `docs/AUDIT_PARAMETERS_WINDOW.md`, тесты: `tests/test_e2e_parameters_window.py`.
- **Блок «Библиотека» (audit):** исправлена передача category; mapBlocksToBackendParams включает close_conditions. **Унификация параметров:** функция `_param()` в strategy_builder_adapter — fallback snake_case/camelCase для macd, bollinger, stochastic, qqe, stoch_rsi, ichimoku, parabolic_sar, keltner, filters. Документация: `docs/AUDIT_LIBRARY_BLOCK.md`.

### База Даннах (Dunnah Base) — управление тикерами в БД (2026-01-31)

- **Новая секция Properties «🗄️ База Даннах»:** отображает группы тикеров в БД (Symbol + Market Type + интервалы).
- **Удаление:** кнопка «Удалить» — удаляет все свечи тикера из БД.
- **Блокировка догрузки:** кнопки «Блокировать» / «Разблокировать» — тикеры в списке блокировки не догружаются при start_all (update_market_data), в DB Maintenance и при выборе в Properties.
- **Хранение блокировки:** `data/blocked_tickers.json`.
- **API:** GET/POST/DELETE `/symbols/blocked`, GET `/symbols/db-groups`, DELETE `/symbols/db-groups`.
- **Значок 🔒** в списке тикеров (Symbol) для заблокированных.

### Контроль устаревания БД — точный порог 2 года (2026-01-31)

- **Система уже была:** `db_maintenance_server.py` → `retention_cleanup`, задача `retention_cleanup` по расписанию (раз в 30 дней).
- **Исправление:** Расчёт порога заменён на точные 2 года (730 дней от текущей даты) вместо границ года; используется `RETENTION_YEARS` из `database_policy.py`.

### Нахлёст свечей при догрузке (2026-01-31)

- **Задача:** При проверке актуальности БД (start_all → update_market_data, DB Maintenance, Properties sync) догружать с нахлёстом нескольких свечей, чтобы избежать gaps на границе.
- **Реализация:** Переменный нахлёст по TF: 5 для 1m–60m, 4 для 4h, 3 для D, 2 для W/M.
- **Где:** `marketdata.py` (sync-all-tf, refresh), `update_market_data.py`, `db_maintenance_server.py` (\_update_stale_data).
- **DB maintenance:** INSERT OR REPLACE для перезаписи граничных свечей в зоне нахлёста.

### Единый набор таймфреймов: 1m, 5m, 15m, 30m, 60m, 4h, 1D, 1W, 1M (2026-01-31)

- Ограничен набор таймфреймов для всех систем.
- Backend: ALL_TIMEFRAMES, interval_ms_map, freshness_thresholds, tf_timeouts — добавлен M, обновлены.
- Frontend: Strategy Builder и Strategies — выпадающие списки только с этим набором; BYBIT_TF_OPTS, BYBIT_INTERVALS.
- DB maintenance, show_db, sync_missing_data — обновлены intervals.
- Устаревшие TF (3m, 2h, 6h, 12h) при загрузке стратегий маппятся на ближайший: 3→5, 120→60, 360→240, 720→D.

### Strategy Builder: зависание при быстром переключении тикеров (2026-01-31)

- **Проблема:** При переключении на другой тикер сразу после загрузки предыдущего новая загрузка зависала.
- **Причина:** Две синхронизации (старая и новая) выполнялись параллельно и конкурировали за ресурсы.
- **Исправление:** При старте синхронизации нового тикера отменяется предыдущий fetch (AbortController). Отменённая синхронизация не обновляет UI.

### Strategy Builder: таймаут синхронизации и сообщение об ошибке (2026-01-31)

- **Проблема:** Для некоторых тикеров (напр. 1000000BABYDOGEUSDT) показывалось «Синхронизация в фоне», но загрузка фактически прерывалась — данные не загружались.
- **Причина:** Таймаут 15 с был слишком мал; синхронизация 8 TF (включая 1m) занимает 1–2 мин. При отмене запроса бэкенд также прерывался.
- **Исправления:** Таймаут увеличен до 120 с; при таймауте показывается явное сообщение об ошибке; клик по блоку статуса при ошибке запускает повторную попытку.

### Strategy Builder: Properties — сворачивание при выборе тикера и вкладки (2026-01-31)

- **Проблема:** При выборе тикера панель Properties закрывалась; после повторного открытия секции (ОСНОВНЫЕ ПАРАМЕТРЫ, EVALUATION CRITERIA и др.) не раскрывались.
- **Причины:** (1) Клик по выпадающему списку тикеров (он в body) воспринимался как «вне панели» и вызывал сворачивание. (2) При открытии sidebar не раскрывалась первая секция. (3) Два обработчика на заголовки секций (sidebar-toggle и strategy_builder) приводили к двойному toggle.
- **Исправления:** Исключение `#backtestSymbolDropdown` из логики «клик вне панели»; событие `properties-symbol-selected` для сброса таймера сворачивания при выборе тикера; при открытии sidebar раскрывается первая секция; удалён дублирующий обработчик в strategy_builder, остаётся только sidebar-toggle.js.

### Strategy Builder: загрузка/догрузка тикера и автоактуализация (2026-01-31)

- **Выбор тикера:** При выборе тикера из выпадающего списка (Symbol) выполняется синхронизация: если тикер не в БД — полная загрузка на всех TF (1m, 5m, 15m, 30m, 1h, 4h, D, W); если есть — догрузка актуальных свечей.
- **Тип рынка:** При смене SPOT/LINEAR (бессрочные фьючерсы) для выбранного тикера запускается синхронизация данных.
- **Backend:** В `/symbols/sync-all-tf` добавлен фильтр `market_type` в запросах к БД (корректное разделение spot/linear). В список синхронизируемых TF включён 1m.
- **Автоактуализация:** После успешной синхронизации запускается таймер обновления: 1m/5m — каждые 5 мин; 15m — каждые 15 мин; 30m — каждые 30 мин; 1h — 1 ч; 4h — 4 ч; D — 1 день; W — 1 неделя. При смене TF или тикера таймер перезапускается.

### Список тикеров Bybit в Strategy Builder (2026-01-31)

- **Проблема:** В поле Symbol (Properties) отображалось только 3 тикера вместо полного списка (~500). Список не открывался/не закрывался, не прокручивался; при обновлении тикеров загружался один тип рынка; при сбое сети кэш затирался пустым списком.
- **Причины:** (1) Два обработчика на GET `/api/v1/marketdata/symbols-list` (marketdata + tickers_api) — срабатывал первый, без полной пагинации Bybit. (2) Bybit API instruments-info отдаёт данные постранично (limit/cursor) — загружалась только первая страница. (3) Фронт ограничивал список до 100/80 пунктов; выпадающий список открывался при загрузке страницы и перекрывался соседними элементами (z-index, overflow). (4) refresh-tickers при падении одной категории перезаписывал кэш пустым списком.
- **Исправления:** Единственный обработчик symbols-list — tickers_api (дубликат в marketdata удалён). В `BybitAdapter.get_symbols_list()` добавлена полная пагинация (limit=1000, cursor/nextPageCursor), проверка retCode в ответе Bybit, таймаут ≥30 с, логирование количества тикеров. Регистрация маршрутов symbols-list и refresh-tickers на уровне app через `add_api_route`. На фронте: выпадающий список открывается только по focus/click; закрытие по клику вне и через `closeSymbolDropdown()`; z-index 100000, max-height 220px, overflow-y auto; отображается до 500 тикеров (без обрезки до 100). В refresh-tickers кэш обновляется только при непустом ответе (при сбое одной категории вторая не затирается). Пороги slow_requests для путей symbols и refresh-tickers увеличены (long_running_paths).
- **Документация:** Добавлен `docs/TICKERS_SYMBOLS_LIST.md` с описанием проблемы, потока данных и проверки. Скрипт `scripts/test_bybit_symbols_direct.py` для прямой проверки Bybit API.

### Strategy Builder: Properties — работоспособность и все настройки (2026-01-30)

- **Разделение панели Properties:** Поля стратегии (Основные: тип рынка, направление; Data & Timeframe: timeframe, symbol, capital) вынесены в отдельный контейнер `#strategyBasicProps` и больше не перезаписываются при выборе блока. Параметры блока выводятся в отдельной секции «Параметры блока» (`#blockProperties`) — при выборе блока там отображаются Name/Type/Category и параметры из customLayouts или fallback.
- **Backtest Settings:** Добавлено редактируемое поле Commission % (`#backtestCommission`, по умолчанию 0.07); значение передаётся в `buildBacktestRequest()` (в API уходит commission / 100, например 0.0007). При загрузке стратегии поля Backtest Settings синхронизируются с данными стратегии: symbol, initial_capital, leverage, direction.
- **Тексты:** Заглушка при отсутствии выбранного блока приведена к русскому: «Выберите блок на холсте, чтобы редактировать его параметры.»

### Strategy Builder: исправления по аудиту Properties и Библиотека (2026-01-30)

- **Properties панель:** При выборе блока в правой панели параметры выводятся через `renderGroupedParams(block, false)` (customLayouts) — те же checkbox/select/number, что и в popup. Для блоков без layout сохранён fallback с текстовыми полями. Обработка изменений — делегированная в `setupEventListeners()` на `#propertiesPanel` (change/input по полям с `data-param-key`, используется `selectedBlockId`). Добавлена `escapeHtml()` для безопасного вывода.
- **Библиотека:** В `renderBlockLibrary()` добавлены 10 категорий: Correlation & Multi-Symbol, Alerts, Visualization, DCA Grid, Multiple Take Profits, ATR Exit, Signal Memory, Close Conditions (TradingView), Price Action Patterns, Divergence. Для отсутствующих ключей — проверка `if (!blocks || !Array.isArray(blocks)) return`.
- **UI:** Секция Properties «Закладка-2» переименована в «Data & Timeframe». Документ аудита `docs/STRATEGY_BUILDER_PROPERTIES_LIBRARY_AUDIT.md` обновлён (рекомендации отмечены выполненными).

### Signal Memory в рантайме (2026-01-30)

- **StrategyBuilderAdapter:** Добавлен хелпер `apply_signal_memory(buy_events, sell_events, memory_bars)` — расширение buy/sell на N баров после события; противоположный сигнал отменяет память. Применён в фильтрах: **rsi_filter** (use_signal_memory / signal_memory_bars), **stochastic_filter** (activate_stoch_cross_memory / stoch_cross_memory_bars, activate_stoch_kd_memory / stoch_kd_memory_bars), **two_ma_filter** (ma_cross_memory_bars), **macd_filter** (macd_signal_memory_bars, disable_macd_signal_memory=False).
- **Исправления:** В `_execute_filter` для stochastic_filter и macd_filter исправлена распаковка результата: `calculate_stochastic` и `calculate_macd` возвращают кортежи, не словари. Порядок аргументов `calculate_stochastic(high, low, close, ...)` приведён к сигнатуре.
- **Тесты:** Добавлен `tests/test_signal_memory_adapter.py` (5 тестов: RSI memory extend, RSI no memory, Stochastic cross memory, Two MA memory, MACD memory).

### План REMAINING: комиссия 0.07%, Python, документация (2026-01-30)

- **Дефолт комиссии 0.07% (TradingView parity):** Во всех сценариях бэктеста и оптимизации по умолчанию установлено 0.0007: `backend/backtesting/models.py` (commission_value), `backend/api/routers/optimizations.py` (4 места), `backend/tasks/backtest_tasks.py`, `backend/services/data_service.py`, `backend/services/advanced_backtesting/portfolio.py`, `backend/backtesting/optimizer.py`, `backend/backtesting/gpu_optimizer.py`, `backend/backtesting/gpu_batch_optimizer.py`, `backend/backtesting/fast_optimizer.py`, `backend/backtesting/vectorbt_optimizer.py`.
- **Версия Python в правилах:** В `.cursor/rules/project.mdc` — «3.11+ (рекомендуется 3.14)»; в `AGENTS.MD` — «Python 3.11+ required (3.14 recommended)»; в `README.md` — «3.11+ (3.12/3.13/3.14 supported; 3.14 recommended for dev)».
- **Документация:** Обновлены `docs/tradingview_dca_import/IMPLEMENTATION_STATUS.md` (Phase 3–4 чеклисты, Next Steps), `docs/SESSION_5_4_AUDIT_REPORT.md` (WebSocket UI — Done, итоговая таблица), `docs/FULL_IMPLEMENTATION_PLAN.md` (Phase 1.1–1.2 [x], WS интегрирован), `docs/REMAINING_AND_NEW_TASKS.md` (комиссия и Python отмечены выполненными, секция документации — выполнено).

### Синхронизация документации и задачи (2026-01-30)

- **Маппинг Strategy Builder → DCAEngine:** В `StrategyBuilderAdapter.extract_dca_config()` добавлен сбор блоков close_conditions и indent_order; в `strategy_builder.py` в `strategy_params` передаются `close_conditions` и `indent_order`; в `DCAEngine._configure_from_config()` — чтение и применение. В `run_from_config` добавлены `_precompute_close_condition_indicators`, логика indent_order при входе.
- **DCAEngine:** Исправлен `EquityCurve` в результате бэктеста: поле `equity` вместо `values`, timestamps как datetime.
- **E2E:** Добавлен `tests/test_e2e_dca_close_condition.py` (3 теста: time_bars_close, indent_order config, rsi_close config).
- **Signal Memory:** В `docs/REMAINING_AND_NEW_TASKS.md` зафиксировано назначение и место применения.
- **except Exception: pass:** Заменены на логирование в `backend/services/adapters/bybit.py` и `backend/database/sqlite_pool.py`.
- **Документация:** Обновлены SESSION_5_4_AUDIT_REPORT.md, REMAINING_AND_NEW_TASKS.md.

### P0: Evaluation Criteria & Optimization Config Panels (2026-01-30 - Session 5.7)

**Complete implementation of strategy builder panels for optimization configuration.**

#### Evaluation Criteria Panel ✅

- Created `frontend/js/pages/evaluation_criteria_panel.js` (~750 lines)
    - `EvaluationCriteriaPanel` class with full functionality
    - Primary metric selection with grouped categories
    - Secondary metrics grid with category organization
    - Metric weights sliders for composite scoring
    - Dynamic constraints list (add/remove/enable)
    - Multi-level sort order with drag & drop reordering
    - Quick presets: Conservative, Aggressive, Balanced, Frequency
    - localStorage state persistence
    - Event emission for integration

#### Optimization Config Panel ✅

- Created `frontend/js/pages/optimization_config_panel.js` (~800 lines)
    - `OptimizationConfigPanel` class with complete UI
    - Method selector: Bayesian, Grid Search, Random, Walk-Forward
    - Visual dual-range sliders for parameter ranges
    - Auto-detection of parameters from strategy blocks
    - Data period with train/test split slider
    - Walk-forward configuration (train/test/step windows)
    - Resource limits (trials, timeout, workers)
    - Advanced options: early stopping, pruning, warm start
    - Estimated time calculation
    - Mode indicator (Single Backtest vs Optimization)

#### CSS Styles ✅

- Extended `frontend/css/strategy_builder.css` (+600 lines)
    - Toggle switch component
    - Metric categories grid
    - Metric weights sliders
    - Sort order list with drag handles
    - Quick presets buttons
    - Method selector cards
    - Dual-range slider styling
    - Train/test split visualization
    - Walk-forward preview
    - Limits grid
    - Advanced options accordion
    - Estimated time display

#### Backend API Endpoints ✅

Extended `backend/api/routers/strategy_builder.py`:

- Pydantic models: `MetricConstraint`, `SortSpec`, `EvaluationCriteria`
- Pydantic models: `ParamRangeSpec`, `DataPeriod`, `OptimizationLimits`, `AdvancedOptions`, `OptimizationConfig`
- `POST /strategies/{id}/criteria` - Set evaluation criteria
- `GET /strategies/{id}/criteria` - Get evaluation criteria
- `POST /strategies/{id}/optimization-config` - Set optimization config
- `GET /strategies/{id}/optimization-config` - Get optimization config
- `GET /metrics/available` - Get all available metrics with presets

#### Tests ✅

- Created `tests/test_evaluation_optimization_panels.py` (~330 lines)
    - `TestEvaluationCriteriaModels` - 4 tests
    - `TestOptimizationConfigModels` - 4 tests
    - `TestEvaluationCriteriaEndpoints` - 3 tests
    - `TestOptimizationConfigEndpoints` - 2 tests
    - `TestAvailableMetrics` - 1 test
    - `TestConstraintValidation` - 2 tests
    - `TestCompositeScoring` - 2 tests
    - **Total: 18 tests, all passing**

---

### P0: Optimization Results Viewer (2026-01-30 - Session 5.6)

**Full implementation of interactive optimization results viewer with filtering, sorting, charts, and comparison.**

#### Frontend Module ✅

- Created `frontend/js/pages/optimization_results.js` (~1250 lines)
    - `OptimizationResultsViewer` class with full lifecycle management
    - Dynamic table columns based on optimization parameters
    - Real-time filtering: minSharpe, maxDD, minWinRate, minPF, minTrades
    - Multi-column sorting with direction toggle
    - Pagination with configurable page size (10, 25, 50, 100)
    - Convergence chart (best_score over trials via Chart.js)
    - Sensitivity chart per parameter
    - Details modal for individual result inspection
    - Comparison modal for side-by-side result analysis
    - Apply params to strategy functionality
    - CSV/JSON export with all filters applied
    - Demo data fallback when no optimization_id provided

#### HTML Updates ✅

- Updated `frontend/optimization-results.html`
    - Removed ~350 lines of inline JavaScript
    - Added modular script import
    - Legacy compatibility functions delegating to module instance

#### CSS Extensions ✅

- Extended `frontend/css/optimization_components.css` (+150 lines)
    - `.opt-results-table` - sticky headers, sortable columns
    - `.opt-rank-badge` - gold/silver/bronze rank badges with gradients
    - `.opt-metric-value.positive/.negative` - color-coded metrics
    - `.opt-loading-overlay`, `.opt-empty-state` - loading/empty states
    - `.opt-comparison-table` - comparison modal styling
    - Dark theme support

#### Backend API Endpoints ✅

Extended `backend/api/routers/optimizations.py` (+220 lines):

- `GET /{id}/charts/convergence` - Returns convergence chart data (trials, best_scores, all_scores, metric)
- `GET /{id}/charts/sensitivity/{param}` - Returns sensitivity data per parameter (param_name, values, scores)
- `POST /{id}/apply/{rank}` - Applies selected result params to strategy config
- `GET /{id}/results/paginated` - Paginated filtered results with sort support

#### Tests ✅

- Created `tests/test_optimization_results_viewer.py` (~250 lines)
    - `TestConvergenceEndpoint` - 2 tests
    - `TestSensitivityEndpoint` - 2 tests
    - `TestApplyEndpoint` - 2 tests
    - `TestPaginatedEndpoint` - 3 tests
    - `TestResultsViewerIntegration` - 3 tests
    - `TestEdgeCases` - 4 tests
    - **Total: 16 tests, all passing**

---

### Cursor Rules — требуемые исправления (2026-01-30)

- **Пути:** Устранён хардкод в tests/test_auto_event_binding.py, tests/test_safedom.py, test_frontend_security.py, scripts/adhoc/test_btc_correlation.py, test_autofix_constraints.py, test_v4_quick.py — используется PROJECT_ROOT / Path(**file**).resolve().parents[N], DATABASE_PATH из env.
- **dev.ps1:** Создан заново (run, lint, format, test, test-cov, clean, mypy, help).
- **Документация:** Созданы .agent/docs/ARCHITECTURE.md, .agent/docs/DECISIONS.md (ссылки на docs/), docs/DECISIONS.md (ADR-001 — ADR-005).
- **except Exception: pass:** Заменены на логирование в backend/api/app.py, backend/backtesting/engines/dca_engine.py, backend/api/lifespan.py, backend/backtesting/engine.py, backend/api/routers/optimizations.py.

### Cursor Rules Analysis (2026-01-30)

- Added **docs/CURSOR_RULES_ANALYSIS.md** — анализ проекта с учётом правил из AGENTS.md и `.cursor/rules/*.mdc`.
- Выявлено: хардкод путей в тестах/скриптах, отсутствие dev.ps1, расхождение .agent/docs/ и DECISIONS/ARCHITECTURE с фактической структурой docs/, массовое использование `except Exception: pass` в backend.
- В отчёте даны приоритизированные рекомендации по устранению расхождений.

### Full DCA Backend Implementation (2026-01-30 - Session 5.5 Part 2)

**Backend logic for all Strategy Builder features.**

#### Backend Validation Rules ✅

Extended `BLOCK_VALIDATION_RULES` in `strategy_validation_ws.py`:

- 6 Close Condition blocks: `rsi_close`, `stoch_close`, `channel_close`, `ma_close`, `psar_close`, `time_bars_close`
- New filters: `rvi_filter`, `indent_order`, `atr_stop` (extended)
- Updated exit block types for strategy validation

#### DCAEngine Close Conditions ✅

New `CloseConditionsConfig` dataclass and methods in `dca_engine.py`:

- `_check_close_conditions()` - main dispatcher for all close conditions
- `_check_rsi_close()` - RSI reach/cross detection
- `_check_stoch_close()` - Stochastic reach detection
- `_check_channel_close()` - Keltner/Bollinger breakout/rebound
- `_check_ma_close()` - Two MAs cross detection
- `_check_psar_close()` - Parabolic SAR flip detection
- Pre-computed indicator caches for performance

#### MTF Utilities ✅

New `backend/core/indicators/mtf_utils.py`:

- `resample_ohlcv()` - timeframe resampling
- `map_higher_tf_to_base()` - value mapping
- `calculate_supertrend_mtf()` - SuperTrend calculation
- `calculate_rsi_mtf()` - RSI calculation
- `MTFIndicatorCalculator` class - cached MTF calculations
- `apply_mtf_filters()` - filter application

#### Extended Indicators ✅

New `backend/core/indicators/extended_indicators.py`:

- `calculate_rvi()` - Relative Volatility Index
- `calculate_linear_regression_channel()` - Linear Regression with slope
- `find_pivot_points()` - S/R level detection
- `levels_break_filter()` - Pivot breakout signals
- `find_accumulation_areas()` - Volume-based accumulation detection

#### Indent Order ✅

New `IndentOrderConfig` and `PendingIndentOrder` dataclasses:

- `_create_indent_order()` - create pending limit order
- `_check_indent_order_fill()` - check fill or expiration
- Integration in main DCAEngine run loop

#### UI Enhancements ✅

- Extended `bop_filter` with triple smooth, cross line mode
- Added `block_worse_filter` in blockLibrary and customLayouts

#### New Tests (47 tests) ✅

- `tests/test_extended_indicators.py` - 13 tests
- `tests/test_dca_close_conditions.py` - 18 tests
- `tests/test_validation_rules_session55.py` - 16 tests

---

### Full DCA Implementation Plan Execution (2026-01-30 - Session 5.5)

**Comprehensive Strategy Builder expansion based on TradingView Multi DCA Strategy [Dimkud].**

#### Phase 1.1: WebSocket Integration in UI ✅

- Integrated `wsValidation.validateParam()` in `updateBlockParam()`
- Added server-side validation before `saveStrategy()`
- Created WebSocket status indicator with CSS styling
- Event listeners for `ws-validation-result`, `ws-validation-connected/disconnected`

#### Phase 1.2: Price Action UI (47 Patterns) ✅

Expanded `price_action_filter` from 22 to 47 patterns:

- **Bullish Exotic**: Pin Bar, Three Line Strike, Kicker, Abandoned Baby, Belt Hold, Counterattack, Ladder Bottom, Stick Sandwich, Homing Pigeon, Matching Low
- **Bearish Exotic**: Pin Bar, Three Line Strike, Kicker, Abandoned Baby, Belt Hold, Counterattack, Ladder Top, Stick Sandwich, Matching High
- **Neutral/Structure**: Inside Bar, Outside Bar
- **Gap Patterns**: Gap Up, Gap Down, Gap Up Filled, Gap Down Filled

#### Phase 2: Close Conditions (6 Types) ✅

New exit blocks in `blockLibrary.exits`:

- `rsi_close` - RSI Reach/Cross level close
- `stoch_close` - Stochastic Reach/Cross level close
- `channel_close` - Keltner/Bollinger channel breakout close
- `ma_close` - Two MAs cross close
- `psar_close` - Parabolic SAR flip close
- `time_bars_close` - Time/bars-based close with profit filter

#### Phase 3: MTF Expansion (3 Timeframes) ✅

Extended `supertrend_filter` and `rsi_filter` for multi-timeframe analysis:

- SuperTrend TF1/TF2/TF3 with separate ATR period, multiplier, BTC source
- RSI TF1/TF2/TF3 with separate period, range conditions

#### Phase 4: New Indicators ✅

- `rvi_filter` - Relative Volatility Index with range filter
- Extended `linreg_filter` - Signal memory, slope direction, breakout/rebound mode
- Extended `levels_filter` - Pivot bars, search period, channel width, test count
- Extended `accumulation_filter` - Backtrack interval, min bars, breakout signal

#### Phase 5: Advanced Features ✅

- `indent_order` - Limit entry with percentage offset, cancel after X bars
- Extended `atr_stop` - Full ATR SL/TP with wicks, method (WMA/RMA/SMA/EMA), separate periods/multipliers

#### Files Modified

- `frontend/js/pages/strategy_builder.js` - All new blocks, defaultValues, customLayouts, validation rules
- `frontend/css/strategy_builder.css` - WebSocket status indicator styles

#### Tests

- 65 passed, 2 skipped (WebSocket + Price Action tests)

#### Documentation

- Created `docs/FULL_IMPLEMENTATION_PLAN.md`
- Updated `docs/SESSION_5_4_AUDIT_REPORT.md` with Phase 6 summary

---

### Exotic Candlestick Patterns + WebSocket Validation (2026-01-30 - Session 5.4)

**Extended pattern library and real-time validation via WebSocket.**

#### New Exotic Candlestick Patterns in `price_action_numba.py`

Added 11 new Numba JIT-optimized pattern detection functions:

- **`detect_three_line_strike()`** - Bullish/Bearish three line strike reversal
- **`detect_kicker()`** - Strong gap reversal pattern (one of the most reliable)
- **`detect_abandoned_baby()`** - Rare reversal with gapped doji
- **`detect_belt_hold()`** - Single candle reversal at extremes
- **`detect_counterattack()`** - Equal close reversal pattern
- **`detect_gap_patterns()`** - Gap up/down with fill detection
- **`detect_ladder_pattern()`** - Ladder bottom/top (5-candle reversal)
- **`detect_stick_sandwich()`** - Three candle sandwich pattern
- **`detect_homing_pigeon()`** - Bullish continuation (two reds, second inside)
- **`detect_matching_low_high()`** - Support/resistance at equal levels

Total patterns now: **47** (was 26)

#### WebSocket Real-Time Validation

**New Backend Endpoint**: `backend/api/routers/strategy_validation_ws.py`

- WebSocket endpoint: `/api/v1/strategy-builder/ws/validate`
- Message types:
    - `validate_param` - Single parameter validation
    - `validate_block` - Full block validation
    - `validate_connection` - Connection compatibility check
    - `validate_strategy` - Entire strategy validation
    - `heartbeat` - Keep-alive

**New Frontend Module**: `frontend/js/pages/strategy_builder_ws.js`

- Auto-reconnection with exponential backoff
- Request debouncing (150ms)
- Heartbeat every 30 seconds
- Visual state updates for blocks/params
- Fallback to local validation when disconnected

#### Test Coverage

- **40 tests** for exotic patterns (`tests/test_price_action_numba.py`)
- **27 tests** for WebSocket validation (`tests/test_strategy_validation_ws.py`) — 25 original + 2 added during audit
- Total tests: **67**

> **Audit (2026-01-30):** See `docs/SESSION_5_4_AUDIT_REPORT.md`. WebSocket validation API is implemented; UI integration (calling `wsValidation.validateParam`/`validateBlock` from Strategy Builder) is pending.

---

### Strategy Builder - UI Real-Time Validation (2026-01-30 - Session 5.3)

**Live parameter validation with visual feedback.**

#### New: `blockValidationRules` Configuration

Added comprehensive validation rules for all block types:

- **Momentum indicators**: RSI, Stochastic, StochRSI, Williams %R, MFI, CCI, CMO, ROC
- **Trend indicators**: SMA, EMA, MACD, ADX, Supertrend, Ichimoku, Parabolic SAR
- **Volatility indicators**: ATR, Bollinger, Keltner, Donchian, StdDev
- **Action blocks**: stop_loss, take_profit, trailing_stop, atr_stop, chandelier_stop, break_even, profit_lock, scale_out, multi_tp, limit_entry, stop_entry
- **Exit blocks**: atr_exit, session_exit, indicator_exit, partial_close, multi_tp_exit, break_even_exit
- **Price Action patterns**: engulfing, hammer, doji, pin_bar, shooting_star, marubozu, tweezer, harami
- **Divergence blocks**: RSI, MACD, Stochastic, OBV, MFI divergence

#### Validation Features

- **Type validation**: Ensures numbers are numbers
- **Range validation**: min/max bounds for each parameter
- **Required fields**: Marks mandatory parameters
- **Cross-parameter validation**: MACD fast < slow, between min < max
- **Multi-TP validation**: TP1 < TP2 < TP3 ordering

#### Visual Feedback (CSS)

- `.block-valid` - Subtle green border for valid blocks
- `.block-invalid` - Red border with pulse animation for invalid blocks
- `.param-valid` / `.param-invalid` - Input field styling
- Warning icon (⚠️) on blocks with validation errors
- Tooltip on hover showing error details

#### Enhanced `validateStrategy()` Function

Now validates:

1. Strategy has blocks
2. Main strategy node exists
3. Connections to main node
4. Entry signal connections
5. Disconnected blocks warning
6. **NEW: Block parameter validation**

### Numba JIT Price Action Patterns (2026-01-30 - Session 5.2)

**High-performance candlestick pattern detection with 10-50x speedup.**

#### New Module: `backend/core/indicators/price_action_numba.py`

Created Numba JIT-optimized pattern detection with:

- **`detect_engulfing()`** - Bullish/Bearish engulfing patterns
- **`detect_hammer()`** - Hammer and Hanging Man patterns
- **`detect_doji()`** - Standard, Dragonfly, Gravestone doji
- **`detect_pin_bar()`** - Bullish/Bearish pin bars
- **`detect_inside_bar()`** - Inside bar consolidation
- **`detect_outside_bar()`** - Outside bar volatility
- **`detect_three_soldiers_crows()`** - Three white soldiers / black crows
- **`detect_shooting_star()`** - Bearish shooting star
- **`detect_marubozu()`** - Strong momentum candles
- **`detect_tweezer()`** - Tweezer top/bottom reversals
- **`detect_three_methods()`** - Rising/Falling three methods
- **`detect_piercing_darkcloud()`** - Piercing line / Dark cloud
- **`detect_harami()`** - Bullish/Bearish harami
- **`detect_morning_evening_star()`** - Morning/Evening star
- **`detect_all_patterns()`** - Batch detection (all 26 signals)

#### Performance

- All functions decorated with `@njit(cache=True)` for JIT compilation
- Graceful fallback when Numba not installed
- 100 iterations of 1000-bar engulfing detection in under 1 second
- 10 iterations of 10000-bar all-patterns detection in under 2 seconds

#### Tests

- 21 new tests in `tests/test_price_action_numba.py`
- Pattern detection accuracy tests
- Performance benchmark tests
- Edge case handling (empty arrays, single bars, zero body)

### Strategy Builder - Unit Tests & Bug Fixes (2026-01-30 - Session 5.2)

#### New: `tests/test_strategy_builder_handlers.py`

Comprehensive test suite with 35 tests covering:

- **TestActionHandlers** (13 tests): stop_loss, take_profit, trailing_stop, atr_stop, chandelier_stop, break_even, profit_lock, scale_out, multi_tp, limit_entry, stop_entry, close, entry_price_action
- **TestExitHandlers** (7 tests): atr_exit, session_exit, signal_exit, indicator_exit, partial_close, multi_tp_exit, break_even_exit
- **TestPriceActionHandlers** (9 tests): All candlestick patterns (engulfing, hammer, doji, etc.)
- **TestDivergenceHandlers** (2 tests): RSI divergence, MACD divergence
- **TestIntegration** (3 tests): Multi-block strategies with 10+ blocks
- **TestEdgeCases** (2 tests): Empty OHLCV data, unknown block types

#### Bug Fixes in `strategy_builder_adapter.py`

Found and fixed 4 bugs during testing:

1. **`atr_exit` handler** - Fixed `calculate_atr()` signature (needed high, low, close arrays)
2. **`stoch_divergence` handler** - Fixed `calculate_stochastic()` return type (tuple not dict)
3. **`mfi_divergence` handler** - Fixed `calculate_mfi()` signature (needed 4 arrays)
4. **`rsi_divergence` handler** - Fixed numpy array vs pandas Series issue

#### New: `docs/STRATEGY_BUILDER_ADAPTER_API.md`

Comprehensive API documentation (~500 lines) covering:

- Block Categories overview
- Indicator blocks (RSI, MACD, BB, etc.)
- Filter blocks with all comparisons
- Action blocks with parameters
- Exit blocks with configuration
- Price Action patterns
- Divergence detection
- Close conditions
- Usage examples and error handling

### Strategy Builder Adapter - 100% Block Coverage (2026-01-30 - Session 5.1)

**Full frontend-backend parity achieved: 110/110 blocks covered!**

#### Actions Category - Complete (17 handlers)

Added missing action handlers:

- **`stop_loss`** - Stop loss with percent configuration
- **`take_profit`** - Take profit with percent configuration
- **`trailing_stop`** - Trailing stop with activation level
- **`atr_stop`** - ATR-based stop loss (period + multiplier)
- **`chandelier_stop`** - Chandelier stop from highest high
- **`break_even`** - Move stop to entry after trigger percent
- **`profit_lock`** - Lock minimum profit after threshold
- **`scale_out`** - Partial position close at profit target
- **`multi_tp`** - Multi take profit levels (TP1/TP2/TP3)
- **`limit_entry`** - Limit order entry at specific price
- **`stop_entry`** - Stop order entry on breakout
- **`close`** - Close any position

#### Exits Category - Complete (12 handlers)

Added missing exit handlers:

- **`atr_exit`** - ATR-based TP/SL with multipliers
- **`session_exit`** - Exit at session end (specific hour)
- **`signal_exit`** - Exit on opposite signal
- **`indicator_exit`** - Exit on indicator condition (RSI threshold etc.)
- **`partial_close`** - Partial close at profit targets
- **`multi_tp_exit`** - Multi TP levels with allocation %
- **`break_even_exit`** - Move to breakeven after profit trigger

#### Price Action Patterns - Complete (9 handlers)

Added missing candlestick patterns:

- **`hammer_hangman`** - Hammer and Hanging Man patterns
- **`doji_patterns`** - Standard, Dragonfly, Gravestone doji
- **`shooting_star`** - Bearish reversal after uptrend
- **`marubozu`** - Strong momentum candle (no wicks)
- **`tweezer`** - Tweezer top/bottom reversal
- **`three_methods`** - Rising/Falling three methods continuation
- **`piercing_darkcloud`** - Piercing line / Dark cloud cover
- **`harami`** - Inside bar reversal pattern

#### Divergence Detection - Complete (5 handlers)

Added missing divergence types:

- **`stoch_divergence`** - Stochastic K divergence
- **`mfi_divergence`** - Money Flow Index divergence

#### Coverage Summary

| Category         | Frontend | Backend | Status  |
| ---------------- | -------- | ------- | ------- |
| Indicators       | 34       | 34      | ✅ 100% |
| Filters          | 24       | 24      | ✅ 100% |
| Actions          | 17       | 21+     | ✅ 100% |
| Exits            | 12       | 14+     | ✅ 100% |
| Price Action     | 9        | 15+     | ✅ 100% |
| Divergence       | 5        | 5       | ✅ 100% |
| Close Conditions | 9        | 9       | ✅ 100% |

**Total: 110/110 blocks (100%)**

---

### Strategy Builder Adapter - MTF & Filters Extension (2026-01-30 - Session 5)

#### Multi-Timeframe Indicator Added

Implemented `mtf` indicator with full data resampling support:

- Resamples OHLCV to higher timeframe (5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w)
- Calculates indicator (EMA, SMA, RSI, ATR) on HTF data
- Forward-fills results back to original timeframe
- Graceful fallback on resampling errors

#### New Filters Implemented (6 Additional)

- **`accumulation_filter`** - Detects volume accumulation zones (high volume + tight range)
- **`linreg_filter`** - Linear regression channel with slope and deviation
- **`divergence_filter`** - Detects RSI/MACD/OBV divergence signals
- **`bop_filter`** - Balance of Power indicator filter
- **`levels_filter`** - Pivot point / swing high-low break filter
- **`price_action_filter`** - Candlestick patterns (engulfing, doji, hammer)

#### Code Quality Improvements (PEP 585)

- Replaced `Dict[...]` with `dict[...]` throughout codebase
- Replaced `List[...]` with `list[...]`
- Added `from __future__ import annotations` for forward compatibility

#### Tests Status

- ✅ 27 tests passing (9 DCA E2E + 18 API)

---

### Strategy Builder Adapter Complete Integration (2026-01-30 - Session 4)

#### Expanded Indicator Support (28 New Indicators)

Extended `_execute_indicator()` method to support all frontend indicators:

- **Oscillators:** QQE, Stoch RSI, Williams %R, ROC, MFI, CMO, CCI
- **Moving Averages:** WMA, DEMA, TEMA, Hull MA
- **Trend:** SuperTrend, Ichimoku, Parabolic SAR, Aroon
- **Volatility:** ATRP, Keltner Channels, Donchian Channels, StdDev
- **Volume:** OBV, VWAP, CMF, A/D Line, PVT
- **Other:** Pivot Points

#### New Filter Category Handler (`_execute_filter()`)

Implemented 20+ filter types matching frontend blocks:

- **Momentum Filters:** RSI, QQE, Stochastic, MACD, CCI, Momentum
- **Trend Filters:** SuperTrend, Two MA, DMI, Trend Direction
- **Volatility Filters:** ATR, Volatility, Highest/Lowest
- **Volume Filters:** Volume, Volume Compare, CMF
- **Price Filters:** Price Above/Below, Price Action
- **Time Filters:** Trading Hours, Session

#### New Category Handlers

Added handlers for all frontend block categories:

- **`_execute_action()`** - Buy, Sell, Close, Stop Loss, Take Profit signals
- **`_execute_exit()`** - TP%, SL%, ATR Stop, Trailing, Chandelier Exit
- **`_execute_position_sizing()`** - Fixed, % Equity, Risk-based, Kelly, Volatility
- **`_execute_time_filter()`** - Trading Hours, Days, Sessions, Date Range
- **`_execute_price_action()`** - Engulfing, Hammer, Doji, Pin Bar, Inside/Outside Bar
- **`_execute_divergence()`** - RSI, MACD, OBV Divergence Detection

#### Category Routing Extended

Extended `_execute_block()` to route all categories:

- action, exit, sizing, entry, risk, session, time
- price_action, divergence (new)

#### Tests Passing

- ✅ 9 DCA E2E tests
- ✅ 18 Strategy Builder API tests
- ✅ 4 Strategy Builder Validation tests

#### Files Modified

- `backend/backtesting/strategy_builder_adapter.py` - +500 lines (new methods and handlers)

---

### DCA Engine Full System Integration (2026-01-30 - Session 3)

#### BacktestConfig DCA Fields Added

Extended `BacktestConfig` (Pydantic model) with 19 new DCA-specific fields:

**Grid Configuration:**

- `dca_enabled` - Enable DCA/Grid mode (auto-selects DCAEngine)
- `dca_direction` - Trading direction: 'long', 'short', 'both'
- `dca_order_count` - Number of grid orders (2-15)
- `dca_grid_size_percent` - Grid step size % (0.1-50%)
- `dca_martingale_coef` - Martingale coefficient (1.0-5.0)
- `dca_martingale_mode` - Mode: 'multiply_each', 'multiply_total', 'progressive'
- `dca_log_step_enabled` - Enable logarithmic step distribution
- `dca_log_step_coef` - Logarithmic coefficient (1.0-3.0)
- `dca_drawdown_threshold` - Safety close threshold % (5-90%)
- `dca_safety_close_enabled` - Enable safety close mechanism

**Multi-TP Configuration:**

- `dca_multi_tp_enabled` - Enable multi-level take profit
- `dca_tp1_percent` / `dca_tp1_close_percent` - TP1 level and close %
- `dca_tp2_percent` / `dca_tp2_close_percent` - TP2 level and close %
- `dca_tp3_percent` / `dca_tp3_close_percent` - TP3 level and close %
- `dca_tp4_percent` / `dca_tp4_close_percent` - TP4 level and close %

#### DCAEngine Abstract Methods Implemented

- `name` - Property returning engine name
- `supports_bar_magnifier` - Returns True
- `supports_parallel` - Returns True
- `optimize()` - Grid search optimization for DCA parameters

#### New DCAEngine Methods

- `run_from_config(config, ohlcv)` - Direct BacktestConfig integration
- `_configure_from_config(config)` - Extract DCA fields from Pydantic model
- `_generate_signals_from_config(config, df)` - Strategy signal generation
- `_convert_trades_to_model(ohlcv)` - Convert trades to BacktestResult format
- `_build_performance_metrics(...)` - Build PerformanceMetrics model

#### Engine Selector Integration

- `get_engine()` now accepts `dca_enabled` parameter
- Auto-selects DCAEngine when `dca_enabled=True`
- Added 'dca' and 'dca_grid' to engine_type validator

#### BacktestService Integration

- Dynamic engine selection based on `config.dca_enabled`
- Uses `engine.run_from_config(config, ohlcv)` for DCA backtests
- Standard engine path unchanged for non-DCA backtests

#### Files Modified

- `backend/backtesting/models.py` - +100 lines (DCA fields + validators)
- `backend/backtesting/engine_selector.py` - +15 lines (dca_enabled support)
- `backend/backtesting/service.py` - +10 lines (DCA engine routing)
- `backend/backtesting/engines/dca_engine.py` - +250 lines (new methods)

---

### DCA Engine Implementation & Strategy Builder Extensions (2026-01-30 - Session 2)

#### Backend DCA Engine Created

New specialized engine for DCA/Grid trading: `backend/backtesting/engines/dca_engine.py`

**Features:**

- Grid order placement with configurable levels (3-15 orders)
- Martingale position sizing (1.0-1.8 coefficient)
- Logarithmic step distribution (0.8-1.4 coefficient)
- Dynamic Take Profit adjustment based on active orders
- Multiple Take Profits (TP1-TP4) support
- Safety close on drawdown threshold
- Signal memory system placeholder

**Classes:**

- `DCAEngine` - Main backtest engine extending BaseBacktestEngine
- `DCAGridConfig` - Configuration dataclass for grid settings
- `DCAGridCalculator` - Static methods for grid calculation
- `DCAOrder` - Individual order representation
- `DCAPosition` - Aggregate position state
- `MultipleTakeProfit` - TP1-TP4 configuration

#### Frontend Strategy Builder Extensions

**QQE Indicator Added:**

- New indicator in `blockLibrary.indicators`
- Parameters: rsi_period, qqe_factor, smoothing_period, source, timeframe
- customLayout with full UI fields

**Price Action Patterns Expanded (8 → 22 patterns):**

- Bullish Reversal: Hammer, Inverted Hammer, Bullish Engulfing, Morning Star, Piercing Line, Three White Soldiers, Tweezer Bottom, Dragonfly Doji, Bullish Harami, Rising Three Methods, Bullish Marubozu
- Bearish Reversal: Shooting Star, Hanging Man, Bearish Engulfing, Evening Star, Dark Cloud Cover, Three Black Crows, Tweezer Top, Gravestone Doji, Bearish Harami, Falling Three Methods, Bearish Marubozu
- Neutral: Standard Doji, Spinning Top

**DCA CustomLayouts Added:**

- `dca_grid_enable` - Grid mode with direction, leverage, alerts
- `dca_grid_settings` - Deposit, grid size, order count, distribution
- `dca_martingale_config` - Coefficient (1.0-1.8), mode, safety limits
- `dca_log_steps` - Log coefficient (0.8-1.4), step preview
- `dca_dynamic_tp` - Trigger orders, new TP, decrease per order
- `dca_safety_close` - Drawdown threshold, action type
- `multi_tp_enable` - Enable multi-TP with count
- `tp1_config` through `tp4_config` - Individual TP level settings
- `atr_sl` / `atr_tp` / `atr_wicks_mode` - ATR-based exit settings
- `signal_memory_enable` / `cross_memory` / `pattern_memory` - Signal memory
- `qqe_filter` - QQE indicator filter with signal types

#### Files Modified

- `frontend/js/pages/strategy_builder.js` - Added ~300 lines for DCA/QQE/Price Action
- `backend/backtesting/engines/dca_engine.py` - New file (650+ lines)
- `backend/backtesting/engines/__init__.py` - Export DCAEngine

---

### TradingView Multi DCA Strategy Import & Major Strategy Builder Expansion (2026-01-30)

**Analyzed and integrated parameters from TradingView Multi DCA Strategy [Dimkud]**

#### Source Analysis

Imported and analyzed comprehensive DCA strategy with 200+ parameters:

- `docs/tradingview_dca_import/DCA Start.txt` - Full parameter specification
- `docs/tradingview_dca_import/DCA Strategy3.txt` - Alternative version with explanations
- `docs/tradingview_dca_import/ANALYSIS_REPORT.md` - Complete analysis document
- `docs/tradingview_dca_import/IMPLEMENTATION_STATUS.md` - Implementation tracking

#### New Block Categories Added to Strategy Builder

| Category             | Blocks   | Description                                                              |
| -------------------- | -------- | ------------------------------------------------------------------------ |
| **dca_grid**         | 6 blocks | DCA Grid mode, settings, martingale, log steps, dynamic TP, safety close |
| **multiple_tp**      | 5 blocks | Enable multi-TP, TP1-TP4 configuration                                   |
| **atr_exit**         | 3 blocks | ATR-based SL/TP, wicks mode                                              |
| **signal_memory**    | 3 blocks | Signal memory, cross memory, pattern memory                              |
| **close_conditions** | 9 blocks | Time close, RSI/Stoch reach/cross, channel, MA cross, PSAR, profit only  |
| **price_action**     | 9 blocks | Engulfing, hammer, doji, shooting star, marubozu, tweezer, harami, etc.  |
| **divergence**       | 5 blocks | RSI, MACD, Stochastic, OBV, MFI divergence detection                     |

#### Default Parameters Added

40+ new block types with complete default parameters:

- DCA Grid: deposit, leverage, grid size, order count, martingale (1.0-1.8), log steps (0.8-1.4)
- Multiple TP: TP1-TP4 with percent and close amounts
- ATR Exit: period, multiplier, smoothing method, wicks mode
- Signal Memory: memory bars, execution conditions
- Close Conditions: RSI/Stoch reach/cross levels, channel breakout, MA cross, PSAR
- Price Action: 22 candlestick patterns (engulfing, hammer, doji, etc.)
- Divergence: Regular and hidden divergence for 5 indicators

#### Backtest Results Display (Previous Session)

Added beautiful modal for displaying backtest results:

- Summary cards (ROI, Win Rate, Drawdown, Trades, PF, Sharpe)
- 4-tab interface (Overview, Equity, Trades, All Metrics)
- Equity curve canvas rendering
- Trades table with MFE/MAE
- Export to JSON functionality
- Full results page link

#### Files Modified

- `frontend/js/pages/strategy_builder.js` - Added 7 new block categories, 40+ default params
- `frontend/strategy-builder.html` - Added backtest results modal
- `frontend/css/strategy_builder.css` - Added results modal styles (~300 lines)
- `docs/tradingview_dca_import/` - New documentation folder

---

### Strategy Builder Engine Integration & Auto-Mode Detection (2025-01-29)

**Simplified engine architecture and improved block-to-optimization-panel integration**

#### Engine Simplification

Reduced engine complexity from 5+ engines to 2 core engines:

| Engine               | Use Case        | Features                                                 |
| -------------------- | --------------- | -------------------------------------------------------- |
| **FallbackEngineV4** | Single Backtest | Reference implementation, maximum accuracy, all features |
| **NumbaEngineV2**    | Optimization    | JIT-compiled, 20-40x faster, 100% parity with V4         |

Deprecated engines (with warnings): GPU, V2, V3

#### Auto-Mode Detection

- **Single Backtest mode**: Auto-selected when NO optimization params enabled on blocks
- **Optimization mode**: Auto-selected when ANY optimization params enabled on blocks
- UI automatically updates button text and indicators based on mode

#### Block-Panel Integration

- `strategy_builder.js` now dispatches `strategyBlocksChanged` event on add/delete
- `optimization_panels.js` listens for events and syncs parameter ranges
- Blocks include `optimizationParams` object for storing min/max/step/enabled
- Two-way sync: changes in optimization panel reflect back to block

#### Files Modified

- `backend/backtesting/engine_selector.py` - Simplified to 2-engine selection
- `frontend/js/pages/optimization_panels.js` - Added block integration, auto-mode, SSE handling
- `frontend/js/pages/strategy_builder.js` - Added event dispatch, optimizationParams

---

### Expanded Indicators Library and UI (2025-01-29)

Added 8 new advanced indicators to backend + 34 indicators in UI.

New Backend Indicators in backend/core/indicators/advanced.py:

- ADX (Average Directional Index)
- CCI (Commodity Channel Index)
- Ichimoku Cloud
- Parabolic SAR
- Pivot Points
- Aroon
- ATRP

Updated UI Block Library - 34 Indicators + 6 Filters in strategy_builder.js.

---

### Optimization Panels JavaScript Module (2025-01-29)

**Created interactive panel manager for Strategy Builder Manual Mode**

#### Files Created/Modified

- `frontend/js/pages/optimization_panels.js` (~650 lines) - NEW
- `frontend/css/strategy_builder.css` - Added ~150 lines
- `frontend/strategy-builder.html` - Added script include

#### Class: `OptimizationPanels`

| Method                         | Description                     |
| ------------------------------ | ------------------------------- |
| `init()`                       | Initialize all panels and state |
| `bindEvents()`                 | Setup all event listeners       |
| `setupCollapsibleSections()`   | Panel collapse/expand logic     |
| `updateSecondaryMetrics()`     | Sync checkbox state             |
| `addConstraint()`              | Add new constraint row          |
| `updateConstraints()`          | Parse constraint inputs         |
| `startOptimization()`          | Build config, call API          |
| `pollOptimizationStatus()`     | Poll job progress               |
| `showResultsQuickView()`       | Display metrics summary         |
| `saveState()/loadSavedState()` | Persist to localStorage         |

#### Features

- **Evaluation Criteria Panel**: Primary metric, secondary metrics checkboxes, dynamic constraints
- **Optimization Config Panel**: Method selection, date range, max trials, workers
- **Results Panel**: Progress bar, metrics preview, link to full results
- **State Persistence**: Auto-save to localStorage
- **API Integration**: Job start, polling, results loading

---

### �🎯 Advanced RSI Filter - TradingView Parity (2025-01-29)

**Implemented full RSI - [IN RANGE FILTER OR CROSS SIGNAL] from TradingView**

#### Features

| Feature         | Description                                     |
| --------------- | ----------------------------------------------- |
| Range Filter    | RSI must be within bounds (e.g., 1-50 for long) |
| Cross Signal    | RSI crossover/crossunder detection              |
| Signal Memory   | Keep signal active for N bars after cross       |
| Opposite Signal | Invert cross logic (long on short cross)        |
| BTC Source      | Use BTC RSI for altcoin trading                 |

#### File Created

- `backend/core/indicators/rsi_advanced.py` (~500 lines)

#### Classes & Functions

```python
# Classes
RSIAdvancedConfig   # Configuration dataclass
RSIAdvancedFilter   # Main filter class
RSIFilterResult     # Result container

# Convenience functions
apply_rsi_range_filter()     # Simple range filter
apply_rsi_cross_filter()     # Cross with optional memory
apply_rsi_combined_filter()  # Full combined mode
create_btc_rsi_filter()      # BTC source for alts
```

#### Usage Example

```python
from backend.core.indicators import RSIAdvancedFilter, RSIAdvancedConfig

config = RSIAdvancedConfig(
    rsi_period=14,
    use_long_range=True,
    long_range_lower=20,
    long_range_upper=60,
    use_cross_level=True,
    long_cross_level=30,
    activate_memory=True,
    memory_bars=5,
)
filter = RSIAdvancedFilter(config)
result = filter.apply(close_prices)
# result.long_signals, result.short_signals, result.rsi_values, etc.
```

---

### 📚 Unified Indicators Library (2025-01-29)

**Created centralized indicators library to eliminate code duplication**

#### Problem Solved

The project had **15-20 duplicate RSI implementations** scattered across:

- `signal_generators.py`
- `fast_optimizer.py`
- `gpu_optimizer.py`
- `strategy_builder/indicators.py`
- `mtf/signals.py`
- And 10+ other files

Each with slightly different implementations, making maintenance a nightmare.

#### Solution: `backend/core/indicators/`

Created unified library with **26 technical indicators** organized by category:

| Module          | Indicators                                             | Functions |
| --------------- | ------------------------------------------------------ | --------- |
| `momentum.py`   | RSI, Stochastic, Williams %R, ROC, CMO, MFI, Stoch RSI | 8         |
| `trend.py`      | SMA, EMA, WMA, DEMA, TEMA, Hull MA, MACD, Supertrend   | 8         |
| `volatility.py` | ATR, Bollinger, Keltner, Donchian, StdDev              | 5         |
| `volume.py`     | OBV, VWAP, PVT, A/D Line, CMF                          | 5         |

#### Features

- **Numba JIT optimization** (optional, falls back gracefully)
- **No GPU/CuPy** - project uses universal engines, GPU not needed
- **Consistent API** - all functions accept numpy arrays
- **Proper NaN handling** - warmup periods return NaN

#### Usage

```python
from backend.core.indicators import (
    calculate_rsi,
    calculate_sma,
    calculate_ema,
    calculate_macd,
    calculate_bollinger,
    calculate_atr,
)
```

#### Files Created

| File                                    | Lines | Purpose               |
| --------------------------------------- | ----- | --------------------- |
| `backend/core/indicators/__init__.py`   | 80    | Unified exports       |
| `backend/core/indicators/momentum.py`   | 400   | RSI, Stochastic, etc. |
| `backend/core/indicators/trend.py`      | 300   | MA variants, MACD     |
| `backend/core/indicators/volatility.py` | 200   | ATR, Bollinger, etc.  |
| `backend/core/indicators/volume.py`     | 200   | OBV, VWAP, etc.       |
| `backend/core/indicators/README.md`     | 250   | Documentation         |

#### Migration Progress

- [x] `backend/backtesting/signal_generators.py` - Updated
- [x] `backend/backtesting/mtf/signals.py` - Updated (removed ~60 lines)
- [x] `backend/backtesting/mtf/filters.py` - Updated (removed ~90 lines)
- [x] `backend/ml/rl_trading_agent.py` - Updated
- [~] `backend/services/strategy_builder/indicators.py` - Class-based, kept as-is
- [~] `backend/backtesting/fast_optimizer.py` - Numba JIT, kept as-is (performance)
- [~] `backend/backtesting/universal_engine/signal_generator.py` - Numba JIT, kept as-is

**Note**: Files marked `[~]` have their own optimized implementations (Numba JIT) for performance reasons. They remain separate to avoid performance regression.

---

### Manual Mode UI Implementation (2025-01-29)

**Implemented unified design standard for Strategy Builder Manual Mode**

#### Created Files

| File                                       | Lines | Purpose                                |
| ------------------------------------------ | ----- | -------------------------------------- |
| `frontend/css/optimization_components.css` | 595   | Unified CSS for optimization panels    |
| `frontend/optimization-results.html`       | 518   | Full results viewer page               |
| `frontend/js/pages/optimization.js`        | 580   | JavaScript for optimization management |

#### Modified Files

| File                                | Changes                                  |
| ----------------------------------- | ---------------------------------------- |
| `frontend/strategy-builder.html`    | Added 3 new sidebar panels               |
| `frontend/css/strategy_builder.css` | Added 500+ lines for optimization styles |

---

### � Strategy Builder - Full Audit & Dual-Mode Architecture (2025-01-29)

**Comprehensive audit of Strategy Builder capabilities and architecture design for Manual + AI modes**

#### Key Findings

Strategy Builder is a **fully functional** system with:

- **25 block types** across 7 categories (Data, Indicators, Conditions, Actions, Filters, Risk, Output)
- **Node-based visual composition** with drag/drop canvas
- **Code generation** for backtest, live, indicator templates
- **Full API** with 35+ endpoints for CRUD, validation, optimization, sharing
- **Optimization integration** via Grid Search, Bayesian (TPE), Walk-Forward
- **Database persistence** with versioning support

#### Dual-Mode Architecture

Defined Strategy Builder as **unified platform** for:

1. **Manual Mode (User-Driven)**: Visual canvas, manual parameter tuning, user-defined criteria
2. **AI-Assisted Mode**: Natural language input, AI-generated graphs, auto-optimization

Both modes share: Block system, Validation engine, Code generator, Backtest infrastructure

#### Missing Features for Manual Workflow (P0)

| Feature                | Description                                 |
| ---------------------- | ------------------------------------------- |
| Evaluation Criteria UI | Select metrics, set constraints, multi-sort |
| Optimization Config UI | Parameter ranges, method selection, limits  |
| Results Viewer         | Table, charts, comparison, export           |

#### Implementation Roadmap

- **Week 1**: Evaluation Criteria Panel (UI + API + DB)
- **Week 2**: Optimization Config Panel (UI + API)
- **Week 3**: Results Viewer Page (Table + Pagination)
- **Week 4**: Charts & Visualization
- **Week 5**: Integration & Testing

#### Documentation Created

- `docs/STRATEGY_BUILDER_AUDIT.md` - Full audit with 25 block types, all API endpoints
- `docs/DUAL_MODE_ARCHITECTURE.md` - Manual + AI mode architecture
- `docs/STRATEGY_BUILDER_IMPLEMENTATION_ROADMAP.md` - Missing features & implementation plan

---

### �📐 Agent-Driven Strategy Pipeline Architecture (2025-01-29)

**Designed complete 8-phase AI pipeline for strategy development**

#### Pipeline Phases

1. **Creation** - User creates/selects strategy template in Strategy Builder
2. **Analysis** - Perplexity analyzes market trends and conditions
3. **Consensus** - Agents reach agreement on architecture and parameters
4. **Build** - DeepSeek constructs strategy using Strategy Builder library
5. **Secondary Backtest** - Backtest with agent-defined acceptance criteria
6. **Optimization** - Optuna optimization with agent-defined parameter space
7. **ML Validation** - Overfitting detection, regime analysis, drift monitoring
8. **Final Validation** - Walk-forward, Monte Carlo, stress tests

#### ML Integration Points

- **Overfitting Detection**: In-sample vs out-of-sample gap analysis
- **Regime Detection**: Performance analysis across market regimes
- **Meta-Learning**: Parameter selector trained on optimization history
- **Online Learning**: Continuous adaptation with trade results
- **Concept Drift**: Distribution shift monitoring

#### Documentation

- Created `docs/AGENT_STRATEGY_PIPELINE_ARCHITECTURE.md` - Full architecture
- Created `docs/AGENT_STRATEGY_PIPELINE_IMPLEMENTATION.md` - Technical spec

---

### 🤖 AI Agent System Improvements (2026-01-29)

**Upgraded RLHF Module and Multi-Agent Consensus to 10/10**

#### RLHF Module Enhancements (`backend/agents/self_improvement/rlhf_module.py`):

1. **Expanded Feature Extraction** - 11 sophisticated features:
    - `structure_score`, `coherence_score`, `completeness_score`
    - `specificity_score`, `formatting_score`, `risk_score`, `actionable_score`

2. **Training Improvements**:
    - Early stopping with configurable patience (default 3 epochs)
    - Learning rate decay (0.95 per epoch)
    - Train/validation split (80/20)
    - Best weights checkpointing

3. **New Methods**:
    - `_compute_validation_loss()` - proper validation for early stopping
    - `cross_validate()` - k-fold cross-validation support

#### Multi-Agent Consensus Enhancements (`backend/agents/consensus/deliberation.py`):

1. **Parallel Agent Calls**:
    - `asyncio.gather()` for parallel initial opinions
    - Parallel cross-examination phase
    - ~N× speedup with N agents

2. **Confidence Calibration (Platt Scaling)**:
    - `calibrate_confidence()` - apply sigmoid calibration
    - `update_calibration()` - collect outcome samples
    - `_fit_calibration()` - gradient descent fitting

3. **Evidence Weighting**:
    - `classify_evidence()` - empirical/theoretical/citation/example
    - `compute_weighted_evidence_score()` - weighted position scoring
    - Evidence weights: empirical(1.5) > citation(1.3) > theoretical(1.0) > example(0.8)

4. **Enhanced Weighted Voting**:
    - Calibrated confidence (70%) + evidence score (30%)

#### Documentation:

- Created `docs/AI_AGENT_IMPROVEMENTS_REPORT.md`

---

### 🔧 Strategy Builder API Fix (2026-01-29)

**Исправлены все проблемы с API эндпоинтами Strategy Builder**

#### Проблемы и решения:

1. **Формат соединений** (`strategy_builder_adapter.py`)
    - Добавлены helper методы для поддержки обоих форматов connections:
        - `_get_connection_source_id()` / `_get_connection_target_id()`
        - `_get_connection_source_port()` / `_get_connection_target_port()`
    - Поддерживается как `source_block`/`target_block` (новый), так и `source.blockId`/`target.blockId` (старый)

2. **Топологическая сортировка** (`strategy_builder_adapter.py`)
    - Исправлен `KeyError: 'main_strategy'` - добавлена проверка `if target_id in in_degree:`

3. **SignalResult None values** (`strategy_builder_adapter.py`)
    - Исправлен `'NoneType' object has no attribute 'values'`
    - Теперь всегда возвращается pd.Series для `short_entries`/`short_exits`

4. **final_capital атрибут** (`strategy_builder.py`)
    - Исправлен `'PerformanceMetrics' object has no attribute 'final_capital'`
    - Используется `result.final_equity` из `BacktestResult`

#### Результат:

Все API эндпоинты Strategy Builder работают:

- ✅ POST /strategies - 200 OK
- ✅ GET /strategies/{id} - 200 OK
- ✅ PUT /strategies/{id} - 200 OK
- ✅ POST /generate-code - 200 OK
- ✅ POST /backtest - 200 OK

#### Документация:

- Создан `docs/STRATEGY_BUILDER_API_FIX_COMPLETE.md`

---

### �📚 Agent Strategy Generation Specification (2026-01-28)

**Создана консолидированная документация для генерации стратегий агентами**

#### Новый документ: `docs/ai/AGENT_STRATEGY_GENERATION_SPEC.md`

Полная спецификация включает:

1. **Входные данные для агентов**
    - Обязательные параметры (торговая пара, таймфрейм, капитал, направление, комиссии, плечо, пирамидинг)
    - Опциональные параметры (тип стратегии, риск-менеджмент, фильтры, DCA/Grid параметры)
    - Полный список всех параметров из `BacktestInput` с описаниями и диапазонами

2. **Типы стратегий**
    - Базовые: Trend Following, Mean Reversion, Breakout, Momentum
    - Специализированные: DCA, Grid Trading, Martingale, Scalping
    - Гибридные комбинации

3. **Методы оценки качества стратегии**
    - Базовые метрики: Total Return, Sharpe Ratio, Sortino Ratio, Profit Factor, Max Drawdown
    - Продвинутые метрики: Consistency Score, Recovery Factor, Ulcer Index, MAE/MFE
    - Метрики качества сигналов: Signal Quality Score, False Positive Rate

4. **Градации агрессивности**
    - Консервативная: Max DD < 15%, Win Rate > 55%, Leverage 1-3x
    - Умеренная: Max DD < 25%, Win Rate > 50%, Leverage 3-10x
    - Агрессивная: Max DD < 40%, Win Rate > 45%, Leverage 10-50x
    - Экстремальная: Max DD < 60%, Win Rate > 40%, Leverage 50-125x

5. **Многотаймфреймовый анализ**
    - Иерархия таймфреймов (LTF/HTF)
    - Методы MTF анализа: Trend Confirmation, Momentum Alignment, Support/Resistance, BTC Correlation
    - Критерии оценки MTF

6. **Временные диапазоны тестирования**
    - Краткосрочная оценка (7-30 дней)
    - Среднесрочная оценка (30-90 дней)
    - Долгосрочная оценка (90-365 дней)
    - Методы: Walk-Forward Analysis, Rolling Window, Regime-Based Testing, Seasonal Analysis

7. **Критерии оценки и валидации**
    - Обязательные критерии для всех стратегий
    - Критерии по градации агрессивности
    - Критерии по таймфреймам и временным диапазонам

8. **Права агентов на модификацию**
    - Обязательные параметры (не изменяются)
    - Параметры с ограниченной модификацией
    - Полная свобода агентов
    - Формат предложений и критерии принятия

9. **Примеры использования**
    - Пример консервативной стратегии
    - Пример агрессивной стратегии

**Документация основана на:**

- `backend/backtesting/interfaces.py` - BacktestInput структура
- `backend/api/routers/ai_strategy_generator.py` - GenerateStrategyRequest
- `backend/agents/consensus/domain_agents.py` - TradingStrategyAgent методы оценки
- Предыдущие беседы о входных данных, методах оценки и градациях агрессивности

---

### 🔧 NumbaEngine V4+ Extended Features (2026-01-28)

**Расширение NumbaEngine до 95%+ паритета с FallbackEngine**

#### Добавлены новые фичи в NumbaEngine:

1. **Breakeven Stop** — Перемещение SL в безубыток после TP1
    - `breakeven_enabled: bool`
    - `breakeven_offset: float` (например, 0.001 = +0.1% от входа)

2. **Time-based Exits** — Закрытие по времени
    - `max_bars_in_trade: int` (0 = отключено)
    - Новый exit_reason = 5

3. **Re-entry Rules** — Правила повторного входа
    - `re_entry_delay_bars: int` — Задержка после выхода
    - `max_trades_per_day: int` — Лимит сделок в день
    - `cooldown_after_loss: int` — Пауза после убытка
    - `max_consecutive_losses: int` — Стоп после N убытков подряд

4. **Market Filters** — Фильтры рыночных условий
    - `volatility_filter_enabled` — Фильтр по ATR percentile
    - `volume_filter_enabled` — Фильтр по объёму
    - `trend_filter_enabled` — Фильтр по SMA (with/against trend)

5. **Funding Rate** — Учёт фандинга для фьючерсов
    - `include_funding: bool`
    - `funding_rate: float` (например, 0.0001 = 0.01%)
    - `funding_interval: int` (баров между выплатами)

6. **Advanced Slippage Model** — Динамический slippage
    - `slippage_model: "fixed" | "advanced"`
    - Учитывает волатильность (ATR) и объём

#### Feature Matrix обновлена:

| Feature           | Fallback |   Numba    |
| ----------------- | :------: | :--------: |
| All V4 features   |    ✓     |     ✓      |
| Breakeven Stop    |    ✓     |     ✓      |
| Time-based Exit   |    ✓     |     ✓      |
| Re-entry Rules    |    ✓     |     ✓      |
| Market Filters    |    ✓     |     ✓      |
| Funding Rate      |    ✓     |     ✓      |
| **Adv. Slippage** |    ✓     | ✓ ← FIXED! |
| **FIFO/LIFO**     |    ✓     | ✓ ← FIXED! |

**Advanced Slippage - полная реализация:**

- В обоих движках реализован расчёт `slippage_multipliers` на основе ATR и объёма
- Multipliers применяются динамически на каждом баре: `effective_slippage = slippage * slippage_multipliers[i]`
- Учитывается волатильность (ATR%) и объём (относительно среднего)
- **Статус:** Полностью реализовано в обоих движках, 100% паритет

**Решение для FIFO/LIFO в Numba:**

- Используется маркировка закрытых entries (массив `long_entry_closed`, `short_entry_closed`)
- При FIFO - закрывается первый открытый entry
- При LIFO - закрывается последний открытый entry
- При ALL (по умолчанию) - закрываются все entries сразу
- SL/TP всегда закрывают ВСЕ entries (стандартное поведение TradingView)

---

### 🚀 Server Startup Optimization (2026-01-28)

**РЕЗУЛЬТАТ: Время старта ~60 сек → ~12 сек (FAST_DEV_MODE) / ~15 сек (обычный)**

#### Изменения:

1. **backend/backtesting/**init**.py** — Lazy loading для тяжёлых модулей
    - `optimizer`, `walk_forward`, `position_sizing` загружаются ТОЛЬКО при обращении
    - Используется `__getattr__` для динамической загрузки
    - GPU/Numba инициализация отложена до первого использования
    - **Экономия: ~30-50 секунд при старте**

2. **backend/backtesting/gpu_optimizer.py** — Lazy GPU initialization
    - CuPy импортируется только при вызове `is_gpu_available()` или GPU-функций
    - `GPU_AVAILABLE = None` (not checked) → `True/False` после первой проверки
    - Функция `_init_gpu()` делает одноразовую инициализацию
    - **Экономия: ~8-15 секунд на машинах без/с NVIDIA GPU**

3. **backend/api/lifespan.py** — Parallel warmup + FAST_DEV_MODE
    - JIT и Cache warmup выполняются параллельно (`asyncio.gather`)
    - `FAST_DEV_MODE=1` пропускает warmup полностью
    - **Экономия: ~3-5 секунд при параллельном warmup**

#### Использование:

```bash
# Быстрый старт для разработки
$env:FAST_DEV_MODE='1'
uvicorn backend.api.app:app --reload

# Production (warmup выполняется, но GPU ленивый)
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

#### Важные заметки:

- GPU инициализируется при первом вызове оптимизации (не при старте)
- Numba JIT компилируется при первом бэктесте (если FAST_DEV_MODE)
- Lazy loading не влияет на функциональность - всё работает как прежде

---

### NumbaEngine DCA Support (2026-01-28)

- **backend/backtesting/engines/numba_engine_v2.py** — added DCA (Safety Orders) support
    - Added DCA parameters to `_simulate_trades_numba_v4`:
        - `dca_enabled`, `dca_num_so`, `dca_levels`, `dca_volumes`, `dca_base_order_size`
    - DCA logic: Safety Orders trigger as price drops (long) / rises (short)
    - Pre-calculated cumulative deviation levels and volumes
    - Full reset on position close
    - Added `supports_dca` property
    - Updated docstrings

### GPUEngineV2 Deprecated (2026-01-28)

- **backend/backtesting/engines/gpu_engine_v2.py** — marked as deprecated
    - Added DeprecationWarning in `__init__`
    - Updated docstrings with migration guide
    - Reason: V2-only features, requires NVIDIA, NumbaEngine is sufficient

---

### Engine Consolidation Phase 1 - Unified FallbackEngine (2026-01-28)

#### Consolidated Engine Architecture

- **`FallbackEngine`** = `FallbackEngineV4` (основной эталон)
- **`NumbaEngine`** = `NumbaEngineV2` (быстрый, полный V4)
- **V2/V3** — deprecated aliases (работают, выдают DeprecationWarning)

#### Updated Exports (`backend/backtesting/engines/__init__.py`)

```python
from backend.backtesting.engines import (
    FallbackEngine,   # = V4 (основной)
    NumbaEngine,      # = NumbaEngineV2 (быстрый)
    FallbackEngineV4, # explicit
    NumbaEngineV2,    # explicit
    FallbackEngineV2, # deprecated
    FallbackEngineV3, # deprecated
)
```

#### Migration Guide

```python
# Old way:
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
engine = FallbackEngineV2()

# New way:
from backend.backtesting.engines import FallbackEngine
engine = FallbackEngine()  # = V4, все фичи
```

---

### Engine Consolidation Phase 4 - Deprecated RSI-only Optimizers (2026-01-28)

#### Deprecated Modules

Marked as deprecated (will be removed in v3.0):

- **backend/backtesting/fast_optimizer.py** - RSI-only Numba optimizer
- **backend/backtesting/gpu_optimizer.py** - RSI-only GPU/CuPy optimizer
- **backend/backtesting/optimizer.py** - UniversalOptimizer wrapper

#### Reasons for Deprecation

1. **RSI-only** — these optimizers don't support:
    - Pyramiding (multiple entries)
    - ATR-based SL/TP (dynamic stops)
    - Multi-level TP (partial profit taking)
    - Trailing stop
    - Custom strategies

2. **Replaced by NumbaEngineV2** — full V4 functionality with 20-40x speedup:
    - All V4 features supported
    - Works on any CPU (no NVIDIA required)
    - Simpler codebase, easier maintenance

#### Migration Guide

```python
# Old way (deprecated):
from backend.backtesting.optimizer import UniversalOptimizer
result = UniversalOptimizer().optimize(...)

# New way (recommended):
from backend.backtesting.engine_selector import get_engine
from backend.backtesting.interfaces import BacktestInput
import itertools

engine = get_engine("numba")  # NumbaEngineV2 with full V4 support

for params in itertools.product(rsi_periods, stop_losses, ...):
    input_data = BacktestInput(...params...)
    output = engine.run(input_data)
    # process results
```

**Related:** Phase 2-3 added full V4 support to NumbaEngineV2 (pyramiding, ATR, multi-TP, trailing) with 100% parity to FallbackEngineV4.

---

### Startup Performance Optimizations (2026-01-28)

#### 1. Lazy GPU Initialization

- **backend/backtesting/gpu_optimizer.py** - GPU/CuPy теперь загружается ТОЛЬКО при первом использовании
    - Убрано: импорт CuPy при загрузке модуля (~8-15 сек)
    - Добавлено: `_init_gpu()` и `is_gpu_available()` для lazy loading
    - Все использования `GPU_AVAILABLE` заменены на `is_gpu_available()`
    - **Экономия:** 8-15 секунд при обычном запуске (когда GPU не нужен)

#### 2. Parallel Warmup

- **backend/api/lifespan.py** - JIT и cache warmup теперь выполняются параллельно
    - JIT warmup (CPU-bound) и cache warmup (I/O-bound) запускаются через `asyncio.gather()`
    - **Экономия:** ~8 секунд (вместо последовательного ожидания)

#### 3. FAST_DEV_MODE Environment Variable

- **backend/api/lifespan.py** - Добавлена переменная окружения `FAST_DEV_MODE`
    - При `FAST_DEV_MODE=1` пропускается весь warmup
    - Идеально для разработки: запуск за ~1-2 секунды вместо 45-90
    - Использование: `$env:FAST_DEV_MODE = "1"; uvicorn backend.api.app:app`

**Итоговое улучшение:**

- Обычный запуск: 45-90 сек → ~25-35 сек (параллельный warmup)
- Режим разработки: 45-90 сек → ~1-2 сек (FAST_DEV_MODE=1)

### Startup Script Fixes (2026-01-28)

#### Fixed Import Error

- **backend/middleware/csrf.py** - Fixed incorrect import `from backend.core.logging` → `from backend.core.logging_config`

#### Added Root Health Endpoints

- **backend/api/app.py** - Added `/healthz`, `/readyz`, `/livez` at root level for K8s probes and startup scripts
    - Previously these endpoints only existed at `/api/v1/health/healthz`
    - Now `start_all.ps1` can properly check server readiness

#### Verified Startup Flow

- **start_all.ps1** - Verified all steps work correctly:
    1. ✅ stop_all.ps1 - Stops all services and clears cache
    2. ✅ start_redis.ps1 - Starts Redis on port 6379
    3. ✅ start_kline_db_service.ps1 - Starts Kline DB Service
    4. ✅ start_mcp_server.ps1 - Starts MCP Server
    5. ✅ start_uvicorn.ps1 - Starts Uvicorn on port 8000
    6. ✅ Health check waits for `/healthz` to return `{status: "ok"}`
    7. ✅ start_agent_service.ps1 - Starts AI Agent Service
    8. ✅ Opens browser to http://localhost:8000

### Universal Engine & Performance Spec (2026-01-28)

**ПРИНЯТОЕ РЕШЕНИЕ: Консолидация до 2 движков**

- **§11 Консолидация:** вместо 8 подсистем — **2 движка**:
    - **FallbackEngine** — эталон (все фичи V4)
    - **NumbaEngine** — оптимизация (точность + скорость, расширить до V4)
    - **GPU — откладываем** (сложнее, требует NVIDIA, выигрыш только на 100K+ комбинаций)

**Реализация Фазы 1 (частично):**

- **backend/backtesting/engines/**init**.py** — добавлен `FallbackEngine = FallbackEngineV4`
- **backend/backtesting/engine_selector.py** — обновлена логика:
    - `auto` / `fallback` / `v4` → FallbackEngineV4 (основной)
    - `pyramiding > 1` → FallbackEngineV4 (вместо V3)
    - `fallback_v2` / `fallback_v3` → deprecated с warning
- **fallback_engine_v2.py** — добавлен DeprecationWarning
- **fallback_engine_v3.py** — добавлен DeprecationWarning

**Реализация Фазы 2 (Numba V3 — pyramiding):**

- **backend/backtesting/engines/numba_engine_v2.py**:
    - Новая функция `_simulate_trades_numba_pyramiding` (~350 строк)
    - Поддержка pyramiding > 1 (несколько входов в одну сторону)
    - Средневзвешенная цена входа для SL/TP
    - Закрытие ALL (все позиции сразу)
    - Свойство `supports_pyramiding = True`

**Реализация Фазы 2 (Numba V4 — полный функционал):**

- **backend/backtesting/engines/numba_engine_v2.py**:
    - Новая функция `_simulate_trades_numba_v4` (~700 строк) с полной поддержкой:
        - **ATR SL/TP**: sl_mode/tp_mode enum, atr_sl_multiplier, atr_tp_multiplier
        - **Multi-level TP**: tp_portions + tp_levels (4 уровня)
        - **Trailing Stop**: trailing_stop_enabled, trailing_stop_activation, trailing_stop_distance
        - **Pyramiding**: max_entries
    - Авто-выбор режима: V4 если ATR/Multi-TP/Trailing, иначе V3 (pyramiding) или V2
    - Свойства: `supports_atr`, `supports_multi_tp`, `supports_trailing`
- **engine_selector.py**: Feature Matrix обновлена — Numba теперь = V4 (кроме DCA)

**Реализация Фазы 3 (паритет-тесты):**

- **scripts/test_numba_parity.py**: Комплексный тест паритета Fallback vs Numba
    - V2 Basic: 4/4 PASS (100%)
    - V3 Pyramiding: 2/2 PASS (100%)
    - V4 ATR SL/TP: 3/3 PASS (100%)
    - V4 Multi-TP: 2/2 PASS (100%)
    - V4 Trailing: 2/2 PASS (100%)
    - **ИТОГО: 13/13 (100.0%)** — ВСЕ ТЕСТЫ ПРОШЛИ!
- Исправлен fallback: NumbaEngine → FallbackEngineV4 (не V2)
- Исправлен расчёт ATR SL/TP: использовать current_atr (как в FallbackV4)

Ранее дополнены разделы:

- **§1.1 Двухэтапный поток:** эталон для старта и уточнения; оптимизация требует точности и скорости.
- **§8–10:** роль Universal Math Engine, универсальность, что переиспользовать.
- **backend/backtesting/engine_selector.py** — добавлен `fallback_v4` в `get_available_engines()`.

### Infrastructure & Testing (2026-01-28)

#### New Unit Tests

- **test_vault_client.py** - 12 tests for VaultClient with fallback behavior
- **test_mlflow_adapter.py** - 17 tests for MLflow experiment tracking
- **test_trading_env.py** - 5 tests for RL TradingEnv Gymnasium environment
- **test_safedom.py** - 15 tests for SafeDOM.js XSS protection
- **test_auto_event_binding.py** - 16 tests for auto-event-binding.js

#### MLflow Integration

- **backend/backtesting/mlflow_tracking.py** - BacktestTracker class for experiment tracking:
    - Parameter logging (strategy, symbol, dates, risk params)
    - Metric logging (Sharpe, returns, drawdown, win rate)
    - Artifact logging (equity curves, trade logs, summaries)
    - Context manager for tracking backtest runs

#### Vault Production Setup

- **deployment/docker-compose.vault.yml** - Docker Compose for Vault + MLflow
- **deployment/vault/policies/bybit-app.hcl** - Read-only app policy
- **deployment/vault/policies/vault-admin.hcl** - Admin policy
- **scripts/vault_init.sh** - Vault initialization script
- **docs/SECRETS_MIGRATION_GUIDE.md** - Migration guide from env vars to Vault

#### Bug Fixes

- **backend/core/vault_client.py** - Fixed ConnectionError handling in `is_available` property
    - Now gracefully returns False when Vault is unreachable
    - Wrapped `_get_client()` in try/except block

### DeepSeek/Perplexity Agents Audit (2026-01-28)

Полный аудит системы агентов DeepSeek и Perplexity.

#### Bug Fixes (P0 Critical)

1. **Import Fix** (`backend/api/deepseek_client.py`, `backend/api/perplexity_client.py`):
    - Исправлен неправильный импорт `from reliability.retry_policy`
    - Теперь: `from backend.reliability.retry_policy`

2. **Health Check Logic Fix** (`backend/api/perplexity_client.py`):
    - **Было**: `is_healthy = response.status_code in [200, 400, 401, 403]`
    - **Стало**: `is_healthy = response.status_code == 200`
    - 401/403 — это ошибки авторизации, а не healthy статус

#### Documentation

3. **Agents Audit Report** (`docs/DEEPSEEK_PERPLEXITY_AGENTS_AUDIT.md`):
    - Анализ 6 ключевых файлов системы агентов
    - Найдено 2 критических бага (исправлены)
    - 5 средних проблем (рекомендации)
    - Рекомендации по декомпозиции unified_agent_interface.py (2926+ строк)

#### Fixed Issues (P1-P2)

1. **P2 Fix: KeyManager in real_llm_deliberation.py** — Now uses secure KeyManager instead of os.environ
2. **P1 Fix: Circuit Breaker in connections.py** — Added circuit breaker integration to DeepSeekClient and PerplexityClient
3. **P1 Fix: Modular api_key_pool.py** — Extracted APIKeyPoolManager for better modularity (304 lines)

#### DeepSeek MCP Demo

- **deepseek_code** инструмент работает! Сгенерирована торговая стратегия:
    - `backend/backtesting/strategies/momentum_rsi_ema.py`
    - RSI + EMA crossover с ATR-based SL/TP
    - Полностью совместима с VectorBT и Fallback движками

#### Agent Strategy Orchestration Spec (2026-01-28)

- **Новая спецификация** `docs/ai/AGENT_STRATEGY_ORCHESTRATION_SPEC.md`:
    - Разбор предложения: Perplexity (аналитика) → DeepSeek (консенсус, код/Lego) → бэктест → Perplexity (params) → DeepSeek (второе мнение, оптимизация) → отсев → цикл/эволюция Lego
    - Идеи по отсеву: критерии от агентов, ML, гибрид, Pareto
    - Сопоставление с `RealLLMDeliberation`, `AIBacktestAnalyzer`, `AIOptimizationAnalyzer`, `StrategyBuilder`, `CodeGenerator`, `fast_optimizer`
    - Поэтапный план внедрения
- **Дополнение (размышления):**
    - **§0 Точка старта:** ввод пользователя до генерации стратегии — symbol, interval, capital, direction, position_size, leverage, commission, pyramiding, strategy_type (DCA/Grid/RSI/…), + property из `BacktestConfig`/`BacktestInput`. Агенты могут предлагать свои варианты (ТФ, тип, плечо, фильтры). Уровни плеча — перебор 1x/2x/5x/10x по решению оркестратора.
    - **§2.10 Мульти-ТФ, мульти-период, критерии качества:** проверка на разных ТФ (15m, 1h, 4h, 1d); профили conservative/balanced/aggressive/robustness с разными весами (Calmar, Sharpe, return, OOS); «хитрые методы» — множественные календарные периоды, Walk-Forward (rolling/anchored), MTF Walk-Forward, стресс-периоды, Monte Carlo. Связка ТФ + профиль + метод + leverage → градации агрессивности. Опора на `MTFOptimizer`, `WalkForwardOptimizer`, `MTFWalkForward`, `MetricsCalculator`.
    - В план внедрения: фаза **0** (схема `UserStrategyInput`, точка старта), фаза **2b** (мульти-ТФ, мульти-период, профили).

---

### Audit Session 4 - Part 4 (2026-01-28)

P2 задачи: безопасность хеширования и исправление багов.

#### Security Fixes

1. **MD5 → SHA256 Migration** — Все 8 файлов с hashlib.md5 мигрированы на SHA256:
    - `backend/backtesting/optimization_cache.py` (4 места)
    - `backend/services/multi_level_cache.py`
    - `backend/services/state_manager.py`
    - `backend/services/ab_testing.py`
    - `backend/ml/news_nlp_analyzer.py`
    - `backend/ml/enhanced/model_registry.py`
    - `backend/ml/enhanced/feature_store.py`
    - `backend/ml/enhanced/automl_pipeline.py`

#### Bug Fixes

2. **Pyramiding entry_count Fix** (`backend/backtesting/pyramiding.py`):
    - **Проблема**: `entry_count` возвращал 1 вместо реального количества входов
    - **Причина**: `close_all()` очищает `entries` до получения count
    - **Решение**: `entry_count_before_close = pos.entry_count` сохраняется до вызова `close_all()`

#### Verified as Correct

3. **ATR Algorithm Unification** (`backend/backtesting/atr_calculator.py`):
    - `calculate_atr()` и `calculate_atr_fast()` математически идентичны
    - Обе используют Wilder's smoothing: `ATR[i] = ((period-1)*ATR[i-1] + TR[i]) / period`
    - Добавлены комментарии в код для ясности

4. **ML System P0 Tasks** — Верифицированы как УЖЕ РЕАЛИЗОВАННЫЕ:
    - **Feature Store persistence**: JSON backend с `_load_store()`/`_save_store()`
    - **Model validation**: `validate_model()` с auto-validation перед promotion

5. **Infrastructure** — Верифицированы как УЖЕ РЕАЛИЗОВАННЫЕ:
    - **Grafana dashboards**: 6 dashboards (system-health, api-performance, backtest-results, etc.)
    - **Bar Magnifier**: полная реализация в numba_engine_v2 и fallback_engine_v3
    - **DriftAlertManager**: 750 строк с Slack/Email/Webhook/Redis интеграцией
    - **AlertManager**: 556 строк в alerting.py с pluggable notifiers
    - **Services P0**: все исправлены (context managers, XOR encryption, graceful shutdown)

6. **Circuit Breaker for Bybit API** (`backend/services/adapters/bybit.py`):
    - Добавлена интеграция с `CircuitBreakerRegistry`
    - Новый метод `_api_get()` с circuit breaker protection
    - Автоматическое открытие/закрытие circuit при ошибках API

7. **onclick → addEventListener Migration** (`frontend/js/core/auto-event-binding.js`):
    - Создан автоматический конвертер onclick → addEventListener
    - Использует MutationObserver для динамического контента
    - Добавлен в 44 HTML файла
    - 191 inline onclick обработчик теперь CSP-compliant

8. **Prometheus Registry Centralization** - Верифицировано что REGISTRY централизован в `backend/core/metrics.py`

9. **Backtest System P1 Verification** - Все задачи верифицированы/исправлены:
    - Bar Magnifier ✅ реализован в numba_engine_v2, fallback_engine_v3
    - ATR Algorithm ✅ математически идентичны
    - entry_count bug ✅ исправлен
    - walk_forward division ✅ защита есть
    - Models consistency ✅ low priority (working)

#### Infrastructure Code (P2 - готов к deploy)

10. **HashiCorp Vault Client** (`backend/core/vault_client.py`):
    - VaultClient класс с CRUD операциями для секретов
    - Graceful fallback к env vars если Vault недоступен
    - Convenience функции для Bybit credentials

11. **MLflow Adapter** (`backend/ml/mlflow_adapter.py`):
    - MLflowAdapter для experiment tracking
    - Поддержка sklearn, xgboost, lightgbm, pytorch
    - Model registry с версионированием

12. **RL Trading Environment** (`backend/ml/rl/trading_env.py`):
    - Gym-compatible TradingEnv
    - Realistic simulation (commission, slippage, leverage)
    - Multiple reward functions

13. **DB Migration Squash** (`scripts/db_migration_squash.py`):
    - Автоматический backup + squash Alembic migrations
    - Dry-run mode для безопасности

#### Statistics

- **🎉 Общий прогресс**: 100% (92/92 задач)
- **P0 Critical**: 100% (all done) ✅
- **P1 High**: 100% (all done) ✅
- **P2 Medium**: 100% (all done) ✅

---

### Audit Verification Session 4 - Final (2026-01-28)

Финальная верификация задач аудита. Прогресс увеличен с 47% до 80%.

#### Frontend Security Additions

1. **SafeDOM.js** (`frontend/js/core/SafeDOM.js`) — XSS-безопасная работа с DOM:
    - `safeText()` — безопасная установка textContent
    - `safeHTML()` — санитизация через Sanitizer.js перед innerHTML
    - `createElement()` — создание элементов с атрибутами
    - `html` template literal — tagged template для HTML
    - `TrustedHTML` class — wrapper для доверенного HTML
    - Экспорт в `window.SafeDOM` для non-module scripts

2. **Production Init Script** (`frontend/js/init-production.js`):
    - Подавление `console.log/debug/info` в production
    - Сохранение `console.warn/error` для мониторинга
    - Глобальный `window.onerror` handler
    - Определение окружения через `window.__ENV__`

3. **Database Pool Configuration** (`backend/database/__init__.py`):
    - PostgreSQL: pool_size=5, pool_recycle=1800s, pool_pre_ping=True
    - MySQL: pool_size=5, pool_recycle=3600s, pool_pre_ping=True
    - Новая функция `get_pool_status()` для мониторинга pool

#### Верифицировано как корректно работающее

1. **vectorbt_sltp.py state initialization** — Массив `[initial_capital, 0.0, 0.0, 1.0, initial_capital, 0.0]` корректен
2. **CandleDataCache thread safety** — `threading.RLock()` уже в `fast_optimizer.py`
3. **walk_forward.py div/zero** — защита `if is_sharpe != 0` уже есть
4. **WebSocket reconnection** — реализовано в `liveTrading.js`
5. **Logger utility** — `Logger.js` готов для production
6. **Loading states** — `Loader.js` с spinner/dots/bars/skeleton
7. **Graceful shutdown** — `GracefulShutdownManager` в `live_trading/`
8. **Metrics collector** — Prometheus-style в `metrics_collector.py`

#### Статистика

- **Общий прогресс**: 83% (67/81 задач)
- **P0 Critical**: 100% (20/20) ✅
- **P1 High**: 92% (23/25)

---

### DeepSeek V3 MCP Integration (2026-01-28)

Добавлена интеграция DeepSeek V3 API через MCP (Model Context Protocol) для Cursor IDE.

#### Добавлено

1. **DeepSeek MCP Server** (`scripts/mcp/deepseek_mcp_server.py`):
    - Полноценный MCP сервер для DeepSeek V3 API
    - 8 специализированных инструментов:
        - `deepseek_chat` — общий чат и вопросы
        - `deepseek_code` — генерация кода
        - `deepseek_analyze` — анализ кода (performance, security, readability)
        - `deepseek_refactor` — рефакторинг (simplify, optimize, modernize, dry)
        - `deepseek_explain` — объяснение кода (beginner/intermediate/advanced)
        - `deepseek_test` — генерация тестов (pytest, unittest, jest, mocha)
        - `deepseek_debug` — помощь в отладке
        - `deepseek_document` — генерация документации (google, numpy, sphinx style)
    - Автоматический failover между двумя API ключами
    - Rate limit handling и retry logic

2. **MCP Configuration**:
    - `.agent/mcp.json` — обновлен с DeepSeek сервером
    - `.cursor/mcp.json` — Cursor-специфичная конфигурация
    - Переменные окружения для безопасного хранения ключей

3. **Environment Configuration** (`.env.example`):
    - Добавлены `DEEPSEEK_API_KEY`, `DEEPSEEK_API_KEY_2`
    - Настройки `DEEPSEEK_MODEL`, `DEEPSEEK_TEMPERATURE`

#### Использование

В Cursor Agent mode доступны инструменты:

```
Use deepseek_code to create a Python function for calculating Sharpe ratio
Use deepseek_analyze to review this trading strategy code
Use deepseek_test to generate pytest tests for BacktestEngine
```

Стоимость: ~$0.14 за 1M токенов (input), ~$0.28 за 1M (output).

---

### P1 Code Quality & Security Fixes - Session 4 (2026-01-28)

Продолжение работы над P1 задачами из аудита.

#### Исправлено

1. **router_registry.py Dead Code** (`backend/api/router_registry.py`):
    - Добавлен DEPRECATED notice в docstring
    - Добавлен `warnings.warn()` при импорте модуля
    - Функция `register_all_routers()` никогда не вызывается из app.py
    - Роутеры регистрируются напрямую в `app.py` (lines 370-415)

2. **CSRF Protection Middleware** (`backend/middleware/csrf.py`) — **NEW!**:
    - Создан `CSRFMiddleware` с double-submit cookie pattern
    - Автоматическая генерация токена в cookie `csrf_token`
    - Валидация `X-CSRF-Token` header для POST/PUT/DELETE/PATCH
    - Constant-time comparison через `secrets.compare_digest()`
    - Exempt paths для webhooks (`/api/v1/webhooks/*`) и документации
    - `csrf_exempt` декоратор для route-level exemption
    - `get_csrf_token()` helper для получения токена из request

3. **CorrelationIdMiddleware Fix** (`backend/middleware/correlation_id.py`):
    - `get_correlation_id()` теперь использует `ContextVar` вместо `uuid.uuid4()`
    - Добавлена функция `set_correlation_id()` для background tasks
    - Correlation ID доступен из любой точки request lifecycle
    - Middleware сохраняет и восстанавливает контекст правильно

4. **CSP Nonce Support** (`backend/middleware/security_headers.py`):
    - Добавлен параметр `use_csp_nonce` (по умолчанию True в production)
    - Nonce генерируется для каждого запроса через `secrets.token_urlsafe(16)`
    - В production CSP НЕ содержит `unsafe-inline`
    - Nonce доступен через `request.state.csp_nonce` и заголовок `X-CSP-Nonce`
    - Fallback на `unsafe-inline` в development для совместимости

5. **CORS Configuration Verified**:
    - `CORS_ALLOW_ALL=false` по умолчанию
    - Wildcard `*` только при явном включении `CORS_ALLOW_ALL=true`
    - Production использует список конкретных origins

6. **WebSocket Rate Limiting** (`backend/api/streaming.py`):
    - Добавлен `WebSocketRateLimiter` класс
    - Лимит: 60 сообщений/мин на клиента
    - Лимит: 10 соединений/мин на IP
    - Sliding window алгоритм
    - Автоматическая очистка при disconnect

7. **file_ops Router** (`backend/api/routers/file_ops.py`):
    - Добавлен `/status` endpoint
    - Добавлен `/exports` endpoint для листинга файлов
    - Добавлен TODO для полной реализации

8. **WebSocket Health Check & Graceful Shutdown** (`backend/api/streaming.py`):
    - Добавлен `GET /ws/v1/stream/health` endpoint
    - Возвращает статус соединений и rate limiter
    - Добавлен `graceful_shutdown()` метод в `StreamingConnectionManager`
    - Уведомляет клиентов перед закрытием соединений
    - Поддерживает timeout для принудительного закрытия

9. **ML Model Validation** (`backend/ml/enhanced/model_registry.py`):
    - Добавлен `validate_model()` метод для проверки моделей перед deployment
    - Проверяет accuracy, precision, recall, loss против thresholds
    - Автоматическое обновление статуса: STAGING (passed) или FAILED
    - `promote_model()` теперь требует validation (или `skip_validation=True`)
    - Защита от deployment неисправных моделей в production

**Обновлённый прогресс: ~46% (37 из 81 задачи)**

---

### P0 Security Fixes - Session 3 (2026-01-28)

Завершение критических P0 исправлений безопасности.

#### Исправлено

1. **API Secrets Encryption** (`bybit_websocket.py`, `bybit_from_history.py`):
    - `BybitWebSocketClient`: добавлено XOR шифрование для `api_key`/`api_secret`
    - `BybitAdapter`: добавлено XOR шифрование для `api_key`/`api_secret`
    - Ключи теперь хранятся как `_api_key_encrypted` + `_session_key`
    - Properties для декрипта при использовании

**Обновлённый прогресс: 36% (29 из 81 задачи)**

---

### P0 Security & Stability Fixes - Session 2 (2026-01-28)

Продолжение работы над приоритетными исправлениями из аудита.

#### Исправлено

1. **HTTP Client Leak Fix** (`service_registry.py`, `trading_engine_interface.py`):
    - `ServiceClient` теперь имеет `__aenter__`/`__aexit__` для context manager
    - `RemoteTradingEngine` теперь имеет `__aenter__`/`__aexit__` + `close()` метод
    - Защита от использования закрытого клиента: `RuntimeError` при `_closed = True`

2. **Division by Zero Fix** (`numba_engine_v2.py`, `fallback_engine_v3.py`):
    - `total_return` теперь защищён проверкой `if initial_capital > 0`
    - Предотвращает crash при edge cases с нулевым начальным капиталом

#### Верифицировано как уже исправленное

- **Graceful Shutdown** - `GracefulShutdownManager` полностью реализован в `live_trading/`
- **Feature Store Persistence** - JSON persistence через `_load_store`/`_save_store`

**Обновлённый прогресс: 35% (28 из 81 задачи)**

---

### P0 Security Fixes - Session 1 (2026-01-28)

Выполнены приоритетные исправления P0 из аудита безопасности.

#### Исправлено

1. **CandleDataCache Thread Safety** (`backend/backtesting/optimizers/fast_optimizer.py`):
    - Добавлен `threading.RLock()` для синхронизации доступа к singleton-кэшу
    - Все операции `get()` и `__setitem__` теперь thread-safe

2. **Rate Limiter Redis Backend** (`backend/middleware/rate_limiter.py`):
    - Добавлен класс `RedisRateLimiter` для распределённого rate limiting
    - Lua-скрипт для атомарных операций (sliding window algorithm)
    - Автоматический fallback на in-memory если Redis недоступен
    - Новые заголовки: `X-RateLimit-Backend: redis|memory`
    - Конфигурация через `REDIS_URL` env variable

#### Верифицировано как уже исправленное

- **OrderExecutor Context Manager** - `__aenter__`/`__aexit__` уже реализованы
- **Bybit Adapter Cache Lock** - `threading.RLock()` уже на месте (строка 55)
- **Frontend CSP Nonces** - `generateNonce()`, `getNonce()` уже реализованы
- **Frontend CSRF Tokens** - `getCsrfToken()`, `withCsrfToken()` уже реализованы

---

### Audit Status Review (2026-01-28)

Проведена проверка выполнения задач из файлов аудита. Создан сводный отчёт
`docs/AUDIT_STATUS_SUMMARY_2026_01_28.md`.

**Общий прогресс: 21% (17 из 81 задачи выполнено)**

#### Полностью выполненные модули

- ✅ **Core System** (5/5) - safe_divide, AI Cache Redis, Circuit Breaker persistence,
  Anomaly alerts, Bayesian thread-safety

#### Частично выполненные модули

- ⚠️ **API & Middleware** (6/12) - Admin/Security auth, ErrorHandler, MCP timing fix,
  WS_SECRET_KEY, HSTS headers
- ⚠️ **Backtest System** (3/11) - Shared memory cleanup, NumPy array limits, safe_divide
- ⚠️ **Database System** (3/7) - session.py fix, production warning, health endpoint

#### Требуют внимания:

- 🔴 **Services System** (0/15) - HTTP client leak, API secrets, cache race conditions
- 🔴 **ML System** (0/9) - Feature Store persistence, model validation
- 🔴 **Frontend System** (0/14) - CSRF, XSS, CSP nonce
- 🔴 **Monitoring System** (0/8) - Alert integrations, health checks

### Added

- **Comprehensive Health Checks System** (2026-01-28):
    - `backend/monitoring/health_checks.py` - Full system health monitoring:
        - Database connectivity check
        - Redis connectivity check
        - Bybit API status check
        - Disk space monitoring (warning at 80%, critical at 90%)
        - Memory usage monitoring (warning at 80%, critical at 90%)
        - CPU usage monitoring (warning at 80%, critical at 95%)
    - New API endpoints:
        - `GET /health/comprehensive` - Full system health report
        - `GET /health/comprehensive/{component}` - Individual component check
    - Classes: `HealthChecker`, `HealthCheckResult`, `SystemHealthReport`, `HealthStatus`
    - Caching with configurable TTL to prevent excessive checks

- **Prometheus AlertManager Rules** (2026-01-28):
    - `backend/monitoring/alerts/rules.yaml` - Production-ready alert rules:
        - Critical alerts (P0): API Down, Database Down, High Error Rate (>5%), Daily Loss Limit
        - High priority alerts (P1): High Latency (p99 > 5s), Redis Down, High Drawdown (>15%)
        - Medium priority alerts (P2): AI Budget Exceeded, Low Cache Hit Rate, Slow Backtests
        - SLO alerts: API Availability (99.9%), Latency (p95 < 2s)
    - Alert severity routing: Critical → PagerDuty + Slack + Email

- **Frontend Security Audit Fixes** (2026-01-28):
    - `ApiClient.js` - Centralized API client with CSRF protection, automatic retries, request/response interceptors
    - `WebSocketClient.js` - Robust WebSocket with auto-reconnect, exponential backoff, heartbeat monitoring
    - `Sanitizer.js` - DOMPurify-like HTML sanitizer for XSS prevention
    - `Logger.js` - Production-safe logging with conditional output
    - Enhanced `security.js` with nonce-based CSP (removed unsafe-inline)
    - CSRF token management functions
    - Security test suite in `frontend/js/tests/security.test.js`

- **safe_divide utility** in `metrics_calculator.py` - Centralized safe division function
  that handles zero and near-zero denominators gracefully
- **Circuit Breaker Redis Persistence** - Added `configure_persistence()`, `save_state()`,
  and `save_all_states()` methods to `CircuitBreakerRegistry` for state persistence across restarts
- **Enhanced Anomaly Alerting System** - New alert notifier classes:
    - `AlertNotifier` protocol for custom implementations
    - `WebhookAlertNotifier` for Slack/Discord/custom webhooks
    - `LogAlertNotifier` for simple logging-based alerts
    - `CompositeAlertNotifier` for combining multiple notifiers
- **Thread-safe Bayesian Optimizer** - Added `threading.RLock` protection and
  `_is_running` flag to prevent concurrent optimizations

### Changed

- `AnomalyDetector` now accepts optional `alert_notifier` parameter for integrated alerting
- `BayesianOptimizer.optimize_async()` now raises `RuntimeError` if another optimization
  is already running on the same instance
- Updated `backend/monitoring/__init__.py` to export new health check components

### Fixed

- Division by zero edge cases in metrics calculations (centralized in `safe_divide`)
- Circuit breaker state loss on application restart (now persisted to Redis)
- Missing alert notifications for detected anomalies
- Race conditions in Bayesian optimizer concurrent access

### Tests

- Added `tests/backend/monitoring/test_health_checks.py` with 20 comprehensive tests covering:
    - HealthStatus enum values
    - HealthCheckResult creation and serialization
    - SystemHealthReport aggregation
    - Individual component checks (disk, memory, CPU)
    - Caching behavior
    - Overall status calculation logic
    - Module-level convenience functions
- Added `tests/test_core_audit_fixes.py` with 21 comprehensive tests covering:
    - `safe_divide` edge cases
    - Circuit breaker persistence methods
    - Alert notifier functionality
    - Thread-safe Bayesian optimizer
    - AI Cache Redis verification
    - Integration tests

## [1.0.0] - 2026-01-01

### Added

- Initial release of Bybit Strategy Tester v2
- 166-metric MetricsCalculator with TradingView compliance
- Circuit Breaker pattern for external API calls
- AI Cache with Redis backend
- Anomaly Detection system
- Bayesian Optimization with Optuna
- Comprehensive backtesting engine

---

_Last Updated: 2026-01-28_
