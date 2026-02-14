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

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
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

    # AI Deliberation — optional, uses real LLM agents for planning
    enable_deliberation: bool = False

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
            "enable_deliberation": self.enable_deliberation,
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

    def __init__(self) -> None:
        """Initialize workflow."""
        self._result = BuilderWorkflowResult()

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
            self._result.status = BuilderStage.PLANNING
            logger.info(f"[BuilderWorkflow] Planning: {config.name}")
            library = await builder_get_block_library()
            if isinstance(library, dict) and "error" in library:
                self._result.errors.append(f"Failed to get block library: {library['error']}")
                logger.warning("Block library unavailable, continuing without validation")
            else:
                self._result.block_library = library

            # Optional AI Deliberation for planning phase
            if config.enable_deliberation:
                await self._run_deliberation(config)

            # Stage 2: Create strategy
            self._result.status = BuilderStage.CREATING
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
            self._result.status = BuilderStage.ADDING_BLOCKS
            block_id_map = {}  # type -> actual ID

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

            logger.info(
                f"[BuilderWorkflow] Added {len(self._result.blocks_added)} blocks (incl. price + main_strategy)"
            )

            # Stage 4: Connect blocks
            self._result.status = BuilderStage.CONNECTING

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

            # Stage 5: Validate
            self._result.status = BuilderStage.VALIDATING
            logger.info("[BuilderWorkflow] Validating strategy...")
            validation = await builder_validate_strategy(self._result.strategy_id)
            self._result.validation = validation

            if isinstance(validation, dict) and not validation.get("is_valid", True):
                errors = validation.get("errors", [])
                logger.warning(f"[BuilderWorkflow] Validation warnings: {errors}")
                # Continue anyway — validation may be advisory

            # Stage 6: Generate code
            self._result.status = BuilderStage.GENERATING_CODE
            logger.info("[BuilderWorkflow] Generating code...")
            code_result = await builder_generate_code(self._result.strategy_id)
            if isinstance(code_result, dict) and "error" not in code_result:
                self._result.generated_code = code_result.get("code", "")

            # Stage 7: Backtest
            self._result.status = BuilderStage.BACKTESTING
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
            for iteration in range(1, config.max_iterations + 1):
                self._result.status = BuilderStage.EVALUATING
                # Backtest response uses "results" key (from run_backtest_from_builder endpoint)
                # but also support "metrics" key for compatibility
                metrics = {}
                if isinstance(backtest, dict):
                    metrics = backtest.get("results", backtest.get("metrics", {}))
                sharpe = metrics.get("sharpe_ratio", 0)
                win_rate = metrics.get("win_rate", 0)

                iteration_record = {
                    "iteration": iteration,
                    "sharpe_ratio": sharpe,
                    "win_rate": win_rate,
                    "total_trades": metrics.get("total_trades", 0),
                    "net_profit": metrics.get("net_profit", 0),
                    "max_drawdown": metrics.get("max_drawdown_pct", 0),
                    "acceptable": (
                        sharpe >= config.min_acceptable_sharpe and win_rate >= config.min_acceptable_win_rate
                    ),
                }
                self._result.iterations.append(iteration_record)

                if iteration_record["acceptable"]:
                    logger.info(
                        f"[BuilderWorkflow] Iteration {iteration}: Strategy meets criteria — "
                        f"Sharpe={sharpe:.2f}, WinRate={win_rate:.1%}"
                    )
                    break

                logger.info(
                    f"[BuilderWorkflow] Iteration {iteration}/{config.max_iterations}: "
                    f"Sharpe={sharpe:.2f} (min {config.min_acceptable_sharpe}), "
                    f"WinRate={win_rate:.1%} (min {config.min_acceptable_win_rate:.0%}) — iterating"
                )

                if iteration >= config.max_iterations:
                    logger.info("[BuilderWorkflow] Max iterations reached, accepting best result")
                    break

                # --- Iterative parameter adjustment ---
                self._result.status = BuilderStage.ITERATING
                adjustments = self._suggest_adjustments(config.blocks, self._result.blocks_added, iteration, metrics)

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
                self._result.status = BuilderStage.GENERATING_CODE
                code_result = await builder_generate_code(self._result.strategy_id)
                if isinstance(code_result, dict) and "error" not in code_result:
                    self._result.generated_code = code_result.get("code", "")

                # Re-run backtest with adjusted parameters
                self._result.status = BuilderStage.BACKTESTING
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

            # Completed
            self._result.status = BuilderStage.COMPLETED

        except Exception as e:
            self._result.status = BuilderStage.FAILED
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

    def _suggest_adjustments(
        self,
        block_defs: list[dict[str, Any]],
        blocks_added: list[dict[str, Any]],
        iteration: int,
        metrics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Suggest parameter adjustments for the next iteration.

        Uses a simple heuristic strategy:
        - If Sharpe is low and drawdown is high → tighten indicator periods
        - If win rate is low → widen overbought/oversold thresholds
        - Each iteration applies a progressively larger adjustment step

        Args:
            block_defs: Original block definitions from config
            blocks_added: Actual blocks added (with IDs)
            iteration: Current iteration number (1-based)
            metrics: Current backtest metrics

        Returns:
            List of {"block_id": ..., "params": {...}} adjustments
        """
        adjustments: list[dict[str, Any]] = []
        step = iteration  # Progressively larger adjustments

        win_rate = metrics.get("win_rate", 0)
        sharpe = metrics.get("sharpe_ratio", 0)
        max_dd = abs(metrics.get("max_drawdown_pct", 0))

        for block in blocks_added:
            block_id = block.get("id", "")
            block_type = block.get("type", "").lower()
            params = block.get("params", {})

            if not params or not block_id:
                continue

            new_params: dict[str, Any] = {}

            # RSI adjustments
            if block_type == "rsi":
                if win_rate < 0.4:
                    # Widen thresholds to filter more noise
                    if "overbought" in params:
                        new_params["overbought"] = min(85, params["overbought"] + 3 * step)
                    if "oversold" in params:
                        new_params["oversold"] = max(15, params["oversold"] - 3 * step)
                if sharpe < 0.3 and "period" in params:
                    # Longer period for smoother signal
                    new_params["period"] = min(30, params["period"] + 2 * step)

            # EMA / SMA adjustments
            elif block_type in ("ema", "sma"):
                if max_dd > 20 and "period" in params:
                    # Longer MA for trend following in volatile markets
                    new_params["period"] = min(50, params["period"] + 3 * step)
                elif sharpe < 0.3 and "period" in params:
                    new_params["period"] = max(5, params["period"] - 2 * step)

            # MACD adjustments
            elif block_type == "macd":
                if win_rate < 0.4 and "signal_period" in params:
                    new_params["signal_period"] = min(15, params["signal_period"] + step)
                if "fast_period" in params and sharpe < 0.3:
                    new_params["fast_period"] = max(5, params["fast_period"] - step)

            # Bollinger Bands adjustments
            elif block_type in ("bollinger", "bbands"):
                if win_rate < 0.4 and "std_dev" in params:
                    new_params["std_dev"] = min(3.0, params["std_dev"] + 0.2 * step)
                if "period" in params and max_dd > 20:
                    new_params["period"] = min(30, params["period"] + 2 * step)

            # Stochastic adjustments
            elif block_type in ("stochastic", "stoch"):
                if win_rate < 0.4:
                    if "overbought" in params:
                        new_params["overbought"] = min(90, params["overbought"] + 3 * step)
                    if "oversold" in params:
                        new_params["oversold"] = max(10, params["oversold"] - 3 * step)

            # ATR / stop-loss/take-profit adjustments
            elif block_type in ("atr", "static_sltp"):
                if max_dd > 20:
                    if "stop_loss" in params:
                        new_params["stop_loss"] = max(0.5, params["stop_loss"] - 0.3 * step)
                    if "take_profit" in params:
                        new_params["take_profit"] = max(0.5, params["take_profit"] + 0.3 * step)

            if new_params:
                adjustments.append({"block_id": block_id, "params": new_params})
                logger.debug(f"[BuilderWorkflow] Adjustment for {block_type} ({block_id}): {new_params}")

        return adjustments

    async def _run_deliberation(self, config: BuilderWorkflowConfig) -> None:
        """
        Run AI deliberation to get expert consensus on strategy blocks.

        Uses RealLLMDeliberation with DeepSeek + Perplexity agents to
        analyze the planned blocks and suggest improvements before building.
        Qwen is excluded due to invalid API key.

        Results are stored in self._result.deliberation and logged.
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
                f"Direction: {config.direction}. Planned blocks: {', '.join(block_names)}. "
                f"Parameters: {config.blocks}. "
                f"Capital: ${config.initial_capital}, Leverage: {config.leverage}x, "
                f"Commission: {config.commission} (0.07%). "
                f"Should I use these blocks and parameters, or suggest improvements? "
                f"Focus on Sharpe ratio optimization and win rate above {config.min_acceptable_win_rate:.0%}."
            )

            # Enrich with market context first
            await deliberation.enrich_for_deliberation(
                question=question,
                symbol=config.symbol,
                strategy_type="builder",
            )

            # Use only available agents (DeepSeek + Perplexity, skip Qwen)
            agents = ["deepseek", "perplexity"]

            result = await deliberation.deliberate(
                question=question,
                agents=agents,
                max_rounds=1,  # Single round to save costs
                min_confidence=0.5,
            )

            self._result.deliberation = {
                "decision": result.decision,
                "confidence": result.confidence,
                "agent_count": len(agents),
                "agents_used": agents,
            }

            logger.info(
                f"[BuilderWorkflow] 🤖 Deliberation result: "
                f"confidence={result.confidence:.2f}, decision={result.decision[:100]}..."
            )

        except Exception as e:
            logger.warning(f"[BuilderWorkflow] AI Deliberation failed (non-fatal): {e}")
            self._result.deliberation = {"error": str(e), "skipped": True}
