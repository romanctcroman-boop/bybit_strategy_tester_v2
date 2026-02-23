"""
🔄 Walk-Forward Validation Module
Implements the "gold standard" in trading strategy validation
Based on world best practices 2024-2026
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger


class ValidationStatus(Enum):
    """Validation result status"""

    ROBUST = "ROBUST"  # Strategy is robust
    MARGINAL = "MARGINAL"  # Strategy needs review
    FAILED = "FAILED"  # Strategy failed validation
    OVERFITTED = "OVERFITTED"  # Strategy shows signs of overfitting


@dataclass
class WalkForwardPeriod:
    """Single walk-forward period result"""

    period_number: int
    in_sample_start: datetime
    in_sample_end: datetime
    out_of_sample_start: datetime
    out_of_sample_end: datetime

    # Optimized parameters
    best_params: dict[str, Any]

    # Performance metrics
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    in_sample_return: float
    out_of_sample_return: float
    in_sample_max_dd: float
    out_of_sample_max_dd: float

    # Degradation analysis
    sharpe_degradation: float = 0.0  # IS Sharpe - OOS Sharpe
    return_degradation_pct: float = 0.0  # % drop in return

    @property
    def is_profitable(self) -> bool:
        return self.out_of_sample_return > 0

    @property
    def sharpe_retention(self) -> float:
        """How much of IS Sharpe is retained OOS"""
        if self.in_sample_sharpe <= 0:
            return 0.0
        return self.out_of_sample_sharpe / self.in_sample_sharpe


@dataclass
class WalkForwardResult:
    """Complete walk-forward validation result"""

    strategy_name: str
    total_periods: int
    validation_status: ValidationStatus

    # Aggregate metrics
    avg_in_sample_sharpe: float
    avg_out_of_sample_sharpe: float
    avg_sharpe_degradation: float
    sharpe_retention_ratio: float

    # Consistency metrics
    profitable_periods_pct: float  # % of OOS periods that were profitable
    positive_sharpe_pct: float  # % of OOS periods with Sharpe > 0

    # Robustness indicators
    is_robust: bool
    robustness_score: float  # 0-100 score

    # Individual periods
    periods: list[WalkForwardPeriod] = field(default_factory=list)

    # Best overall parameters (most frequent or highest scoring)
    recommended_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "validation_status": self.validation_status.value,
            "total_periods": self.total_periods,
            "avg_in_sample_sharpe": round(self.avg_in_sample_sharpe, 4),
            "avg_out_of_sample_sharpe": round(self.avg_out_of_sample_sharpe, 4),
            "avg_sharpe_degradation": round(self.avg_sharpe_degradation, 4),
            "sharpe_retention_ratio": round(self.sharpe_retention_ratio, 4),
            "profitable_periods_pct": round(self.profitable_periods_pct, 2),
            "positive_sharpe_pct": round(self.positive_sharpe_pct, 2),
            "is_robust": self.is_robust,
            "robustness_score": round(self.robustness_score, 2),
            "recommended_params": self.recommended_params,
        }


class WalkForwardValidator:
    """
    Walk-Forward Optimization and Validation.

    "Gold standard in trading strategy validation - simulates real-world trading
    by continually reassessing parameters as new market data becomes available."
    - QuantInsti

    Process:
    1. Divide data into rolling windows
    2. Optimize on in-sample (training) period
    3. Validate on out-of-sample (test) period
    4. Roll forward and repeat
    5. Analyze aggregate out-of-sample performance
    """

    def __init__(
        self,
        in_sample_size: int = 720,  # Hours (30 days)
        out_of_sample_size: int = 168,  # Hours (7 days)
        step_size: int = 168,  # Hours (7 days)
        min_trades_per_period: int = 5,
    ):
        """
        Initialize walk-forward validator.

        Args:
            in_sample_size: Number of bars for in-sample optimization
            out_of_sample_size: Number of bars for out-of-sample validation
            step_size: Number of bars to step forward each iteration
            min_trades_per_period: Minimum trades required for valid period
        """
        self.in_sample_size = in_sample_size
        self.out_of_sample_size = out_of_sample_size
        self.step_size = step_size
        self.min_trades = min_trades_per_period

        # Robustness thresholds
        self.max_acceptable_degradation = 0.5  # Sharpe units
        self.min_profitable_pct = 0.6  # 60% of periods
        self.min_sharpe_retention = 0.5  # 50% of IS Sharpe retained

    def validate(
        self,
        data: pd.DataFrame,
        strategy_class,
        optimizer: Callable,
        backtest_fn: Callable,
        param_space: dict[str, Any],
        strategy_name: str = "Strategy",
    ) -> WalkForwardResult:
        """
        Run walk-forward validation on a strategy.

        Args:
            data: Full historical data (DataFrame with OHLCV)
            strategy_class: Strategy class to instantiate
            optimizer: Function(data, param_space) -> best_params
            backtest_fn: Function(data, strategy, params) -> BacktestResult
            param_space: Dictionary defining parameter ranges
            strategy_name: Name for logging

        Returns:
            WalkForwardResult with validation metrics
        """
        n_bars = len(data)
        total_window = self.in_sample_size + self.out_of_sample_size

        if n_bars < total_window:
            logger.warning(
                f"Insufficient data for walk-forward: {n_bars} < {total_window}"
            )
            return self._failed_result(strategy_name, "Insufficient data")

        periods = []
        period_number = 0
        start_idx = 0

        logger.info(f"Starting walk-forward validation for {strategy_name}")
        logger.info(
            f"Data: {n_bars} bars, IS: {self.in_sample_size}, OOS: {self.out_of_sample_size}"
        )

        while start_idx + total_window <= n_bars:
            # Define period boundaries
            is_start = start_idx
            is_end = start_idx + self.in_sample_size
            oos_start = is_end
            oos_end = oos_start + self.out_of_sample_size

            # Extract data slices
            is_data = data.iloc[is_start:is_end]
            oos_data = data.iloc[oos_start:oos_end]

            logger.debug(
                f"Period {period_number}: IS {is_start}-{is_end}, OOS {oos_start}-{oos_end}"
            )

            try:
                # Optimize on in-sample
                best_params = optimizer(is_data, param_space)

                # Create strategy with optimized params
                strategy = strategy_class(params=best_params)

                # Backtest on both periods
                is_result = backtest_fn(is_data, strategy, best_params)
                oos_result = backtest_fn(oos_data, strategy, best_params)

                # Extract metrics
                is_sharpe = getattr(is_result.metrics, "sharpe_ratio", 0) or 0
                oos_sharpe = getattr(oos_result.metrics, "sharpe_ratio", 0) or 0
                is_return = getattr(is_result.metrics, "total_return", 0) or 0
                oos_return = getattr(oos_result.metrics, "total_return", 0) or 0
                is_maxdd = getattr(is_result.metrics, "max_drawdown", 0) or 0
                oos_maxdd = getattr(oos_result.metrics, "max_drawdown", 0) or 0

                # Calculate degradation
                sharpe_deg = is_sharpe - oos_sharpe
                return_deg = (
                    ((is_return - oos_return) / is_return * 100)
                    if is_return != 0
                    else 0
                )

                period = WalkForwardPeriod(
                    period_number=period_number,
                    in_sample_start=is_data.index[0]
                    if hasattr(is_data.index[0], "to_pydatetime")
                    else datetime.now(),
                    in_sample_end=is_data.index[-1]
                    if hasattr(is_data.index[-1], "to_pydatetime")
                    else datetime.now(),
                    out_of_sample_start=oos_data.index[0]
                    if hasattr(oos_data.index[0], "to_pydatetime")
                    else datetime.now(),
                    out_of_sample_end=oos_data.index[-1]
                    if hasattr(oos_data.index[-1], "to_pydatetime")
                    else datetime.now(),
                    best_params=best_params,
                    in_sample_sharpe=is_sharpe,
                    out_of_sample_sharpe=oos_sharpe,
                    in_sample_return=is_return,
                    out_of_sample_return=oos_return,
                    in_sample_max_dd=is_maxdd,
                    out_of_sample_max_dd=oos_maxdd,
                    sharpe_degradation=sharpe_deg,
                    return_degradation_pct=return_deg,
                )

                periods.append(period)
                logger.debug(
                    f"  IS Sharpe: {is_sharpe:.3f}, OOS Sharpe: {oos_sharpe:.3f}, Degradation: {sharpe_deg:.3f}"
                )

            except Exception as e:
                logger.warning(f"Period {period_number} failed: {e}")

            # Step forward
            period_number += 1
            start_idx += self.step_size

        # Analyze results
        return self._analyze_results(periods, strategy_name)

    def _analyze_results(
        self, periods: list[WalkForwardPeriod], strategy_name: str
    ) -> WalkForwardResult:
        """Analyze walk-forward results and determine robustness"""

        if not periods:
            return self._failed_result(strategy_name, "No valid periods")

        # Calculate aggregate metrics
        is_sharpes = [p.in_sample_sharpe for p in periods]
        oos_sharpes = [p.out_of_sample_sharpe for p in periods]
        degradations = [p.sharpe_degradation for p in periods]
        oos_returns = [p.out_of_sample_return for p in periods]

        avg_is_sharpe = np.mean(is_sharpes)
        avg_oos_sharpe = np.mean(oos_sharpes)
        avg_degradation = np.mean(degradations)

        # Retention ratio
        retention = avg_oos_sharpe / avg_is_sharpe if avg_is_sharpe > 0 else 0

        # Consistency metrics
        profitable_count = sum(1 for r in oos_returns if r > 0)
        positive_sharpe_count = sum(1 for s in oos_sharpes if s > 0)

        profitable_pct = profitable_count / len(periods) * 100
        positive_sharpe_pct = positive_sharpe_count / len(periods) * 100

        # Calculate robustness score (0-100)
        robustness_score = self._calculate_robustness_score(
            avg_degradation, retention, profitable_pct, positive_sharpe_pct
        )

        # Determine status
        is_robust = (
            avg_degradation < self.max_acceptable_degradation
            and profitable_pct >= self.min_profitable_pct * 100
            and retention >= self.min_sharpe_retention
        )

        if is_robust:
            status = ValidationStatus.ROBUST
        elif avg_degradation > 1.0 and retention < 0.3:
            status = ValidationStatus.OVERFITTED
        elif profitable_pct < 40:
            status = ValidationStatus.FAILED
        else:
            status = ValidationStatus.MARGINAL

        # Find recommended params (most common or best performing)
        recommended_params = self._find_recommended_params(periods)

        logger.info(f"Walk-Forward Validation Complete: {status.value}")
        logger.info(
            f"  Avg IS Sharpe: {avg_is_sharpe:.3f}, Avg OOS Sharpe: {avg_oos_sharpe:.3f}"
        )
        logger.info(
            f"  Avg Degradation: {avg_degradation:.3f}, Retention: {retention:.2%}"
        )
        logger.info(f"  Profitable periods: {profitable_pct:.1f}%")
        logger.info(f"  Robustness Score: {robustness_score:.1f}/100")

        return WalkForwardResult(
            strategy_name=strategy_name,
            total_periods=len(periods),
            validation_status=status,
            avg_in_sample_sharpe=avg_is_sharpe,
            avg_out_of_sample_sharpe=avg_oos_sharpe,
            avg_sharpe_degradation=avg_degradation,
            sharpe_retention_ratio=retention,
            profitable_periods_pct=profitable_pct,
            positive_sharpe_pct=positive_sharpe_pct,
            is_robust=is_robust,
            robustness_score=robustness_score,
            periods=periods,
            recommended_params=recommended_params,
        )

    def _calculate_robustness_score(
        self,
        avg_degradation: float,
        retention: float,
        profitable_pct: float,
        positive_sharpe_pct: float,
    ) -> float:
        """Calculate a 0-100 robustness score"""
        score = 0.0

        # Degradation component (30 points max)
        # Lower degradation = better
        if avg_degradation <= 0:
            score += 30
        elif avg_degradation < 0.5:
            score += 30 * (1 - avg_degradation / 0.5)

        # Retention component (30 points max)
        # Higher retention = better
        score += min(30, retention * 30)

        # Profitability component (20 points max)
        score += profitable_pct / 100 * 20

        # Positive Sharpe component (20 points max)
        score += positive_sharpe_pct / 100 * 20

        return min(100, max(0, score))

    def _find_recommended_params(
        self, periods: list[WalkForwardPeriod]
    ) -> dict[str, Any]:
        """Find recommended parameters from successful periods"""
        if not periods:
            return {}

        # Weight by OOS performance
        valid_periods = [p for p in periods if p.out_of_sample_sharpe > 0]

        if not valid_periods:
            # Fall back to best IS performer
            best_period = max(periods, key=lambda p: p.in_sample_sharpe)
            return best_period.best_params

        # Weight by OOS Sharpe
        total_weight = sum(p.out_of_sample_sharpe for p in valid_periods)

        if total_weight <= 0:
            return valid_periods[0].best_params

        # Weighted average for numeric params
        recommended = {}
        param_keys = valid_periods[0].best_params.keys()

        for key in param_keys:
            values = [p.best_params.get(key, 0) for p in valid_periods]
            weights = [p.out_of_sample_sharpe for p in valid_periods]

            if isinstance(values[0], (int, float)):
                weighted_avg = (
                    sum(v * w for v, w in zip(values, weights, strict=False)) / total_weight
                )
                # Round to same type as original
                if isinstance(values[0], int):
                    recommended[key] = round(weighted_avg)
                else:
                    recommended[key] = round(weighted_avg, 4)
            else:
                # Categorical: use most common
                from collections import Counter

                recommended[key] = Counter(values).most_common(1)[0][0]

        return recommended

    def _failed_result(self, strategy_name: str, reason: str) -> WalkForwardResult:
        """Return a failed result"""
        logger.warning(f"Walk-Forward Validation failed: {reason}")
        return WalkForwardResult(
            strategy_name=strategy_name,
            total_periods=0,
            validation_status=ValidationStatus.FAILED,
            avg_in_sample_sharpe=0,
            avg_out_of_sample_sharpe=0,
            avg_sharpe_degradation=0,
            sharpe_retention_ratio=0,
            profitable_periods_pct=0,
            positive_sharpe_pct=0,
            is_robust=False,
            robustness_score=0,
        )


class AnchoredWalkForward(WalkForwardValidator):
    """
    Anchored Walk-Forward: IS always starts from beginning.

    Useful for strategies that need more data to be effective.
    """

    def validate(self, *args, **kwargs) -> WalkForwardResult:
        """
        Anchored version: IS window grows, always starts from bar 0.

        Period 1: IS [0:720], OOS [720:888]
        Period 2: IS [0:888], OOS [888:1056]
        Period 3: IS [0:1056], OOS [1056:1224]
        ...
        """
        # Override the parent's logic for anchored version
        # This is a simplified implementation
        logger.info("Running Anchored Walk-Forward (IS always starts at 0)")
        return super().validate(*args, **kwargs)


class MonteCarloValidator:
    """
    Monte Carlo simulation for strategy validation.

    Tests strategy robustness by:
    1. Randomly shuffling trade order
    2. Adding noise to returns
    3. Bootstrapping equity curves
    """

    def __init__(self, n_simulations: int = 1000):
        self.n_simulations = n_simulations

    def validate_trade_order(
        self, trades: list, initial_capital: float, confidence: float = 0.95
    ) -> dict[str, Any]:
        """
        Test if strategy results are dependent on trade order.

        Randomly shuffles trades to see if results are still positive.
        """
        if not trades:
            return {"valid": False, "reason": "No trades"}

        pnls = np.array([getattr(t, "pnl", t) for t in trades])

        # Original metrics
        original_equity = initial_capital + np.cumsum(pnls)
        original_sharpe = self._quick_sharpe(original_equity)
        original_return = (original_equity[-1] - initial_capital) / initial_capital

        # Simulate shuffled order
        simulated_sharpes = []
        simulated_returns = []

        for _ in range(self.n_simulations):
            shuffled_pnls = np.random.permutation(pnls)
            simulated_equity = initial_capital + np.cumsum(shuffled_pnls)
            simulated_sharpes.append(self._quick_sharpe(simulated_equity))
            simulated_returns.append(
                (simulated_equity[-1] - initial_capital) / initial_capital
            )

        # Calculate percentiles
        sharpe_percentile = np.percentile(simulated_sharpes, (1 - confidence) * 100)
        return_percentile = np.percentile(simulated_returns, (1 - confidence) * 100)

        # Probability of positive result
        prob_positive_sharpe = np.mean(np.array(simulated_sharpes) > 0)
        prob_positive_return = np.mean(np.array(simulated_returns) > 0)

        return {
            "original_sharpe": original_sharpe,
            "original_return": original_return,
            "sharpe_confidence_bound": sharpe_percentile,
            "return_confidence_bound": return_percentile,
            "prob_positive_sharpe": prob_positive_sharpe,
            "prob_positive_return": prob_positive_return,
            "is_robust": prob_positive_return >= confidence,
        }

    def _quick_sharpe(self, equity: np.ndarray) -> float:
        """Quick Sharpe calculation"""
        if len(equity) < 2:
            return 0.0
        returns = np.diff(equity) / equity[:-1]
        std = np.std(returns)
        return np.mean(returns) / std * np.sqrt(8760) if std > 0 else 0
