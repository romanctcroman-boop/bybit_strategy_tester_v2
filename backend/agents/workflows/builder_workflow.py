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

import asyncio
import copy
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
    builder_disconnect_blocks,
    builder_generate_code,
    builder_get_block_library,
    builder_remove_block,
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

    # Primary LLM agent for single-agent calls (claude | perplexity)
    agent: str = "claude"

    # Existing strategy — when set, skip create/blocks/connect stages (optimize mode)
    existing_strategy_id: str | None = None

    # Optimizer sweep mode — agents suggest parameter RANGES, optimizer finds best values
    # True  → each iteration: agents propose {min, max, step} → grid/bayesian sweep
    # False → each iteration: agents propose single values (original behavior)
    use_optimizer_mode: bool = False

    # ── Evaluation config (from Evaluation panel) ─────────────────────────────
    # ALL scoring, sorting, and acceptance decisions use ONLY these settings.
    # primary_metric  — the single metric that drives optimization and iteration.
    # secondary_metrics — additional metrics shown in results.
    # constraints     — hard filters: [{"metric": "max_drawdown", "operator": "<=", "value": 20}]
    # sort_order      — multi-level result sorting: [{"metric": "...", "direction": "desc"}]
    # use_composite   — if True, primary score is a weighted composite of all metrics.
    # weights         — per-metric weights for composite scoring.
    evaluation_config: dict[str, Any] = field(
        default_factory=lambda: {
            "primary_metric": "sharpe_ratio",
            "secondary_metrics": ["win_rate", "max_drawdown", "profit_factor"],
            "constraints": [],
            "sort_order": [],
            "use_composite": False,
            "weights": None,
        }
    )

    def get_primary_metric(self) -> str:
        """Return the primary evaluation metric (from Evaluation panel)."""
        return self.evaluation_config.get("primary_metric", "sharpe_ratio") or "sharpe_ratio"

    def get_min_acceptable_primary(self) -> float:
        """Return minimum acceptable value for the primary metric.

        For sharpe_ratio this is min_acceptable_sharpe.
        For win_rate, min_profit_factor, etc. sensible defaults are returned.
        The caller can override via constraints.
        """
        metric = self.get_primary_metric()
        _defaults: dict[str, float] = {
            "sharpe_ratio": self.min_acceptable_sharpe,
            "sortino_ratio": self.min_acceptable_sharpe,
            "calmar_ratio": self.min_acceptable_sharpe,
            "profit_factor": 1.0,
            "win_rate": self.min_acceptable_win_rate * 100,  # stored as %
            "total_return": 0.0,
            "cagr": 0.0,
        }
        return _defaults.get(metric, 0.0)

    def evaluate_metrics(self, metrics: dict[str, Any]) -> tuple[float, bool]:
        """Score a backtest result using Evaluation panel settings.

        Returns:
            (score, is_acceptable): score is the primary metric value (or
            composite if use_composite=True).  is_acceptable is True when
            all hard constraints pass AND the primary metric meets its minimum.
        """
        from backend.optimization.scoring import calculate_composite_score

        primary = self.get_primary_metric()
        use_composite = self.evaluation_config.get("use_composite", False)
        weights = self.evaluation_config.get("weights")
        constraints = self.evaluation_config.get("constraints") or []

        # ── 1. Score ──────────────────────────────────────────────────────────
        if use_composite and weights:
            score = calculate_composite_score(metrics, primary, weights)
        else:
            raw = metrics.get(primary, 0) or 0
            # win_rate is stored as percentage in metrics; keep as-is for threshold comparison
            score = raw if primary == "win_rate" and raw > 1 else float(raw)

        # ── 2. Hard constraints ───────────────────────────────────────────────
        passes_constraints = True
        for c in constraints:
            m = c.get("metric", "")
            op = c.get("operator", ">=")
            val = float(c.get("value", 0))
            mv = float(metrics.get(m, 0) or 0)
            if op in (">=", ">") and not (mv >= val if op == ">=" else mv > val):
                passes_constraints = False
                break
            if op in ("<=", "<") and not (mv <= val if op == "<=" else mv < val):
                passes_constraints = False
                break

        # ── 3. Minimum primary metric ─────────────────────────────────────────
        min_primary = self.get_min_acceptable_primary()
        meets_minimum = score >= min_primary

        is_acceptable = (
            meets_minimum
            and passes_constraints
            and win_rate_ok(metrics, self.min_acceptable_win_rate)
            and (not self.require_positive_profit or (metrics.get("net_profit", 0) or 0) > 0)
        )

        return score, is_acceptable

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
            "use_optimizer_mode": self.use_optimizer_mode,
            "evaluation_config": self.evaluation_config,
        }


def win_rate_ok(metrics: dict[str, Any], min_win_rate: float) -> bool:
    """Check win_rate threshold (handles both % and fraction representation)."""
    raw = metrics.get("win_rate", 0) or 0
    fraction = raw / 100.0 if raw > 1 else raw
    return fraction >= min_win_rate


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
    # True when the run used optimizer sweep mode (for UI display)
    used_optimizer_mode: bool = False
    # Final saved version name/id — set after the iteration loop completes
    final_version_name: str = ""
    final_version_id: str = ""

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
            "used_optimizer_mode": self.used_optimizer_mode,
            "final_version_name": self.final_version_name,
            "final_version_id": self.final_version_id,
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
                  - agent (str)  — "claude" | "perplexity" | "a2a"
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
            agent:    Agent name ("claude", "perplexity").
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
            used_optimizer_mode=config.use_optimizer_mode,
        )
        # Store selected agent for use in helper methods that don't receive config
        self._primary_agent: str = config.agent if config.agent in {"claude", "perplexity"} else "claude"
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

            # ── Optimize mode: load existing strategy FIRST so deliberation
            # and _plan_blocks have access to real blocks/connections.
            if config.existing_strategy_id:
                self._result.strategy_id = config.existing_strategy_id
                logger.info(f"[BuilderWorkflow] Optimize mode — using existing strategy: {config.existing_strategy_id}")
                self._emit_agent_log(
                    agent=self._primary_agent,
                    role="planner",
                    prompt=f"Optimizing existing strategy: {config.existing_strategy_id}",
                    response=f"🔧 Optimize mode — loading existing strategy blocks and connections.\n"
                    f"Symbol: {config.symbol} | Timeframe: {config.timeframe}m | "
                    f"Agent: {self._primary_agent}",
                    title=f"🔧 Optimize mode — {config.symbol} {config.timeframe}m",
                )

                # Fetch existing strategy state.  We need blocks (with params) and
                # connections (graph topology) for both deliberation context and
                # _suggest_adjustments prompt building.
                self._set_stage(BuilderStage.CREATING)
                try:
                    from backend.agents.mcp.tools.strategy_builder import (
                        builder_get_strategy,
                    )

                    existing = await builder_get_strategy(config.existing_strategy_id)
                    if isinstance(existing, dict) and "error" not in existing:
                        raw_blocks = existing.get("blocks", [])
                        raw_connections = existing.get("connections", [])

                        # Fallback: if top-level blocks list is sparse (no params),
                        # try to pull richer block data from builder_graph.blocks.
                        # This also covers the case where the frontend sent empty arrays.
                        if not raw_blocks or not any(b.get("params") for b in raw_blocks):
                            graph = existing.get("builder_graph") or {}
                            graph_blocks = graph.get("blocks", [])
                            if graph_blocks and any(b.get("params") for b in graph_blocks):
                                logger.info("[BuilderWorkflow] Using builder_graph.blocks (richer params)")
                                raw_blocks = graph_blocks

                        # Same fallback for connections
                        if not raw_connections:
                            graph = existing.get("builder_graph") or {}
                            raw_connections = graph.get("connections", [])

                        # If the frontend provided blocks in the payload, prefer
                        # those (they are the live canvas state, always current)
                        # but fall back to DB data when the frontend sent nothing.
                        if config.blocks:
                            logger.info(
                                f"[BuilderWorkflow] Using canvas blocks from payload "
                                f"({len(config.blocks)} blocks, {len(config.connections)} connections)"
                            )
                        else:
                            config.blocks = raw_blocks
                            config.connections = raw_connections
                            logger.info(
                                f"[BuilderWorkflow] Loaded blocks from DB: "
                                f"{len(raw_blocks)} blocks, {len(raw_connections)} connections"
                            )

                        self._result.blocks_added = config.blocks
                        self._result.connections_made = config.connections
                        logger.info(
                            f"[BuilderWorkflow] Strategy context ready: "
                            f"{len(self._result.blocks_added)} blocks "
                            f"({sum(1 for b in self._result.blocks_added if b.get('params'))} with params), "
                            f"{len(self._result.connections_made)} connections"
                        )

                        # ── Sync payload connections to DB ──────────────────────────
                        # If the payload provided connections (filtered by caller),
                        # write them to DB immediately so that subsequent
                        # builder_update_block_params GET/PUT cycles preserve the
                        # correct topology rather than restoring removed connections.
                        _payload_conn_ids = {c.get("id") for c in config.connections}
                        _raw_conn_ids = {c.get("id") for c in raw_connections}
                        if config.connections and _payload_conn_ids != _raw_conn_ids:
                            try:
                                sync_payload = {
                                    "name": existing.get("name", config.name),
                                    "description": existing.get("description", ""),
                                    "symbol": existing.get("symbol", config.symbol),
                                    "timeframe": existing.get("timeframe", config.timeframe),
                                    "direction": existing.get("direction", config.direction),
                                    "market_type": existing.get("market_type", "linear"),
                                    "initial_capital": existing.get("initial_capital", config.initial_capital),
                                    "leverage": existing.get("leverage", round(config.leverage)),
                                    "blocks": config.blocks,
                                    "connections": config.connections,
                                }
                                from backend.agents.mcp.tools.strategy_builder import _api_put

                                await _api_put(
                                    f"/strategies/{config.existing_strategy_id}",
                                    json_data=sync_payload,
                                )
                                logger.info(
                                    f"[BuilderWorkflow] Synced {len(config.connections)} payload connections "
                                    f"to DB (was {len(raw_connections)} — removed "
                                    f"{len(raw_connections) - len(config.connections)} filtered connections)"
                                )
                            except Exception as _sync_err:
                                logger.warning(f"[BuilderWorkflow] Could not sync connections to DB: {_sync_err}")
                    else:
                        logger.warning(
                            f"[BuilderWorkflow] Could not load existing strategy details: "
                            f"{existing}. Continuing with optimize anyway."
                        )
                except Exception as e:
                    logger.warning(
                        f"[BuilderWorkflow] Failed to fetch existing strategy: {e}. Continuing with optimize anyway."
                    )

            # ── Auto-fix: inject SL/TP config when no exit block present ──────
            # Instead of adding a structural block (which can get lost from builder_blocks
            # during the long LLM/optimizer cycle), we set stop_loss / take_profit at the
            # config level so the backtest engine enforces them directly.
            # The backtest endpoint is also patched to accept these as valid exit conditions.
            if config.existing_strategy_id and config.blocks:
                _exit_types = {
                    "static_sltp",
                    "exit",
                    "trailing_stop",
                    "atr_exit",
                    "multi_tp",
                    "trailing_stop_exit",
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
                }
                if not any(b.get("type") in _exit_types for b in config.blocks):
                    if config.stop_loss is None:
                        config.stop_loss = 0.02  # 2% SL
                    if config.take_profit is None:
                        config.take_profit = 0.04  # 4% TP
                    logger.info(
                        "[BuilderWorkflow] Optimize mode: no exit block found — "
                        f"injecting SL={config.stop_loss * 100:.1f}% TP={config.take_profit * 100:.1f}% "
                        "into backtest config (no structural block added)"
                    )
                    self._emit_agent_log(
                        agent="system",
                        role="planner",
                        prompt="Auto-fix: missing exit conditions",
                        response=(
                            f"✅ Strategy has no exit block. Using SL={config.stop_loss * 100:.1f}% / "
                            f"TP={config.take_profit * 100:.1f}% from backtest config so all iterations "
                            "can run. Optimizer will tune indicator parameters."
                        ),
                        title="🔧 Auto-fix: SL/TP injected from config",
                    )

            # LLM block planning: only for new strategies when no blocks provided
            if not config.existing_strategy_id and not config.blocks:
                await self._plan_blocks(config)

            # Optional AI Deliberation — now always has populated config.blocks
            if config.enable_deliberation:
                await self._run_deliberation(config)

            # Build mode: Stages 2-4 — create strategy, add blocks, connect
            if not config.existing_strategy_id:
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
                leverage=round(config.leverage),
                direction=config.direction,
                commission=config.commission,
                stop_loss=config.stop_loss,
                take_profit=config.take_profit,
            )
            self._result.backtest_results = backtest

            # ── Detect backtest errors / zero-trade warnings ───────────────────
            if isinstance(backtest, dict):
                if "error" in backtest:
                    err_msg = f"Initial backtest failed: {backtest['error']}"
                    logger.warning(f"[BuilderWorkflow] {err_msg}")
                    self._result.errors.append(err_msg)
                    self._emit_agent_log(
                        agent="system",
                        role="backtest",
                        prompt="Running initial backtest",
                        response=err_msg,
                        title="⚠️ Backtest error — strategy may have missing connections",
                    )
                elif backtest.get("warnings"):
                    for w in backtest["warnings"]:
                        logger.warning(f"[BuilderWorkflow] Backtest warning: {w}")
                        self._emit_agent_log(
                            agent="system",
                            role="backtest",
                            prompt="Backtest signal check",
                            response=w,
                            title="⚠️ Backtest warning",
                        )
                _init_trades = (backtest.get("results") or {}).get("total_trades", 0)
                if _init_trades == 0 and "error" not in backtest:
                    logger.warning(
                        "[BuilderWorkflow] Initial backtest produced 0 trades — "
                        "strategy may have missing entry/exit connections"
                    )
                    self._emit_agent_log(
                        agent="system",
                        role="backtest",
                        prompt="Initial backtest result",
                        response="0 trades generated. Optimizer sweep will be skipped until trades are detected.",
                        title="⚠️ 0 trades — checking connections",
                    )
                elif _init_trades < 20 and "error" not in backtest:
                    logger.warning(
                        f"[BuilderWorkflow] Initial backtest: only {_init_trades} trades — "
                        "signal conditions are too restrictive. Agents will receive sparse-signal warning."
                    )
                    self._emit_agent_log(
                        agent="system",
                        role="backtest",
                        prompt="Initial backtest result",
                        response=(
                            f"⚠️ Sparse signals: only {_init_trades} trades in the full backtest period. "
                            "For a 30m strategy you need 2+ trades/day minimum. "
                            "The AND-gate logic is too restrictive — agents must widen entry conditions "
                            "(e.g. use continuous SuperTrend signal instead of on-change-only, "
                            "raise RSI cross level, or replace AND with OR)."
                        ),
                        title=f"⚠️ Sparse signals ({_init_trades} trades) — conditions too tight",
                    )

            # Stage 8: Evaluate + Iterative optimization loop
            best_primary_score: float = float("-inf")
            primary_score: float = float("-inf")  # set on first iteration; guard for post-loop code
            best_iteration_record: dict[str, Any] = {}
            best_blocks_snapshot: list[dict[str, Any]] = []
            best_backtest_result: dict[str, Any] = {}

            # ── Hypothesis-testing state across iterations ────────────────────
            # Carries optimizer findings from one iteration to the next so agents
            # can narrow/shift ranges based on what was already explored.
            _prev_opt_ranges: list[dict[str, Any]] | None = None
            _prev_opt_best_params: dict[str, Any] | None = None
            _prev_opt_score: float | None = None

            for iteration in range(1, config.max_iterations + 1):
                self._set_stage(BuilderStage.EVALUATING)
                # Backtest response uses "results" key (from run_backtest_from_builder endpoint)
                # but also support "metrics" key for compatibility
                metrics = {}
                if isinstance(backtest, dict) and "error" not in backtest:
                    metrics = backtest.get("results", backtest.get("metrics", {}))

                # ── Evaluate via Evaluation panel config (single source of truth) ──
                primary_score, is_acceptable = config.evaluate_metrics(metrics)
                primary_metric = config.get_primary_metric()

                # Keep sharpe for logging/memory (always useful regardless of primary_metric)
                sharpe = float(metrics.get("sharpe_ratio", 0) or 0)
                raw_win_rate = metrics.get("win_rate", 0)
                win_rate = raw_win_rate / 100.0 if raw_win_rate > 1 else raw_win_rate

                iteration_record = {
                    "iteration": iteration,
                    "primary_metric": primary_metric,
                    "primary_score": primary_score,
                    "sharpe_ratio": sharpe,
                    "win_rate": win_rate,
                    "total_trades": metrics.get("total_trades", 0),
                    "net_profit": metrics.get("net_profit", 0),
                    "max_drawdown": metrics.get("max_drawdown", metrics.get("max_drawdown_pct", 0)),
                    "acceptable": is_acceptable,
                }
                self._result.iterations.append(iteration_record)

                # ── Save iteration result to Episodic Memory ──────────────────
                await self._memory_store_iteration(config, iteration_record, self._result.blocks_added)

                # Track best result by primary metric (not hardcoded sharpe)
                if primary_score > best_primary_score:
                    best_primary_score = primary_score
                    best_iteration_record = iteration_record
                    best_blocks_snapshot = copy.deepcopy(self._result.blocks_added)
                    best_backtest_result = backtest if isinstance(backtest, dict) else {}

                if iteration_record["acceptable"]:
                    logger.info(
                        f"[BuilderWorkflow] Iteration {iteration}: Strategy meets criteria — "
                        f"{primary_metric}={primary_score:.3f}, Sharpe={sharpe:.2f}, WinRate={win_rate:.1%}"
                    )
                    break

                logger.info(
                    f"[BuilderWorkflow] Iteration {iteration}/{config.max_iterations}: "
                    f"{primary_metric}={primary_score:.3f} (min {config.get_min_acceptable_primary():.3f}), "
                    f"Sharpe={sharpe:.2f}, WinRate={win_rate:.1%} (min {config.min_acceptable_win_rate:.0%}), "
                    f"NetProfit={metrics.get('net_profit', 0):.2f} "
                    f"{'✅' if metrics.get('net_profit', 0) > 0 else '❌'} — iterating"
                )

                # --- Iterative parameter adjustment ---
                self._set_stage(BuilderStage.ITERATING)

                # ── Shared context for _suggest_adjustments calls ──────────
                _bt_warnings = backtest.get("warnings", []) if isinstance(backtest, dict) else []
                _iters_hist = list(self._result.iterations)  # snapshot before new iter added
                _delib_plan = self._result.deliberation.get("decision", "") or None

                if config.use_optimizer_mode:
                    # ── Step 0: Topology intelligence — restructure graph if needed ─────
                    # Agents first check for STRUCTURAL problems (wrong connections, dead
                    # blocks, OR/AND gate issues) that parameter tuning cannot fix.
                    # This runs BEFORE param optimization so the optimizer works on a
                    # topologically correct graph, not a broken one.
                    _live_connections = list(self._result.connections_made or [])
                    topo_changes = await self._suggest_topology_changes(
                        blocks=self._result.blocks_added,
                        connections=_live_connections,
                        metrics=metrics,
                        iteration=iteration,
                        iterations_history=_iters_hist,
                    )
                    if topo_changes:
                        applied_topo = await self._apply_topology_changes(
                            strategy_id=self._result.strategy_id,
                            changes=topo_changes,
                            current_connections=_live_connections,
                            current_metrics=metrics,
                        )
                        if applied_topo:
                            # Sync connections_made with what was actually changed
                            self._result.connections_made = _live_connections
                            logger.info(
                                f"[BuilderWorkflow] 🏗️ Topology restructured: "
                                f"{len(applied_topo)}/{len(topo_changes)} changes applied "
                                f"— running quick backtest to get new baseline"
                            )
                            # Quick re-backtest after topology change so optimizer
                            # sees the new graph, not the old broken one.
                            _topo_sl = config.stop_loss if (config.stop_loss and config.stop_loss >= 0.001) else None
                            _topo_tp = (
                                config.take_profit if (config.take_profit and config.take_profit >= 0.001) else None
                            )
                            _topo_backtest = await builder_run_backtest(
                                strategy_id=self._result.strategy_id,
                                symbol=config.symbol,
                                interval=config.timeframe,
                                start_date=config.start_date,
                                end_date=config.end_date,
                                initial_capital=config.initial_capital,
                                leverage=round(config.leverage),
                                direction=config.direction,
                                stop_loss=_topo_sl,
                                take_profit=_topo_tp,
                            )
                            if isinstance(_topo_backtest, dict) and "error" not in _topo_backtest:
                                backtest = _topo_backtest
                                metrics = backtest.get("results", backtest.get("metrics", {}))
                                _topo_sharpe = float(metrics.get("sharpe_ratio", 0) or 0)
                                _topo_trades = int(metrics.get("total_trades", 0))
                                logger.info(
                                    f"[BuilderWorkflow] 🏗️ Post-topology baseline: "
                                    f"Sharpe={_topo_sharpe:.3f}, Trades={_topo_trades}"
                                )
                                # Recalculate primary score for the new baseline
                                primary_score, _ = config.evaluate_metrics(metrics)
                                # Reset hypothesis state — topology changed everything
                                _prev_opt_ranges = None
                                _prev_opt_best_params = None
                                _prev_opt_score = None
                            else:
                                logger.warning(
                                    "[BuilderWorkflow] Post-topology backtest failed — "
                                    "continuing with optimizer on new topology anyway"
                                )

                    # ── Hypothesis-testing mode: agents propose ranges → optimizer sweeps ──
                    # Agents ALWAYS propose parameter RANGES (never fixed values).
                    # Each iteration is a hypothesis test:
                    #   1. Agents propose ranges (informed by previous iteration's findings)
                    #   2. Optimizer sweeps those ranges (Optuna TPE/CMA-ES)
                    #   3. Best found params are applied → next backtest
                    #   4. Agents narrow/shift ranges based on what worked or failed
                    # No fallback to fixed-value suggestions inside optimizer mode.
                    agent_ranges = await self._suggest_param_ranges(
                        blocks_added=self._result.blocks_added,
                        iteration=iteration,
                        metrics=metrics,
                        connections=self._result.connections_made,
                        backtest_warnings=_bt_warnings,
                        iterations_history=_iters_hist,
                        deliberation_plan=_delib_plan,
                        previous_ranges=_prev_opt_ranges,
                        previous_best_params=_prev_opt_best_params,
                        previous_opt_score=_prev_opt_score,
                        current_score=primary_score,
                    )
                    opt_result: dict[str, Any] | None = None
                    if agent_ranges:
                        opt_result = await self._run_optimizer_for_ranges(config, agent_ranges)

                    if opt_result and opt_result.get("best_params"):
                        _opt_score = opt_result.get("best_score", float("-inf"))
                        # Apply optimizer params UNCONDITIONALLY — even when optimizer
                        # score ≤ current score we still apply them, because the next
                        # iteration's agents need to start from a known point in
                        # parameter space, not a stale baseline.
                        by_block: dict[str, dict[str, Any]] = {}
                        for path, value in opt_result["best_params"].items():
                            bid, _, param = path.partition(".")
                            by_block.setdefault(bid, {})[param] = value
                        adjustments = [{"block_id": bid, "params": params} for bid, params in by_block.items()]
                        _improved = "↑ improved" if _opt_score > primary_score else "→ same region"
                        logger.info(
                            f"[BuilderWorkflow] 🔬 Hypothesis {iteration}: {_improved} — "
                            f"{len(adjustments)} block(s), optimizer_score={_opt_score:.3f} "
                            f"(baseline={primary_score:.3f})"
                        )
                        # Store findings for next iteration's hypothesis refinement
                        _prev_opt_ranges = agent_ranges
                        _prev_opt_best_params = dict(opt_result["best_params"])
                        _prev_opt_score = _opt_score
                    else:
                        # Optimizer found no valid params (all trials NaN/pruned).
                        # Record the failed ranges so next-iteration agents can
                        # shift to unexplored territory.
                        logger.info(
                            f"[BuilderWorkflow] 🔬 Hypothesis {iteration}: optimizer found no valid "
                            f"params — recording failed ranges for agents to avoid next cycle"
                        )
                        _prev_opt_ranges = agent_ranges  # agents see what was already tried
                        _prev_opt_best_params = None
                        _prev_opt_score = None
                        adjustments = []
                else:
                    # ── Direct mode: agents suggest single values (original) ──
                    adjustments = await self._suggest_adjustments(
                        config.blocks,
                        self._result.blocks_added,
                        iteration,
                        metrics,
                        connections=self._result.connections_made,
                        backtest_warnings=_bt_warnings,
                        iterations_history=_iters_hist,
                        deliberation_plan=_delib_plan,
                    )

                if not adjustments:
                    logger.info("[BuilderWorkflow] No adjustments possible, stopping iteration")
                    break

                # Apply each adjustment; track failures so we can skip the
                # backtest if every single update failed (no-op iteration).
                failed_blocks: list[str] = []
                for adj in adjustments:
                    block_id: str = str(adj["block_id"])
                    new_params = adj["params"]
                    logger.info(f"[BuilderWorkflow] Adjusting block {block_id}: {new_params}")
                    update_result = await builder_update_block_params(
                        strategy_id=self._result.strategy_id,
                        block_id=block_id,
                        params=new_params,
                    )
                    if isinstance(update_result, dict) and "error" in update_result:
                        err_msg = f"Iteration {iteration}: Failed to adjust {block_id}: {update_result['error']}"
                        self._result.errors.append(err_msg)
                        logger.warning(f"[BuilderWorkflow] {err_msg}")
                        failed_blocks.append(block_id)
                    else:
                        # Update local blocks_added so _suggest_adjustments sees
                        # the new params in the next iteration's graph description.
                        for b in self._result.blocks_added:
                            if b.get("id") == block_id:
                                b.setdefault("params", {}).update(new_params)
                                break

                if len(failed_blocks) == len(adjustments):
                    logger.warning(
                        f"[BuilderWorkflow] All {len(adjustments)} block update(s) failed "
                        f"({failed_blocks}) — skipping backtest for iteration {iteration + 1}"
                    )
                    continue

                # Save a version snapshot to DB after each successful adjustment
                try:
                    import re as _re

                    from backend.agents.mcp.tools.strategy_builder import (
                        builder_clone_strategy,
                    )

                    base_name = _re.sub(r"[_ ]*AI-\d+$", "", config.name).rstrip("_- ")
                    version_name = f"{base_name} AI-{iteration}"
                    clone = await builder_clone_strategy(
                        strategy_id=self._result.strategy_id,
                        new_name=version_name,
                    )
                    if isinstance(clone, dict) and "error" not in clone:
                        logger.info(
                            f"[BuilderWorkflow] 💾 Version snapshot saved: {version_name} (id={clone.get('id', '?')})"
                        )
                        iteration_record["version_name"] = version_name
                        iteration_record["version_strategy_id"] = clone.get("id", "")
                    else:
                        logger.warning(f"[BuilderWorkflow] Version snapshot failed (non-fatal): {clone}")
                except Exception as snap_err:
                    logger.warning(f"[BuilderWorkflow] Version snapshot error (non-fatal): {snap_err}")

                # Re-generate code after adjustments
                self._set_stage(BuilderStage.GENERATING_CODE)
                code_result = await builder_generate_code(self._result.strategy_id)
                if isinstance(code_result, dict) and "error" not in code_result:
                    self._result.generated_code = code_result.get("code", "")

                # Re-run backtest with adjusted parameters
                self._set_stage(BuilderStage.BACKTESTING)
                logger.info(f"[BuilderWorkflow] Re-running backtest (iteration {iteration + 1})...")
                # Sanitize SL/TP: 0.0 fails BacktestConfig(ge=0.001) — treat as None
                _iter_sl = config.stop_loss if (config.stop_loss and config.stop_loss >= 0.001) else None
                _iter_tp = config.take_profit if (config.take_profit and config.take_profit >= 0.001) else None
                backtest = await builder_run_backtest(
                    strategy_id=self._result.strategy_id,
                    symbol=config.symbol,
                    interval=config.timeframe,
                    start_date=config.start_date,
                    end_date=config.end_date,
                    initial_capital=config.initial_capital,
                    leverage=round(config.leverage),
                    direction=config.direction,
                    commission=config.commission,
                    stop_loss=_iter_sl,
                    take_profit=_iter_tp,
                )
                self._result.backtest_results = backtest

                # Detect and surface iteration backtest errors/warnings
                if isinstance(backtest, dict):
                    if "error" in backtest:
                        iter_err = f"Iteration {iteration + 1} backtest error: {backtest['error']}"
                        logger.warning(f"[BuilderWorkflow] {iter_err}")
                        self._result.errors.append(iter_err)
                        self._emit_agent_log(
                            agent="system",
                            role="backtest",
                            prompt=f"Re-running backtest (iteration {iteration + 1})",
                            response=iter_err,
                            title=f"⚠️ Backtest error — iteration {iteration + 1}",
                        )
                    elif backtest.get("warnings"):
                        for _w in backtest["warnings"]:
                            logger.warning(f"[BuilderWorkflow] Iteration backtest warning: {_w}")
                    _iter_trades = (backtest.get("results") or {}).get("total_trades", 0)
                    if _iter_trades == 0 and "error" not in backtest:
                        logger.warning(f"[BuilderWorkflow] Iteration {iteration + 1} backtest: 0 trades")

                # Gate 2: last iteration — capture optimizer-adjusted backtest result then stop
                if iteration >= config.max_iterations:
                    if isinstance(backtest, dict) and "error" not in backtest:
                        _final_m = backtest.get("results", backtest.get("metrics", {}))
                        _final_sharpe = float(_final_m.get("sharpe_ratio", 0) or 0)
                        _final_wr = _final_m.get("win_rate", 0)
                        _final_wr_frac = _final_wr / 100.0 if _final_wr > 1 else _final_wr
                        _final_score, _final_ok = config.evaluate_metrics(_final_m)
                        _final_record: dict[str, Any] = {
                            "iteration": iteration + 1,
                            "primary_metric": primary_metric,
                            "primary_score": _final_score,
                            "sharpe_ratio": _final_sharpe,
                            "win_rate": _final_wr_frac,
                            "total_trades": _final_m.get("total_trades", 0),
                            "net_profit": _final_m.get("net_profit", 0),
                            "max_drawdown": _final_m.get("max_drawdown", _final_m.get("max_drawdown_pct", 0)),
                            "acceptable": _final_ok,
                            "_gate2_capture": True,  # not a real iteration; excluded from naming count
                        }
                        self._result.iterations.append(_final_record)
                        if _final_score > best_primary_score:
                            best_primary_score = _final_score
                            best_iteration_record = _final_record
                            best_blocks_snapshot = copy.deepcopy(self._result.blocks_added)
                        logger.info(
                            f"[BuilderWorkflow] Optimizer result captured: "
                            f"{primary_metric}={_final_score:.3f}, Sharpe={_final_sharpe:.3f}, "
                            f"Trades={_final_m.get('total_trades', 0)}"
                        )
                    logger.info("[BuilderWorkflow] Max iterations reached, accepting best result")
                    break

            # ── Save best config to Semantic Memory (survives restarts) ───────
            await self._memory_store_best_config(config, best_iteration_record)

            # ── Restore best-iteration params if last iteration was worse ──────
            # The live strategy always ends up with the LAST iteration's params,
            # but the BEST params may have been from an earlier iteration
            # (e.g. optimizer swept to a worse region on the last pass, or
            # the final LLM tweak degraded the result). Re-apply the best
            # block params so the final clone captures the actual best result.
            # Use the final Gate 2 score (last appended record), not the score
            # from the START of the last iteration — they differ because the
            # Bayesian sweep + LLM adjustments run AFTER primary_score is set.
            _last_primary = (
                self._result.iterations[-1].get("primary_score", primary_score)
                if self._result.iterations
                else primary_score
            )
            if best_blocks_snapshot and best_primary_score > _last_primary:
                logger.info(
                    f"[BuilderWorkflow] ↩️ Restoring best-iteration params "
                    f"(best={best_primary_score:.3f} > last={_last_primary:.3f})"
                )
                from backend.agents.mcp.tools.strategy_builder import (
                    builder_update_block_params as _ubp,
                )

                for _best_b in best_blocks_snapshot:
                    _bid = _best_b.get("id", "")
                    _best_params = _best_b.get("params") or {}
                    _curr_b = next((b for b in self._result.blocks_added if b.get("id") == _bid), None)
                    _curr_params = (_curr_b.get("params") or {}) if _curr_b else {}
                    _diff = {k: v for k, v in _best_params.items() if _curr_params.get(k) != v}
                    if _diff:
                        await _ubp(
                            strategy_id=self._result.strategy_id,
                            block_id=_bid,
                            params=_diff,
                        )
                        if _curr_b:
                            _curr_b.setdefault("params", {}).update(_diff)
                self._result.blocks_added = copy.deepcopy(best_blocks_snapshot)
                self._result.backtest_results = best_backtest_result
                self._emit_agent_log(
                    agent="system",
                    role="optimizer",
                    prompt="Restoring best iteration params",
                    response=f"↩️ Params restored from best iteration (score={best_primary_score:.3f})",
                    title="↩️ Best params restored",
                )

            # ── Save FINAL version as a named clone ───────────────────────────
            # Always save a permanent "final" clone so the user has a clearly
            # named snapshot with the best parameters that came out of this run.
            # Naming convention:
            #   optimize mode : {base}_opt_v{iterations}
            #   build mode    : {name}_ai_v{iterations}
            try:
                from backend.agents.mcp.tools.strategy_builder import (
                    builder_clone_strategy,
                )

                # Exclude the Gate 2 "final capture" record from the count
                _total_iters = sum(1 for r in self._result.iterations if not r.get("_gate2_capture"))
                import re as _re

                _base = _re.sub(r"[_ ]*AI-\d+$", "", config.name).rstrip("_- ")
                _final_name = f"{_base} AI-{_total_iters}"

                final_clone = await builder_clone_strategy(
                    strategy_id=self._result.strategy_id,
                    new_name=_final_name,
                )
                if isinstance(final_clone, dict) and "error" not in final_clone:
                    self._result.final_version_name = _final_name
                    self._result.final_version_id = final_clone.get("id", "")
                    logger.info(
                        f"[BuilderWorkflow] ✅ Final version saved: {_final_name} (id={self._result.final_version_id})"
                    )
                    self._emit_agent_log(
                        agent=self._primary_agent,
                        role="planner",
                        prompt="Saving final optimized version",
                        response=f"✅ Final strategy saved as «{_final_name}»\nID: {self._result.final_version_id}",
                        title=f"💾 Saved: {_final_name}",
                    )
                else:
                    logger.warning(f"[BuilderWorkflow] Final version clone failed: {final_clone}")
            except Exception as _fv_err:
                logger.warning(f"[BuilderWorkflow] Final version save error (non-fatal): {_fv_err}")

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
        # NOTE: "and", "or", "not" are LOGIC blocks (category="logic"), NOT conditions.
        # Logic blocks combine signals but are not entry conditions themselves
        # — they should NOT be auto-wired to action blocks.
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
            "Indicators: rsi, ema, sma, macd, bollinger, bbands, atr, stochastic, adx, "
            "supertrend, vwap, cci, williams_r, mfi, roc, momentum, obv. "
            "Conditions: crossover, crossunder, greater_than, less_than, between, equals. "
            "Logic (signal combinators, NOT entry conditions): and, or, not. "
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
            from backend.agents.unified_agent_interface import UnifiedAgentInterface

            _agent_name = config.agent if config.agent in {"claude", "perplexity"} else "claude"
            _interface = UnifiedAgentInterface()
            raw_text: str = await _interface.ask(_agent_name, prompt) or ""
            logger.debug(f"[BuilderWorkflow] LLM plan raw response from {_agent_name} ({len(raw_text)} chars)")

            # Emit agent log so the SSE panel can show what the planner said
            self._emit_agent_log(
                agent=_agent_name,
                role="planner",
                prompt=prompt,
                response=raw_text,
                title=f"📐 Strategy Design for {config.symbol} {config.timeframe}m",
            )

            result: dict[str, Any] = {"response": raw_text, "success": bool(raw_text)}

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
        # Map both raw names and resolved IDs so has_downstream works correctly
        explicit_sources: set[str] = set()
        for conn in explicit_connections:
            src = conn.get("source", "")
            if src:
                explicit_sources.add(src)
                # Also add the resolved actual block ID so we don't double-wire
                resolved_src = block_id_map.get(src, "")
                if resolved_src:
                    explicit_sources.add(resolved_src)

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
            # Check both the raw plan name and the resolved actual block ID
            has_downstream = (
                cond["id"] in explicit_sources or cond["type"] in explicit_sources or cond_id in explicit_sources
            )

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

    # ──────────────────────────────────────────────────────────────────────────
    # Graph description helper — formats visual block graph for agent prompts
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _describe_graph_for_agents(
        blocks: list[dict[str, Any]],
        connections: list[dict[str, Any]],
    ) -> str:
        """Format the visual node graph as human-readable text for agent prompts.

        Produces a compact but complete description of the block graph:
        block IDs, types, roles, current parameters, and the signal-flow
        connections between them.  This is injected into every agent prompt so
        that agents understand the existing graph structure before suggesting
        any parameter changes.

        Args:
            blocks: List of block dicts with at least ``id``, ``type``, and
                optional ``name``/``params`` keys.
            connections: List of connection dicts with ``source_block_id``,
                ``source_port``, ``target_block_id``, ``target_port`` keys.
                The REST API also emits ``source``/``target`` aliases.

        Returns:
            Multi-line human-readable string describing the graph.
        """
        _BLOCK_ROLE = {
            # Indicators — compute numeric values from price data
            "rsi": "indicator (RSI momentum oscillator, output: long_signal/short_signal)",
            "ema": "indicator (Exponential Moving Average, output: value)",
            "sma": "indicator (Simple Moving Average, output: value)",
            "macd": "indicator (MACD momentum, output: macd/signal/histogram/long_signal/short_signal)",
            "bollinger": "indicator (Bollinger Bands, output: upper/middle/lower/long_signal/short_signal)",
            "bbands": "indicator (Bollinger Bands, output: upper/middle/lower/long_signal/short_signal)",
            "atr": "indicator (Average True Range volatility, output: value)",
            "stochastic": "indicator (Stochastic oscillator, output: k/d/long_signal/short_signal)",
            "stoch": "indicator (Stochastic oscillator, output: k/d/long_signal/short_signal)",
            "adx": "indicator (Average Directional Index trend strength, output: adx/plus_di/minus_di)",
            "supertrend": "indicator (SuperTrend trend-follower, output: direction/long_signal/short_signal)",
            "vwap": "indicator (Volume Weighted Average Price, output: value)",
            "cci": "indicator (Commodity Channel Index, output: value/long_signal/short_signal)",
            "williams_r": "indicator (Williams %R oscillator, output: value/long_signal/short_signal)",
            "mfi": "indicator (Money Flow Index volume-oscillator, output: value/long_signal/short_signal)",
            "roc": "indicator (Rate of Change momentum, output: value)",
            "momentum": "indicator (Momentum oscillator, output: value)",
            "obv": "indicator (On-Balance Volume, output: value)",
            # Conditions — evaluate a boolean True/False signal
            "crossover": "condition (True when input_a crosses ABOVE input_b, output: result)",
            "crossunder": "condition (True when input_a crosses BELOW input_b, output: result)",
            "greater_than": "condition (True when input_a > input_b, output: result)",
            "less_than": "condition (True when input_a < input_b, output: result)",
            "between": "condition (True when value is between lower/upper bounds, output: result)",
            "equals": "condition (True when input_a == input_b, output: result)",
            # Logic gates — combine boolean signals
            "and": "logic gate (output True only when ALL inputs are True, output: result)",
            "or": "logic gate (output True when ANY input is True, output: result)",
            "not": "logic gate (inverts boolean input, output: result)",
            # Data sources
            "price": "data source (emits OHLCV price data, output: close/open/high/low/volume)",
            # Actions — trigger trade entries/exits
            "buy": "action (triggers LONG entry when signal=True)",
            "buy_market": "action (triggers LONG market entry when signal=True)",
            "sell": "action (triggers SHORT entry when signal=True)",
            "sell_market": "action (triggers SHORT market entry when signal=True)",
            "close_long": "action (closes LONG position when signal=True)",
            "close_short": "action (closes SHORT position when signal=True)",
            "close_all": "action (closes ALL positions when signal=True)",
            # Risk management
            "static_sltp": "risk management (fixed Stop-Loss/Take-Profit percentages)",
            "atr_sltp": "risk management (ATR-based dynamic Stop-Loss/Take-Profit)",
            "trailing_stop_exit": "risk management (trailing stop exit)",
            # Strategy aggregator
            "strategy": "strategy node (MAIN NODE — aggregates all action signals into the backtest engine)",
        }

        lines: list[str] = []

        lines.append("STRATEGY GRAPH (visual node editor):")
        lines.append(
            "Each block is a node. Connections carry signals between ports. "
            "The STRATEGY node is the final aggregator — all trade signals must reach it."
        )
        lines.append("")
        lines.append("BLOCKS (do NOT add, remove, or rename any block):")

        # Identify which block IDs are tunable (have actual params to adjust)
        _TUNABLE_TYPES = {
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
            "cci",
            "williams_r",
            "mfi",
            "roc",
            "momentum",
            "obv",
            "static_sltp",
            "atr_sltp",
            "crossover",
            "crossunder",
            "greater_than",
            "less_than",
            "between",
        }

        for b in blocks:
            bid = b.get("id") or b.get("block_id", "?")
            btype = (b.get("type") or b.get("block_type", "unknown")).lower()
            block_name = b.get("name") or btype.upper()
            params = b.get("params") or {}
            role = _BLOCK_ROLE.get(btype, f"block (type={btype})")
            tunable = "✏️ tunable" if (btype in _TUNABLE_TYPES and params) else "🔒 no params"

            if params:
                params_str = ", ".join(f"{k}={v}" for k, v in params.items())
                lines.append(f"  • [{bid}] {block_name} ({role}) — params: {{{params_str}}} [{tunable}]")
            else:
                lines.append(f"  • [{bid}] {block_name} ({role}) [{tunable}]")

        lines.append("")
        lines.append("SIGNAL FLOW (connections — do NOT change any connection):")

        # Normalise connection keys — REST API uses both source_block_id and source
        def _src_id(c: dict[str, Any]) -> str:
            return c.get("source_block_id") or c.get("source") or "?"

        def _tgt_id(c: dict[str, Any]) -> str:
            return c.get("target_block_id") or c.get("target") or "?"

        def _src_port(c: dict[str, Any]) -> str:
            return c.get("source_port") or "out"

        def _tgt_port(c: dict[str, Any]) -> str:
            return c.get("target_port") or "in"

        if connections:
            for conn in connections:
                lines.append(f"  {_src_id(conn)}:{_src_port(conn)}  →  {_tgt_id(conn)}:{_tgt_port(conn)}")
        else:
            lines.append("  (no connections stored — infer from block roles)")

        lines.append("")
        lines.append(
            "⚠️  CONSTRAINT: You may ONLY suggest changes to parameter VALUES of existing blocks. "
            "Do NOT add new blocks, remove blocks, or change any connections."
        )

        return "\n".join(lines)

    @staticmethod
    def _build_block_catalog() -> str:
        """Format ALL available block types from DEFAULT_PARAM_RANGES into a compact catalog.

        This is injected into agent prompts so they know the FULL set of blocks they can
        add or suggest — not just the blocks currently in the strategy.

        Returns:
            Multi-line human-readable catalog grouped by category.
        """
        from backend.optimization.builder_optimizer import DEFAULT_PARAM_RANGES

        # Human-readable metadata per block type: category, description, output ports
        _BLOCK_META: dict[str, dict[str, str]] = {
            # Oscillators → entry signals
            "rsi": {"cat": "oscillator", "desc": "RSI momentum — cross level or range filter", "ports": "long, short"},
            "macd": {"cat": "oscillator", "desc": "MACD histogram cross zero/signal line", "ports": "long, short"},
            "stochastic": {"cat": "oscillator", "desc": "Stochastic %K/%D overbought/oversold", "ports": "long, short"},
            "cci": {"cat": "oscillator", "desc": "Commodity Channel Index momentum", "ports": "long, short"},
            "williams_r": {"cat": "oscillator", "desc": "Williams %R oscillator", "ports": "long, short"},
            "qqe": {"cat": "oscillator", "desc": "QQE — smoothed RSI with dynamic signal band", "ports": "long, short"},
            "divergence": {
                "cat": "oscillator",
                "desc": "Price/indicator divergence (RSI, MACD, Stoch, CMF, MFI)",
                "ports": "long, short",
            },
            "aroon": {
                "cat": "oscillator",
                "desc": "Aroon trend strength + direction crossover",
                "ports": "long, short",
            },
            # Trend indicators
            "supertrend": {
                "cat": "trend",
                "desc": "SuperTrend ATR follower. ⚠️ connect to filter_long (not entry_long) to avoid over-trading every bar",
                "ports": "long, short",
            },
            "ichimoku": {
                "cat": "trend",
                "desc": "Ichimoku cloud multi-component (tenkan/kijun/senkou)",
                "ports": "long, short",
            },
            "parabolic_sar": {"cat": "trend", "desc": "Parabolic SAR trend reversal dots", "ports": "long, short"},
            "adx": {
                "cat": "trend",
                "desc": "ADX trend strength — best as filter: pass when ADX > threshold",
                "ports": "long, short (connect fromPort='long' to toPort='filter_long' on strategy)",
            },
            # Moving averages
            "ema": {"cat": "trend_ma", "desc": "EMA — connect via two_mas for crossover signals", "ports": "value"},
            "sma": {"cat": "trend_ma", "desc": "SMA — connect via two_mas for crossover signals", "ports": "value"},
            "two_mas": {
                "cat": "trend_ma",
                "desc": "Dual MA crossover (fast MA × slow MA cross)",
                "ports": "long, short",
            },
            # Volatility / breakout
            "keltner_bollinger": {
                "cat": "volatility",
                "desc": "BB-inside-Keltner squeeze → breakout momentum signals",
                "ports": "long, short",
            },
            "donchian": {
                "cat": "volatility",
                "desc": "Donchian Channel N-bar high/low breakout",
                "ports": "long, short",
            },
            "highest_lowest_bar": {
                "cat": "volatility",
                "desc": "N-bar high/low breakout with ATR confirmation",
                "ports": "long, short",
            },
            "bollinger": {
                "cat": "volatility",
                "desc": "Bollinger Bands — outputs price bands, NOT bool signals. Use keltner_bollinger for entry signals.",
                "ports": "upper, middle, lower, percentb",
            },
            "keltner": {"cat": "volatility", "desc": "Keltner Channel ATR bands", "ports": "upper, middle, lower"},
            "atr": {"cat": "volatility", "desc": "ATR value — pair with atr_volatility filter", "ports": "value"},
            # Volume
            "cmf": {"cat": "volume", "desc": "Chaikin Money Flow volume momentum (positive=bullish)", "ports": "value"},
            # Filters (AND-gate: connect fromPort='long' toPort='filter_long' on strategy)
            # IMPORTANT: filter block OUTPUT ports are 'long' and 'short' — NOT 'filter_long'/'filter_short'
            # 'filter_long'/'filter_short' are TARGET ports on the strategy node, not source ports
            "supertrend_filter": {
                "cat": "filter",
                "desc": "SuperTrend AND-gate filter — enforce trend alignment (alias: supertrend). Use generate_on_trend_change=True.",
                "ports": "long, short",
            },
            "rsi_filter": {
                "cat": "filter",
                "desc": "RSI level range filter (oversold/overbought gates)",
                "ports": "long, short",
            },
            "macd_filter": {
                "cat": "filter",
                "desc": "MACD histogram sign filter — bullish/bearish bias gate",
                "ports": "long, short",
            },
            "stochastic_filter": {
                "cat": "filter",
                "desc": "Stochastic %K range filter — overbought/oversold gate",
                "ports": "long, short",
            },
            "two_ma_filter": {
                "cat": "filter",
                "desc": "Two-MA alignment filter — price above/below MA pair",
                "ports": "long, short",
            },
            "qqe_filter": {
                "cat": "filter",
                "desc": "QQE trend direction filter — smoothed RSI bias gate",
                "ports": "long, short",
            },
            "volume_filter": {
                "cat": "filter",
                "desc": "Volume ratio filter — confirms with above-average volume",
                "ports": "long, short",
            },
            "rvi_filter": {"cat": "filter", "desc": "Relative Vigor Index filter", "ports": "long, short"},
            "mfi_filter": {
                "cat": "filter",
                "desc": "Money Flow Index filter — volume-weighted momentum",
                "ports": "long, short",
            },
            "cci_filter": {"cat": "filter", "desc": "CCI range filter", "ports": "long, short"},
            "momentum_filter": {"cat": "filter", "desc": "Price momentum ROC filter", "ports": "long, short"},
            "accumulation_areas": {
                "cat": "filter",
                "desc": "Accumulation zone detector — entries near support/resistance",
                "ports": "long, short",
            },
            # Exit blocks
            "static_sltp": {
                "cat": "exit",
                "desc": "Static SL/TP % with optional breakeven. PRIMARY exit.",
                "ports": "sl_tp",
            },
            "trailing_stop_exit": {
                "cat": "exit",
                "desc": "Trailing stop — activates at N%, trails by M%",
                "ports": "sl_tp",
            },
            "atr_exit": {"cat": "exit", "desc": "ATR-dynamic SL/TP — adapts to volatility", "ports": "sl_tp"},
            "multi_tp_exit": {
                "cat": "exit",
                "desc": "3-level TP with partial position close at each level",
                "ports": "sl_tp",
            },
            "close_by_time": {
                "cat": "exit",
                "desc": "Time-based exit: close after N bars (+ optional min_profit gate)",
                "ports": "sl_tp",
            },
            "close_channel": {
                "cat": "exit",
                "desc": "Close when price re-enters BB/Keltner channel (squeeze exit)",
                "ports": "sl_tp",
            },
            "close_ma_cross": {
                "cat": "exit",
                "desc": "Close on fast/slow MA crossover (+ optional min_profit gate)",
                "ports": "sl_tp",
            },
            "close_rsi": {"cat": "exit", "desc": "Close when RSI reaches overbought/oversold level", "ports": "sl_tp"},
            "close_stochastic": {
                "cat": "exit",
                "desc": "Close when Stochastic reaches overbought/oversold",
                "ports": "sl_tp",
            },
            "close_psar": {"cat": "exit", "desc": "Close on Parabolic SAR flip (trend reversal)", "ports": "sl_tp"},
            "chandelier_exit": {
                "cat": "exit",
                "desc": "Chandelier stop: ATR multiplier below highest high",
                "ports": "sl_tp",
            },
            "break_even_exit": {
                "cat": "exit",
                "desc": "Move SL to breakeven after price moves N% in profit",
                "ports": "sl_tp",
            },
            # Entry refinement
            "dca": {
                "cat": "entry",
                "desc": "DCA grid — multiple entry orders below initial entry",
                "ports": "entry_long",
            },
            # MA variants (use via two_mas for crossover)
            "wma": {"cat": "trend_ma", "desc": "Weighted MA — heavier weight on recent bars", "ports": "value"},
            "dema": {"cat": "trend_ma", "desc": "Double EMA — less lag than EMA", "ports": "value"},
            "tema": {"cat": "trend_ma", "desc": "Triple EMA — minimal lag trend follower", "ports": "value"},
            "hull_ma": {"cat": "trend_ma", "desc": "Hull MA — very smooth, minimal lag", "ports": "value"},
            # Additional oscillators
            "stoch_rsi": {
                "cat": "oscillator",
                "desc": "Stochastic RSI — RSI of RSI, highly sensitive",
                "ports": "long, short",
            },
            "roc": {"cat": "oscillator", "desc": "Rate of Change — % price change over N bars", "ports": "long, short"},
            "cmo": {
                "cat": "oscillator",
                "desc": "Chande Momentum Oscillator — bounded momentum",
                "ports": "long, short",
            },
        }

        cat_order = ["oscillator", "trend", "trend_ma", "volatility", "volume", "filter", "exit", "entry"]
        cat_labels = {
            "oscillator": "ENTRY SIGNALS — Oscillators (connect to entry_long / entry_short)",
            "trend": "ENTRY SIGNALS — Trend Indicators (entry or filter_long / filter_short)",
            "trend_ma": "ENTRY SIGNALS — Moving Averages (use via two_mas block for crossover)",
            "volatility": "VOLATILITY & BREAKOUT (entry_long or filter_long)",
            "volume": "VOLUME INDICATORS",
            "filter": "FILTERS — AND-gate (connect to filter_long / filter_short)",
            "exit": "EXIT BLOCKS (connect to sl_tp port)",
            "entry": "ENTRY REFINEMENT",
        }

        # Group by category
        by_cat: dict[str, list[str]] = {}
        for block_type in DEFAULT_PARAM_RANGES:
            meta = _BLOCK_META.get(block_type, {"cat": "other", "desc": "", "ports": "long, short"})
            cat = meta["cat"]
            by_cat.setdefault(cat, []).append(block_type)

        lines = [
            "## FULL BLOCK CATALOG — ALL available block types (use when proposing add_block)",
            "Port semantics: entry_long/entry_short = OR-gate (any fires → trade). "
            "filter_long/filter_short = AND-gate (ALL must pass). sl_tp = exit block port.\n",
        ]
        for cat in cat_order:
            block_types = by_cat.get(cat, [])
            if not block_types:
                continue
            lines.append(f"  [{cat_labels[cat]}]")
            for bt in block_types:
                meta = _BLOCK_META.get(bt, {"desc": "", "ports": "long, short"})
                params = DEFAULT_PARAM_RANGES.get(bt, {})
                key_params = [
                    f"{pn}[{spec.get('low', '?')}..{spec.get('high', '?')}]" for pn, spec in list(params.items())[:5]
                ]
                if len(params) > 5:
                    key_params.append(f"+{len(params) - 5} more")
                lines.append(
                    f"    {bt}: {meta.get('desc', '')} | ports→{meta.get('ports', '?')} "
                    f"| params: {', '.join(key_params)}"
                )
            lines.append("")

        return "\n".join(lines)

    async def _suggest_adjustments(
        self,
        block_defs: list[dict[str, Any]],
        blocks_added: list[dict[str, Any]],
        iteration: int,
        metrics: dict[str, Any],
        connections: list[dict[str, Any]] | None = None,
        backtest_warnings: list[str] | None = None,
        iterations_history: list[dict[str, Any]] | None = None,
        deliberation_plan: str | None = None,
    ) -> list[dict[str, Any]]:
        """Use a 3-agent parallel consensus to suggest parameter adjustments.

        Sends the complete visual block graph (blocks + connections + topology)
        along with backtest metrics to DeepSeek, Qwen, and Perplexity in
        parallel via AgentToAgentCommunicator.parallel_consensus().  Each agent
        proposes parameter-only adjustments; structural changes are explicitly
        forbidden in the prompt.  Their responses are merged: adjustments that
        appear in 2+ responses take priority.

        Falls back to a single DeepSeek call if A2A is unavailable, and to
        the rule-based heuristic if all LLM calls fail.

        Args:
            block_defs: Original block definitions from config.
            blocks_added: Actual blocks added (with IDs and current params).
            iteration: Current iteration number (1-based).
            metrics: Backtest metrics from the last run.
            connections: Current connections list (for graph topology context).

        Returns:
            List of ``{"block_id": ..., "params": {...}}`` adjustments.
        """
        # === AUTO-FIX: sparse-signal boolean params =====================================
        # When trades are critically sparse, deterministically fix known culprits
        # BEFORE calling LLMs. These are structural boolean params that the agent
        # prompt cannot change (constraint says "numeric only").
        #
        # Strategy:
        #   SuperTrend + RSI in AND gate → RSI stays as trigger, SuperTrend becomes filter.
        #   SuperTrend alone          → disable on-change-only, make continuous filter.
        #   RSI alone (no SuperTrend) → switch to range mode for continuous signals.
        _adj_trades = int(metrics.get("total_trades", 0))
        if _adj_trades < 15:
            auto_fixes: list[dict[str, Any]] = []
            # First pass: detect SuperTrend blocks with generate_on_trend_change=True.
            # When such a block exists we must NOT also disable RSI use_cross_level —
            # that combination (RSI range + SuperTrend continuous) creates the opposite
            # problem: both conditions are nearly always true → floods entries with
            # near-zero win rate. Instead keep RSI in trigger (cross) mode and let
            # SuperTrend act as the continuous directional filter.
            # Detect ANY SuperTrend block regardless of its current mode.
            # Even when ST was already fixed to continuous mode (generate_on_trend_change=False)
            # in a prior iteration, RSI must still stay as the discrete trigger —
            # NOT switch to range mode. Using only "change mode=True" caused iteration 2
            # to flood entries: ST already fixed → _has_st_change_mode=False → RSI flipped
            # to range mode → both filters nearly always True → 200+ noisy entries.
            _has_supertrend_block = any((_b.get("type") or "").lower() == "supertrend" for _b in blocks_added)
            for _b in blocks_added:
                _btype = (_b.get("type") or "").lower()
                _bparams = _b.get("params") or {}
                _bid = _b.get("id", "")
                # SuperTrend: disable "on-change-only" → continuous trend filter.
                if _btype == "supertrend" and _bparams.get("generate_on_trend_change", False):
                    auto_fixes.append({"block_id": _bid, "params": {"generate_on_trend_change": False}})
                    logger.info(
                        f"[BuilderWorkflow] Auto-fix: block {_bid} (supertrend) "
                        "generate_on_trend_change → False (sparse signals)"
                    )
                # RSI cross-level handling depends on whether a SuperTrend filter exists:
                if _btype == "rsi" and _bparams.get("use_cross_level", False):
                    if _has_supertrend_block:
                        # SuperTrend is being fixed to continuous mode → RSI stays as
                        # the discrete trigger (use_cross_level=True).
                        # Just widen extreme cross levels so crossings happen 15–30× per period.
                        rsi_level_fix: dict[str, Any] = {}
                        _cross_l = float(_bparams.get("cross_long_level", 29))
                        _cross_s = float(_bparams.get("cross_short_level", 55))
                        if _cross_l < 35:
                            rsi_level_fix["cross_long_level"] = 40.0
                            # Config Conflict guard: cross_long_level must be >= long_rsi_more.
                            # If long_rsi_more > new cross_long_level, RSI engine detects
                            # conflict and switches to "cross-into-range" mode → very sparse
                            # signals (cross through 42 from below is rare).
                            _long_more = float(_bparams.get("long_rsi_more", 30))
                            if _long_more > 40.0:
                                rsi_level_fix["long_rsi_more"] = 35.0
                                logger.info(
                                    f"[BuilderWorkflow] Auto-fix: block {_bid} (rsi) "
                                    f"long_rsi_more → 35 (was {_long_more}, would conflict with cross_long_level=40)"
                                )
                        if _cross_s > 65:
                            rsi_level_fix["cross_short_level"] = 60.0
                            # Symmetric guard for short side
                            _short_less = float(_bparams.get("short_rsi_less", 70))
                            if _short_less < 60.0:
                                rsi_level_fix["short_rsi_less"] = 65.0
                                logger.info(
                                    f"[BuilderWorkflow] Auto-fix: block {_bid} (rsi) "
                                    f"short_rsi_less → 65 (was {_short_less}, would conflict with cross_short_level=60)"
                                )
                        if rsi_level_fix:
                            auto_fixes.append({"block_id": _bid, "params": rsi_level_fix})
                            logger.info(
                                f"[BuilderWorkflow] Auto-fix: block {_bid} (rsi) "
                                f"widened cross levels → {rsi_level_fix} "
                                "(SuperTrend present → RSI stays in cross-trigger mode)"
                            )
                    else:
                        # No SuperTrend counterpart — switch RSI to range mode.
                        auto_fixes.append({"block_id": _bid, "params": {"use_cross_level": False}})
                        logger.info(
                            f"[BuilderWorkflow] Auto-fix: block {_bid} (rsi) "
                            "use_cross_level → False (no SuperTrend filter, switching to range mode)"
                        )
            if auto_fixes:
                self._emit_agent_log(
                    agent="system",
                    role="optimizer",
                    prompt="Sparse signal auto-fix",
                    response=(
                        f"🔧 Auto-fixed {len(auto_fixes)} sparse-signal boolean params "
                        f"({_adj_trades} trades detected):\n"
                        + "\n".join(f"  • {f['block_id']}: {f['params']}" for f in auto_fixes)
                    ),
                    title=f"🔧 Auto-fix: sparse signal params ({_adj_trades} trades)",
                )
                return auto_fixes
        # =========================================================================

        # Include ALL blocks in the summary — never filter by params presence,
        # because logic gates / buy / sell blocks without params are still
        # important for the agent to understand the graph structure.
        blocks_summary = [
            {"id": b.get("id"), "type": b.get("type"), "params": b.get("params") or {}} for b in blocks_added
        ]

        # Build a human-readable graph description for the agent prompt
        graph_description = self._describe_graph_for_agents(
            blocks=blocks_added,
            connections=connections or self._result.connections_made or [],
        )

        win_rate = metrics.get("win_rate", 0)
        # Normalise — API returns percentage (52.11) not fraction (0.52)
        if win_rate > 1:
            win_rate = win_rate / 100.0

        # List only the tunable blocks (those with non-empty params) for the
        # adjustment section — purely to help agents focus their output.
        tunable_blocks = [b for b in blocks_summary if b.get("params")]
        tunable_json = json.dumps(tunable_blocks, indent=2)

        # Build iteration history section for the prompt
        _history_section = ""
        if iterations_history:
            _history_section = "\n══════════════════════════════════════════════════════════════\nITERATION HISTORY (avoid repeating failed configurations)\n══════════════════════════════════════════════════════════════\n"
            for _rec in iterations_history:
                _status = "✅ ACCEPTABLE" if _rec.get("acceptable") else "❌ not acceptable"
                _history_section += (
                    f"• Iter {_rec.get('iteration', '?')}: "
                    f"Sharpe={_rec.get('sharpe_ratio', 0):.3f}, "
                    f"Trades={_rec.get('total_trades', 0)}, "
                    f"WR={(_rec.get('win_rate', 0) * 100):.1f}%, "
                    f"DD={abs(_rec.get('max_drawdown', 0)):.1f}%  {_status}\n"
                )

        # Build warnings section
        _warnings_section = ""
        if backtest_warnings:
            _warnings_section = "\n══════════════════════════════════════════════════════════════\nBACKTEST WARNINGS (engine-detected issues — fix these!)\n══════════════════════════════════════════════════════════════\n"
            for _w in backtest_warnings:
                _warnings_section += f"⚠️  {_w}\n"
            if any("DIRECTION_MISMATCH" in w for w in backtest_warnings):
                _warnings_section += "→ DIRECTION_MISMATCH: strategy is configured for direction='both' but only one side has signals.\n   Check that entry_long AND entry_short connections both receive signals.\n"

        # Build long/short breakdown
        _long_trades = metrics.get("long_trades", metrics.get("total_trades", 0))
        _short_trades = metrics.get("short_trades", 0)
        _ls_section = ""
        if _long_trades is not None or _short_trades is not None:
            _ls_section = f"\n• Long Trades   : {_long_trades}  |  Short Trades: {_short_trades}"
            if _short_trades == 0 and _long_trades > 0:
                _ls_section += "  ← ⚠️ DIRECTION MISMATCH: zero short trades despite direction='both'. entry_short signals may be missing."

        _delib_section = ""
        if deliberation_plan:
            _delib_section = (
                f"\n══════════════════════════════════════════════════════════════\n"
                f"PRE-RUN MULTI-AGENT CONSENSUS PLAN (agreed before iterations started)\n"
                f"══════════════════════════════════════════════════════════════\n"
                f"{deliberation_plan}\n"
                f"→ Your parameter adjustments MUST be consistent with this plan.\n"
                f"  If iterations have diverged from it, steer back toward it.\n"
            )

        prompt = f"""You are a quantitative strategy parameter optimizer and part of a MULTI-AGENT system.
Other AI agents (DeepSeek, Qwen, Claude) are independently analyzing the same strategy.
Your suggestions will be merged with theirs — propose well-reasoned, evidence-based changes.
{_history_section}{_warnings_section}{_delib_section}
══════════════════════════════════════════════════════════════
HOW THE VISUAL STRATEGY BUILDER WORKS
══════════════════════════════════════════════════════════════
The strategy is a VISUAL NODE GRAPH — a set of typed blocks connected
by ports.  Signal flows left-to-right:

  PRICE → INDICATOR(s) → CONDITION(s) / LOGIC GATE(s) → ACTION(s) → STRATEGY

• Indicator blocks (rsi, ema, macd, cci, mfi, supertrend, …) read price
  data and output numeric values or boolean long_signal/short_signal.
• Condition blocks (crossover, greater_than, …) compare inputs and output
  True/False.
• Logic gate blocks (and, or, not) combine boolean signals — they do NOT
  generate new signals, they only filter/combine existing ones.
• Action blocks (buy, sell, close_long, …) trigger trade entries/exits.
• The STRATEGY node is the final aggregator — receives entry_long,
  entry_short, exit_long, exit_short signals and drives the backtester.
• Risk blocks (static_sltp, atr_sltp) set Stop-Loss and Take-Profit.

══════════════════════════════════════════════════════════════
CURRENT STRATEGY GRAPH (existing — DO NOT CHANGE STRUCTURE)
══════════════════════════════════════════════════════════════
{graph_description}

══════════════════════════════════════════════════════════════
LAST BACKTEST RESULTS (iteration {iteration})
══════════════════════════════════════════════════════════════
• Sharpe Ratio  : {metrics.get("sharpe_ratio", 0):.3f}
• Win Rate      : {win_rate:.1%}
• Max Drawdown  : {abs(metrics.get("max_drawdown_pct", 0)):.1f}%
• Net Profit    : {metrics.get("net_profit", 0):.2f} {"✅ profitable" if metrics.get("net_profit", 0) > 0 else "❌ LOSING MONEY — must fix"}
• Total Trades  : {metrics.get("total_trades", 0)}{"  ← ⛔ CRITICAL: near-zero. Entry logic is broken — must widen conditions drastically" if metrics.get("total_trades", 0) < 5 else ("  ← ⚠️ TOO FEW: target ≥2/day. Loosen AND→OR, disable on-change-only signals, raise cross levels" if metrics.get("total_trades", 0) < 20 else ("  ← too many, reduce signal frequency" if metrics.get("total_trades", 0) > 300 else ""))}{_ls_section}

══════════════════════════════════════════════════════════════
TUNABLE BLOCKS (only these have adjustable parameters)
══════════════════════════════════════════════════════════════
{tunable_json}

══════════════════════════════════════════════════════════════
YOUR TASK
══════════════════════════════════════════════════════════════
Suggest PARAMETER VALUE changes to improve Net Profit and Sharpe Ratio.

ABSOLUTE CONSTRAINTS — violating these will break the strategy:
1. ❌ Do NOT add any new blocks.
2. ❌ Do NOT remove any blocks.
3. ❌ Do NOT change any connections between blocks.
4. ❌ Do NOT suggest changes to buy/sell/logic/strategy/price blocks (they have no params).
5. ✅ Only change numeric parameter values of indicator and risk-management blocks.

PROFITABILITY RULES:
• Net Profit < 0 → change parameters SIGNIFICANTLY (strategy is losing money).
• static_sltp: take_profit_percent MUST be >= 2x stop_loss_percent.
• Total Trades > 200 → widen indicator thresholds or increase periods to reduce noise.
• Win Rate < 40% → tighten entry conditions (RSI: raise overbought, lower oversold).
• Max Drawdown > 30% → tighten stop_loss_percent.
• If already profitable and Sharpe ≥ 1.0 → return empty array [].

OUTPUT FORMAT — return ONLY a JSON array, no explanation:
[{{"block_id": "exact_block_id_here", "params": {{"param_name": new_value}}}}]

Use the exact block IDs from the TUNABLE BLOCKS list above.
Only include blocks that need changes.
Only include the specific parameters that should change."""

        # ── Try multi-agent consensus first (A2A parallel) ────────────────────
        try:
            import os

            from backend.agents.models import AgentType

            a2a = _get_a2a_communicator()

            # Only use Claude + Perplexity
            available_agents = []
            if os.environ.get("ANTHROPIC_API_KEY"):
                available_agents.append(AgentType.CLAUDE)
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
            logger.warning(f"[BuilderWorkflow] A2A consensus failed ({a2a_err}), falling back to single LLM")

        # ── Single-agent fallback (uses config.agent set at run() start) ──────
        try:
            from backend.agents.unified_agent_interface import UnifiedAgentInterface

            _agent_name = getattr(self, "_primary_agent", "claude")
            _interface = UnifiedAgentInterface()
            raw_text_fallback: str = await _interface.ask(_agent_name, prompt) or ""

            # Emit agent log for the single-agent fallback
            self._emit_agent_log(
                agent=_agent_name,
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
                f"[BuilderWorkflow] 🤖 {_agent_name} suggested {len(adjustments)} adjustments (iteration {iteration})"
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

    async def _suggest_param_ranges(
        self,
        blocks_added: list[dict[str, Any]],
        iteration: int,
        metrics: dict[str, Any],
        connections: list[dict[str, Any]] | None = None,
        backtest_warnings: list[str] | None = None,
        iterations_history: list[dict[str, Any]] | None = None,
        deliberation_plan: str | None = None,
        previous_ranges: list[dict[str, Any]] | None = None,
        previous_best_params: dict[str, Any] | None = None,
        previous_opt_score: float | None = None,
        current_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Use agents to suggest parameter RANGES (min/max/step) for optimizer sweep.

        Instead of suggesting a single value, each agent proposes a narrow sweep
        range for the most impactful parameters.  The ranges from all agents are
        merged (intersection) by ``_merge_agent_ranges()``.

        Returns:
            List of ``{"block_id": ..., "ranges": {"param": {"min", "max", "step", "type"}}}``
        """
        from backend.optimization.builder_optimizer import DEFAULT_PARAM_RANGES

        graph_description = self._describe_graph_for_agents(
            blocks=blocks_added,
            connections=connections or self._result.connections_made or [],
        )

        # Build set of connected block IDs — disconnected blocks don't affect backtest
        _conns_for_filter = connections or self._result.connections_made or []
        _connected_ids_for_ranges: set[str] = set()
        for _c in _conns_for_filter:
            _src = _c.get("source") or {}
            _tgt = _c.get("target") or {}
            _raw_sid = _src.get("blockId") if isinstance(_src, dict) else None
            _raw_sid = _raw_sid or _c.get("source_block_id", "")
            _raw_tid = _tgt.get("blockId") if isinstance(_tgt, dict) else None
            _raw_tid = _raw_tid or _c.get("target_block_id", "")
            # Guard: source_block_id may be a nested dict if frontend sends {blockId, portId}
            _sid = _raw_sid.get("blockId", "") if isinstance(_raw_sid, dict) else (_raw_sid or "")
            _tid = _raw_tid.get("blockId", "") if isinstance(_raw_tid, dict) else (_raw_tid or "")
            if isinstance(_sid, str) and _sid:
                _connected_ids_for_ranges.add(_sid)
            if isinstance(_tid, str) and _tid:
                _connected_ids_for_ranges.add(_tid)

        # Build per-block available-ranges hint for the prompt
        # Only include CONNECTED blocks — disconnected blocks waste LLM tokens and
        # Optuna trial budget on parameters that have zero effect on backtest results.
        available_ranges: dict[str, Any] = {}
        for block in blocks_added:
            bt = block.get("type", "").lower()
            bid = block.get("id", bt)
            if bt == "strategy":
                continue  # strategy node has no optimizable params
            # Skip disconnected blocks
            if _connected_ids_for_ranges and bid not in _connected_ids_for_ranges:
                logger.debug(
                    f"[_suggest_param_ranges] Skipping disconnected block '{bid}' (type='{bt}') "
                    "from available_ranges — not in any connection"
                )
                continue
            if bt in DEFAULT_PARAM_RANGES:
                available_ranges[bid] = {
                    "type": bt,
                    "current_params": block.get("params", {}),
                    "optimizable": DEFAULT_PARAM_RANGES[bt],
                }

        win_rate = metrics.get("win_rate", 0)
        if win_rate > 1:
            win_rate /= 100.0
        sharpe = metrics.get("sharpe_ratio", 0)
        net_profit = metrics.get("net_profit", 0)
        max_dd = metrics.get("max_drawdown_pct", metrics.get("max_drawdown", 0))
        total_trades = int(metrics.get("total_trades", 0))

        # Build a clear trades warning — agents MUST know if signal frequency is broken
        if total_trades < 5:
            trades_note = (
                f"{total_trades}  ⛔ CRITICAL: near-zero trades. "
                "Parameter tuning CANNOT fix this. The entry signal conditions are completely broken. "
                "Widen them drastically: remove AND gates, disable 'generate_on_trend_change', "
                "use a simpler single-indicator entry."
            )
        elif total_trades < 20:
            trades_note = (
                f"{total_trades}  ⚠️ TOO FEW: target ≥ 2 trades/day for this timeframe. "
                "Signal conditions are too restrictive — the priority is MORE trades, not better Sharpe. "
                "Widen: raise RSI cross level, disable on-change-only SuperTrend, loosen AND to OR."
            )
        else:
            trades_note = str(total_trades)

        # Build iteration history so agents don't repeat what didn't work
        _history_lines = ""
        if self._result.iterations:
            _history_lines = "\n## Previous iteration results (avoid repeating what failed)\n"
            for _rec in self._result.iterations:
                _status = "✅ acceptable" if _rec.get("acceptable") else "❌ not acceptable"
                _history_lines += (
                    f"- Iter {_rec['iteration']}: Sharpe={_rec.get('sharpe_ratio', 0):.3f}, "
                    f"WR={_rec.get('win_rate', 0) * 100:.1f}%, "
                    f"Trades={_rec.get('total_trades', 0)}, "
                    f"DD={_rec.get('max_drawdown', 0):.1f}%, "
                    f"Score={_rec.get('primary_score', 0):.3f} {_status}\n"
                )
            _history_lines += (
                "Use this history to guide your range proposals: if a previous iteration "
                "already explored a region with poor results, shift the ranges to unexplored territory.\n"
            )

        # Memory recall from previous successful runs (cross-session learning)
        _memory_context_ranges = ""
        try:
            _mem = _get_workflow_memory()
            _past = await _mem.recall(
                query=f"{self._config_symbol if hasattr(self, '_config_symbol') else ''} "
                f"optimizer best params {total_trades} trades",
                top_k=2,
                min_importance=0.55,
            )
            if _past:
                _memory_context_ranges = "\n## Past successful configurations (from memory)\n"
                for _p in _past:
                    _memory_context_ranges += f"- {_p.content}\n"
        except Exception:
            pass  # memory unavailable — continue without

        # Long/short breakdown for direction mismatch awareness
        _long_tr = metrics.get("long_trades", total_trades)
        _short_tr = metrics.get("short_trades", 0)
        _ls_note = f"\n- Long Trades: {_long_tr}  |  Short Trades: {_short_tr}"
        if _short_tr == 0 and _long_tr > 0:
            _ls_note += "  ← DIRECTION MISMATCH: zero short trades. entry_short port receives no signal."

        # Deliberation plan section
        _delib_ranges = ""
        if deliberation_plan:
            _delib_ranges = (
                f"\n## Pre-run multi-agent consensus plan (follow this when proposing ranges)\n"
                f"{deliberation_plan}\n"
                f"→ Align your range proposals with the above plan. "
                f"The plan was agreed before any iterations ran — steer toward it.\n"
            )

        # Backtest warnings section
        _warn_ranges = ""
        if backtest_warnings:
            _warn_ranges = "\n## Backtest warnings\n"
            for _w in backtest_warnings:
                _warn_ranges += f"- {_w}\n"

        # External iteration history override (if caller passes it)
        if iterations_history:
            _history_lines = "\n## Previous iteration results (avoid repeating what failed)\n"
            for _rec in iterations_history:
                _status = "✅ acceptable" if _rec.get("acceptable") else "❌ not acceptable"
                _history_lines += (
                    f"- Iter {_rec['iteration']}: Sharpe={_rec.get('sharpe_ratio', 0):.3f}, "
                    f"WR={_rec.get('win_rate', 0) * 100:.1f}%, "
                    f"Trades={_rec.get('total_trades', 0)}, "
                    f"DD={_rec.get('max_drawdown', 0):.1f}%, "
                    f"Score={_rec.get('primary_score', 0):.3f} {_status}\n"
                )
            _history_lines += (
                "Use this history to guide your range proposals: if a previous iteration "
                "already explored a region with poor results, shift the ranges to unexplored territory.\n"
            )

        # ── Hypothesis refinement context from previous iteration ────────────
        # Agents receive: what ranges were swept last time, what params the
        # optimizer found, and what score resulted.  They should use this to
        # NARROW ranges around confirmed-good regions, SHIFT away from
        # confirmed-bad regions, or WIDEN if the optimizer got stuck.
        _hypothesis_section = ""
        if previous_ranges is not None:
            _prev_ranges_summary = json.dumps(
                {item["block_id"]: item.get("ranges", {}) for item in (previous_ranges or [])},
                indent=2,
            )
            _hypothesis_section = "\n## HYPOTHESIS REFINEMENT (previous iteration findings)\n"
            _hypothesis_section += (
                "The previous iteration ran an optimizer sweep over these ranges:\n"
                f"```json\n{_prev_ranges_summary}\n```\n"
            )
            if previous_best_params:
                _best_str = json.dumps(previous_best_params, indent=2)
                _score_str = f"{previous_opt_score:.4f}" if previous_opt_score is not None else "N/A"
                _hypothesis_section += f"Optimizer found best params (score={_score_str}):\n```json\n{_best_str}\n```\n"
                if previous_opt_score is not None and previous_opt_score > current_score:
                    _hypothesis_section += (
                        "→ The optimizer IMPROVED the score. NARROW your ranges around the best params above "
                        "(±20-30% of each value) to drill deeper into this region with finer steps.\n"
                    )
                else:
                    _hypothesis_section += (
                        "→ The optimizer did NOT improve vs baseline. SHIFT your ranges: "
                        "try a DIFFERENT region (e.g. slower/faster indicator period, higher/lower threshold). "
                        "Do NOT repeat the same ranges — they were already explored.\n"
                    )
            else:
                _hypothesis_section += (
                    "→ Optimizer found NO valid params in those ranges (all trials pruned/NaN). "
                    "The proposed ranges are likely producing zero trades or invalid combinations. "
                    "Propose COMPLETELY DIFFERENT ranges — especially widen signal thresholds "
                    "(e.g. lower RSI cross_short_level, raise cross_long_level, disable AND gates).\n"
                )
            _hypothesis_section += "\n"

        prompt = f"""You are part of a MULTI-AGENT system optimizing a visual block-based trading strategy.
Other AI agents (DeepSeek, Qwen, Claude) propose ranges independently — yours will be MERGED with theirs.
Propose WIDE, well-reasoned ranges focused on fixing the biggest problem first.
The Bayesian optimizer (Optuna TPE) handles LARGE parameter spaces efficiently — use WIDE ranges and FINE steps.
{_hypothesis_section}{_history_lines}{_memory_context_ranges}{_delib_ranges}{_warn_ranges}
## Current backtest results
- Sharpe Ratio: {sharpe:.3f}
- Win Rate: {win_rate * 100:.1f}%
- Net Profit: ${net_profit:.2f}
- Max Drawdown: {max_dd:.2f}%
- Total Trades: {trades_note}{_ls_note}
- Iteration: {iteration}

## Strategy block graph (full topology)
{graph_description}

## Blocks currently in THIS strategy (optimizable, connected)
{json.dumps(available_ranges, indent=2)}

{self._build_block_catalog()}
## Your task
Return PARAMETER RANGES for the Bayesian optimizer to sweep.
Focus on blocks already in the strategy above. If a block type above has no entry in the strategy yet,
you may propose adding it via topology changes in a separate step — not here.

**CRITICAL RULES:**
1. **Include EVERY CONNECTED indicator and exit block** shown in the list above — do NOT skip them.
   Each connected block must appear as a separate entry in the output JSON array.
   Disconnected blocks are NOT shown above — do not invent block IDs not in the list.
2. **Range width:** If HYPOTHESIS REFINEMENT section above is present, follow its instructions
   (narrow/shift/widen) — they take priority. Otherwise use the FULL allowed range for first
   iteration so the optimizer can discover the best region.
3. **Use fine steps** (step=1 for integers, step=0.1–0.5 for floats) for high precision.
4. **RSI period range: 7 to 100.** Slow RSI (period 50-100) often outperforms on 30m+ TFs.
   The Bayesian optimizer explores efficiently — suggest the FULL range 7-100.
5. **RSI cross_long_level: explore full range 15-85 (step=1).**
   IMPORTANT: cross_long_level < long_rsi_more is VALID — the engine uses a conflict-resolution
   path that fires an extended-cross signal when RSI enters the range from below. Do NOT avoid
   this region — it is where many best configs live.
6. **static_sltp block is the most powerful lever.** ALWAYS include it with wide ranges:
   stop_loss_percent min=0.5 max=20.0 step=0.25, take_profit_percent min=0.5 max=20.0 step=0.25.
   breakeven_activation_percent min=0.1 max=5.0 step=0.1.
   Include both tight (1-2%) and wide (5-15%) SL/TP values to explore all risk/reward profiles.
7. **close_by_time interaction (CRITICAL if close_by_time block is present):**
   min_profit_percent MUST be >= take_profit_percent + 2.0. This ensures TP fires FIRST.
   Use min_profit range: [TP_min + 2.0, 25.0] step=0.5 — do NOT start from 0.
8. If strategy already meets targets (Sharpe >= 1.5, Net Profit > 0, Trades >= 30), return [].

## Output format (JSON array only, no markdown, no explanation)
[
  {{
    "block_id": "exact_block_id_from_list_above",
    "ranges": {{
      "param_name": {{"min": 10, "max": 50, "step": 1, "type": "int"}},
      "param_name2": {{"min": 0.5, "max": 15.0, "step": 0.25, "type": "float"}}
    }}
  }},
  {{
    "block_id": "another_block_id",
    "ranges": {{
      "another_param": {{"min": 30, "max": 75, "step": 1, "type": "float"}}
    }}
  }}
]
"""

        # ── Try multi-agent consensus (A2A) ──────────────────────────────────
        try:
            import os

            from backend.agents.models import AgentType

            a2a = _get_a2a_communicator()
            available_agents = []
            if os.environ.get("ANTHROPIC_API_KEY"):
                available_agents.append(AgentType.CLAUDE)
            if os.environ.get("PERPLEXITY_API_KEY"):
                available_agents.append(AgentType.PERPLEXITY)

            if len(available_agents) >= 2:
                logger.info(
                    f"[BuilderWorkflow] 🤝 A2A range consensus: "
                    f"{[a.value for a in available_agents]} (iteration {iteration})"
                )
                consensus_result = await a2a.parallel_consensus(
                    question=prompt,
                    agents=available_agents,
                    context={
                        "task": "param_ranges",
                        "iteration": iteration,
                        "require_json_array": True,
                    },
                )
                # Collect all per-agent JSON arrays
                all_responses: list[dict[str, Any]] = []
                for resp in consensus_result.get("individual_responses", []):
                    agent_name = resp.get("agent", "unknown")
                    agent_text = resp.get("content", "")
                    self._emit_agent_log(
                        agent=agent_name,
                        role="optimizer",
                        prompt=prompt,
                        response=agent_text,
                        title=f"🎯 Param Ranges — iteration {iteration}",
                    )
                    all_responses.append({"agent": agent_name, "response": agent_text})

                merged = self._merge_agent_ranges(all_responses)
                if merged:
                    logger.info(f"[BuilderWorkflow] 🤝 A2A range consensus: {len(merged)} block(s)")
                    return merged
                logger.info("[BuilderWorkflow] A2A range consensus empty — falling back to single LLM")

        except Exception as a2a_err:
            logger.warning(f"[BuilderWorkflow] A2A range consensus failed ({a2a_err}), falling back")

        # ── Single-agent fallback (uses config.agent set at run() start) ──────
        try:
            from backend.agents.unified_agent_interface import UnifiedAgentInterface

            _agent_name = getattr(self, "_primary_agent", "claude")
            _interface = UnifiedAgentInterface()
            raw_text: str = await _interface.ask(_agent_name, prompt) or ""
            self._emit_agent_log(
                agent=_agent_name,
                role="optimizer",
                prompt=prompt,
                response=raw_text,
                title=f"🎯 Param Ranges — iteration {iteration} (fallback)",
            )
            arr_match = re.search(r"\[.*?\]", raw_text, re.DOTALL)
            if arr_match:
                try:
                    parsed = json.loads(arr_match.group())
                    return parsed if isinstance(parsed, list) else []
                except json.JSONDecodeError:
                    pass
            return []

        except Exception as e:
            logger.warning(f"[BuilderWorkflow] All range suggestions failed: {e}")
            return []

    def _merge_agent_ranges(
        self,
        responses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge range suggestions from multiple agents.

        For each block+param: use the tightest common window
        (max of mins, min of maxima, min of steps) so the sweep stays
        focused even when agents disagree slightly.

        Args:
            responses: List of ``{"agent": ..., "response": "<json text>"}`` dicts.

        Returns:
            Merged list of ``{"block_id": ..., "ranges": {...}}`` items.
        """
        all_suggestions: list[list[dict[str, Any]]] = []
        for r in responses:
            text = r.get("response", "") if isinstance(r, dict) else str(r)
            arr_m = re.search(r"\[.*?\]", text, re.DOTALL)
            if arr_m:
                try:
                    parsed = json.loads(arr_m.group())
                    if isinstance(parsed, list) and parsed:
                        all_suggestions.append(parsed)
                except json.JSONDecodeError:
                    pass

        if not all_suggestions:
            return []
        if len(all_suggestions) == 1:
            return all_suggestions[0]

        # Index: {block_id: {param: [range_dict, ...]}}
        index: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for suggestion_list in all_suggestions:
            for item in suggestion_list:
                bid = item.get("block_id")
                ranges = item.get("ranges", {})
                if not bid or not ranges:
                    continue
                index.setdefault(bid, {})
                for param, rng in ranges.items():
                    if isinstance(rng, dict):
                        index[bid].setdefault(param, []).append(rng)

        # Merge: WIDEST window per param (union, not intersection).
        # Previous behavior (intersection) narrowed ranges when agents disagreed,
        # defeating the purpose of wide-range Bayesian optimization.
        merged: list[dict[str, Any]] = []
        for bid, params in index.items():
            block_ranges: dict[str, Any] = {}
            for param, agent_ranges in params.items():
                if len(agent_ranges) == 1:
                    block_ranges[param] = agent_ranges[0]
                    continue
                # Take the widest window across all agents + finest step
                lo = min(r.get("min", 1) for r in agent_ranges)
                hi = max(r.get("max", 100) for r in agent_ranges)
                st = min(r.get("step", 1) for r in agent_ranges)
                block_ranges[param] = {
                    "min": lo,
                    "max": hi,
                    "step": st,
                    "type": agent_ranges[0].get("type", "int"),
                }
            if block_ranges:
                merged.append({"block_id": bid, "ranges": block_ranges})
        return merged

    # =========================================================================
    # TOPOLOGY INTELLIGENCE — agents can restructure the graph, not just tune
    # =========================================================================

    async def _suggest_topology_changes(
        self,
        blocks: list[dict[str, Any]],
        connections: list[dict[str, Any]],
        metrics: dict[str, Any],
        iteration: int,
        iterations_history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Ask agents to propose STRUCTURAL changes to the strategy graph.

        Unlike ``_suggest_param_ranges`` which only tunes parameter values,
        this method lets agents restructure the graph:

        * **disconnect** — remove a wire (e.g. remove OR-gate noise source)
        * **reconnect** — change a port (entry_long → filter_long)
        * **add_block** — add a new indicator/filter block with connections
        * **remove_block** — delete a block that is hurting performance

        Returns:
            List of topology change dicts, each with ``"action"`` key.
            Empty list = no structural changes proposed.

        Supported actions::

            {"action": "disconnect",
             "connection_id": "conn_abc123",
             "reason": "Supertrend OR-gate fires every bar → 200+ trades"}

            {"action": "reconnect",
             "connection_id": "conn_abc123",
             "new_target_port": "filter_long",
             "reason": "Use Supertrend as AND-filter, not entry signal"}

            {"action": "remove_block",
             "block_id": "supertrend_1",
             "reason": "Block is not connected — dead weight"}

            {"action": "add_block",
             "block_type": "adx",
             "params": {"period": 14, "threshold": 25},
             "connect_from_port": "long",
             "connect_to_block_id": "strategy_node",
             "connect_to_port": "filter_long",
             "reason": "ADX filter reduces false entries in ranging market"}
        """
        # Build a human-readable graph description with connection IDs
        graph_lines = ["## Current strategy graph (blocks + wires)\n"]
        block_by_id: dict[str, dict[str, Any]] = {b.get("id", ""): b for b in blocks}
        for b in blocks:
            bt = b.get("type", "?")
            bid = b.get("id", "?")
            params = b.get("params", {})
            graph_lines.append(f"  Block [{bid}] type={bt} params={json.dumps(params)}")

        graph_lines.append("\n  Connections (connection_id → source_block:port → target_block:port):")
        for c in connections:
            cid = c.get("id", "?")
            src = c.get("source", {})
            tgt = c.get("target", {})
            src_bid = src.get("blockId", c.get("source_block_id", "?"))
            src_port = src.get("portId", c.get("source_port", "?"))
            tgt_bid = tgt.get("blockId", c.get("target_block_id", "?"))
            tgt_port = tgt.get("portId", c.get("target_port", "?"))
            src_type = block_by_id.get(src_bid, {}).get("type", "?")
            tgt_type = block_by_id.get(tgt_bid, {}).get("type", "?")
            graph_lines.append(f"    [{cid}] {src_type}({src_bid}):{src_port} → {tgt_type}({tgt_bid}):{tgt_port}")
        graph_description = "\n".join(graph_lines)

        win_rate = metrics.get("win_rate", 0)
        if win_rate > 1:
            win_rate /= 100.0
        sharpe = metrics.get("sharpe_ratio", 0)
        total_trades = int(metrics.get("total_trades", 0))
        max_dd = metrics.get("max_drawdown_pct", metrics.get("max_drawdown", 0))
        net_profit = metrics.get("net_profit", 0)

        # Build iteration history
        _hist = ""
        if iterations_history:
            _hist = "\n## Iteration history\n"
            for rec in iterations_history:
                _hist += (
                    f"  Iter {rec['iteration']}: Sharpe={rec.get('sharpe_ratio', 0):.3f}, "
                    f"Trades={rec.get('total_trades', 0)}, WR={rec.get('win_rate', 0) * 100:.1f}%, "
                    f"DD={rec.get('max_drawdown', 0):.1f}%\n"
                )

        # Detect known problematic patterns for the prompt
        _diagnoses = []
        if total_trades > 100 and win_rate < 0.40:
            _diagnoses.append(
                "⛔ OVER-TRADING: >100 trades with low WR. "
                "Likely cause: an indicator in OR-gate fires EVERY BAR (e.g. Supertrend with "
                "generate_on_trend_change=False connected to entry_long via OR). "
                "Fix: disconnect that block from entry port OR reconnect it to filter_long port."
            )
        if 5 <= total_trades < 20:
            _diagnoses.append(
                "⛔ TOO FEW TRADES (5–19): Strategy is OVER-FILTERED — AND-gate blocks are "
                "preventing entry signals. DO NOT add any more filter blocks. "
                "Fix: disconnect one filter_long connection (move it to entry_long) or "
                "remove a filter block entirely. Look for blocks connected to filter_long "
                "and disconnect the most restrictive one."
            )
        if total_trades < 5:
            _diagnoses.append(
                "⛔ UNDER-TRADING: <5 trades. "
                "Likely cause: AND-gate with conflicting conditions (e.g. RSI AND Supertrend never "
                "fire simultaneously). Fix: disconnect one filter_long connection or remove a filter block."
            )
        if sharpe < -0.3 and total_trades > 50:
            _diagnoses.append(
                "⛔ NEGATIVE SHARPE with many trades. "
                "Strategy is losing money consistently. "
                "Consider: removing a noisy indicator, adding an ADX/trend filter, "
                "or changing entry_long connections to filter_long."
            )

        # Detect declining-trades pattern across iterations (progressive over-filtering)
        if iterations_history and len(iterations_history) >= 2:
            prev_trades = iterations_history[-1].get("total_trades", 0)
            prev2_trades = (
                iterations_history[-2].get("total_trades", 0) if len(iterations_history) >= 2 else prev_trades
            )
            if total_trades < prev_trades < prev2_trades and total_trades < 30:
                _diagnoses.append(
                    "⛔ PROGRESSIVE OVER-FILTERING DETECTED: Trades are declining each iteration "
                    f"({prev2_trades} → {prev_trades} → {total_trades}). "
                    "Adding more filters is making the strategy worse! "
                    "MANDATORY: return [] (no topology changes) — let the parameter optimizer work instead. "
                    "Or remove/disconnect one existing filter_long block."
                )

        _diag_text = "\n".join(_diagnoses) if _diagnoses else "No obvious structural problems detected."

        block_catalog = self._build_block_catalog()

        prompt = f"""You are an expert trading strategy architect analyzing a visual block-based strategy graph.
Your task: propose STRUCTURAL changes to fix fundamental problems that parameter tuning CANNOT solve.

{block_catalog}
{_hist}
## Current backtest metrics (iteration {iteration})
- Sharpe: {sharpe:.3f}
- Win Rate: {win_rate * 100:.1f}%
- Total Trades: {total_trades}
- Max Drawdown: {max_dd:.1f}%
- Net Profit: ${net_profit:.2f}

## Automated diagnosis
{_diag_text}

{graph_description}

## Port semantics (CRITICAL — use exact port names)
- entry_long / entry_short → fires a TRADE on this bar. OR-gate: ANY connected block fires → trade.
- filter_long / filter_short → AND-gate: ALL connected filters must pass → trade.
- sl_tp → stop-loss / take-profit exit block port.
- Supertrend with generate_on_trend_change=False fires signal EVERY BAR while trend is active.
  Connected to entry_long → creates hundreds of trades. Fix: reconnect to filter_long.

## Available actions
1. disconnect: remove a wire by connection_id
2. reconnect: keep the wire but change its target port
3. remove_block: delete a block (also removes its connections)
4. add_block: add a new block with connections

## Rules
1. Only propose changes that fix the root cause shown in the diagnosis.
2. If metrics are acceptable (Sharpe > 1.0, Trades ≥ 20, WR ≥ 40%), return [].
3. Maximum 2 topology changes per iteration — don't restructure everything at once.
4. Prefer reconnect over remove_block — keep blocks, just change how they wire.
5. Never remove the strategy node or static_sltp exit block.
6. Always provide a "reason" for each change — it will be logged.
7. ⛔ CRITICAL: If Total Trades < 20, NEVER add filter blocks (add_block with connect_to_port="filter_long"). The strategy is already too restrictive. Adding more filters will kill remaining signals.
8. ⛔ CRITICAL: If diagnosis says "PROGRESSIVE OVER-FILTERING", return [] immediately — no changes.

## Output format (JSON array only, no markdown, no explanation)
[
  {{
    "action": "disconnect",
    "connection_id": "exact_conn_id_from_graph_above",
    "reason": "one-line diagnosis"
  }},
  {{
    "action": "reconnect",
    "connection_id": "exact_conn_id_from_graph_above",
    "new_source_block_id": "...",
    "new_source_port": "...",
    "new_target_block_id": "...",
    "new_target_port": "filter_long",
    "reason": "one-line diagnosis"
  }},
  {{
    "action": "remove_block",
    "block_id": "exact_block_id_from_graph_above",
    "reason": "one-line diagnosis"
  }},
  {{
    "action": "add_block",
    "block_type": "adx",
    "params": {{"period": 14, "threshold": 25}},
    "connect_from_port": "long",
    "connect_to_block_id": "strategy_node",
    "connect_to_port": "filter_long",
    "reason": "one-line diagnosis"
  }}
]
"""
        # Ask agents via parallel_consensus (same API as _suggest_param_ranges).
        # Claude + Perplexity both see the full catalog and vote on topology changes.
        # We pick the first non-empty JSON array from the individual responses.
        try:
            import os

            from backend.agents.agent_to_agent_communicator import AgentToAgentCommunicator
            from backend.agents.models import AgentType

            a2a: AgentToAgentCommunicator = _get_a2a_communicator()
            available_agents = []
            if os.environ.get("ANTHROPIC_API_KEY"):
                available_agents.append(AgentType.CLAUDE)
            if os.environ.get("PERPLEXITY_API_KEY"):
                available_agents.append(AgentType.PERPLEXITY)
            if not available_agents:
                logger.warning("[BuilderWorkflow] No API keys for topology agent — skipping")
                return []

            consensus = await asyncio.wait_for(
                a2a.parallel_consensus(
                    question=prompt,
                    agents=available_agents,
                    context={"task": "topology_analysis", "json_mode": True},
                ),
                timeout=90.0,
            )
            # Pick first individual response that contains a valid JSON array
            raw_text = ""
            for resp in consensus.get("individual_responses", []):
                candidate = resp.get("content", "").strip()
                if "[" in candidate and "]" in candidate:
                    raw_text = candidate
                    break
            if not raw_text:
                raw_text = consensus.get("consensus", "")
        except TimeoutError:
            logger.warning("[BuilderWorkflow] Topology agent timed out (90s) — skipping")
            return []
        except Exception as e:
            logger.warning(f"[BuilderWorkflow] Topology agent error: {e} — skipping")
            return []

        # Parse JSON array from response
        try:
            # Strip markdown fences if present
            raw_text = re.sub(r"```(?:json)?\s*", "", raw_text).strip().strip("```").strip()
            # Extract first JSON array
            m = re.search(r"\[.*\]", raw_text, re.DOTALL)
            if not m:
                return []
            changes: list[dict[str, Any]] = json.loads(m.group(0))
            if not isinstance(changes, list):
                return []
            # Validate each change has action key
            valid = [c for c in changes if isinstance(c, dict) and "action" in c]
            logger.info(
                f"[BuilderWorkflow] 🏗️ Topology agent proposed {len(valid)} change(s): {[c['action'] for c in valid]}"
            )
            return valid
        except Exception as e:
            logger.warning(f"[BuilderWorkflow] Could not parse topology response: {e}")
            return []

    async def _apply_topology_changes(
        self,
        strategy_id: str,
        changes: list[dict[str, Any]],
        current_connections: list[dict[str, Any]],
        current_metrics: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply topology changes proposed by ``_suggest_topology_changes``.

        Returns list of successfully applied changes (failed ones are skipped
        with a warning — we never abort the whole iteration for a topology error).
        """
        applied: list[dict[str, Any]] = []

        _ENTRY_PORTS = {"entry_long", "entry_short"}
        # Guard: prevent adding filter blocks when strategy already has too few trades
        _current_trades = int((current_metrics or {}).get("total_trades", 999))

        def _sim_has_entry(conns: list[dict], remove_id: str | None = None, add_port: str | None = None) -> bool:
            """Simulate whether connections still have ≥1 entry_long/short after a change."""
            remaining = [c for c in conns if c.get("id") != remove_id]
            if add_port and add_port in _ENTRY_PORTS:
                return True  # adding a new entry connection — safe
            for c in remaining:
                tgt = c.get("target", {}) or {}
                port = tgt.get("portId") or c.get("target_port", "")
                if port in _ENTRY_PORTS:
                    return True
            return False

        for change in changes:
            action = change.get("action", "")
            reason = change.get("reason", "")

            try:
                if action == "disconnect":
                    conn_id = change.get("connection_id", "")
                    if not conn_id:
                        logger.warning("[BuilderWorkflow] disconnect: missing connection_id")
                        continue
                    # Safety: refuse if this would leave no entry_long/short connections
                    if not _sim_has_entry(current_connections, remove_id=conn_id):
                        logger.warning(
                            f"[BuilderWorkflow] disconnect [{conn_id}] BLOCKED — would leave "
                            f"strategy with no entry_long/entry_short connections"
                        )
                        continue
                    result = await builder_disconnect_blocks(
                        strategy_id=strategy_id,
                        connection_id=conn_id,
                    )
                    if "error" in result:
                        logger.warning(f"[BuilderWorkflow] disconnect {conn_id}: {result['error']}")
                        continue
                    logger.info(f"[BuilderWorkflow] 🏗️ Disconnected [{conn_id}] — {reason}")
                    applied.append(change)
                    # Update local connections snapshot
                    current_connections[:] = [c for c in current_connections if c.get("id") != conn_id]

                elif action == "reconnect":
                    conn_id = change.get("connection_id", "")
                    new_src_bid = change.get("new_source_block_id")
                    new_src_port = change.get("new_source_port")
                    new_tgt_bid = change.get("new_target_block_id")
                    new_tgt_port = change.get("new_target_port")
                    # Safety: refuse if removing this connection would leave no entry_long/short
                    # (the reconnect will add a new connection to new_tgt_port, which may not be entry)
                    if conn_id and (new_tgt_port not in _ENTRY_PORTS):
                        if not _sim_has_entry(current_connections, remove_id=conn_id, add_port=new_tgt_port):
                            logger.warning(
                                f"[BuilderWorkflow] reconnect [{conn_id}] BLOCKED — moving last "
                                f"entry signal from entry_long to '{new_tgt_port}' would leave "
                                f"strategy with no entry conditions"
                            )
                            continue

                    # Step 1: remove old connection
                    if conn_id:
                        result = await builder_disconnect_blocks(
                            strategy_id=strategy_id,
                            connection_id=conn_id,
                        )
                        if "error" in result:
                            logger.warning(f"[BuilderWorkflow] reconnect: disconnect {conn_id}: {result['error']}")
                            continue
                        current_connections[:] = [c for c in current_connections if c.get("id") != conn_id]

                    # Step 2: find source/target from the original connection if not overridden
                    orig = next((c for c in self._result.connections_made or [] if c.get("id") == conn_id), {})
                    src_bid = new_src_bid or orig.get("source", {}).get("blockId", orig.get("source_block_id", ""))
                    src_port = new_src_port or orig.get("source", {}).get("portId", orig.get("source_port", "out"))
                    tgt_bid = new_tgt_bid or orig.get("target", {}).get("blockId", orig.get("target_block_id", ""))
                    tgt_port = new_tgt_port or orig.get("target", {}).get("portId", orig.get("target_port", "in"))

                    if not (src_bid and tgt_bid):
                        logger.warning(f"[BuilderWorkflow] reconnect: cannot resolve src/tgt blocks for {conn_id}")
                        continue

                    result = await builder_connect_blocks(
                        strategy_id=strategy_id,
                        source_block_id=src_bid,
                        source_port=src_port,
                        target_block_id=tgt_bid,
                        target_port=tgt_port,
                    )
                    if "error" in result:
                        logger.warning(f"[BuilderWorkflow] reconnect: connect error: {result['error']}")
                        continue
                    new_conn = result.get("connection", {})
                    current_connections.append(new_conn)
                    logger.info(
                        f"[BuilderWorkflow] 🏗️ Reconnected [{conn_id}] "
                        f"→ {src_bid}:{src_port} → {tgt_bid}:{tgt_port} — {reason}"
                    )
                    applied.append(change)

                elif action == "remove_block":
                    block_id = change.get("block_id", "")
                    if not block_id:
                        logger.warning("[BuilderWorkflow] remove_block: missing block_id")
                        continue
                    # Safety: never remove strategy node
                    target_block = next((b for b in self._result.blocks_added if b.get("id") == block_id), {})
                    if target_block.get("type") in ("strategy", "static_sltp"):
                        logger.warning(
                            f"[BuilderWorkflow] remove_block: refusing to remove protected block "
                            f"'{block_id}' (type={target_block.get('type')})"
                        )
                        continue
                    result = await builder_remove_block(
                        strategy_id=strategy_id,
                        block_id=block_id,
                    )
                    if "error" in result:
                        logger.warning(f"[BuilderWorkflow] remove_block {block_id}: {result['error']}")
                        continue
                    # Update local state
                    self._result.blocks_added = [b for b in self._result.blocks_added if b.get("id") != block_id]
                    current_connections[:] = [
                        c
                        for c in current_connections
                        if c.get("source", {}).get("blockId") != block_id
                        and c.get("target", {}).get("blockId") != block_id
                    ]
                    logger.info(f"[BuilderWorkflow] 🏗️ Removed block [{block_id}] — {reason}")
                    applied.append(change)

                elif action == "add_block":
                    block_type = change.get("block_type", "")
                    params = change.get("params", {})
                    connect_from_port = change.get("connect_from_port", "long")
                    connect_to_block_id = change.get("connect_to_block_id", "")
                    connect_to_port = change.get("connect_to_port", "filter_long")

                    if not block_type:
                        logger.warning("[BuilderWorkflow] add_block: missing block_type")
                        continue

                    # Hard guard: never add filter blocks when trades are already low.
                    # Topology agent may still suggest this despite the prompt rules.
                    if connect_to_port in ("filter_long", "filter_short") and _current_trades < 20:
                        logger.warning(
                            f"[BuilderWorkflow] add_block BLOCKED: would add filter '{block_type}' "
                            f"to '{connect_to_port}' but current trades={_current_trades} < 20. "
                            f"Adding more filters will eliminate all trades. Skipping."
                        )
                        continue

                    # Validate block_type against BLOCK_REGISTRY to prevent hallucinated types
                    # (e.g. "supertrend_filter") from being added — unknown blocks produce no
                    # signals and silently break the entire optimizer run.
                    try:
                        from backend.backtesting.indicators import BLOCK_REGISTRY as _BREG

                        _SPECIAL_TYPES = {
                            "strategy",
                            "condition",
                            "filter",
                            "exit",
                            "static_sltp",
                            "close_by_time",
                            "tp_percent",
                            "sl_percent",
                            "atr_exit",
                            "close_channel",
                            "close_rsi",
                            "channel",
                            "price_action",
                            "divergence",
                            "momentum",
                            "pivot_points",
                            "highest_lowest_bar",
                            "two_mas",
                        }
                        if block_type not in _BREG and block_type not in _SPECIAL_TYPES:
                            logger.warning(
                                f"[BuilderWorkflow] add_block BLOCKED: '{block_type}' not in "
                                f"BLOCK_REGISTRY — topology agent hallucinated unknown type. "
                                f"Skipping to prevent silent signal loss."
                            )
                            continue
                    except Exception:
                        pass  # If registry import fails, proceed and let the API handle it

                    result = await builder_add_block(
                        strategy_id=strategy_id,
                        block_type=block_type,
                        params=params,
                    )
                    if "error" in result:
                        logger.warning(f"[BuilderWorkflow] add_block {block_type}: {result['error']}")
                        continue

                    new_block = result.get("block", {})
                    new_block_id = new_block.get("id", "")
                    if not new_block_id:
                        logger.warning("[BuilderWorkflow] add_block: no block id in response")
                        continue

                    # Wire new block into the graph
                    if connect_to_block_id:
                        conn_result = await builder_connect_blocks(
                            strategy_id=strategy_id,
                            source_block_id=new_block_id,
                            source_port=connect_from_port,
                            target_block_id=connect_to_block_id,
                            target_port=connect_to_port,
                        )
                        if "error" not in conn_result:
                            current_connections.append(conn_result.get("connection", {}))

                    self._result.blocks_added.append(new_block)
                    logger.info(
                        f"[BuilderWorkflow] 🏗️ Added block [{new_block_id}] type={block_type} "
                        f"→ {connect_to_block_id}:{connect_to_port} — {reason}"
                    )
                    applied.append(change)

                else:
                    logger.warning(f"[BuilderWorkflow] Unknown topology action: {action!r}")

            except Exception as e:
                logger.error(f"[BuilderWorkflow] _apply_topology_changes [{action}] error: {e}")

        return applied

    async def _run_optimizer_for_ranges(
        self,
        config: BuilderWorkflowConfig,
        agent_ranges: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Convert agent-suggested ranges to optimizer format and run sweep.

        Fetches the current strategy graph and OHLCV data, builds the
        ``custom_ranges`` list expected by ``generate_builder_param_combinations``,
        then runs either a grid search (≤ 200 combos) or Optuna Bayesian search
        (> 200 combos, capped at 50 trials, 2-minute timeout) via the existing
        ``run_builder_grid_search`` / ``run_builder_optuna_search`` helpers.

        Args:
            config: Current workflow config (symbol, timeframe, dates, capital…).
            agent_ranges: Output of ``_suggest_param_ranges()``.
                          Each item: ``{"block_id": ..., "ranges": {"param": {min,max,step,type}}}``

        Returns:
            Dict with ``best_params``, ``best_score``, ``best_metrics``,
            ``tested_combinations`` on success; ``None`` on failure.
        """
        from backend.backtesting.service import BacktestService

        # ── Convert agent ranges → custom_ranges format ──────────────────────
        # custom_ranges format: [{param_path, low, high, step, type, enabled}]
        from backend.optimization.builder_optimizer import (
            DEFAULT_PARAM_RANGES,
            _merge_ranges,
            clone_graph_with_params,
            extract_optimizable_params,
            generate_builder_param_combinations,
            run_builder_backtest,
            run_builder_grid_search,
            run_builder_optuna_search,
        )

        # Pre-build block_id → block_type map (needed for constraint enforcement and
        # DEFAULT_PARAM_RANGES expansion). Populated from loaded strategy blocks.
        _block_type_map: dict[str, str] = {}
        for _blk in self._result.blocks_added or []:
            _bid = _blk.get("id", _blk.get("block_id", ""))
            _bt = _blk.get("type", "").lower()
            if _bid:
                _block_type_map[_bid] = _bt

        custom_ranges: list[dict[str, Any]] = []
        for item in agent_ranges:
            block_id = item.get("block_id", "")
            for param, rng in item.get("ranges", {}).items():
                lo = rng.get("min", 1)
                hi = rng.get("max", 100)
                st = rng.get("step", 1)
                ptype = rng.get("type", "int")
                # ── Safety clamps to prevent degenerate RSI configs ───────────
                # RSI period < 10 on 30m+ TF → 300+ daily crossings → commission bleed
                if param == "period" and lo < 10:
                    logger.warning(f"[BuilderWorkflow] Clamping {block_id}.period min {lo} → 10 (hard floor)")
                    lo = 10
                # cross_long_level: allow values as low as 20.
                # cross_long_level < long_rsi_more is VALID — oscillators.py conflict-resolution
                # path fires an extended-cross signal at range entry (long_rsi_more). This region
                # produces the current best config (cross=36, long_rsi_more=43 → 124 signals).
                if param == "cross_long_level" and lo < 20:
                    logger.warning(f"[BuilderWorkflow] Clamping {block_id}.cross_long_level min {lo} → 20")
                    lo = 20
                # stop_loss_percent sanity floor: SL < 1% causes too many whipsaws on 30m.
                # Note: now using FallbackV4 in optimizer so compounding parity gap is gone.
                # Floor is just a sanity guard against extreme configs.
                if param == "stop_loss_percent" and lo < 1.0:
                    logger.warning(f"[BuilderWorkflow] Clamping {block_id}.stop_loss_percent min {lo} → 1.0")
                    lo = 1.0
                if lo >= hi:
                    logger.debug(
                        f"[BuilderWorkflow] Skipping invalid range for {block_id}.{param}: min={lo} >= max={hi}"
                    )
                    continue
                custom_ranges.append(
                    {
                        "param_path": f"{block_id}.{param}",
                        "param_key": param,
                        "block_type": _block_type_map.get(block_id, ""),
                        "low": lo,
                        "high": hi,
                        "step": st,
                        "type": ptype,
                        "enabled": True,
                    }
                )

        # ── Expand narrow LLM ranges to at least DEFAULT_PARAM_RANGES width ──
        # LLMs sometimes suggest narrow ranges (±20% around current value) even when
        # instructed to use full range. This guard ensures the optimizer always has at
        # least the default coverage for each parameter.
        for _cr in custom_ranges:
            _pp = _cr["param_path"]
            _parts = _pp.split(".", 1)
            if len(_parts) != 2:
                continue
            _bid, _pname = _parts
            _btype = _block_type_map.get(_bid, "")
            if not _btype or _btype not in DEFAULT_PARAM_RANGES:
                continue
            _def_range = DEFAULT_PARAM_RANGES[_btype].get(_pname)
            if _def_range is None:
                continue
            _def_lo = _def_range.get("low", _cr["low"])
            _def_hi = _def_range.get("high", _cr["high"])
            # Only expand, never shrink — LLM might narrow for good reason (e.g. direction filter)
            if _cr["low"] > _def_lo:
                logger.info(
                    f"[BuilderWorkflow] Expanding {_pp} low {_cr['low']} → {_def_lo} "
                    f"(LLM narrowed below DEFAULT_PARAM_RANGES)"
                )
                _cr["low"] = _def_lo
            if _cr["high"] < _def_hi:
                logger.info(
                    f"[BuilderWorkflow] Expanding {_pp} high {_cr['high']} → {_def_hi} "
                    f"(LLM narrowed below DEFAULT_PARAM_RANGES)"
                )
                _cr["high"] = _def_hi

        if not custom_ranges:
            logger.warning("[BuilderWorkflow] No valid ranges from agents — skipping optimizer sweep")
            return None

        # ── Build strategy graph from in-memory state (no server required) ─────
        # Prefer live in-memory blocks/connections over MCP fetch; fall back to
        # API only when in-memory state is empty (should never happen in practice).
        blocks = self._result.blocks_added or config.blocks or []
        connections = self._result.connections_made or config.connections or []
        if not blocks:
            from backend.agents.mcp.tools.strategy_builder import builder_get_strategy

            graph_resp = await builder_get_strategy(self._result.strategy_id)
            if not graph_resp or "error" in graph_resp:
                logger.warning(f"[BuilderWorkflow] Could not fetch strategy graph: {graph_resp}")
                return None
            blocks = graph_resp.get("blocks") or graph_resp.get("builder_blocks") or []
            connections = graph_resp.get("connections") or graph_resp.get("builder_connections") or []
        strategy_graph: dict[str, Any] = {
            "name": config.name,
            "blocks": blocks,
            "connections": connections,
            "direction": config.direction,
            "interval": config.timeframe,
        }

        # ── Filter custom_ranges to connected blocks only (belt-and-suspenders) ─
        # _suggest_param_ranges already excludes disconnected blocks from the LLM prompt,
        # but LLMs may still return block IDs not in the graph. Filter here to be safe.
        _sweep_connected_ids: set[str] = set()
        for _c in connections:
            _src = _c.get("source") or {}
            _tgt = _c.get("target") or {}
            _raw_sid = _src.get("blockId") if isinstance(_src, dict) else None
            _raw_sid = _raw_sid or _c.get("source_block_id", "")
            _raw_tid = _tgt.get("blockId") if isinstance(_tgt, dict) else None
            _raw_tid = _raw_tid or _c.get("target_block_id", "")
            _sid = _raw_sid.get("blockId", "") if isinstance(_raw_sid, dict) else (_raw_sid or "")
            _tid = _raw_tid.get("blockId", "") if isinstance(_raw_tid, dict) else (_raw_tid or "")
            if isinstance(_sid, str) and _sid:
                _sweep_connected_ids.add(_sid)
            if isinstance(_tid, str) and _tid:
                _sweep_connected_ids.add(_tid)
        if _sweep_connected_ids:
            _before = len(custom_ranges)
            custom_ranges = [cr for cr in custom_ranges if cr["param_path"].split(".")[0] in _sweep_connected_ids]
            _dropped = _before - len(custom_ranges)
            if _dropped:
                logger.info(f"[BuilderWorkflow] Filtered {_dropped} custom_range(s) for disconnected blocks")

        # ── Extract all optimizable params (needed by _merge_ranges) ─────────
        all_params = extract_optimizable_params(strategy_graph)
        # If extract found nothing (e.g. non-standard block types), build
        # minimal param specs directly from the agent-supplied custom_ranges so
        # the sweep can still run.
        if all_params:
            active_specs = _merge_ranges(all_params, custom_ranges)
        else:
            logger.info(
                "[BuilderWorkflow] extract_optimizable_params returned empty — building specs from agent ranges directly"
            )
            active_specs = [
                {
                    "block_id": cr["param_path"].split(".")[0],
                    "block_type": "",
                    "block_name": cr["param_path"].split(".")[0],
                    "param_key": cr["param_path"].split(".", 1)[1] if "." in cr["param_path"] else cr["param_path"],
                    "param_path": cr["param_path"],
                    "type": cr.get("type", "int"),
                    "low": cr["low"],
                    "high": cr["high"],
                    "step": cr.get("step", 1),
                    "default": cr["low"],
                    "current_value": cr["low"],
                }
                for cr in custom_ranges
            ]

        if not active_specs:
            logger.warning("[BuilderWorkflow] No active param specs after merge — skipping optimizer sweep")
            return None

        # ── Estimate combination count ────────────────────────────────────────
        total_combos = 1
        for cr in custom_ranges:
            n = max(1, int((cr["high"] - cr["low"]) / cr["step"]) + 1)
            total_combos *= n

        # ── Fetch OHLCV data with warmup ────────────────────────────────────
        # Load 45 extra days before start_date so Wilder RSI (and other EWM
        # indicators) are fully converged before the optimization window starts.
        # This matches the API router warmup window (45d × 48 bars/30m = 2160 bars)
        # and eliminates the cold-start bias where optimizer signal counts differ
        # from real backtest signal counts (observed: 107 cold vs 149 warm entries
        # for period=40 on 30m BTCUSDT, causing optimizer Sharpe=0.792 → real=0.507).
        from datetime import datetime, timedelta

        _WARMUP_DAYS = 45
        _opt_start = datetime.fromisoformat(config.start_date)
        _warmup_start = _opt_start - timedelta(days=_WARMUP_DAYS)

        service = BacktestService()
        try:
            ohlcv = await service._fetch_historical_data(
                symbol=config.symbol,
                interval=config.timeframe,
                start_date=_warmup_start,
                end_date=datetime.fromisoformat(config.end_date),
                market_type="linear",
            )
        except Exception as fetch_err:
            logger.error(f"[BuilderWorkflow] Could not fetch OHLCV for optimizer: {fetch_err}")
            return None

        if ohlcv is None or len(ohlcv) == 0:
            logger.warning("[BuilderWorkflow] No OHLCV data available — skipping optimizer sweep")
            return None

        # Extract min_trades from Evaluation panel constraints (if set).
        # This prevents the optimizer from selecting degenerate solutions
        # with very few trades (which can have artificially high Sharpe).
        _eval_constraints = config.evaluation_config.get("constraints") or []
        _min_trades_constraint = max(
            next(
                (
                    int(c.get("value", 0))
                    for c in _eval_constraints
                    if c.get("metric") == "total_trades" and c.get("operator") in (">=", ">")
                ),
                0,
            ),
            15,  # floor: matches _MIN_TRADES_FOR_SWEEP; prevent degenerate 1-4 trade solutions
        )

        config_params: dict[str, Any] = {
            "symbol": config.symbol,
            "interval": config.timeframe,
            "initial_capital": config.initial_capital,
            "leverage": config.leverage,
            "commission": config.commission,
            "direction": config.direction,
            "use_fixed_amount": False,
            "fixed_amount": 0.0,
            "engine_type": "numba",  # NumbaEngineV2 = 20-40x faster; top-5 re-verified by FallbackV4 below
            # Use primary_metric from Evaluation panel — single source of truth
            "optimize_metric": config.get_primary_metric(),
            # Pass min_trades from evaluation panel so optimizer skips degenerate configs
            "min_trades": _min_trades_constraint,
            # Warmup cutoff: ohlcv includes _WARMUP_DAYS extra bars before start_date.
            # run_builder_backtest will generate signals on the full warmup dataset
            # (so RSI is converged), then slice to [warmup_cutoff:] before running
            # the backtest engine — no trades in the warmup window.
            "warmup_cutoff": config.start_date,
        }

        # ── Choose method based on realistic trial count ─────────────────────
        # Hard-cap trials to keep each sweep within a few minutes.
        MAX_GRID_COMBOS = 200  # above this → Bayesian is more efficient
        MAX_SWEEP_SECONDS = 300  # 5-minute budget per sweep (3 iters × 300s = 15 min total)

        if total_combos > MAX_GRID_COMBOS:
            method = "bayesian"
            # n_trials=None → Optuna runs until timeout, no artificial trial cap.
            # Correct for spaces of 10^3–10^9+ combos: TPE samples intelligently.
            n_trials = None
            logger.info(
                f"[BuilderWorkflow] {total_combos:,} theoretical combos → "
                f"Bayesian sweep (unlimited trials, timeout={MAX_SWEEP_SECONDS}s)"
            )
        else:
            method = "grid"
            n_trials = total_combos
            logger.info(f"[BuilderWorkflow] Grid sweep: {total_combos} combinations, timeout={MAX_SWEEP_SECONDS}s")

        param_list_str = ", ".join(
            f"{cr['param_path']}: [{cr['low']}..{cr['high']} step {cr['step']}]" for cr in custom_ranges
        )
        actual_label = f"∞ trials / {MAX_SWEEP_SECONDS}s budget" if method == "bayesian" else f"{total_combos} combos"
        self._emit_agent_log(
            agent="system",
            role="optimizer",
            prompt=f"Optimizer sweep: {method}, {actual_label}",
            response=f"Parameters: {param_list_str}",
            title=f"🎯 Optimizer sweep — {method} ({actual_label})",
        )

        # ── Run the optimizer ─────────────────────────────────────────────────
        optimize_metric = config.get_primary_metric()
        try:
            if method == "bayesian":
                result = await asyncio.to_thread(
                    run_builder_optuna_search,
                    base_graph=strategy_graph,
                    ohlcv=ohlcv,
                    param_specs=active_specs,
                    config_params=config_params,
                    optimize_metric=optimize_metric,
                    n_trials=n_trials,
                    top_n=5,
                    timeout_seconds=MAX_SWEEP_SECONDS,
                )
            else:
                param_combinations, _, _capped = generate_builder_param_combinations(
                    param_specs=active_specs,
                    custom_ranges=custom_ranges,
                    search_method="grid",
                    max_iterations=0,
                )
                result = await asyncio.to_thread(
                    run_builder_grid_search,
                    base_graph=strategy_graph,
                    ohlcv=ohlcv,
                    param_combinations=param_combinations,
                    config_params=config_params,
                    optimize_metric=optimize_metric,
                    max_results=5,
                    timeout_seconds=MAX_SWEEP_SECONDS,
                )

            if result and result.get("best_params"):
                best = result["best_params"]
                _best_score = result.get("best_score", 0)
                # If the optimizer fell back to unfiltered results (min_trades violated),
                # reject the params — they're from degenerate low-trade solutions.
                _top = (result.get("top_results") or [{}])[0]
                if _top.get("_below_min_trades"):
                    logger.warning(
                        f"[BuilderWorkflow] Optimizer best params rejected — below min_trades "
                        f"(required={_top.get('_min_trades_required', '?')}). "
                        "Returning None so caller falls back to structural adjustments."
                    )
                    return None

                # NOTE: cross_long_level < long_rsi_more is VALID (oscillators.py
                # conflict-resolution path fires extended-cross at range boundary).
                # The baseline strategy uses cross=36, long_rsi_more=43 → 124 signals.
                # No clamping needed here.

                # ── FallbackV4 cross-verification of top candidates ───────────────
                # NumbaEngine uses equity-based compounding position sizing while
                # FallbackV4 uses fixed sizing.  This parity gap can make NumbaEngine
                # Sharpe misleading for certain SL/TP configurations.
                # Solution: re-run the top-N candidates with FallbackV4 and pick the
                # one with the best real-engine Sharpe.
                _top_results = result.get("top_results", [])
                if _top_results:
                    _v4_config = {**config_params, "engine_type": "fallback"}
                    _best_v4_score: float | None = None
                    _best_v4_params: dict[str, Any] = best

                    for _cand in _top_results[:5]:
                        _cand_params = _cand.get("params", {})
                        if not _cand_params:
                            continue
                        _cand_graph = clone_graph_with_params(strategy_graph, _cand_params)
                        _v4_res = run_builder_backtest(_cand_graph, ohlcv, _v4_config)
                        if _v4_res is None:
                            continue
                        _v4_score = float(_v4_res.get(optimize_metric, 0) or 0)
                        logger.info(
                            f"[BuilderWorkflow] FallbackV4 verify: "
                            f"numba={_cand.get('score', 0):.3f} v4={_v4_score:.3f} "
                            f"params={_cand_params}"
                        )
                        if _best_v4_score is None or _v4_score > _best_v4_score:
                            _best_v4_score = _v4_score
                            _best_v4_params = _cand_params

                    if _best_v4_score is not None:
                        logger.info(
                            f"[BuilderWorkflow] ✅ FallbackV4 best: score={_best_v4_score:.3f} "
                            f"(NumbaEngine best was {_best_score:.3f}) — using V4 result"
                        )
                        best = _best_v4_params
                        _best_score = _best_v4_score

                # ── Post-optimizer SL sanity floor ───────────────────────────────
                # Enforce SL >= 1.0% — anything tighter is too noisy on 30m timeframe.
                for _k in list(best.keys()):
                    if _k.endswith(".stop_loss_percent"):
                        _sl_val = float(best[_k])
                        if _sl_val < 1.0:
                            logger.warning(f"[BuilderWorkflow] Post-opt SL clamp: {_k} {_sl_val:.2f} → 1.0")
                            best[_k] = 1.0

                # ── Post-optimizer close_by_time / TP cross-block constraint ─────
                # When both static_sltp and close_by_time are present, ensure
                # min_profit_percent >= take_profit_percent + 2.0 so TP fires first.
                # If min_profit < TP, the time exit fires prematurely at the lower
                # threshold, cutting off TP gains entirely.
                _tp_key = next((k for k in best if k.endswith(".take_profit_percent")), None)
                _mp_key = next((k for k in best if k.endswith(".min_profit_percent")), None)
                if _tp_key and _mp_key:
                    _tp_val = float(best[_tp_key])
                    _mp_val = float(best[_mp_key])
                    _mp_min = _tp_val + 2.0
                    if _mp_val < _mp_min:
                        logger.warning(
                            f"[BuilderWorkflow] Cross-block constraint: {_mp_key} {_mp_val:.2f} "
                            f"< take_profit({_tp_val:.2f}) + 2.0 → adjusted to {_mp_min:.2f}"
                        )
                        best[_mp_key] = _mp_min

                logger.info(f"[BuilderWorkflow] ✅ Optimizer best: score={_best_score:.3f} params={best}")
                return {
                    "best_params": best,
                    "best_score": _best_score,
                    "best_metrics": result.get("best_metrics", {}),
                    "tested_combinations": result.get("tested_combinations", 0),
                }

        except Exception as opt_err:
            logger.error(f"[BuilderWorkflow] Optimizer sweep failed: {opt_err}", exc_info=True)

        return None

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
        """Debate system removed — no-op stub."""
        logger.info("[BuilderWorkflow] Debate system removed — skipping deliberation")
        self._result.deliberation = {"skipped": True, "reason": "debate_system_removed"}
