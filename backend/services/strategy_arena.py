"""
Strategy Arena - Tournament System для автоматического сравнения стратегий
Round-robin tournament с multi-metric scoring
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class TournamentStatus(str, Enum):
    """Статус турнира"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StrategyMetrics:
    """Метрики производительности стратегии"""
    strategy_id: str
    strategy_name: str
    
    # Performance metrics
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    
    # Risk metrics
    volatility: float = 0.0
    var_95: float = 0.0  # Value at Risk 95%
    
    # Execution info
    backtest_duration: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Сериализация в dict"""
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "total_return": round(self.total_return, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "volatility": round(self.volatility, 4),
            "backtest_duration": round(self.backtest_duration, 2),
            "errors": self.errors
        }


@dataclass
class TournamentResult:
    """Результат турнира"""
    tournament_id: str
    tournament_name: str
    status: TournamentStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Participants and results
    participants: List[str] = field(default_factory=list)
    strategy_metrics: Dict[str, StrategyMetrics] = field(default_factory=dict)
    
    # Rankings
    ranked_strategies: List[Tuple[str, float]] = field(default_factory=list)  # (strategy_id, score)
    winner_id: Optional[str] = None
    winner_name: Optional[str] = None
    
    # Statistics
    total_participants: int = 0
    successful_backtests: int = 0
    failed_backtests: int = 0
    
    def to_dict(self) -> Dict:
        """Сериализация в dict"""
        return {
            "tournament_id": self.tournament_id,
            "tournament_name": self.tournament_name,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "participants": self.participants,
            "strategy_metrics": {
                sid: metrics.to_dict() 
                for sid, metrics in self.strategy_metrics.items()
            },
            "ranked_strategies": [
                {"strategy_id": sid, "score": round(score, 4)}
                for sid, score in self.ranked_strategies
            ],
            "winner_id": self.winner_id,
            "winner_name": self.winner_name,
            "total_participants": self.total_participants,
            "successful_backtests": self.successful_backtests,
            "failed_backtests": self.failed_backtests
        }


class StrategyArena:
    """
    Tournament system для сравнения торговых стратегий
    
    Features:
        - Round-robin tournament (каждая стратегия vs. каждая)
        - Multi-metric weighted scoring
        - Parallel backtesting (5-10 стратегий одновременно)
        - Automatic ranking и winner selection
        - Promotion/demotion system
    
    Scoring Weights (default):
        - Sharpe Ratio: 30%
        - Sortino Ratio: 20%
        - Win Rate: 20%
        - Max Drawdown: 15% (inverted - lower is better)
        - Total Return: 15%
    
    Usage:
        arena = StrategyArena()
        result = await arena.run_tournament(
            strategies=[strategy1, strategy2, strategy3],
            tournament_name="Q4 2025 Tournament"
        )
        print(f"Winner: {result.winner_name}")
    """
    
    # Default scoring weights (must sum to 1.0)
    DEFAULT_WEIGHTS = {
        "sharpe_ratio": 0.30,
        "sortino_ratio": 0.20,
        "win_rate": 0.20,
        "max_drawdown": 0.15,  # Inverted (lower is better)
        "total_return": 0.15
    }
    
    def __init__(
        self,
        max_workers: int = 5,
        backtest_func: Optional[callable] = None,
        scoring_weights: Optional[Dict[str, float]] = None,
        use_multiprocessing: bool = True
    ):
        """
        Args:
            max_workers: Maximum concurrent backtests
            backtest_func: Custom backtest function (optional)
            scoring_weights: Custom metric weights (optional)
            use_multiprocessing: If False, run backtests sequentially (useful for testing with local functions)
        """
        self.max_workers = max_workers
        self.backtest_func = backtest_func or self._default_backtest
        self.scoring_weights = scoring_weights or self.DEFAULT_WEIGHTS
        self.use_multiprocessing = use_multiprocessing
        
        # Validate weights sum to 1.0
        weight_sum = sum(self.scoring_weights.values())
        if not np.isclose(weight_sum, 1.0, atol=0.01):
            raise ValueError(f"Scoring weights must sum to 1.0, got {weight_sum}")
        
        logger.info(f"StrategyArena initialized: max_workers={max_workers}")
        logger.info(f"Scoring weights: {self.scoring_weights}")
    
    async def run_tournament(
        self,
        strategies: List[Dict[str, Any]],
        tournament_name: str = "Strategy Tournament",
        tournament_id: Optional[str] = None
    ) -> TournamentResult:
        """
        Run tournament для списка стратегий
        
        Args:
            strategies: List of strategy configs [{"id": "...", "name": "...", "code": "...", ...}, ...]
            tournament_name: Human-readable tournament name
            tournament_id: Unique tournament ID (auto-generated if None)
        
        Returns:
            TournamentResult with rankings and winner
        """
        tournament_id = tournament_id or f"tournament_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"🏆 Starting tournament: {tournament_name} (ID: {tournament_id})")
        logger.info(f"📊 Participants: {len(strategies)}")
        
        # Initialize result
        result = TournamentResult(
            tournament_id=tournament_id,
            tournament_name=tournament_name,
            status=TournamentStatus.RUNNING,
            started_at=datetime.now(),
            participants=[s["id"] for s in strategies],
            total_participants=len(strategies)
        )
        
        try:
            # Step 1: Run backtests in parallel
            strategy_metrics = await self._run_parallel_backtests(strategies)
            result.strategy_metrics = strategy_metrics
            result.successful_backtests = len([m for m in strategy_metrics.values() if not m.errors])
            result.failed_backtests = len([m for m in strategy_metrics.values() if m.errors])
            
            # Step 2: Calculate scores
            scored_strategies = self._calculate_scores(strategy_metrics)
            
            # Step 3: Rank strategies
            result.ranked_strategies = sorted(scored_strategies.items(), key=lambda x: x[1], reverse=True)
            
            # Step 4: Select winner
            if result.ranked_strategies:
                winner_id, winner_score = result.ranked_strategies[0]
                result.winner_id = winner_id
                result.winner_name = strategy_metrics[winner_id].strategy_name
                
                logger.info(f"🥇 Winner: {result.winner_name} (score: {winner_score:.4f})")
            
            result.status = TournamentStatus.COMPLETED
            result.completed_at = datetime.now()
            
            # Log final results
            self._log_tournament_summary(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Tournament failed: {e}")
            result.status = TournamentStatus.FAILED
            result.completed_at = datetime.now()
            raise
    
    async def _run_parallel_backtests(
        self,
        strategies: List[Dict[str, Any]]
    ) -> Dict[str, StrategyMetrics]:
        """Run backtests in parallel using ProcessPoolExecutor or sequentially"""
        
        if not self.use_multiprocessing:
            # Sequential execution (useful for testing with local functions)
            logger.info(f"🔄 Running {len(strategies)} backtests sequentially")
            strategy_metrics = {}
            
            for strategy in strategies:
                strategy_id = strategy["id"]
                try:
                    metrics = self._run_single_backtest(strategy)
                    strategy_metrics[strategy_id] = metrics
                    
                    logger.info(f"✅ Backtest completed: {metrics.strategy_name} "
                               f"(Return: {metrics.total_return:.2%}, Sharpe: {metrics.sharpe_ratio:.2f})")
                except Exception as e:
                    logger.error(f"❌ Backtest failed: {strategy['name']} - {e}")
                    strategy_metrics[strategy_id] = StrategyMetrics(
                        strategy_id=strategy_id,
                        strategy_name=strategy["name"],
                        errors=[str(e)]
                    )
            
            return strategy_metrics
        
        # Parallel execution with ProcessPoolExecutor
        logger.info(f"🚀 Running {len(strategies)} backtests in parallel (max_workers={self.max_workers})")
        
        strategy_metrics = {}
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all backtest tasks
            future_to_strategy = {
                executor.submit(self._run_single_backtest, strategy): strategy
                for strategy in strategies
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_strategy):
                strategy = future_to_strategy[future]
                strategy_id = strategy["id"]
                
                try:
                    metrics = future.result()
                    strategy_metrics[strategy_id] = metrics
                    
                    logger.info(f"✅ Backtest completed: {metrics.strategy_name} "
                               f"(Return: {metrics.total_return:.2%}, Sharpe: {metrics.sharpe_ratio:.2f})")
                    
                except Exception as e:
                    logger.error(f"❌ Backtest failed: {strategy['name']} - {e}")
                    # Create failed metrics
                    strategy_metrics[strategy_id] = StrategyMetrics(
                        strategy_id=strategy_id,
                        strategy_name=strategy["name"],
                        errors=[str(e)]
                    )
        
        return strategy_metrics
    
    def _run_single_backtest(self, strategy: Dict[str, Any]) -> StrategyMetrics:
        """
        Run single backtest (executed in separate process)
        
        This method will be called by ProcessPoolExecutor
        """
        import time
        start_time = time.time()
        
        try:
            # Execute backtest function
            backtest_result = self.backtest_func(strategy)
            
            # Extract metrics from backtest result
            metrics = StrategyMetrics(
                strategy_id=strategy["id"],
                strategy_name=strategy["name"],
                total_return=backtest_result.get("total_return", 0.0),
                sharpe_ratio=backtest_result.get("sharpe_ratio", 0.0),
                sortino_ratio=backtest_result.get("sortino_ratio", 0.0),
                max_drawdown=backtest_result.get("max_drawdown", 0.0),
                win_rate=backtest_result.get("win_rate", 0.0),
                profit_factor=backtest_result.get("profit_factor", 0.0),
                total_trades=backtest_result.get("total_trades", 0),
                winning_trades=backtest_result.get("winning_trades", 0),
                losing_trades=backtest_result.get("losing_trades", 0),
                volatility=backtest_result.get("volatility", 0.0),
                backtest_duration=time.time() - start_time
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Backtest execution error: {e}")
            return StrategyMetrics(
                strategy_id=strategy["id"],
                strategy_name=strategy["name"],
                backtest_duration=time.time() - start_time,
                errors=[str(e)]
            )
    
    def _calculate_scores(
        self,
        strategy_metrics: Dict[str, StrategyMetrics]
    ) -> Dict[str, float]:
        """
        Calculate weighted scores for all strategies
        
        Score formula:
            score = Σ (normalized_metric * weight)
            
        Normalization:
            - For positive metrics (higher is better): (value - min) / (max - min)
            - For negative metrics (lower is better): (max - value) / (max - min)
        """
        
        # Filter out failed strategies
        valid_metrics = {
            sid: m for sid, m in strategy_metrics.items() 
            if not m.errors
        }
        
        if not valid_metrics:
            logger.warning("No valid strategies to score")
            return {}
        
        # Extract metric arrays for normalization
        metric_arrays = {
            "sharpe_ratio": [m.sharpe_ratio for m in valid_metrics.values()],
            "sortino_ratio": [m.sortino_ratio for m in valid_metrics.values()],
            "win_rate": [m.win_rate for m in valid_metrics.values()],
            "max_drawdown": [abs(m.max_drawdown) for m in valid_metrics.values()],  # Use absolute value
            "total_return": [m.total_return for m in valid_metrics.values()]
        }
        
        # Calculate min/max for each metric
        metric_ranges = {}
        for metric_name, values in metric_arrays.items():
            metric_ranges[metric_name] = {
                "min": np.min(values),
                "max": np.max(values),
                "range": np.max(values) - np.min(values)
            }
        
        # Calculate scores
        scores = {}
        for strategy_id, metrics in valid_metrics.items():
            score = 0.0
            
            # Sharpe Ratio (higher is better)
            if metric_ranges["sharpe_ratio"]["range"] > 0:
                normalized = (metrics.sharpe_ratio - metric_ranges["sharpe_ratio"]["min"]) / metric_ranges["sharpe_ratio"]["range"]
                score += normalized * self.scoring_weights["sharpe_ratio"]
            
            # Sortino Ratio (higher is better)
            if metric_ranges["sortino_ratio"]["range"] > 0:
                normalized = (metrics.sortino_ratio - metric_ranges["sortino_ratio"]["min"]) / metric_ranges["sortino_ratio"]["range"]
                score += normalized * self.scoring_weights["sortino_ratio"]
            
            # Win Rate (higher is better)
            if metric_ranges["win_rate"]["range"] > 0:
                normalized = (metrics.win_rate - metric_ranges["win_rate"]["min"]) / metric_ranges["win_rate"]["range"]
                score += normalized * self.scoring_weights["win_rate"]
            
            # Max Drawdown (LOWER is better - inverted)
            if metric_ranges["max_drawdown"]["range"] > 0:
                abs_dd = abs(metrics.max_drawdown)
                normalized = (metric_ranges["max_drawdown"]["max"] - abs_dd) / metric_ranges["max_drawdown"]["range"]
                score += normalized * self.scoring_weights["max_drawdown"]
            
            # Total Return (higher is better)
            if metric_ranges["total_return"]["range"] > 0:
                normalized = (metrics.total_return - metric_ranges["total_return"]["min"]) / metric_ranges["total_return"]["range"]
                score += normalized * self.scoring_weights["total_return"]
            
            scores[strategy_id] = score
        
        return scores
    
    def _default_backtest(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Default backtest function (placeholder)
        
        In production, this should call actual backtest engine
        """
        import random
        import time
        
        # Simulate backtest execution
        time.sleep(random.uniform(0.1, 0.5))
        
        # Generate mock metrics
        return {
            "total_return": random.uniform(-0.2, 0.5),
            "sharpe_ratio": random.uniform(-1.0, 3.0),
            "sortino_ratio": random.uniform(-0.5, 4.0),
            "max_drawdown": random.uniform(-0.4, -0.05),
            "win_rate": random.uniform(0.3, 0.7),
            "profit_factor": random.uniform(0.8, 2.5),
            "total_trades": random.randint(50, 500),
            "winning_trades": random.randint(20, 300),
            "losing_trades": random.randint(20, 200),
            "volatility": random.uniform(0.01, 0.05)
        }
    
    def _log_tournament_summary(self, result: TournamentResult):
        """Log tournament summary"""
        
        duration = (result.completed_at - result.started_at).total_seconds()
        
        logger.info("=" * 80)
        logger.info(f"🏆 TOURNAMENT COMPLETE: {result.tournament_name}")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration:.2f}s")
        logger.info(f"Participants: {result.total_participants}")
        logger.info(f"Successful: {result.successful_backtests}")
        logger.info(f"Failed: {result.failed_backtests}")
        logger.info("")
        logger.info("🏅 Top 5 Strategies:")
        
        for rank, (strategy_id, score) in enumerate(result.ranked_strategies[:5], 1):
            metrics = result.strategy_metrics[strategy_id]
            logger.info(f"  {rank}. {metrics.strategy_name}")
            logger.info(f"     Score: {score:.4f}")
            logger.info(f"     Return: {metrics.total_return:.2%}, Sharpe: {metrics.sharpe_ratio:.2f}, "
                       f"WinRate: {metrics.win_rate:.2%}, MaxDD: {metrics.max_drawdown:.2%}")
        
        logger.info("=" * 80)


# =============================================================================
# Convenience Functions
# =============================================================================

async def run_strategy_tournament(
    strategies: List[Dict[str, Any]],
    tournament_name: str = "Strategy Tournament",
    max_workers: int = 5,
    custom_weights: Optional[Dict[str, float]] = None,
    use_multiprocessing: bool = True
) -> TournamentResult:
    """
    Convenience function to run tournament
    
    Args:
        strategies: List of strategy configs
        tournament_name: Tournament name
        max_workers: Max parallel backtests
        custom_weights: Custom scoring weights
        use_multiprocessing: If False, run sequentially (useful for testing)
    
    Returns:
        TournamentResult
    """
    arena = StrategyArena(
        max_workers=max_workers,
        scoring_weights=custom_weights,
        use_multiprocessing=use_multiprocessing
    )
    
    result = await arena.run_tournament(
        strategies=strategies,
        tournament_name=tournament_name
    )
    
    return result
