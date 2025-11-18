"""
Tournament Orchestrator - координирует соревнования стратегий с ML оптимизацией

Quick Win #3: Tournament + ML Integration
Объединяет: Sandbox, Optuna, Market Regime Detection, Knowledge Base
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import pandas as pd
import numpy as np


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
    initial_params: Dict[str, Any] = field(default_factory=dict)
    optimized_params: Optional[Dict[str, Any]] = None
    param_space: Optional[Dict[str, Dict[str, Any]]] = None
    
    # Results
    backtest_result: Optional[Dict[str, Any]] = None
    final_score: float = 0.0
    rank: Optional[int] = None
    execution_time: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class TournamentConfig:
    """Конфигурация турнира"""
    tournament_name: str
    
    # Optimization settings
    enable_optimization: bool = True
    optimization_trials: int = 50
    optimization_timeout: Optional[float] = None
    
    # Execution settings
    max_workers: int = 5
    execution_timeout: int = 300  # seconds per strategy
    
    # Market regime aware
    detect_market_regime: bool = True
    regime_aware_scoring: bool = True
    
    # Scoring weights
    scoring_weights: Dict[str, float] = field(default_factory=lambda: {
        "sharpe_ratio": 0.30,
        "total_return": 0.25,
        "max_drawdown": 0.20,
        "win_rate": 0.15,
        "sortino_ratio": 0.10
    })
    
    # Knowledge Base logging
    enable_kb_logging: bool = True


@dataclass
class TournamentResult:
    """Результаты турнира"""
    tournament_id: str
    tournament_name: str
    status: TournamentStatus
    
    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration: float = 0.0
    
    # Participants
    participants: List[StrategyEntry] = field(default_factory=list)
    total_participants: int = 0
    successful_backtests: int = 0
    failed_backtests: int = 0
    
    # Winner
    winner: Optional[StrategyEntry] = None
    top_3: List[StrategyEntry] = field(default_factory=list)
    
    # Market context
    market_regime: Optional[str] = None
    market_regime_confidence: float = 0.0
    
    # Metadata
    optimization_time: float = 0.0
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


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
        tournament_storage=None
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
        
        self._active_tournaments: Dict[str, TournamentResult] = {}
    
    async def run_tournament(
        self,
        strategies: List[StrategyEntry],
        data: pd.DataFrame,
        config: Optional[TournamentConfig] = None
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
        
        tournament_id = f"tournament_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        started_at = datetime.now()
        
        logger.info(f"Starting tournament: {tournament_id}")
        logger.info(f"Participants: {len(strategies)}")
        logger.info(f"Optimization: {'enabled' if config.enable_optimization else 'disabled'}")
        
        # Initialize result
        result = TournamentResult(
            tournament_id=tournament_id,
            tournament_name=config.tournament_name,
            status=TournamentStatus.RUNNING,
            started_at=started_at,
            total_participants=len(strategies),
            participants=strategies
        )
        
        self._active_tournaments[tournament_id] = result
        
        try:
            # Step 1: Market Regime Detection
            if config.detect_market_regime and self.regime_detector:
                logger.info("Detecting market regime...")
                regime_result = self.regime_detector.detect_regime(data)
                result.market_regime = regime_result.regime.value
                result.market_regime_confidence = regime_result.confidence
                logger.info(f"Market regime: {regime_result.regime.value} ({regime_result.confidence:.2%})")
            
            # Step 2: Strategy Optimization
            if config.enable_optimization and self.optimizer:
                logger.info("Starting strategy optimization phase...")
                result.status = TournamentStatus.OPTIMIZING
                opt_start = datetime.now()
                
                await self._optimize_strategies(strategies, data, config)
                
                result.optimization_time = (datetime.now() - opt_start).total_seconds()
                logger.info(f"Optimization complete: {result.optimization_time:.1f}s")
            
            # Step 3: Strategy Execution
            logger.info("Starting strategy execution phase...")
            result.status = TournamentStatus.EXECUTING
            exec_start = datetime.now()
            
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
            result.successful_backtests = sum(1 for s in strategies if s.backtest_result and not s.errors)
            result.failed_backtests = result.total_participants - result.successful_backtests
            
            # Complete
            result.status = TournamentStatus.COMPLETED
            result.completed_at = datetime.now()
            result.total_duration = (result.completed_at - started_at).total_seconds()
            
            logger.info(f"Tournament complete!")
            logger.info(f"Winner: {result.winner.strategy_name if result.winner else 'None'}")
            logger.info(f"Score: {result.winner.final_score:.4f}" if result.winner else "")
            
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
        strategies: List[StrategyEntry],
        data: pd.DataFrame,
        config: TournamentConfig
    ):
        """Optimize all strategies in parallel"""
        if not self.optimizer:
            logger.warning("Optimizer not available, skipping optimization")
            return
        
        async def optimize_one(strategy: StrategyEntry):
            """Optimize single strategy"""
            if not strategy.param_space:
                logger.warning(f"No param space for {strategy.strategy_name}, skipping optimization")
                return
            
            try:
                logger.debug(f"Optimizing: {strategy.strategy_name}")
                
                opt_result = await self.optimizer.optimize_strategy(
                    strategy_code=strategy.strategy_code,
                    data=data,
                    param_space=strategy.param_space,
                    n_trials=config.optimization_trials,
                    timeout=config.optimization_timeout
                )
                
                strategy.optimized_params = opt_result.best_params
                logger.info(f"Optimized {strategy.strategy_name}: {opt_result.best_params}")
                
            except Exception as e:
                logger.error(f"Optimization failed for {strategy.strategy_name}: {e}")
                strategy.errors.append(f"Optimization error: {str(e)}")
                strategy.optimized_params = strategy.initial_params  # Fallback
        
        # Optimize in parallel (limited by max_workers)
        semaphore = asyncio.Semaphore(config.max_workers)
        
        async def optimize_with_semaphore(strategy):
            async with semaphore:
                await optimize_one(strategy)
        
        await asyncio.gather(*[optimize_with_semaphore(s) for s in strategies])
    
    async def _execute_strategies(
        self,
        strategies: List[StrategyEntry],
        data: pd.DataFrame,
        config: TournamentConfig
    ):
        """Execute all strategies in parallel"""
        
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
                        data=data.to_dict(),
                        params=params,
                        timeout=config.execution_timeout
                    )
                    
                    if result.get("success"):
                        strategy.backtest_result = result.get("metrics", {})
                    else:
                        error_msg = result.get("error", "Unknown error")
                        strategy.errors.append(f"Execution error: {error_msg}")
                        logger.error(f"Execution failed for {strategy.strategy_name}: {error_msg}")
                else:
                    # Fallback: mock execution (for testing without sandbox)
                    logger.warning(f"No sandbox, using mock execution for {strategy.strategy_name}")
                    strategy.backtest_result = self._mock_backtest_result()
                
                strategy.execution_time = (datetime.now() - exec_start).total_seconds()
                logger.info(f"Executed {strategy.strategy_name} in {strategy.execution_time:.1f}s")
                
            except Exception as e:
                logger.error(f"Execution failed for {strategy.strategy_name}: {e}")
                strategy.errors.append(f"Execution exception: {str(e)}")
                strategy.execution_time = (datetime.now() - exec_start).total_seconds()
        
        # Execute in parallel (limited by max_workers)
        semaphore = asyncio.Semaphore(config.max_workers)
        
        async def execute_with_semaphore(strategy):
            async with semaphore:
                await execute_one(strategy)
        
        await asyncio.gather(*[execute_with_semaphore(s) for s in strategies])
    
    def _calculate_scores(
        self,
        strategies: List[StrategyEntry],
        config: TournamentConfig,
        market_regime: Optional[str] = None
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
        self,
        score: float,
        result: Dict[str, Any],
        market_regime: str
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
    
    def _assign_rankings(self, strategies: List[StrategyEntry]):
        """Assign rankings based on final scores"""
        # Sort by score (descending)
        strategies.sort(key=lambda s: s.final_score, reverse=True)
        
        # Assign ranks
        for i, strategy in enumerate(strategies, start=1):
            strategy.rank = i
    
    def _mock_backtest_result(self) -> Dict[str, Any]:
        """Generate mock backtest result for testing"""
        return {
            "sharpe_ratio": np.random.uniform(-1, 3),
            "total_return": np.random.uniform(-0.2, 0.5),
            "max_drawdown": np.random.uniform(0.05, 0.30),
            "win_rate": np.random.uniform(0.3, 0.7),
            "sortino_ratio": np.random.uniform(-1, 3),
            "total_trades": int(np.random.uniform(10, 100)),
            "profit_factor": np.random.uniform(0.5, 2.5)
        }
    
    async def _store_tournament_trace(
        self,
        result: TournamentResult,
        config: TournamentConfig
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
                    "params": result.winner.optimized_params or result.winner.initial_params
                } if result.winner else None,
                "top_3": [
                    {
                        "rank": s.rank,
                        "strategy_name": s.strategy_name,
                        "final_score": s.final_score
                    }
                    for s in result.top_3
                ],
                "timing": {
                    "optimization_time": result.optimization_time,
                    "execution_time": result.execution_time,
                    "total_duration": result.total_duration
                }
            }
            
            await self.reasoning_storage.store_reasoning_trace(
                agent_type="tournament_orchestrator",
                task_type="strategy_tournament",
                input_prompt=f"Run tournament: {result.tournament_name} with {result.total_participants} strategies",
                reasoning_chain=reasoning_chain,
                final_conclusion=f"Winner: {result.winner.strategy_name if result.winner else 'None'}, Score: {result.winner.final_score if result.winner else 0:.4f}",
                processing_time=result.total_duration
            )
            
            logger.info(f"Tournament trace stored in Knowledge Base")
            
        except Exception as e:
            logger.error(f"Failed to store tournament trace: {e}")
    
    async def _store_tournament_result(self, result: TournamentResult):
        """Store tournament in database"""
        if not self.tournament_storage:
            return
        
        try:
            await self.tournament_storage.store_tournament(result)
            logger.info(f"Tournament result stored in database")
        except Exception as e:
            logger.error(f"Failed to store tournament result: {e}")
    
    def get_tournament_status(self, tournament_id: str) -> Optional[TournamentResult]:
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
        from backend.ml import StrategyOptimizer, MarketRegimeDetector
        
        # Initialize orchestrator
        orchestrator = TournamentOrchestrator(
            optimizer=StrategyOptimizer(),
            regime_detector=MarketRegimeDetector()
        )
        
        # Mock data
        data = pd.DataFrame({
            "open": np.random.rand(200),
            "high": np.random.rand(200),
            "low": np.random.rand(200),
            "close": np.random.rand(200),
            "volume": np.random.rand(200)
        })
        
        # Define strategies
        strategies = [
            StrategyEntry(
                strategy_id="rsi_1",
                strategy_name="RSI Strategy",
                strategy_code="# RSI code here",
                param_space={
                    "rsi_period": {"type": "int", "low": 10, "high": 30}
                }
            ),
            StrategyEntry(
                strategy_id="ma_1",
                strategy_name="MA Crossover",
                strategy_code="# MA code here",
                param_space={
                    "fast_period": {"type": "int", "low": 5, "high": 20},
                    "slow_period": {"type": "int", "low": 20, "high": 50}
                }
            )
        ]
        
        # Run tournament
        result = await orchestrator.run_tournament(
            strategies=strategies,
            data=data,
            config=TournamentConfig(
                tournament_name="Example Tournament",
                enable_optimization=False,  # Disable for quick test
                max_workers=2
            )
        )
        
        print(f"\n✅ Tournament Complete!")
        print(f"Winner: {result.winner.strategy_name if result.winner else 'None'}")
        print(f"Score: {result.winner.final_score:.4f}" if result.winner else "")
        print(f"Market Regime: {result.market_regime}")
        print(f"Duration: {result.total_duration:.1f}s")
        
        print(f"\n📊 Rankings:")
        for strategy in result.participants[:5]:
            print(f"  #{strategy.rank}: {strategy.strategy_name} - {strategy.final_score:.4f}")
    
    asyncio.run(example())
