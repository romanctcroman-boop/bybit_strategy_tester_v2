"""
Builder Workflow — AI Agent orchestration for the visual Strategy Builder.

Provides a full pipeline for agents to build and test strategies through
the same Strategy Builder interface that users see:

1. **Plan** — Analyze market context and decide which blocks to use
2. **Create** — Create a new strategy canvas
3. **Build** — Add indicator, filter, condition, action, and exit blocks
4. **Wire** — Connect blocks together in a logical signal flow
5. **Validate** — Validate the strategy for completeness
6. **Generate** — Generate Python code from the block graph
7. **Backtest** — Run backtest and collect metrics
8. **Evaluate** — Score results and decide whether to iterate

All operations go through the same REST API that the frontend uses,
so every action is visible to the user in real-time.

Added 2026-02-14 — Agent x Strategy Builder Integration.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from functools import lru_cache
from typing import Any

from loguru import logger

from backend.agents.mcp.tools.strategy_builder import (
    builder_add_block,
    builder_connect_blocks,
    builder_create_strategy,
    builder_generate_code,
    builder_get_block_library,
    builder_run_backtest,
    builder_update_block_params,
    builder_validate_strategy,
)

# ---------------------------------------------------------------------------
# Singletons — shared across all BuilderWorkflow instances in one process
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_workflow_memory():
    """Return the process-wide HierarchicalMemory instance (SQLite backend).

    Persists backtest results, best parameter configs, and optimization history
    so that subsequent workflow runs can learn from past experiments on the
    same strategy / symbol / timeframe.
    """
    from backend.agents.memory.hierarchical_memory import HierarchicalMemory

    persist_path = "agent_memory/builder_workflow"
    logger.info(f"[BuilderWorkflow] 🧠 HierarchicalMemory initialised at {persist_path!r}")
    return HierarchicalMemory(persist_path=persist_path)


@lru_cache(maxsize=1)
def _get_a2a_communicator():
    """Return the process-wide AgentToAgentCommunicator instance.

    Used in _suggest_adjustments to run a 3-agent parallel consensus instead
    of a single DeepSeek query — DeepSeek, Qwen, and Perplexity each propose
    parameter changes which are then merged into a unified adjustment list.
    """
    from backend.agents.agent_to_agent_communicator import AgentToAgentCommunicator

    logger.info("[BuilderWorkflow] 🤝 AgentToAgentCommunicator initialised")
    return AgentToAgentCommunicator()


class BuilderStage(str, Enum):
    """Stages of the builder workflow pipeline."""

    IDLE = "idle"
    PLANNING = "planning"
    CREATING = "creating"
    ADDING_BLOCKS = "adding_blocks"
    CONNECTING = "connecting"
    VALIDATING = "validating"
    GENERATING_CODE = "generating_code"
    BACKTESTING = "backtesting"
    EVALUATING = "evaluating"
    ITERATING = "iterating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BuilderWorkflowConfig:
    """Configuration for a builder workflow run."""

    # Strategy settings
    name: str = "Agent Strategy"
    symbol: str = "BTCUSDT"
    timeframe: str = "15"
    direction: str = "both"
    initial_capital: float = 10000.0
    leverage: float = 10.0

    # Backtest period
    start_date: str = "2025-01-01"
    end_date: str = "2025-06-01"
    commission: float = 0.0007  # NEVER change — TradingView parity

    # Stop loss / Take profit
    stop_loss: float | None = None
    take_profit: float | None = None

    # Block plan — agent specifies which blocks to use
    blocks: list[dict[str, Any]] = field(default_factory=list)
    connections: list[dict[str, Any]] = field(default_factory=list)

    # Iteration settings
    max_iterations: int = 3
    min_acceptable_sharpe: float = 0.5
    min_acceptable_win_rate: float = 0.4

    # Profit goal: strategy is only accepted when net profit is positive
    require_positive_profit: bool = True

    # AI Deliberation — optional, uses real LLM agents for planning
    enable_deliberation: bool = False

    # Existing strategy — when set, skip create/blocks/connect stages (optimize mode)
    existing_strategy_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to dict."""
        return {
            "name": self.name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "initial_capital": self.initial_capital,
            "leverage": self.leverage,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "commission": self.commission,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "blocks": self.blocks,
            "connections": self.connections,
            "max_iterations": self.max_iterations,
            "min_acceptable_sharpe": self.min_acceptable_sharpe,
            "min_acceptable_win_rate": self.min_acceptable_win_rate,
            "require_positive_profit": self.require_positive_profit,
            "enable_deliberation": self.enable_deliberation,
            "existing_strategy_id": self.existing_strategy_id,
        }


@dataclass
class BuilderWorkflowResult:
    """Result of a builder workflow run."""

    workflow_id: str = ""
    strategy_id: str = ""
    status: BuilderStage = BuilderStage.IDLE
    config: dict[str, Any] = field(default_factory=dict)
    block_library: dict[str, Any] = field(default_factory=dict)
    blocks_added: list[dict[str, Any]] = field(default_factory=list)
    connections_made: list[dict[str, Any]] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    generated_code: str = ""
    backtest_results: dict[str, Any] = field(default_factory=dict)
    iterations: list[dict[str, Any]] = field(default_factory=list)
    # Shared audit dict populated by both _plan_blocks and _run_deliberation.
    # Keys are additive — both can be present simultaneously:
    #   "llm_plan"  → set by _plan_blocks  (blocks/connections counts, token usage)
    #   "decision"  → set by _run_deliberation (agent consensus text + applied flag)
    deliberation: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to dict."""
        return {
            "workflow_id": self.workflow_id,
            "strategy_id": self.strategy_id,
            "status": self.status.value,
            "config": self.config,
            "blocks_added": self.blocks_added,
            "connections_made": self.connections_made,
            "validation": self.validation,
            "generated_code": self.generated_code[:500] if self.generated_code else "",
            "backtest_results": self.backtest_results,
            "iterations": self.iterations,
            "deliberation": self.deliberation,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class BuilderWorkflow:
    """
    Orchestrates building a strategy through the Strategy Builder UI.

    Usage:
        config = BuilderWorkflowConfig(
            name="RSI + EMA Crossover",
            blocks=[
                {"type": "rsi", "params": {"period": 14}},
                {"type": "ema", "params": {"period": 21}},
                {"type": "crossover"},
                {"type": "buy"},
                {"type": "sell"},
                {"type": "static_sltp", "params": {"stop_loss": 2.0, "take_profit": 3.0}},
            ],
            connections=[
                {"source": "rsi", "source_port": "value",
                 "target": "crossover", "target_port": "input_a"},
                {"source": "ema", "source_port": "value",
                 "target": "crossover", "target_port": "input_b"},
                {"source": "crossover", "source_port": "signal",
                 "target": "buy", "target_port": "condition"},
            ],
        )
        workflow = BuilderWorkflow()
        result = await workflow.run(config)
    """

    def __init__(
        self,
        on_stage_change: Callable[[BuilderStage], None] | None = None,
        on_agent_log: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize workflow.

        Args:
            on_stage_change: Optional callback invoked synchronously whenever
                ``self._result.status`` changes.  Used by the SSE endpoint to
                push stage events without patching the dataclass class.
            on_agent_log: Optional callback invoked with an ``agent_log`` dict
                whenever an LLM agent is called.  Dict keys:
                  - agent (str)  — "deepseek" | "qwen" | "perplexity" | "a2a"
                  - role  (str)  — "planner" | "deliberation" | "optimizer"
                  - prompt (str) — first 400 chars of the prompt sent
                  - response (str) — first 600 chars of the response received
                  - ts    (str)  — ISO-8601 timestamp
        """
        self._result = BuilderWorkflowResult()
        self._on_stage_change = on_stage_change
        self._on_agent_log = on_agent_log

    def _set_stage(self, stage: BuilderStage) -> None:
        """Set ``self._result.status`` and fire the optional callback."""
        self._result.status = stage
        if self._on_stage_change is not None:
            self._on_stage_change(stage)

    def _emit_agent_log(
        self,
        agent: str,
        role: str,
        prompt: str,
        response: str,
        title: str | None = None,
    ) -> None:
        """Fire the on_agent_log callback if registered.

        Args:
            agent:    Agent name ("deepseek", "qwen", "perplexity").
            role:     Task role ("planner", "deliberation", "optimizer").
            prompt:   Full prompt sent (stored truncated for context).
            response: Full response received (displayed in the UI card).
            title:    Short human-readable label shown instead of raw prompt.
                      Auto-generated from role if not provided.
        """
        if self._on_agent_log is not None:
            _role_titles = {
                "planner": "📐 Strategy Planning",
                "deliberation": "🤝 Agent Deliberation",
                "optimizer": "⚙️ Parameter Optimization",
            }
            auto_title = title or _role_titles.get(role, role.title())
            self._on_agent_log(
                {
                    "agent": agent,
                    "role": role,
                    "title": auto_title,
                    # Keep a short excerpt of the prompt for context tooltip
                    "prompt_excerpt": prompt[200:400].strip() or prompt[:200].strip(),
                    "response": response[:800],
                    "ts": datetime.now(UTC).isoformat(),
                }
            )

    async def run(self, config: BuilderWorkflowConfig) -> BuilderWorkflowResult:
        """
        Execute the full builder workflow.

        Args:
            config: Workflow configuration with blocks, connections, and settings

        Returns:
            BuilderWorkflowResult with all stages' output
        """
        self._result = BuilderWorkflowResult(
            workflow_id=f"bw_{uuid.uuid4().hex[:12]}",
            config=config.to_dict(),
            started_at=datetime.now(UTC).isoformat(),
        )
        start_time = time.monotonic()

        try:
            # Stage 1: Get block library for validation
            self._set_stage(BuilderStage.PLANNING)
            logger.info(f"[BuilderWorkflow] Planning: {config.name}")
            library = await builder_get_block_library()
            if isinstance(library, dict) and "error" in library:
                self._result.errors.append(f"Failed to get block library: {library['error']}")
                logger.warning("Block library unavailable, continuing without validation")
            else:
                self._result.block_library = library

            # P3 fix: plan blocks BEFORE deliberation so deliberation sees the plan
            # LLM block planning: if no blocks provided, ask DeepSeek to design them
            if not config.existing_strategy_id and not config.blocks:
                await self._plan_blocks(config)

            # Optional AI Deliberation for planning phase
            if config.enable_deliberation:
                await self._run_deliberation(config)

            # Check mode: existing strategy (optimize) vs new strategy (build)
            if config.existing_strategy_id:
                # ── Optimize mode: skip Stages 2-4, reuse existing strategy ──
                self._result.strategy_id = config.existing_strategy_id
                logger.info(f"[BuilderWorkflow] Optimize mode — using existing strategy: {config.existing_strategy_id}")

                # Fetch existing strategy state for iteration context
                self._set_stage(BuilderStage.CREATING)
                try:
                    from backend.agents.mcp.tools.strategy_builder import (
                        builder_get_strategy,
                    )

                    existing = await builder_get_strategy(config.existing_strategy_id)
                    if isinstance(existing, dict) and "error" not in existing:
                        self._result.blocks_added = existing.get("blocks", [])
                        self._result.connections_made = existing.get("connections", [])
                        logger.info(
                            f"[BuilderWorkflow] Loaded existing strategy: "
                            f"{len(self._result.blocks_added)} blocks, "
                            f"{len(self._result.connections_made)} connections"
                        )
                    else:
                        logger.warning(
                            f"[BuilderWorkflow] Could not load existing strategy details: "
                            f"{existing}. Continuing with optimize anyway."
                        )
                except Exception as e:
                    logger.warning(
                        f"[BuilderWorkflow] Failed to fetch existing strategy: {e}. Continuing with optimize anyway."
                    )
            else:
                # ── Build mode: Stages 2-4 — create strategy, add blocks, connect ──
                await self._run_build_stages(config)

            # Stage 5: Validate
            self._set_stage(BuilderStage.VALIDATING)
            logger.info("[BuilderWorkflow] Validating strategy...")
            validation = await builder_validate_strategy(self._result.strategy_id)
            self._result.validation = validation

            if isinstance(validation, dict) and not validation.get("is_valid", True):
                errors = validation.get("errors", [])
                logger.warning(f"[BuilderWorkflow] Validation warnings: {errors}")
                # Continue anyway — validation may be advisory

            # Stage 6: Generate code
            self._set_stage(BuilderStage.GENERATING_CODE)
            logger.info("[BuilderWorkflow] Generating code...")
            code_result = await builder_generate_code(self._result.strategy_id)
            if isinstance(code_result, dict) and "error" not in code_result:
                self._result.generated_code = code_result.get("code", "")

            # Stage 7: Backtest
            self._set_stage(BuilderStage.BACKTESTING)
            logger.info("[BuilderWorkflow] Running backtest...")
            backtest = await builder_run_backtest(
                strategy_id=self._result.strategy_id,
                symbol=config.symbol,
                interval=config.timeframe,
                start_date=config.start_date,
                end_date=config.end_date,
                initial_capital=config.initial_capital,
                leverage=int(config.leverage),
                direction=config.direction,
                commission=config.commission,
                stop_loss=config.stop_loss,
                take_profit=config.take_profit,
            )
            self._result.backtest_results = backtest

            # Stage 8: Evaluate + Iterative optimization loop
            best_sharpe: float = float("-inf")
            best_iteration_record: dict[str, Any] = {}

            for iteration in range(1, config.max_iterations + 1):
                self._set_stage(BuilderStage.EVALUATING)
                # Backtest response uses "results" key (from run_backtest_from_builder endpoint)
                # but also support "metrics" key for compatibility
                metrics = {}
                if isinstance(backtest, dict):
                    metrics = backtest.get("results", backtest.get("metrics", {}))
                sharpe = metrics.get("sharpe_ratio", 0)
                # win_rate from the API is already a percentage (e.g. 52.11 for 52.11%)
                # Normalize to fraction (0-1) for comparison with min_acceptable_win_rate
                raw_win_rate = metrics.get("win_rate", 0)
                win_rate = raw_win_rate / 100.0 if raw_win_rate > 1 else raw_win_rate

                iteration_record = {
                    "iteration": iteration,
                    "sharpe_ratio": sharpe,
                    "win_rate": win_rate,
                    "total_trades": metrics.get("total_trades", 0),
                    "net_profit": metrics.get("net_profit", 0),
                    "max_drawdown": metrics.get("max_drawdown", metrics.get("max_drawdown_pct", 0)),
                    "acceptable": (
                        sharpe >= config.min_acceptable_sharpe
                        and win_rate >= config.min_acceptable_win_rate
                        and (not config.require_positive_profit or metrics.get("net_profit", 0) > 0)
                    ),
                }
                self._result.iterations.append(iteration_record)

                # ── Save iteration result to Episodic Memory ──────────────────
                await self._memory_store_iteration(config, iteration_record, self._result.blocks_added)

                # Track best result for Semantic Memory at the end
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_iteration_record = iteration_record

                if iteration_record["acceptable"]:
                    logger.info(
                        f"[BuilderWorkflow] Iteration {iteration}: Strategy meets criteria — "
                        f"Sharpe={sharpe:.2f}, WinRate={win_rate:.1%}"
                    )
                    break

                logger.info(
                    f"[BuilderWorkflow] Iteration {iteration}/{config.max_iterations}: "
                    f"Sharpe={sharpe:.2f} (min {config.min_acceptable_sharpe}), "
                    f"WinRate={win_rate:.1%} (min {config.min_acceptable_win_rate:.0%}), "
                    f"NetProfit={metrics.get('net_profit', 0):.2f} "
                    f"{'✅' if metrics.get('net_profit', 0) > 0 else '❌'} — iterating"
                )

                if iteration >= config.max_iterations:
                    logger.info("[BuilderWorkflow] Max iterations reached, accepting best result")
                    break

                # --- Iterative parameter adjustment ---
                self._set_stage(BuilderStage.ITERATING)
                adjustments = await self._suggest_adjustments(
                    config.blocks, self._result.blocks_added, iteration, metrics
                )

                if not adjustments:
                    logger.info("[BuilderWorkflow] No adjustments possible, stopping iteration")
                    break

                for adj in adjustments:
                    block_id = adj["block_id"]
                    new_params = adj["params"]
                    logger.info(f"[BuilderWorkflow] Adjusting block {block_id}: {new_params}")
                    result = await builder_update_block_params(
                        strategy_id=self._result.strategy_id,
                        block_id=block_id,
                        params=new_params,
                    )
                    if isinstance(result, dict) and "error" in result:
                        self._result.errors.append(
                            f"Iteration {iteration}: Failed to adjust {block_id}: {result['error']}"
                        )

                # Re-generate code after adjustments
                self._set_stage(BuilderStage.GENERATING_CODE)
                code_result = await builder_generate_code(self._result.strategy_id)
                if isinstance(code_result, dict) and "error" not in code_result:
                    self._result.generated_code = code_result.get("code", "")

                # Re-run backtest with adjusted parameters
                self._set_stage(BuilderStage.BACKTESTING)
                logger.info(f"[BuilderWorkflow] Re-running backtest (iteration {iteration + 1})...")
                backtest = await builder_run_backtest(
                    strategy_id=self._result.strategy_id,
                    symbol=config.symbol,
                    interval=config.timeframe,
                    start_date=config.start_date,
                    end_date=config.end_date,
                    initial_capital=config.initial_capital,
                    leverage=int(config.leverage),
                    direction=config.direction,
                    commission=config.commission,
                    stop_loss=config.stop_loss,
                    take_profit=config.take_profit,
                )
                self._result.backtest_results = backtest

            # ── Save best config to Semantic Memory (survives restarts) ───────
            await self._memory_store_best_config(config, best_iteration_record)

            # Completed
            self._set_stage(BuilderStage.COMPLETED)

        except Exception as e:
            self._set_stage(BuilderStage.FAILED)
            self._result.errors.append(str(e))
            logger.error(f"[BuilderWorkflow] Failed: {e}")

        finally:
            self._result.duration_seconds = time.monotonic() - start_time
            self._result.completed_at = datetime.now(UTC).isoformat()
            logger.info(f"[BuilderWorkflow] {self._result.status.value} in {self._result.duration_seconds:.1f}s")

        return self._result

    # Block types mapped to their roles for auto-wiring
    _ACTION_TYPES = {"buy", "sell", "buy_market", "sell_market", "close_long", "close_short", "close_all"}
    _CONDITION_TYPES = {
        "crossover",
        "crossunder",
        "greater_than",
        "less_than",
        "between",
        "equals",
        "and",
        "or",
        "not",
    }
    _INDICATOR_TYPES = {
        "rsi",
        "ema",
        "sma",
        "macd",
        "bollinger",
        "bbands",
        "atr",
        "stochastic",
        "stoch",
        "adx",
        "supertrend",
        "vwap",
        "obv",
        "cci",
        "williams_r",
        "mfi",
        "roc",
        "momentum",
    }

    # Which action types map to which main_strategy ports
    _ACTION_PORT_MAP = {
        "buy": "entry_long",
        "buy_market": "entry_long",
        "sell": "entry_short",
        "sell_market": "entry_short",
        "close_long": "exit_long",
        "close_short": "exit_short",
        "close_all": "exit_long",  # plus exit_short below
    }

    async def _plan_blocks(self, config: BuilderWorkflowConfig) -> None:
        """Ask DeepSeek to design the block graph from a free-text strategy description.

        Called when ``config.blocks`` is empty — i.e. the user typed a description
        instead of picking a preset.  The LLM returns a JSON object with ``blocks``
        and ``connections`` arrays that are merged into ``config``.

        If the LLM call fails or returns invalid JSON the workflow falls back to
        a minimal RSI preset so that build stages can still proceed.

        Args:
            config: Mutable workflow config.  ``config.blocks`` and
                ``config.connections`` are updated in-place on success.
        """
        description = config.name  # frontend passes user description as name
        logger.info(f"[BuilderWorkflow] 🤖 LLM block planning for: {description!r}")

        # ── Recall past successful configs from memory before asking LLM ──────
        memory_context = ""
        try:
            memory = _get_workflow_memory()
            past_configs = await memory.recall(
                query=f"{config.symbol} {config.timeframe} strategy optimization best config",
                top_k=3,
                min_importance=0.6,
            )
            if past_configs:
                memory_context = "\n\nPast successful configurations for reference:\n"
                for item in past_configs:
                    memory_context += f"- {item.content}\n"
                logger.info(f"[BuilderWorkflow] 🧠 Recalled {len(past_configs)} relevant memories for planning")
        except Exception as mem_err:
            logger.debug(f"[BuilderWorkflow] Memory recall for planning unavailable: {mem_err}")

        # Available block types exposed in the system
        available = (
            "Indicators: rsi, ema, sma, macd, bollinger, atr, stochastic, adx, "
            "supertrend, vwap, cci, williams_r, mfi, roc, momentum, obv. "
            "Conditions: crossover, crossunder, greater_than, less_than, between, and, or, not. "
            "Actions: buy, sell, close_long, close_short, close_all. "
            "Risk: static_sltp, atr_sltp. "
            "Data: price."
        )

        prompt = f"""You are a quantitative trading strategy designer specializing in PROFITABLE strategies.

User request: "{description}"
Market: {config.symbol}, timeframe {config.timeframe}min, direction {config.direction}.
Commission: {config.commission} (0.07% per trade — avoid over-trading).
Capital: ${config.initial_capital}, Leverage: {config.leverage}x.
Goals: Sharpe ≥ {config.min_acceptable_sharpe}, Win Rate ≥ {config.min_acceptable_win_rate:.0%},
       **Net Profit MUST BE POSITIVE** — strategy must make money after commissions.

Key rules for profitability:
- Use TREND-FOLLOWING blocks (EMA, MACD, SuperTrend) as primary signals — they outperform mean-reversion in crypto
- Set Take Profit at LEAST 2x the Stop Loss (e.g. SL=1.5%, TP=3.5%) for positive expectancy
- Avoid signals that fire too often — trade quality over quantity (max ~5-10 trades/day at 15m)
- For direction={config.direction}: {"use both buy AND sell blocks" if config.direction == "both" else "use primarily " + ("buy" if config.direction == "long" else "sell") + " blocks"}
- Always include a static_sltp block with stop_loss_percent ≤ 2.0 and take_profit_percent ≥ 3.5
{memory_context}
Available block types:
{available}

Design a complete strategy as a JSON object with two arrays:
- "blocks": list of {{type, id, params}} objects
- "connections": list of {{source, source_port, target, target_port}} objects

Rules:
1. Every strategy MUST have at least one buy and one sell action block.
2. id values must be unique slugs (e.g. "rsi_14", "ema_fast").
3. connections reference blocks by their id.
4. params must only include keys the block type actually supports.
5. Always include a static_sltp block with stop_loss_percent ≤ 2.0 and take_profit_percent ≥ 3.5.
6. Return ONLY the JSON object, no explanation.

Recommended approach for positive profit (EMA + RSI combination):
{{
  "blocks": [
    {{"type": "ema", "id": "ema_fast", "params": {{"period": 9}}}},
    {{"type": "ema", "id": "ema_slow", "params": {{"period": 21}}}},
    {{"type": "rsi", "id": "rsi_filter", "params": {{"period": 14, "use_cross_level": true, "cross_long_level": 40, "cross_short_level": 60}}}},
    {{"type": "crossover", "id": "cross_up", "params": {{}}}},
    {{"type": "crossunder", "id": "cross_dn", "params": {{}}}},
    {{"type": "buy", "id": "buy_1", "params": {{}}}},
    {{"type": "sell", "id": "sell_1", "params": {{}}}},
    {{"type": "static_sltp", "id": "sltp_1", "params": {{"stop_loss_percent": 1.5, "take_profit_percent": 3.5}}}}
  ],
  "connections": [
    {{"source": "ema_fast", "source_port": "value", "target": "cross_up", "target_port": "input_a"}},
    {{"source": "ema_slow", "source_port": "value", "target": "cross_up", "target_port": "input_b"}},
    {{"source": "ema_fast", "source_port": "value", "target": "cross_dn", "target_port": "input_a"}},
    {{"source": "ema_slow", "source_port": "value", "target": "cross_dn", "target_port": "input_b"}},
    {{"source": "cross_up", "source_port": "result", "target": "buy_1", "target_port": "signal"}},
    {{"source": "cross_dn", "source_port": "result", "target": "sell_1", "target_port": "signal"}}
  ]
}}"""

        try:
            from backend.agents.unified_agent_interface import get_agent_interface

            agent = get_agent_interface()
            result = await agent.query_deepseek(
                prompt,
                model="deepseek-chat",
                temperature=0.3,  # low temp for structured JSON output
                max_tokens=1500,
                use_cache=False,
            )

            raw_text: str = result.get("response", "") or ""
            logger.debug(f"[BuilderWorkflow] LLM plan raw response ({len(raw_text)} chars)")

            # Emit agent log so the SSE panel can show what the planner said
            self._emit_agent_log(
                agent="deepseek",
                role="planner",
                prompt=prompt,
                response=raw_text,
                title=f"📐 Strategy Design for {config.symbol} {config.timeframe}m",
            )

            # Extract JSON from response — model may wrap in ```json ... ```
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON object found in LLM response")

            plan = json.loads(json_match.group())
            planned_blocks: list[dict[str, Any]] = plan.get("blocks", [])
            planned_conns: list[dict[str, Any]] = plan.get("connections", [])

            if not planned_blocks:
                raise ValueError("LLM returned empty blocks array")

            # Validate required action blocks present
            has_buy = any(b.get("type") in ("buy", "buy_market") for b in planned_blocks)
            has_sell = any(b.get("type") in ("sell", "sell_market") for b in planned_blocks)
            if not has_buy or not has_sell:
                raise ValueError(f"LLM plan missing buy/sell actions (has_buy={has_buy}, has_sell={has_sell})")

            config.blocks = planned_blocks
            config.connections = planned_conns
            self._result.deliberation["llm_plan"] = {
                "blocks": len(planned_blocks),
                "connections": len(planned_conns),
                "prompt_tokens": result.get("tokens_used", {}).get("prompt_tokens")
                if result.get("tokens_used")
                else None,
            }
            logger.info(
                f"[BuilderWorkflow] ✅ LLM planned {len(planned_blocks)} blocks, {len(planned_conns)} connections"
            )

        except Exception as e:
            logger.warning(f"[BuilderWorkflow] LLM block planning failed ({e}), falling back to EMA+RSI preset")
            # EMA crossover + RSI filter — trend-following approach with positive expectancy
            config.blocks = [
                {"type": "ema", "id": "ema_fast", "params": {"period": 9}},
                {"type": "ema", "id": "ema_slow", "params": {"period": 21}},
                {
                    "type": "rsi",
                    "id": "rsi_filter",
                    "params": {
                        "period": 14,
                        "use_cross_level": True,
                        "cross_long_level": 40,
                        "cross_short_level": 60,
                    },
                },
                {"type": "crossover", "id": "cross_up", "params": {}},
                {"type": "crossunder", "id": "cross_dn", "params": {}},
                {"type": "buy", "id": "buy_1", "params": {}},
                {"type": "sell", "id": "sell_1", "params": {}},
                {
                    "type": "static_sltp",
                    "id": "sltp_1",
                    "params": {
                        "stop_loss_percent": 1.5,
                        "take_profit_percent": 3.5,  # 2.3x risk-reward
                    },
                },
            ]
            config.connections = [
                {"source": "ema_fast", "source_port": "value", "target": "cross_up", "target_port": "input_a"},
                {"source": "ema_slow", "source_port": "value", "target": "cross_up", "target_port": "input_b"},
                {"source": "ema_fast", "source_port": "value", "target": "cross_dn", "target_port": "input_a"},
                {"source": "ema_slow", "source_port": "value", "target": "cross_dn", "target_port": "input_b"},
                {"source": "cross_up", "source_port": "result", "target": "buy_1", "target_port": "signal"},
                {"source": "cross_dn", "source_port": "result", "target": "sell_1", "target_port": "signal"},
            ]
            self._result.errors.append(f"LLM planning failed (fallback to EMA crossover preset): {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # Memory helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _memory_store_iteration(
        self,
        config: BuilderWorkflowConfig,
        iteration_record: dict[str, Any],
        blocks_added: list[dict[str, Any]],
    ) -> None:
        """Save a single backtest iteration result to Episodic Memory.

        Stores symbol, timeframe, block params, and metrics so that future
        runs on the same market can recall what was tried and with what result.
        """
        try:
            memory = _get_workflow_memory()
            from backend.agents.memory.hierarchical_memory import MemoryType

            blocks_summary = [
                {"type": b.get("type"), "params": b.get("params", {})} for b in blocks_added if b.get("params")
            ]
            content = (
                f"Backtest iteration {iteration_record.get('iteration')}: "
                f"symbol={config.symbol} tf={config.timeframe} "
                f"sharpe={iteration_record.get('sharpe_ratio', 0):.3f} "
                f"win_rate={iteration_record.get('win_rate', 0):.1%} "
                f"trades={iteration_record.get('total_trades', 0)} "
                f"profit={iteration_record.get('net_profit', 0):.2f} "
                f"blocks={json.dumps(blocks_summary)}"
            )
            importance = min(1.0, max(0.1, (iteration_record.get("sharpe_ratio", 0) + 1) / 3))
            await memory.store(
                content=content,
                memory_type=MemoryType.EPISODIC,
                importance=importance,
                tags=["backtest", config.symbol, f"tf_{config.timeframe}", "iteration"],
                metadata={
                    "symbol": config.symbol,
                    "timeframe": config.timeframe,
                    "sharpe_ratio": iteration_record.get("sharpe_ratio", 0),
                    "win_rate": iteration_record.get("win_rate", 0),
                    "total_trades": iteration_record.get("total_trades", 0),
                },
                source="builder_workflow",
            )
            logger.debug(
                f"[BuilderWorkflow] 🧠 Iteration result saved to Episodic Memory (importance={importance:.2f})"
            )
        except Exception as e:
            logger.debug(f"[BuilderWorkflow] Memory store iteration failed (non-fatal): {e}")

    async def _memory_store_best_config(
        self,
        config: BuilderWorkflowConfig,
        best_record: dict[str, Any],
    ) -> None:
        """Persist the best block configuration to Semantic Memory.

        High importance — survives process restarts and is recalled during
        future planning for the same symbol/timeframe combination.
        """
        if not best_record:
            return
        try:
            memory = _get_workflow_memory()
            from backend.agents.memory.hierarchical_memory import MemoryType

            blocks_summary = [
                {"type": b.get("type"), "params": b.get("params", {})}
                for b in self._result.blocks_added
                if b.get("params")
            ]
            sharpe = best_record.get("sharpe_ratio", 0)
            content = (
                f"Best configuration for {config.symbol} {config.timeframe}min "
                f"direction={config.direction}: "
                f"sharpe={sharpe:.3f} "
                f"win_rate={best_record.get('win_rate', 0):.1%} "
                f"trades={best_record.get('total_trades', 0)} "
                f"blocks={json.dumps(blocks_summary)}"
            )
            # Only save configs with positive Sharpe to Semantic memory
            importance = min(1.0, max(0.3, (sharpe + 1) / 2.5)) if sharpe > 0 else 0.3
            await memory.store(
                content=content,
                memory_type=MemoryType.SEMANTIC,
                importance=importance,
                tags=["best_config", config.symbol, f"tf_{config.timeframe}", config.direction],
                metadata={
                    "symbol": config.symbol,
                    "timeframe": config.timeframe,
                    "direction": config.direction,
                    "sharpe_ratio": sharpe,
                    "blocks": blocks_summary,
                },
                source="builder_workflow",
            )
            logger.info(
                f"[BuilderWorkflow] 🧠 Best config saved to Semantic Memory "
                f"(Sharpe={sharpe:.3f}, importance={importance:.2f})"
            )
        except Exception as e:
            logger.debug(f"[BuilderWorkflow] Memory store best config failed (non-fatal): {e}")

    async def _run_build_stages(self, config: BuilderWorkflowConfig) -> None:
        """Execute Stages 2-4: create strategy, add blocks, connect blocks.

        This is the 'build from scratch' path. Skipped in optimize mode
        when ``config.existing_strategy_id`` is set.
        """
        # Stage 2: Create strategy
        self._set_stage(BuilderStage.CREATING)
        logger.info(f"[BuilderWorkflow] Creating strategy: {config.name}")
        strategy = await builder_create_strategy(
            name=config.name,
            symbol=config.symbol,
            timeframe=config.timeframe,
            direction=config.direction,
            initial_capital=config.initial_capital,
            leverage=config.leverage,
        )
        if isinstance(strategy, dict) and "error" in strategy:
            raise RuntimeError(f"Failed to create strategy: {strategy['error']}")

        self._result.strategy_id = strategy.get("id", "")
        logger.info(f"[BuilderWorkflow] Strategy created: {self._result.strategy_id}")

        # Stage 3: Add blocks
        self._set_stage(BuilderStage.ADDING_BLOCKS)
        block_id_map: dict[str, str] = {}

        # Layout blocks in a grid: indicators left, conditions center, actions right
        x_offsets = {
            "indicator": 100,
            "filter": 100,
            "condition": 400,
            "crossover": 400,
            "crossunder": 400,
            "greater_than": 400,
            "less_than": 400,
            "between": 400,
            "equals": 400,
            "action": 700,
            "buy": 700,
            "sell": 700,
            "close": 700,
            "exit": 700,
            "stop_loss": 700,
            "take_profit": 700,
        }

        # Add a "price" input block first — feeds close data to indicators
        logger.info("[BuilderWorkflow] Adding price input block")
        price_result = await builder_add_block(
            strategy_id=self._result.strategy_id,
            block_type="price",
            block_id="price_input",
            name="PRICE",
            x=50,
            y=200,
            params={"source": "close"},
        )
        if isinstance(price_result, dict) and "error" not in price_result:
            price_block = price_result.get("block", {})
            block_id_map["price"] = price_block.get("id", "price_input")
            block_id_map["price_input"] = price_block.get("id", "price_input")
            self._result.blocks_added.append(price_block)

        for i, block_def in enumerate(config.blocks):
            block_type = block_def.get("type", "")
            params = block_def.get("params", {})
            custom_id = block_def.get("id")
            name = block_def.get("name")

            # Auto-layout
            x = x_offsets.get(block_type, 400)
            y = 100 + (i * 120)

            logger.info(f"[BuilderWorkflow] Adding block: {block_type} at ({x}, {y})")
            result = await builder_add_block(
                strategy_id=self._result.strategy_id,
                block_type=block_type,
                block_id=custom_id,
                name=name,
                x=x,
                y=y,
                params=params,
            )

            if isinstance(result, dict) and "error" in result:
                self._result.errors.append(f"Failed to add block {block_type}: {result['error']}")
                continue

            added_block = result.get("block", {})
            actual_id = added_block.get("id", "")
            block_id_map[block_type] = actual_id
            if custom_id:
                block_id_map[custom_id] = actual_id
            self._result.blocks_added.append(added_block)

        # Add a main_strategy node — the adapter needs this to aggregate signals
        logger.info("[BuilderWorkflow] Adding main_strategy aggregator node")
        main_result = await builder_add_block(
            strategy_id=self._result.strategy_id,
            block_type="strategy",
            block_id="main_strategy",
            name="STRATEGY",
            x=950,
            y=300,
            params={"isMain": True},
        )
        if isinstance(main_result, dict) and "error" not in main_result:
            main_block = main_result.get("block", {})
            main_block["isMain"] = True  # Ensure isMain is set
            block_id_map["strategy"] = main_block.get("id", "main_strategy")
            block_id_map["main_strategy"] = main_block.get("id", "main_strategy")
            self._result.blocks_added.append(main_block)

        # Auto-add exit block (static_sltp) when no exit blocks are present.
        # The backtest endpoint requires exit conditions — without them it returns 400.
        _EXIT_BLOCK_TYPES = {
            "static_sltp",
            "trailing_stop_exit",
            "atr_exit",
            "time_exit",
            "session_exit",
            "break_even_exit",
            "chandelier_exit",
            "partial_close",
            "multi_tp_exit",
            "tp_percent",
            "sl_percent",
            "rsi_close",
            "stoch_close",
            "channel_close",
            "ma_close",
            "psar_close",
            "time_bars_close",
            "stop_loss",
            "take_profit",
            "trailing_stop",
            "atr_stop",
            "chandelier_stop",
            "break_even",
            "profit_lock",
        }
        has_exit_block = any(b.get("type", "").lower() in _EXIT_BLOCK_TYPES for b in config.blocks)
        if not has_exit_block:
            sl_pct = config.stop_loss if config.stop_loss else 0.02
            tp_pct = config.take_profit if config.take_profit else 0.04
            logger.info(
                f"[BuilderWorkflow] No exit blocks in preset — auto-adding static_sltp "
                f"(SL={sl_pct * 100:.1f}%, TP={tp_pct * 100:.1f}%)"
            )
            sltp_result = await builder_add_block(
                strategy_id=self._result.strategy_id,
                block_type="static_sltp",
                block_id="auto_sltp",
                name="SL/TP",
                x=950,
                y=500,
                params={
                    "stop_loss_percent": sl_pct * 100,
                    "take_profit_percent": tp_pct * 100,
                },
            )
            if isinstance(sltp_result, dict) and "error" not in sltp_result:
                sltp_block = sltp_result.get("block", {})
                block_id_map["static_sltp"] = sltp_block.get("id", "auto_sltp")
                block_id_map["auto_sltp"] = sltp_block.get("id", "auto_sltp")
                self._result.blocks_added.append(sltp_block)
            else:
                self._result.errors.append(f"Failed to auto-add SL/TP block: {sltp_result.get('error', 'unknown')}")

        logger.info(f"[BuilderWorkflow] Added {len(self._result.blocks_added)} blocks (incl. price + main_strategy)")

        # Stage 4: Connect blocks
        self._set_stage(BuilderStage.CONNECTING)

        # First, apply user-defined connections
        for conn_def in config.connections:
            source = conn_def.get("source", "")
            source_port = conn_def.get("source_port", "value")
            target = conn_def.get("target", "")
            target_port = conn_def.get("target_port", "input")

            # Resolve block type names to actual IDs
            source_id = block_id_map.get(source, source)
            target_id = block_id_map.get(target, target)

            logger.info(f"[BuilderWorkflow] Connecting: {source_id}:{source_port} → {target_id}:{target_port}")
            result = await builder_connect_blocks(
                strategy_id=self._result.strategy_id,
                source_block_id=source_id,
                source_port=source_port,
                target_block_id=target_id,
                target_port=target_port,
            )

            if isinstance(result, dict) and "error" in result:
                self._result.errors.append(f"Failed to connect {source}→{target}: {result['error']}")
                continue

            self._result.connections_made.append(result.get("connection", {}))

        # Auto-wire missing connections:
        # 1. condition → action blocks (if condition has no downstream action)
        # 2. action → main_strategy (always needed)
        auto_connections = self._infer_missing_connections(config.blocks, block_id_map, config.connections)
        for auto_conn in auto_connections:
            source_id = auto_conn["source_id"]
            source_port = auto_conn["source_port"]
            target_id = auto_conn["target_id"]
            target_port = auto_conn["target_port"]

            logger.info(f"[BuilderWorkflow] Auto-wiring: {source_id}:{source_port} → {target_id}:{target_port}")
            result = await builder_connect_blocks(
                strategy_id=self._result.strategy_id,
                source_block_id=source_id,
                source_port=source_port,
                target_block_id=target_id,
                target_port=target_port,
            )

            if isinstance(result, dict) and "error" in result:
                self._result.errors.append(f"Auto-wire failed {source_id}→{target_id}: {result['error']}")
                continue

            self._result.connections_made.append(result.get("connection", {}))

        logger.info(f"[BuilderWorkflow] Made {len(self._result.connections_made)} connections")

    def _infer_missing_connections(
        self,
        block_defs: list[dict[str, Any]],
        block_id_map: dict[str, str],
        explicit_connections: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Infer missing connections that the user/preset didn't specify.

        Auto-wires:
        1. condition → action: if a condition block has no downstream action,
           connect it to the first compatible action block.
        2. action → main_strategy: connect every action block to the main_strategy
           node's appropriate port (entry_long, entry_short, exit_long, exit_short).

        Args:
            block_defs: Original block definitions from config
            block_id_map: Mapping of type/id → actual block ID
            explicit_connections: User-defined connections

        Returns:
            List of auto-connections to create
        """
        auto_connections: list[dict[str, Any]] = []
        main_id = block_id_map.get("main_strategy", block_id_map.get("strategy", ""))

        if not main_id:
            logger.warning("[BuilderWorkflow] No main_strategy node — cannot auto-wire")
            return auto_connections

        # Build set of explicit connection targets (source→target pairs)
        explicit_targets: set[str] = set()
        for conn in explicit_connections:
            src = conn.get("source", "")
            tgt = conn.get("target", "")
            explicit_targets.add(f"{src}→{tgt}")

        # Categorize blocks by role
        condition_blocks: list[dict[str, Any]] = []
        action_blocks: list[dict[str, Any]] = []
        for bdef in block_defs:
            btype = bdef.get("type", "").lower()
            bid = bdef.get("id", btype)
            if btype in self._CONDITION_TYPES:
                condition_blocks.append({"type": btype, "id": bid})
            elif btype in self._ACTION_TYPES:
                action_blocks.append({"type": btype, "id": bid})

        # 1. condition → action auto-wiring
        # If condition has no explicit downstream action, connect to matching actions
        buy_actions = [a for a in action_blocks if a["type"] in ("buy", "buy_market")]
        sell_actions = [a for a in action_blocks if a["type"] in ("sell", "sell_market")]

        for cond in condition_blocks:
            cond_id = block_id_map.get(cond["id"], block_id_map.get(cond["type"], ""))
            if not cond_id:
                continue

            # Check if condition already has downstream connections
            has_downstream = any(conn.get("source", "") in (cond["id"], cond["type"]) for conn in explicit_connections)

            if not has_downstream:
                # Smart wiring: crossover → buy, crossunder → sell
                is_crossover = cond["type"] in ("crossover", "cross_up")
                is_crossunder = cond["type"] in ("crossunder", "cross_down")

                if is_crossover:
                    # crossover signals a bullish event → connect to buy only
                    for ba in buy_actions:
                        ba_id = block_id_map.get(ba["id"], block_id_map.get(ba["type"], ""))
                        if ba_id:
                            auto_connections.append(
                                {
                                    "source_id": cond_id,
                                    "source_port": "result",
                                    "target_id": ba_id,
                                    "target_port": "signal",
                                }
                            )
                elif is_crossunder:
                    # crossunder signals a bearish event → connect to sell only
                    for sa in sell_actions:
                        sa_id = block_id_map.get(sa["id"], block_id_map.get(sa["type"], ""))
                        if sa_id:
                            auto_connections.append(
                                {
                                    "source_id": cond_id,
                                    "source_port": "result",
                                    "target_id": sa_id,
                                    "target_port": "signal",
                                }
                            )
                else:
                    # Generic condition (greater_than, less_than, etc.)
                    # Connect to buy actions; if no crossunder exists, also to sell
                    for ba in buy_actions:
                        ba_id = block_id_map.get(ba["id"], block_id_map.get(ba["type"], ""))
                        if ba_id:
                            auto_connections.append(
                                {
                                    "source_id": cond_id,
                                    "source_port": "result",
                                    "target_id": ba_id,
                                    "target_port": "signal",
                                }
                            )
                    crossunder_exists = any(
                        b.get("type", "").lower() in ("crossunder", "cross_down") for b in block_defs
                    )
                    if not crossunder_exists:
                        for sa in sell_actions:
                            sa_id = block_id_map.get(sa["id"], block_id_map.get(sa["type"], ""))
                            if sa_id:
                                auto_connections.append(
                                    {
                                        "source_id": cond_id,
                                        "source_port": "result",
                                        "target_id": sa_id,
                                        "target_port": "signal",
                                    }
                                )

        # 2. action → main_strategy auto-wiring (ALWAYS needed)
        for action in action_blocks:
            action_id = block_id_map.get(action["id"], block_id_map.get(action["type"], ""))
            if not action_id:
                continue

            target_port = self._ACTION_PORT_MAP.get(action["type"], "entry_long")
            auto_connections.append(
                {
                    "source_id": action_id,
                    "source_port": "signal",
                    "target_id": main_id,
                    "target_port": target_port,
                }
            )

            # close_all needs both exit_long and exit_short
            if action["type"] == "close_all":
                auto_connections.append(
                    {
                        "source_id": action_id,
                        "source_port": "signal",
                        "target_id": main_id,
                        "target_port": "exit_short",
                    }
                )

        logger.info(f"[BuilderWorkflow] Auto-wired {len(auto_connections)} connections")
        return auto_connections

    async def _suggest_adjustments(
        self,
        block_defs: list[dict[str, Any]],
        blocks_added: list[dict[str, Any]],
        iteration: int,
        metrics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Use a 3-agent parallel consensus to suggest parameter adjustments.

        Sends current blocks + metrics to DeepSeek, Qwen, and Perplexity in
        parallel via AgentToAgentCommunicator.parallel_consensus().  Each agent
        proposes adjustments from its own perspective (quant, technical,
        macro/sentiment), then their responses are merged: adjustments that
        appear in 2+ responses take priority.

        Falls back to a single DeepSeek call if A2A is unavailable, and to
        the rule-based heuristic if all LLM calls fail.

        Args:
            block_defs: Original block definitions from config.
            blocks_added: Actual blocks added (with IDs and current params).
            iteration: Current iteration number (1-based).
            metrics: Backtest metrics from the last run.

        Returns:
            List of ``{"block_id": ..., "params": {...}}`` adjustments.
        """
        blocks_summary = [
            {"id": b.get("id"), "type": b.get("type"), "params": b.get("params", {})}
            for b in blocks_added
            if b.get("params")
        ]

        win_rate = metrics.get("win_rate", 0)
        # Normalise — API returns percentage (52.11) not fraction (0.52)
        if win_rate > 1:
            win_rate = win_rate / 100.0

        prompt = f"""You are a quant strategy optimizer. PRIMARY GOAL: make Net Profit POSITIVE.

Current backtest results (iteration {iteration}):
- Sharpe Ratio: {metrics.get("sharpe_ratio", 0):.3f}
- Win Rate: {win_rate:.1%}
- Max Drawdown: {abs(metrics.get("max_drawdown_pct", 0)):.1f}%
- Net Profit: {metrics.get("net_profit", 0):.2f} {"✅" if metrics.get("net_profit", 0) > 0 else "❌ MUST FIX"}
- Total Trades: {metrics.get("total_trades", 0)} {"(too many — reduce frequency)" if metrics.get("total_trades", 0) > 300 else ""}

Current blocks and parameters:
{json.dumps(blocks_summary, indent=2)}

Profitability rules:
1. If Net Profit < 0: the strategy loses money — MUST change parameters significantly
2. static_sltp: take_profit_percent MUST be ≥ 2x stop_loss_percent (positive risk/reward)
3. If too many trades (>200): widen RSI thresholds, increase EMA periods to reduce noise
4. If win rate < 40%: tighten entry conditions (RSI overbought lower, oversold higher)
5. If max drawdown > 30%: reduce stop_loss_percent or add tighter exit conditions

Suggest parameter adjustments to make Net Profit positive and improve Sharpe ratio.
Return ONLY a JSON array of adjustments. Each item: {{"block_id": "...", "params": {{"key": value}}}}.
Only include blocks that need changes. Only include changed parameters.
Return [] if strategy is already profitable and Sharpe > 1.0.
Do not include explanations, only the JSON array."""

        # ── Try multi-agent consensus first (A2A parallel) ────────────────────
        try:
            import os

            from backend.agents.models import AgentType

            a2a = _get_a2a_communicator()

            # Only use agents for which we have API keys
            available_agents = []
            if os.environ.get("DEEPSEEK_API_KEY"):
                available_agents.append(AgentType.DEEPSEEK)
            if os.environ.get("QWEN_API_KEY"):
                available_agents.append(AgentType.QWEN)
            if os.environ.get("PERPLEXITY_API_KEY"):
                available_agents.append(AgentType.PERPLEXITY)

            if len(available_agents) >= 2:
                logger.info(
                    f"[BuilderWorkflow] 🤝 A2A parallel consensus: "
                    f"{[a.value for a in available_agents]} (iteration {iteration})"
                )
                consensus_result = await a2a.parallel_consensus(
                    question=prompt,
                    agents=available_agents,
                    context={
                        "task": "parameter_adjustment",
                        "iteration": iteration,
                        "symbol": "",  # don't leak strategy to Perplexity web-search
                        "require_json_array": True,
                    },
                )

                # Merge adjustments from all agents — collect all JSON arrays found
                # in each individual response and merge by majority vote
                all_adjustments: list[dict[str, Any]] = []
                for resp in consensus_result.get("individual_responses", []):
                    agent_resp_text = resp.get("content", "")
                    # Emit per-agent log for the SSE panel
                    agent_name = resp.get("agent", "unknown")
                    self._emit_agent_log(
                        agent=agent_name,
                        role="optimizer",
                        prompt=prompt,
                        response=agent_resp_text,
                        title=f"⚙️ Param Optimization — iteration {iteration}",
                    )
                    arr_match = re.search(r"\[.*?\]", agent_resp_text, re.DOTALL)
                    if arr_match:
                        try:
                            agent_adjs = json.loads(arr_match.group())
                            if isinstance(agent_adjs, list):
                                all_adjustments.extend(agent_adjs)
                        except json.JSONDecodeError:
                            pass

                merged = self._merge_agent_adjustments(all_adjustments)
                if merged:
                    logger.info(
                        f"[BuilderWorkflow] 🤝 A2A consensus produced {len(merged)} adjustments "
                        f"(confidence={consensus_result.get('confidence_score', 0):.2f})"
                    )
                    return merged

                # Fall through if consensus produced nothing useful
                logger.info("[BuilderWorkflow] A2A consensus returned empty — falling back to single LLM")

        except Exception as a2a_err:
            logger.warning(f"[BuilderWorkflow] A2A consensus failed ({a2a_err}), falling back to single DeepSeek")

        # ── Single DeepSeek fallback ──────────────────────────────────────────
        try:
            from backend.agents.unified_agent_interface import get_agent_interface

            agent = get_agent_interface()
            result = await agent.query_deepseek(
                prompt,
                model="deepseek-chat",
                temperature=0.2,
                max_tokens=800,
                use_cache=False,
            )

            raw_text_fallback = result.get("response", "") or ""

            # Emit agent log for the single-DeepSeek fallback
            self._emit_agent_log(
                agent="deepseek",
                role="optimizer",
                prompt=prompt,
                response=raw_text_fallback,
                title=f"⚙️ Param Optimization — iteration {iteration} (fallback)",
            )

            arr_match = re.search(r"\[.*\]", raw_text_fallback, re.DOTALL)
            if not arr_match:
                raise ValueError("No JSON array in LLM adjustments response")

            adjustments = json.loads(arr_match.group())
            if not isinstance(adjustments, list):
                raise ValueError("LLM returned non-list adjustments")

            logger.info(
                f"[BuilderWorkflow] 🤖 DeepSeek suggested {len(adjustments)} adjustments (iteration {iteration})"
            )
            return adjustments

        except Exception as e:
            logger.warning(f"[BuilderWorkflow] All LLM adjustments failed ({e}), using heuristic fallback")
            return self._heuristic_adjustments(blocks_added, iteration, metrics)

    def _merge_agent_adjustments(
        self,
        all_adjustments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge parameter adjustments from multiple agents.

        Strategy: for each block_id, average numeric params that ≥2 agents
        agreed to change; keep unique params that only one agent suggested.

        Args:
            all_adjustments: Raw list of adjustments from all agents (may have
                duplicates for the same block_id).

        Returns:
            Deduplicated and averaged adjustment list.
        """
        # Group by block_id
        by_block: dict[str, list[dict[str, Any]]] = {}
        for adj in all_adjustments:
            bid = adj.get("block_id", "")
            if not bid:
                continue
            by_block.setdefault(bid, []).append(adj.get("params", {}))

        merged: list[dict[str, Any]] = []
        for block_id, params_list in by_block.items():
            # Collect all param keys across all agents
            all_keys: set[str] = set()
            for p in params_list:
                all_keys.update(p.keys())

            merged_params: dict[str, Any] = {}
            for key in all_keys:
                values = [p[key] for p in params_list if key in p]
                if not values:
                    continue
                # Average numeric values; use first value for non-numeric
                numeric_vals = [v for v in values if isinstance(v, (int, float))]
                if numeric_vals:
                    avg = sum(numeric_vals) / len(numeric_vals)
                    # Round to int if original values were int
                    if all(isinstance(v, int) for v in numeric_vals):
                        merged_params[key] = round(avg)
                    else:
                        merged_params[key] = round(avg, 4)
                else:
                    merged_params[key] = values[0]

            if merged_params:
                merged.append({"block_id": block_id, "params": merged_params})

        return merged

    def _heuristic_adjustments(
        self,
        blocks_added: list[dict[str, Any]],
        iteration: int,
        metrics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Rule-based fallback when LLM adjustment call fails.

        Kept as a private method so it is still unit-testable and can be
        called from ``_suggest_adjustments`` on error.
        """
        adjustments: list[dict[str, Any]] = []
        step = iteration

        win_rate = metrics.get("win_rate", 0)
        if win_rate > 1:
            win_rate = win_rate / 100.0
        sharpe = metrics.get("sharpe_ratio", 0)
        max_dd = abs(metrics.get("max_drawdown_pct", 0))

        for block in blocks_added:
            block_id = block.get("id", "")
            block_type = block.get("type", "").lower()
            params = block.get("params", {})

            if not params or not block_id:
                continue

            new_params: dict[str, Any] = {}

            if block_type == "rsi":
                if win_rate < 0.4:
                    if "overbought" in params:
                        new_params["overbought"] = min(85, params["overbought"] + 3 * step)
                    if "oversold" in params:
                        new_params["oversold"] = max(15, params["oversold"] - 3 * step)
                if sharpe < 0.3 and "period" in params:
                    new_params["period"] = min(30, params["period"] + 2 * step)

            elif block_type in ("ema", "sma"):
                if max_dd > 20 and "period" in params:
                    new_params["period"] = min(50, params["period"] + 3 * step)
                elif sharpe < 0.3 and "period" in params:
                    new_params["period"] = max(5, params["period"] - 2 * step)

            elif block_type == "macd":
                if win_rate < 0.4 and "signal_period" in params:
                    new_params["signal_period"] = min(15, params["signal_period"] + step)
                if "fast_period" in params and sharpe < 0.3:
                    new_params["fast_period"] = max(5, params["fast_period"] - step)

            elif block_type in ("bollinger", "bbands"):
                if win_rate < 0.4 and "std_dev" in params:
                    new_params["std_dev"] = min(3.0, params["std_dev"] + 0.2 * step)
                if "period" in params and max_dd > 20:
                    new_params["period"] = min(30, params["period"] + 2 * step)

            elif block_type in ("stochastic", "stoch"):
                if win_rate < 0.4:
                    if "overbought" in params:
                        new_params["overbought"] = min(90, params["overbought"] + 3 * step)
                    if "oversold" in params:
                        new_params["oversold"] = max(10, params["oversold"] - 3 * step)

            elif block_type in ("atr", "static_sltp"):
                current_sl = params.get("stop_loss_percent", params.get("stop_loss", 2.0))
                current_tp = params.get("take_profit_percent", params.get("take_profit", 4.0))
                net_profit = metrics.get("net_profit", 0)
                if max_dd > 20:
                    if "stop_loss_percent" in params:
                        new_params["stop_loss_percent"] = max(0.8, current_sl - 0.3 * step)
                    elif "stop_loss" in params:
                        new_params["stop_loss"] = max(0.5, params["stop_loss"] - 0.3 * step)
                # Ensure TP is always at least 2x SL for positive expectancy
                if current_tp < current_sl * 2:
                    if "take_profit_percent" in params:
                        new_params["take_profit_percent"] = round(current_sl * 2.5, 1)
                    elif "take_profit" in params:
                        new_params["take_profit"] = round(params.get("stop_loss", 2.0) * 2.5, 1)
                # If net profit is deeply negative, boost TP aggressively
                if net_profit < -1000 and "take_profit_percent" in params:
                    new_params["take_profit_percent"] = max(current_tp, round(current_sl * 3.0, 1))

            if new_params:
                adjustments.append({"block_id": block_id, "params": new_params})
                logger.debug(f"[BuilderWorkflow] Heuristic adj {block_type} ({block_id}): {new_params}")

        return adjustments

    async def _run_deliberation(self, config: BuilderWorkflowConfig) -> None:
        """Run AI deliberation and apply the resulting block plan to ``config``.

        Uses RealLLMDeliberation with DeepSeek + Perplexity + Qwen agents to
        analyse the planned blocks and suggest improvements before building.

        If the deliberation response contains a JSON object with ``blocks``
        and ``connections`` arrays those values **replace** ``config.blocks``
        and ``config.connections`` so that the build stages use the LLM-
        recommended design.

        Results are stored in ``self._result.deliberation`` and logged.
        """
        try:
            from backend.agents.consensus.real_llm_deliberation import (
                RealLLMDeliberation,
            )

            logger.info("[BuilderWorkflow] 🤖 Starting AI Deliberation for planning...")

            deliberation = RealLLMDeliberation(enable_perplexity_enrichment=True)

            # Build the question from config
            block_names = [b.get("type", "?") for b in config.blocks]
            question = (
                f"I'm building a trading strategy for {config.symbol} on {config.timeframe}m timeframe. "
                f"Direction: {config.direction}. Planned blocks: {', '.join(block_names) or 'none yet'}. "
                f"Parameters: {json.dumps(config.blocks)}. "
                f"Capital: ${config.initial_capital}, Leverage: {config.leverage}x, "
                f"Commission: {config.commission} (0.07%). "
                f"Should I use these blocks and parameters, or suggest improvements? "
                f"Focus on Sharpe ratio optimization and win rate above {config.min_acceptable_win_rate:.0%}. "
                f"If you recommend changes, include a JSON object at the END of your reply with "
                f'keys "blocks" and "connections" (same schema as the builder API) '
                f"so the changes can be applied automatically."
            )

            # Enrich with market context first
            await deliberation.enrich_for_deliberation(
                question=question,
                symbol=config.symbol,
                strategy_type="builder",
            )

            # Use all available agents — check env keys at runtime
            import os

            agents: list[str] = []
            if os.environ.get("DEEPSEEK_API_KEY"):
                agents.append("deepseek")
            if os.environ.get("QWEN_API_KEY"):
                agents.append("qwen")
            if os.environ.get("PERPLEXITY_API_KEY"):
                agents.append("perplexity")

            if not agents:
                logger.warning("[BuilderWorkflow] No LLM API keys found — skipping deliberation")
                self._result.deliberation = {"skipped": True, "reason": "no_api_keys"}
                return

            result = await deliberation.deliberate(
                question=question,
                agents=agents,
                max_rounds=1,  # Single round to save costs
                min_confidence=0.5,
            )

            decision_text: str = result.decision or ""

            # Build per-agent vote lookup from final_votes (position + reasoning)
            vote_by_agent: dict[str, str] = {}
            for vote in getattr(result, "final_votes", []) or []:
                aid = getattr(vote, "agent_id", "")
                position = getattr(vote, "position", "")
                reasoning = getattr(vote, "reasoning", "")
                confidence = getattr(vote, "confidence", None)
                parts = []
                if position:
                    parts.append(f"**Position:** {position}")
                if reasoning:
                    parts.append(f"**Reasoning:** {reasoning}")
                if confidence is not None:
                    parts.append(f"**Confidence:** {confidence:.0%}")
                if aid:
                    vote_by_agent[aid] = "\n".join(parts) if parts else position or reasoning

            # Also check rounds for individual agent responses
            for rnd in getattr(result, "rounds", []) or []:
                for vote in getattr(rnd, "votes", []) or []:
                    aid = getattr(vote, "agent_id", "")
                    if aid and aid not in vote_by_agent:
                        position = getattr(vote, "position", "")
                        reasoning = getattr(vote, "reasoning", "")
                        confidence = getattr(vote, "confidence", None)
                        parts = []
                        if position:
                            parts.append(f"**Position:** {position}")
                        if reasoning:
                            parts.append(f"**Reasoning:** {reasoning}")
                        if confidence is not None:
                            parts.append(f"**Confidence:** {confidence:.0%}")
                        vote_by_agent[aid] = "\n".join(parts) if parts else position or reasoning

            # Emit per-agent logs so the SSE panel shows each agent's unique position
            conf_label = f"{result.confidence:.0%}" if result.confidence else ""
            for agent_name in agents:
                individual_response = vote_by_agent.get(agent_name, "")
                if not individual_response:
                    # Fallback: show consensus decision with agent-role framing
                    individual_response = f"[Consensus reached] {decision_text[:600]}"
                self._emit_agent_log(
                    agent=agent_name,
                    role="deliberation",
                    prompt=question,
                    response=individual_response,
                    title=f"🤝 Deliberation — consensus {conf_label}",
                )

            self._result.deliberation = {
                "decision": decision_text,
                "confidence": result.confidence,
                "agent_count": len(agents),
                "agents_used": agents,
            }

            # ── Apply deliberation output to config if JSON plan found ──
            json_match = re.search(r"\{.*\}", decision_text, re.DOTALL)
            if json_match:
                try:
                    plan = json.loads(json_match.group())
                    new_blocks = plan.get("blocks")
                    new_conns = plan.get("connections")
                    if new_blocks and isinstance(new_blocks, list):
                        has_buy = any(b.get("type") in ("buy", "buy_market") for b in new_blocks)
                        has_sell = any(b.get("type") in ("sell", "sell_market") for b in new_blocks)
                        if has_buy and has_sell:
                            config.blocks = new_blocks
                            config.connections = new_conns or []
                            self._result.deliberation["applied_to_config"] = True
                            logger.info(
                                f"[BuilderWorkflow] ✅ Deliberation plan applied: "
                                f"{len(new_blocks)} blocks, {len(new_conns or [])} connections"
                            )
                        else:
                            logger.warning(
                                "[BuilderWorkflow] Deliberation JSON found but missing buy/sell — not applied"
                            )
                except Exception as parse_err:
                    logger.warning(f"[BuilderWorkflow] Could not parse deliberation JSON: {parse_err}")

            logger.info(
                f"[BuilderWorkflow] 🤖 Deliberation result: "
                f"confidence={result.confidence:.2f}, decision={decision_text[:100]}..."
            )

        except Exception as e:
            logger.warning(f"[BuilderWorkflow] AI Deliberation failed (non-fatal): {e}")
            self._result.deliberation = {"error": str(e), "skipped": True}
