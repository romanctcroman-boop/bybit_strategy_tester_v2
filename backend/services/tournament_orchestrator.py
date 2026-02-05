"""
Tournament Orchestrator - координирует соревнования стратегий с ML оптимизацией

Quick Win #3: Tournament + ML Integration
Объединяет: Sandbox, Optuna, Market Regime Detection, Knowledge Base
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from backend.ml import MultiModelDriftDetector
from backend.monitoring import SelfLearningSignalPublisher
from backend.services.latency_auto_tuner import LatencyAutoTuner

logger = logging.getLogger(__name__)


class TournamentStatus(str, Enum):
    """Статус турнира"""

    PENDING = "pending"
    RUNNING = "running"
    OPTIMIZING = "optimizing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StrategyEntry:
    """Участник турнира"""

    strategy_id: str
    strategy_name: str
    strategy_code: str
    initial_params: dict[str, Any] = field(default_factory=dict)
    optimized_params: dict[str, Any] | None = None
    param_space: dict[str, dict[str, Any]] | None = None

    # Results
    backtest_result: dict[str, Any] | None = None
    final_score: float = 0.0
    rank: int | None = None
    execution_time: float = 0.0
    errors: list[str] = field(default_factory=list)
    drift_status: dict[str, Any] = field(default_factory=dict)
    drift_events: list[dict[str, Any]] = field(default_factory=list)
    requires_emergency_retrain: bool = False


@dataclass
class TournamentConfig:
    """Конфигурация турнира"""

    tournament_name: str

    # Optimization settings
    enable_optimization: bool = True
    optimization_trials: int = 50
    optimization_timeout: float | None = None

    # Execution settings
    max_workers: int = 5
    execution_timeout: int = 300  # seconds per strategy

    # Market regime aware
    detect_market_regime: bool = True
    regime_aware_scoring: bool = True

    # Scoring weights
    scoring_weights: dict[str, float] = field(
        default_factory=lambda: {
            "sharpe_ratio": 0.30,
            "total_return": 0.25,
            "max_drawdown": 0.20,
            "win_rate": 0.15,
            "sortino_ratio": 0.10,
        }
    )

    # Knowledge Base logging
    enable_kb_logging: bool = True
    # Drift monitoring
    enable_drift_monitoring: bool = True
    drift_retrain_threshold: int = 3
    drift_baseline_alpha: float = 0.25


@dataclass
class TournamentResult:
    """Результаты турнира"""

    tournament_id: str
    tournament_name: str
    status: TournamentStatus

    # Timing
    started_at: datetime
    completed_at: datetime | None = None
    total_duration: float = 0.0

    # Participants
    participants: list[StrategyEntry] = field(default_factory=list)
    total_participants: int = 0
    successful_backtests: int = 0
    failed_backtests: int = 0

    # Winner
    winner: StrategyEntry | None = None
    top_3: list[StrategyEntry] = field(default_factory=list)

    # Market context
    market_regime: str | None = None
    market_regime_confidence: float = 0.0

    # Metadata
    optimization_time: float = 0.0
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    drift_snapshot: dict[str, Any] = field(default_factory=dict)


class TournamentOrchestrator:
    """
    Координатор турниров стратегий

    Pipeline:
    1. Market Regime Detection
    2. Strategy Optimization (Optuna) - parallel
    3. Strategy Execution (Sandbox) - parallel
    4. Results Aggregation & Scoring
    5. Winner Selection
    6. Knowledge Base Logging

    Example:
        orchestrator = TournamentOrchestrator(
            optimizer=StrategyOptimizer(),
            sandbox=SandboxExecutor(),
            regime_detector=MarketRegimeDetector(),
            reasoning_storage=ReasoningStorageService()
        )

        strategies = [
            StrategyEntry(
                strategy_id="rsi_1",
                strategy_name="RSI Strategy",
                strategy_code=rsi_code,
                param_space={
                    "rsi_period": {"type": "int", "low": 10, "high": 30},
                    "threshold": {"type": "float", "low": 0.01, "high": 0.05}
                }
            ),
            # ... more strategies
        ]

        result = await orchestrator.run_tournament(
            strategies=strategies,
            data=df,
            config=TournamentConfig(tournament_name="Test Tournament")
        )
    """

    def __init__(
        self,
        optimizer=None,
        sandbox=None,
        regime_detector=None,
        reasoning_storage=None,
        tournament_storage=None,
        drift_monitor: MultiModelDriftDetector | None = None,
        self_learning_publisher: SelfLearningSignalPublisher | None = None,
        latency_tuner: LatencyAutoTuner | None = None,
    ):
        """
        Initialize orchestrator with dependencies

        Args:
            optimizer: StrategyOptimizer instance
            sandbox: SandboxExecutor instance
            regime_detector: MarketRegimeDetector instance
            reasoning_storage: ReasoningStorageService instance
            tournament_storage: TournamentStorageService instance
        """
        self.optimizer = optimizer
        self.sandbox = sandbox
        self.regime_detector = regime_detector
        self.reasoning_storage = reasoning_storage
        self.tournament_storage = tournament_storage
        self.drift_monitor = drift_monitor or MultiModelDriftDetector()
        self.self_learning_publisher = self_learning_publisher
        self.latency_tuner = latency_tuner

        self._active_tournaments: dict[str, TournamentResult] = {}
        self._performance_baseline: dict[str, float] = {}
        self._drift_events_buffer: list[dict[str, Any]] = []
        self._active_retrains: set[str] = set()

    async def run_tournament(
        self,
        strategies: list[StrategyEntry],
        data: pd.DataFrame,
        config: TournamentConfig | None = None,
    ) -> TournamentResult:
        """
        Запустить турнир стратегий

        Args:
            strategies: List of strategy entries
            data: Historical market data for backtesting
            config: Tournament configuration

        Returns:
            TournamentResult with rankings and metrics
        """
        config = config or TournamentConfig(tournament_name="Unnamed Tournament")

        if self.latency_tuner:
            self.latency_tuner.register_baselines(config)

        tournament_id = f"tournament_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        started_at = datetime.now()

        logger.info(f"Starting tournament: {tournament_id}")
        logger.info(f"Participants: {len(strategies)}")
        logger.info(
            f"Optimization: {'enabled' if config.enable_optimization else 'disabled'}"
        )

        # Initialize result
        result = TournamentResult(
            tournament_id=tournament_id,
            tournament_name=config.tournament_name,
            status=TournamentStatus.RUNNING,
            started_at=started_at,
            total_participants=len(strategies),
            participants=strategies,
        )

        self._active_tournaments[tournament_id] = result

        try:
            # Step 1: Market Regime Detection
            if config.detect_market_regime and self.regime_detector:
                logger.info("Detecting market regime...")
                regime_result = self.regime_detector.detect_regime(data)
                result.market_regime = regime_result.regime.value
                result.market_regime_confidence = regime_result.confidence
                logger.info(
                    f"Market regime: {regime_result.regime.value} ({regime_result.confidence:.2%})"
                )

            # Step 2: Strategy Optimization
            if config.enable_optimization and self.optimizer:
                logger.info("Starting strategy optimization phase...")
                result.status = TournamentStatus.OPTIMIZING
                opt_start = datetime.now()

                self._apply_latency_overrides(config, "optimization", result.metadata)
                await self._optimize_strategies(strategies, data, config)

                result.optimization_time = (datetime.now() - opt_start).total_seconds()
                logger.info(f"Optimization complete: {result.optimization_time:.1f}s")
                if self.latency_tuner:
                    self.latency_tuner.record_optimizer_latency(
                        result.optimization_time
                    )

            # Step 3: Strategy Execution
            logger.info("Starting strategy execution phase...")
            result.status = TournamentStatus.EXECUTING
            exec_start = datetime.now()

            self._apply_latency_overrides(config, "execution", result.metadata)
            await self._execute_strategies(strategies, data, config)

            result.execution_time = (datetime.now() - exec_start).total_seconds()
            logger.info(f"Execution complete: {result.execution_time:.1f}s")

            # Step 4: Calculate Scores & Rankings
            logger.info("Calculating scores and rankings...")
            self._calculate_scores(strategies, config, result.market_regime)
            self._assign_rankings(strategies)

            # Step 5: Determine Winner
            result.winner = strategies[0] if strategies else None
            result.top_3 = strategies[:3]

            # Count successes/failures
            result.successful_backtests = sum(
                1 for s in strategies if s.backtest_result and not s.errors
            )
            result.failed_backtests = (
                result.total_participants - result.successful_backtests
            )

            if self.latency_tuner:
                result.metadata["latency_auto_tuner"] = (
                    self.latency_tuner.export_metrics()
                )

            result.drift_snapshot = self._build_drift_snapshot(
                strategies, result, config
            )
            await self._publish_self_learning_snapshot(result.drift_snapshot)

            # Complete
            result.status = TournamentStatus.COMPLETED
            result.completed_at = datetime.now()
            result.total_duration = (result.completed_at - started_at).total_seconds()

            logger.info("Tournament complete!")
            logger.info(
                f"Winner: {result.winner.strategy_name if result.winner else 'None'}"
            )
            logger.info(
                f"Score: {result.winner.final_score:.4f}" if result.winner else ""
            )

            # Step 6: Store in Knowledge Base
            if config.enable_kb_logging and self.reasoning_storage:
                await self._store_tournament_trace(result, config)

            # Step 7: Store in Tournament DB
            if self.tournament_storage:
                await self._store_tournament_result(result)

        except Exception as e:
            logger.error(f"Tournament failed: {e}", exc_info=True)
            result.status = TournamentStatus.FAILED
            result.completed_at = datetime.now()
            result.total_duration = (result.completed_at - started_at).total_seconds()
            raise

        finally:
            del self._active_tournaments[tournament_id]

        return result

    async def _optimize_strategies(
        self,
        strategies: list[StrategyEntry],
        data: pd.DataFrame,
        config: TournamentConfig,
    ):
        """Optimize all strategies in parallel"""
        if not self.optimizer:
            logger.warning("Optimizer not available, skipping optimization")
            return

        async def optimize_one(strategy: StrategyEntry):
            """Optimize single strategy"""
            if not strategy.param_space:
                logger.warning(
                    f"No param space for {strategy.strategy_name}, skipping optimization"
                )
                return

            try:
                logger.debug(f"Optimizing: {strategy.strategy_name}")

                opt_result = await self.optimizer.optimize_strategy(
                    strategy_code=strategy.strategy_code,
                    data=data,
                    param_space=strategy.param_space,
                    n_trials=config.optimization_trials,
                    timeout=config.optimization_timeout,
                )

                strategy.optimized_params = opt_result.best_params
                logger.info(
                    f"Optimized {strategy.strategy_name}: {opt_result.best_params}"
                )

            except Exception as e:
                logger.error(f"Optimization failed for {strategy.strategy_name}: {e}")
                strategy.errors.append(f"Optimization error: {e!s}")
                strategy.optimized_params = strategy.initial_params  # Fallback

        # Optimize in parallel (limited by max_workers)
        semaphore = asyncio.Semaphore(config.max_workers)

        async def optimize_with_semaphore(strategy):
            async with semaphore:
                await optimize_one(strategy)

        await asyncio.gather(*[optimize_with_semaphore(s) for s in strategies])

    async def _execute_strategies(
        self,
        strategies: list[StrategyEntry],
        data: pd.DataFrame,
        config: TournamentConfig,
    ):
        """Execute all strategies in parallel"""

        data_payload = data.to_dict()

        async def execute_one(strategy: StrategyEntry):
            """Execute single strategy"""
            exec_start = datetime.now()

            try:
                logger.debug(f"Executing: {strategy.strategy_name}")

                # Use optimized params if available, otherwise initial
                params = strategy.optimized_params or strategy.initial_params

                if self.sandbox:
                    # Execute in sandbox (safe)
                    result = await self.sandbox.execute(
                        code=strategy.strategy_code,
                        data=data_payload,
                        params=params,
                        timeout=config.execution_timeout,
                    )

                    if result.get("success"):
                        strategy.backtest_result = result.get("metrics", {})
                    else:
                        error_msg = result.get("error", "Unknown error")
                        strategy.errors.append(f"Execution error: {error_msg}")
                        logger.error(
                            f"Execution failed for {strategy.strategy_name}: {error_msg}"
                        )
                else:
                    # Fallback: mock execution (for testing without sandbox)
                    logger.warning(
                        f"No sandbox, using mock execution for {strategy.strategy_name}"
                    )
                    strategy.backtest_result = self._mock_backtest_result()

                strategy.execution_time = (datetime.now() - exec_start).total_seconds()
                logger.info(
                    f"Executed {strategy.strategy_name} in {strategy.execution_time:.1f}s"
                )
                if self.latency_tuner:
                    self.latency_tuner.record_execution_latency(strategy.execution_time)

                await self._handle_drift_tracking(
                    strategy,
                    config,
                    data_payload,
                )

            except Exception as e:
                logger.error(f"Execution failed for {strategy.strategy_name}: {e}")
                strategy.errors.append(f"Execution exception: {e!s}")
                strategy.execution_time = (datetime.now() - exec_start).total_seconds()

        # Execute in parallel (limited by max_workers)
        semaphore = asyncio.Semaphore(config.max_workers)

        async def execute_with_semaphore(strategy):
            async with semaphore:
                await execute_one(strategy)

        await asyncio.gather(*[execute_with_semaphore(s) for s in strategies])

    def _build_drift_snapshot(
        self,
        strategies: list[StrategyEntry],
        tournament: TournamentResult,
        config: TournamentConfig,
    ) -> dict[str, Any]:
        """Summarize drift + self-learning state for dashboards."""

        snapshot_strategies = []
        total_drift_events = 0

        for strategy in strategies:
            drift_events = strategy.drift_events[-5:]
            total_drift_events += len(drift_events)
            snapshot_strategies.append(
                {
                    "strategy_id": strategy.strategy_id,
                    "strategy_name": strategy.strategy_name,
                    "rank": strategy.rank,
                    "final_score": strategy.final_score,
                    "requires_emergency_retrain": strategy.requires_emergency_retrain,
                    "drift_status": strategy.drift_status,
                    "recent_drift_events": drift_events,
                }
            )

        models_needing_retrain = (
            self.drift_monitor.get_models_needing_retrain(
                config.drift_retrain_threshold
            )
            if self.drift_monitor
            else []
        )

        return {
            "tournament_id": tournament.tournament_id,
            "tournament_name": tournament.tournament_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "total_participants": tournament.total_participants,
            "drift_monitoring_enabled": config.enable_drift_monitoring,
            "total_drift_events": total_drift_events,
            "models_needing_retrain": models_needing_retrain,
            "strategies": snapshot_strategies,
            "latency_auto_tuner": self.latency_tuner.export_metrics()
            if self.latency_tuner
            else None,
        }

    async def _publish_self_learning_snapshot(self, snapshot: dict[str, Any]) -> None:
        if not snapshot or not self.self_learning_publisher:
            return

        try:
            await self.self_learning_publisher.publish_snapshot(snapshot)
        except Exception as exc:
            logger.error("Failed to publish self-learning snapshot: %s", exc)

    def _apply_latency_overrides(
        self,
        config: TournamentConfig,
        phase: str,
        metadata: dict[str, Any],
    ) -> None:
        if not self.latency_tuner:
            return

        adjustments = self.latency_tuner.apply_adaptive_overrides(config, phase)
        if adjustments:
            metadata.setdefault("latency_adjustments", []).append(
                {
                    "phase": phase,
                    "applied_at": datetime.now(UTC).isoformat(),
                    "adjustments": adjustments,
                }
            )

    async def _handle_drift_tracking(
        self,
        strategy: StrategyEntry,
        config: TournamentConfig,
        data_payload: dict[str, Any],
    ) -> None:
        """Update drift detector with latest metrics and act on alerts."""

        if not (
            config.enable_drift_monitoring
            and self.drift_monitor
            and strategy.backtest_result
        ):
            return

        actual_return = strategy.backtest_result.get("total_return")
        if actual_return is None:
            return

        baseline = self._performance_baseline.get(strategy.strategy_id, actual_return)
        predicted = baseline
        drift_detected = self.drift_monitor.update(
            strategy.strategy_id,
            predicted,
            actual_return,
        )

        alpha = max(0.05, min(config.drift_baseline_alpha, 0.9))
        self._performance_baseline[strategy.strategy_id] = (
            1 - alpha
        ) * baseline + alpha * actual_return

        status = self.drift_monitor.get_status(strategy.strategy_id)
        strategy.drift_status = status

        if drift_detected:
            payload = {
                "strategy_id": strategy.strategy_id,
                "strategy_name": strategy.strategy_name,
                "timestamp": datetime.now(UTC).isoformat(),
                "baseline_return": predicted,
                "actual_return": actual_return,
                "status": status,
            }
            strategy.drift_events.append(payload)
            self._drift_events_buffer.append(payload)
            if len(self._drift_events_buffer) > 200:
                self._drift_events_buffer = self._drift_events_buffer[-200:]
            await self._log_drift_event(strategy, payload)

        if status.get("drift_detected_count", 0) >= config.drift_retrain_threshold:
            await self._trigger_emergency_retrain(strategy, data_payload, config)

    async def _trigger_emergency_retrain(
        self,
        strategy: StrategyEntry,
        data_payload: dict[str, Any],
        config: TournamentConfig,
    ) -> None:
        """Run a lightweight optimization pass when drift persists."""

        if strategy.strategy_id in self._active_retrains:
            return

        if not self.optimizer or not strategy.param_space:
            strategy.requires_emergency_retrain = True
            logger.warning(
                "Emergency retrain skipped for %s (optimizer or param space missing)",
                strategy.strategy_name,
            )
            return

        self._active_retrains.add(strategy.strategy_id)
        strategy.requires_emergency_retrain = True

        try:
            retrain_trials = max(5, min(20, config.optimization_trials // 2 or 5))
            logger.info(
                "⚠️ Drift threshold reached for %s → running emergency retrain (%s trials)",
                strategy.strategy_name,
                retrain_trials,
            )

            opt_result = await self.optimizer.optimize_strategy(
                strategy_code=strategy.strategy_code,
                data=pd.DataFrame(data_payload),
                param_space=strategy.param_space,
                n_trials=retrain_trials,
                timeout=config.optimization_timeout,
                study_name=f"drift_{strategy.strategy_id}_{datetime.now().strftime('%H%M%S')}",
            )

            strategy.optimized_params = opt_result.best_params

            if self.sandbox:
                retrain_exec = await self.sandbox.execute(
                    code=strategy.strategy_code,
                    data=data_payload,
                    params=strategy.optimized_params,
                    timeout=config.execution_timeout,
                )

                if retrain_exec.get("success"):
                    strategy.backtest_result = retrain_exec.get(
                        "metrics", strategy.backtest_result
                    )
                    strategy.errors = []
                else:
                    strategy.errors.append(
                        f"Emergency retrain execution failed: {retrain_exec.get('error')}"
                    )
            else:
                strategy.backtest_result = self._mock_backtest_result()

            logger.info("✅ Emergency retrain complete for %s", strategy.strategy_name)

        except Exception as exc:
            logger.error(
                "Emergency retrain failed for %s: %s",
                strategy.strategy_name,
                exc,
            )
            strategy.errors.append(f"Emergency retrain error: {exc}")
        finally:
            self._active_retrains.discard(strategy.strategy_id)

    async def _log_drift_event(
        self,
        strategy: StrategyEntry,
        payload: dict[str, Any],
    ) -> None:
        """Persist drift events to the knowledge base for later analysis."""

        if not self.reasoning_storage:
            return

        try:
            await self.reasoning_storage.store_reasoning_trace(
                agent_type="tournament_orchestrator",
                task_type="drift_monitoring",
                input_prompt=(
                    f"Monitor drift for {strategy.strategy_name} during tournament"
                ),
                reasoning_chain=payload,
                final_conclusion=(
                    f"Drift count={payload['status'].get('drift_detected_count', 0)}"
                ),
                processing_time=strategy.execution_time,
            )
        except Exception as exc:
            logger.error("Failed to log drift event: %s", exc)

    def _calculate_scores(
        self,
        strategies: list[StrategyEntry],
        config: TournamentConfig,
        market_regime: str | None = None,
    ):
        """Calculate weighted scores for all strategies"""
        for strategy in strategies:
            if not strategy.backtest_result or strategy.errors:
                strategy.final_score = -999.0  # Penalty for failed strategies
                continue

            result = strategy.backtest_result
            weights = config.scoring_weights

            # Base score calculation
            score = 0.0

            # Sharpe Ratio (normalize to 0-1, typical range -2 to 4)
            sharpe = result.get("sharpe_ratio", 0)
            sharpe_normalized = max(0, min((sharpe + 2) / 6, 1))
            score += sharpe_normalized * weights.get("sharpe_ratio", 0.3)

            # Total Return (normalize to 0-1, typical range -50% to +100%)
            total_return = result.get("total_return", 0)
            return_normalized = max(0, min((total_return + 0.5) / 1.5, 1))
            score += return_normalized * weights.get("total_return", 0.25)

            # Max Drawdown (invert and normalize, typical range 0-50%)
            max_dd = abs(result.get("max_drawdown", 0.5))
            dd_normalized = 1 - min(max_dd / 0.5, 1)
            score += dd_normalized * weights.get("max_drawdown", 0.2)

            # Win Rate (already 0-1)
            win_rate = result.get("win_rate", 0)
            score += win_rate * weights.get("win_rate", 0.15)

            # Sortino Ratio (normalize to 0-1, typical range -2 to 4)
            sortino = result.get("sortino_ratio", 0)
            sortino_normalized = max(0, min((sortino + 2) / 6, 1))
            score += sortino_normalized * weights.get("sortino_ratio", 0.1)

            # Market regime adjustment (optional)
            if config.regime_aware_scoring and market_regime:
                score = self._adjust_score_for_regime(score, result, market_regime)

            strategy.final_score = score
            logger.debug(f"{strategy.strategy_name}: score = {score:.4f}")

    def _adjust_score_for_regime(
        self, score: float, result: dict[str, Any], market_regime: str
    ) -> float:
        """Adjust score based on market regime"""
        # Bonus/penalty based on strategy performance in current regime

        if market_regime in ["trending_up", "trending_down"]:
            # Bonus for trend-following strategies
            if result.get("trend_alignment", 0) > 0.5:
                score *= 1.1

        elif market_regime == "ranging":
            # Bonus for mean-reversion strategies
            if result.get("mean_reversion_score", 0) > 0.5:
                score *= 1.1

        elif market_regime == "volatile":
            # Penalty for high-frequency strategies
            if result.get("trade_frequency", 0) > 10:
                score *= 0.9

        return score

    def _assign_rankings(self, strategies: list[StrategyEntry]):
        """Assign rankings based on final scores"""
        # Sort by score (descending)
        strategies.sort(key=lambda s: s.final_score, reverse=True)

        # Assign ranks
        for i, strategy in enumerate(strategies, start=1):
            strategy.rank = i

    def _mock_backtest_result(self) -> dict[str, Any]:
        """Generate mock backtest result for testing"""
        return {
            "sharpe_ratio": np.random.uniform(-1, 3),
            "total_return": np.random.uniform(-0.2, 0.5),
            "max_drawdown": np.random.uniform(0.05, 0.30),
            "win_rate": np.random.uniform(0.3, 0.7),
            "sortino_ratio": np.random.uniform(-1, 3),
            "total_trades": int(np.random.uniform(10, 100)),
            "profit_factor": np.random.uniform(0.5, 2.5),
        }

    async def _store_tournament_trace(
        self, result: TournamentResult, config: TournamentConfig
    ):
        """Store tournament in Knowledge Base"""
        if not self.reasoning_storage:
            return

        try:
            # Prepare reasoning chain
            reasoning_chain = {
                "tournament_id": result.tournament_id,
                "tournament_name": result.tournament_name,
                "total_participants": result.total_participants,
                "optimization_enabled": config.enable_optimization,
                "market_regime": result.market_regime,
                "market_regime_confidence": result.market_regime_confidence,
                "winner": {
                    "strategy_name": result.winner.strategy_name,
                    "final_score": result.winner.final_score,
                    "params": result.winner.optimized_params
                    or result.winner.initial_params,
                }
                if result.winner
                else None,
                "top_3": [
                    {
                        "rank": s.rank,
                        "strategy_name": s.strategy_name,
                        "final_score": s.final_score,
                    }
                    for s in result.top_3
                ],
                "drift_snapshot": result.drift_snapshot,
                "timing": {
                    "optimization_time": result.optimization_time,
                    "execution_time": result.execution_time,
                    "total_duration": result.total_duration,
                },
            }

            await self.reasoning_storage.store_reasoning_trace(
                agent_type="tournament_orchestrator",
                task_type="strategy_tournament",
                input_prompt=f"Run tournament: {result.tournament_name} with {result.total_participants} strategies",
                reasoning_chain=reasoning_chain,
                final_conclusion=f"Winner: {result.winner.strategy_name if result.winner else 'None'}, Score: {result.winner.final_score if result.winner else 0:.4f}",
                processing_time=result.total_duration,
            )

            logger.info("Tournament trace stored in Knowledge Base")

        except Exception as e:
            logger.error(f"Failed to store tournament trace: {e}")

    async def _store_tournament_result(self, result: TournamentResult):
        """Store tournament in database"""
        if not self.tournament_storage:
            return

        try:
            await self.tournament_storage.store_tournament(result)
            logger.info("Tournament result stored in database")
        except Exception as e:
            logger.error(f"Failed to store tournament result: {e}")

    def get_tournament_status(self, tournament_id: str) -> TournamentResult | None:
        """Get status of active tournament"""
        return self._active_tournaments.get(tournament_id)

    async def cancel_tournament(self, tournament_id: str) -> bool:
        """Cancel active tournament"""
        tournament = self._active_tournaments.get(tournament_id)
        if tournament:
            tournament.status = TournamentStatus.CANCELLED
            logger.info(f"Tournament {tournament_id} cancelled")
            return True
        return False


# Example usage
if __name__ == "__main__":

    async def example():
        from backend.ml import MarketRegimeDetector, StrategyOptimizer

        # Initialize orchestrator
        orchestrator = TournamentOrchestrator(
            optimizer=StrategyOptimizer(), regime_detector=MarketRegimeDetector()
        )

        # Mock data
        data = pd.DataFrame(
            {
                "open": np.random.rand(200),
                "high": np.random.rand(200),
                "low": np.random.rand(200),
                "close": np.random.rand(200),
                "volume": np.random.rand(200),
            }
        )

        # Define strategies
        strategies = [
            StrategyEntry(
                strategy_id="rsi_1",
                strategy_name="RSI Strategy",
                strategy_code="# RSI code here",
                param_space={"rsi_period": {"type": "int", "low": 10, "high": 30}},
            ),
            StrategyEntry(
                strategy_id="ma_1",
                strategy_name="MA Crossover",
                strategy_code="# MA code here",
                param_space={
                    "fast_period": {"type": "int", "low": 5, "high": 20},
                    "slow_period": {"type": "int", "low": 20, "high": 50},
                },
            ),
        ]

        # Run tournament
        result = await orchestrator.run_tournament(
            strategies=strategies,
            data=data,
            config=TournamentConfig(
                tournament_name="Example Tournament",
                enable_optimization=False,  # Disable for quick test
                max_workers=2,
            ),
        )

        print("\n✅ Tournament Complete!")
        print(f"Winner: {result.winner.strategy_name if result.winner else 'None'}")
        print(f"Score: {result.winner.final_score:.4f}" if result.winner else "")
        print(f"Market Regime: {result.market_regime}")
        print(f"Duration: {result.total_duration:.1f}s")

        print("\n📊 Rankings:")
        for strategy in result.participants[:5]:
            print(
                f"  #{strategy.rank}: {strategy.strategy_name} - {strategy.final_score:.4f}"
            )

    asyncio.run(example())
