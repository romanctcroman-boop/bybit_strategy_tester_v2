"""
Autonomous Backtesting Workflow — Full Self-Coordinating Pipeline.

Orchestrates a multi-step process:
1. **Fetch** — Retrieve OHLCV data from the kline database
2. **Evolve** — Run AI-powered strategy evolution (StrategyEvolution)
3. **Backtest** — Execute the best strategy via BacktestService
4. **Report** — Generate a markdown/JSON performance report
5. **Learn** — Persist result in vector memory for future retrieval

Each step is independently retriable and logged.

Integration points:
- BacktestService (backend.backtesting.service)
- StrategyEvolution (backend.agents.self_improvement.strategy_evolution)
- VectorMemoryStore (backend.agents.memory.vector_store)
- log_agent_action MCP tool (backend.agents.mcp.trading_tools)

Added 2026-02-12 per Agent Ecosystem Audit — Additional Directions.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from loguru import logger

# =============================================================================
# DATA MODELS
# =============================================================================


class PipelineStage(str, Enum):
    """Stages of the autonomous backtesting pipeline."""

    IDLE = "idle"
    FETCHING = "fetching"
    EVOLVING = "evolving"
    BACKTESTING = "backtesting"
    REPORTING = "reporting"
    LEARNING = "learning"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowConfig:
    """Configuration for an autonomous workflow run."""

    symbol: str = "BTCUSDT"
    interval: str = "15"
    start_date: str = "2025-06-01"
    end_date: str = "2025-07-01"
    initial_capital: float = 10000.0
    leverage: float = 10.0
    direction: str = "both"
    stop_loss: float | None = None
    take_profit: float | None = None

    # Evolution parameters
    max_generations: int = 3
    evolution_enabled: bool = True

    # Fallback strategy if evolution is disabled
    fallback_strategy_type: str = "rsi"
    fallback_strategy_params: dict[str, Any] = field(
        default_factory=lambda: {"period": 14, "overbought": 70, "oversold": 30}
    )

    # Report format
    report_format: str = "markdown"

    # Learning
    save_to_memory: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to dict."""
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": self.initial_capital,
            "leverage": self.leverage,
            "direction": self.direction,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "max_generations": self.max_generations,
            "evolution_enabled": self.evolution_enabled,
            "fallback_strategy_type": self.fallback_strategy_type,
            "fallback_strategy_params": self.fallback_strategy_params,
            "report_format": self.report_format,
            "save_to_memory": self.save_to_memory,
        }


@dataclass
class WorkflowStatus:
    """Real-time status of a running workflow."""

    workflow_id: str
    stage: PipelineStage = PipelineStage.IDLE
    progress_pct: float = 0.0
    started_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    current_step_info: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "stage": self.stage.value,
            "progress_pct": round(self.progress_pct, 1),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_step_info": self.current_step_info,
            "errors": self.errors,
        }


@dataclass
class WorkflowResult:
    """Final output of a completed workflow pipeline."""

    workflow_id: str
    config: WorkflowConfig
    status: WorkflowStatus

    # Stage outputs
    data_rows: int = 0
    evolution_result: dict[str, Any] | None = None
    backtest_result: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    memory_doc_id: str | None = None

    # Timing
    total_duration_s: float = 0.0
    stage_durations: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "config": self.config.to_dict(),
            "status": self.status.to_dict(),
            "data_rows": self.data_rows,
            "evolution_result": self.evolution_result,
            "backtest_result": self.backtest_result,
            "report": self.report,
            "memory_doc_id": self.memory_doc_id,
            "total_duration_s": round(self.total_duration_s, 2),
            "stage_durations": {k: round(v, 2) for k, v in self.stage_durations.items()},
        }

    @property
    def success(self) -> bool:
        return self.status.stage == PipelineStage.COMPLETED


# =============================================================================
# WORKFLOW ENGINE
# =============================================================================


class AutonomousBacktestingWorkflow:
    """
    Full autonomous pipeline: fetch → evolve → backtest → report → learn.

    Usage::

        workflow = AutonomousBacktestingWorkflow()
        config = WorkflowConfig(symbol="BTCUSDT", interval="15")
        result = await workflow.run(config)
        print(result.to_dict())
    """

    # In-memory registry of active workflows (keyed by workflow_id)
    _active: dict[str, WorkflowStatus] = {}

    def __init__(self) -> None:
        self._workflow_id: str = ""
        self._status: WorkflowStatus | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, config: WorkflowConfig) -> WorkflowResult:
        """
        Execute the full autonomous pipeline.

        Args:
            config: Workflow configuration

        Returns:
            WorkflowResult with outputs from every stage
        """
        self._workflow_id = str(uuid.uuid4())[:12]
        self._status = WorkflowStatus(
            workflow_id=self._workflow_id,
            started_at=datetime.now(UTC),
        )
        AutonomousBacktestingWorkflow._active[self._workflow_id] = self._status

        result = WorkflowResult(
            workflow_id=self._workflow_id,
            config=config,
            status=self._status,
        )

        t0 = time.perf_counter()

        logger.info(
            f"🚀 Workflow {self._workflow_id} started: "
            f"{config.symbol} {config.interval} "
            f"({config.start_date} → {config.end_date})"
        )

        try:
            # Step 1 — Fetch data
            data_rows = await self._step_fetch(config, result)

            # Step 2 — Evolve (optional)
            strategy_type, strategy_params = await self._step_evolve(config, result, data_rows)

            # Step 3 — Backtest
            await self._step_backtest(config, result, strategy_type, strategy_params)

            # Step 4 — Report
            await self._step_report(config, result)

            # Step 5 — Learn
            await self._step_learn(config, result)

            self._update_stage(PipelineStage.COMPLETED, 100.0, "Pipeline complete")

        except Exception as exc:
            logger.error(f"Workflow {self._workflow_id} failed: {exc}")
            self._update_stage(PipelineStage.FAILED, info=str(exc))
            self._status.errors.append(str(exc))

        finally:
            self._status.completed_at = datetime.now(UTC)
            result.total_duration_s = time.perf_counter() - t0
            # Log final action
            await self._log_action(
                "workflow_complete" if result.success else "workflow_failed",
                {
                    "duration_s": result.total_duration_s,
                    "stages": list(result.stage_durations.keys()),
                    "errors": self._status.errors,
                },
                success=result.success,
            )
            AutonomousBacktestingWorkflow._active.pop(self._workflow_id, None)

        return result

    @classmethod
    def get_status(cls, workflow_id: str) -> WorkflowStatus | None:
        """Get the status of an active or recently completed workflow."""
        return cls._active.get(workflow_id)

    @classmethod
    def list_active(cls) -> list[dict[str, Any]]:
        """List all currently active workflows."""
        return [s.to_dict() for s in cls._active.values()]

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    async def _step_fetch(self, config: WorkflowConfig, result: WorkflowResult) -> int:
        """Stage 1: Fetch OHLCV data."""
        self._update_stage(PipelineStage.FETCHING, 5.0, "Loading market data…")
        t = time.perf_counter()

        try:
            from backend.services.smart_kline_service import SmartKlineService

            svc = SmartKlineService()
            df = await asyncio.to_thread(
                svc.get_klines_for_backtest,
                symbol=config.symbol,
                interval=config.interval,
                start_date=config.start_date,
                end_date=config.end_date,
            )

            if df is None or (hasattr(df, "empty") and df.empty):
                raise ValueError(
                    f"No data for {config.symbol}/{config.interval} from {config.start_date} to {config.end_date}"
                )

            rows = len(df)
            result.data_rows = rows

        except ImportError:
            # Fallback: try BacktestService directly (it fetches data internally)
            logger.warning("SmartKlineService unavailable, data will be fetched during backtest")
            rows = 0
            result.data_rows = 0

        result.stage_durations["fetch"] = time.perf_counter() - t
        self._update_stage(PipelineStage.FETCHING, 15.0, f"Loaded {rows} candles")
        return rows

    async def _step_evolve(
        self,
        config: WorkflowConfig,
        result: WorkflowResult,
        data_rows: int,
    ) -> tuple[str, dict[str, Any]]:
        """Stage 2: Run strategy evolution (or return fallback)."""
        if not config.evolution_enabled:
            logger.info("Evolution disabled — using fallback strategy")
            return config.fallback_strategy_type, config.fallback_strategy_params

        self._update_stage(PipelineStage.EVOLVING, 20.0, "Running AI evolution…")
        t = time.perf_counter()

        try:
            from backend.agents.mcp.trading_tools import evolve_strategy

            evo_result = await evolve_strategy(
                symbol=config.symbol,
                timeframe=config.interval,
                max_generations=config.max_generations,
                initial_capital=config.initial_capital,
                leverage=int(config.leverage),
                direction=config.direction,
                start_date=config.start_date,
                end_date=config.end_date,
            )

            result.evolution_result = evo_result

            if "error" in evo_result:
                logger.warning(f"Evolution failed: {evo_result['error']} — using fallback")
                self._status.errors.append(f"Evolution: {evo_result['error']}")
                return config.fallback_strategy_type, config.fallback_strategy_params

            # Extract best strategy from evolution result
            best = evo_result.get("best_generation")
            if best and best.get("strategy_type"):
                strategy_type = best["strategy_type"]
                strategy_params = best.get("strategy_params", {})
                logger.info(f"Evolution selected: {strategy_type} (fitness={best.get('fitness_score', 0):.1f})")
            else:
                strategy_type = config.fallback_strategy_type
                strategy_params = config.fallback_strategy_params

        except Exception as exc:
            logger.warning(f"Evolution error: {exc} — using fallback")
            self._status.errors.append(f"Evolution: {exc}")
            strategy_type = config.fallback_strategy_type
            strategy_params = config.fallback_strategy_params

        result.stage_durations["evolve"] = time.perf_counter() - t
        self._update_stage(PipelineStage.EVOLVING, 45.0, f"Evolved → {strategy_type}")
        return strategy_type, strategy_params

    async def _step_backtest(
        self,
        config: WorkflowConfig,
        result: WorkflowResult,
        strategy_type: str,
        strategy_params: dict[str, Any],
    ) -> None:
        """Stage 3: Run backtest with the chosen strategy."""
        self._update_stage(PipelineStage.BACKTESTING, 50.0, "Running backtest…")
        t = time.perf_counter()

        from backend.agents.mcp.trading_tools import run_backtest

        bt_result = await run_backtest(
            symbol=config.symbol,
            interval=config.interval,
            strategy_type=strategy_type,
            strategy_params=strategy_params,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_capital,
            leverage=config.leverage,
            direction=config.direction,
            stop_loss=config.stop_loss,
            take_profit=config.take_profit,
        )

        result.backtest_result = bt_result

        if "error" in bt_result:
            raise RuntimeError(f"Backtest failed: {bt_result['error']}")

        result.stage_durations["backtest"] = time.perf_counter() - t
        trades = bt_result.get("total_trades", 0)
        ret = bt_result.get("total_return_pct", 0)
        self._update_stage(
            PipelineStage.BACKTESTING,
            70.0,
            f"Backtest done: {trades} trades, {ret:.2f}% return",
        )

    async def _step_report(self, config: WorkflowConfig, result: WorkflowResult) -> None:
        """Stage 4: Generate a performance report."""
        self._update_stage(PipelineStage.REPORTING, 75.0, "Generating report…")
        t = time.perf_counter()

        try:
            from backend.agents.mcp.trading_tools import generate_backtest_report

            report = await generate_backtest_report(format=config.report_format)
            result.report = report

        except Exception as exc:
            logger.warning(f"Report generation skipped: {exc}")
            self._status.errors.append(f"Report: {exc}")
            # Build a minimal report from the backtest result
            bt = result.backtest_result or {}
            result.report = {
                "format": "json",
                "metrics": bt,
                "assessment": "UNKNOWN",
                "recommendations": [],
            }

        result.stage_durations["report"] = time.perf_counter() - t
        self._update_stage(PipelineStage.REPORTING, 85.0, "Report generated")

    async def _step_learn(self, config: WorkflowConfig, result: WorkflowResult) -> None:
        """Stage 5: Save results to vector memory for future retrieval."""
        if not config.save_to_memory:
            self._update_stage(PipelineStage.LEARNING, 95.0, "Learning skipped")
            return

        self._update_stage(PipelineStage.LEARNING, 88.0, "Saving to memory…")
        t = time.perf_counter()

        bt = result.backtest_result or {}
        if "error" in bt or not bt.get("status"):
            logger.info("Skipping memory save — no valid backtest result")
            return

        try:
            from backend.agents.memory.vector_store import VectorMemoryStore

            store = VectorMemoryStore()
            doc_id = await store.save_backtest_result(
                backtest_id=result.workflow_id,
                strategy_type=bt.get("strategy", "unknown"),
                strategy_params=bt.get("strategy_params", {}),
                metrics={
                    "win_rate": bt.get("win_rate", 0),
                    "total_return_pct": bt.get("total_return_pct", 0),
                    "sharpe_ratio": bt.get("sharpe_ratio", 0),
                    "max_drawdown_pct": bt.get("max_drawdown_pct", 0),
                    "total_trades": bt.get("total_trades", 0),
                    "profit_factor": bt.get("profit_factor", 0),
                    "final_capital": bt.get("final_capital", 0),
                },
                symbol=config.symbol,
                interval=config.interval,
            )
            result.memory_doc_id = doc_id
            logger.info(f"Workflow result saved to memory: {doc_id}")

        except Exception as exc:
            logger.warning(f"Memory save failed (non-fatal): {exc}")
            self._status.errors.append(f"Memory: {exc}")

        result.stage_durations["learn"] = time.perf_counter() - t
        self._update_stage(PipelineStage.LEARNING, 95.0, "Learned from results")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_stage(
        self,
        stage: PipelineStage,
        progress: float | None = None,
        info: str = "",
    ) -> None:
        """Update current workflow status."""
        if self._status:
            self._status.stage = stage
            if progress is not None:
                self._status.progress_pct = progress
            self._status.current_step_info = info
            self._status.updated_at = datetime.now(UTC)

    async def _log_action(
        self,
        action: str,
        details: dict[str, Any] | None = None,
        success: bool = True,
    ) -> None:
        """Log a workflow action via the MCP logging tool."""
        try:
            from backend.agents.mcp.trading_tools import log_agent_action

            await log_agent_action(
                agent_name="autonomous_workflow",
                action=action,
                details=details,
                result_summary=f"Workflow {self._workflow_id}",
                success=success,
            )
        except Exception:
            pass  # Logging is best-effort
