"""
🎲 Monte Carlo Simulation Module

Provides statistical validation of trading strategy results through
randomization and confidence interval estimation.

Monte Carlo Methods:
1. Trade Sequence Shuffling - Randomize order of trades
2. Returns Bootstrapping - Sample with replacement
3. Equity Curve Simulation - Generate confidence bands
4. Drawdown Distribution - Estimate worst-case scenarios

Example Usage:
    from backend.backtesting.monte_carlo import MonteCarloSimulator

    # Create simulator from backtest trades
    mc = MonteCarloSimulator(trades=backtest_result.trades)

    # Run simulation
    result = mc.run_simulation(
        n_simulations=10000,
        confidence_levels=[0.95, 0.99],
    )

    # Access results
    print(f"95% CI for Final Equity: {result.equity_ci_95}")
    print(f"99% CI for Max Drawdown: {result.drawdown_ci_99}")
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class SimulationMethod(Enum):
    """Monte Carlo simulation methods."""

    TRADE_SHUFFLE = "trade_shuffle"  # Shuffle trade order
    BOOTSTRAP = "bootstrap"  # Sample with replacement
    BLOCK_BOOTSTRAP = "block_bootstrap"  # Preserve some serial correlation
    PARAMETRIC = "parametric"  # Assume normal distribution


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""

    # Simulation parameters
    n_simulations: int
    method: SimulationMethod
    n_trades: int

    # Final equity statistics
    mean_final_equity: float
    median_final_equity: float
    std_final_equity: float
    equity_ci_90: Tuple[float, float] = (0.0, 0.0)
    equity_ci_95: Tuple[float, float] = (0.0, 0.0)
    equity_ci_99: Tuple[float, float] = (0.0, 0.0)

    # Drawdown statistics
    mean_max_drawdown: float = 0.0
    median_max_drawdown: float = 0.0
    worst_drawdown: float = 0.0  # Worst across all simulations
    drawdown_ci_95: Tuple[float, float] = (0.0, 0.0)
    drawdown_ci_99: Tuple[float, float] = (0.0, 0.0)

    # Risk metrics
    probability_of_ruin: float = 0.0  # P(equity < ruin_threshold)
    probability_of_profit: float = 0.0  # P(final_equity > initial)
    var_95: float = 0.0  # Value at Risk (5th percentile of returns)
    cvar_95: float = 0.0  # Conditional VaR (expected shortfall)

    # Sharpe distribution
    mean_sharpe: float = 0.0
    sharpe_ci_95: Tuple[float, float] = (0.0, 0.0)

    # Percentiles
    equity_percentiles: Dict[int, float] = field(default_factory=dict)
    drawdown_percentiles: Dict[int, float] = field(default_factory=dict)

    # Raw simulation data (optional)
    all_final_equities: Optional[np.ndarray] = None
    all_max_drawdowns: Optional[np.ndarray] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "n_simulations": self.n_simulations,
            "method": self.method.value,
            "n_trades": self.n_trades,
            "mean_final_equity": round(self.mean_final_equity, 2),
            "median_final_equity": round(self.median_final_equity, 2),
            "std_final_equity": round(self.std_final_equity, 2),
            "equity_ci_90": [round(x, 2) for x in self.equity_ci_90],
            "equity_ci_95": [round(x, 2) for x in self.equity_ci_95],
            "equity_ci_99": [round(x, 2) for x in self.equity_ci_99],
            "mean_max_drawdown": round(self.mean_max_drawdown, 4),
            "median_max_drawdown": round(self.median_max_drawdown, 4),
            "worst_drawdown": round(self.worst_drawdown, 4),
            "drawdown_ci_95": [round(x, 4) for x in self.drawdown_ci_95],
            "drawdown_ci_99": [round(x, 4) for x in self.drawdown_ci_99],
            "probability_of_ruin": round(self.probability_of_ruin, 4),
            "probability_of_profit": round(self.probability_of_profit, 4),
            "var_95": round(self.var_95, 4),
            "cvar_95": round(self.cvar_95, 4),
            "mean_sharpe": round(self.mean_sharpe, 4),
            "sharpe_ci_95": [round(x, 4) for x in self.sharpe_ci_95],
            "equity_percentiles": {
                k: round(v, 2) for k, v in self.equity_percentiles.items()
            },
            "drawdown_percentiles": {
                k: round(v, 4) for k, v in self.drawdown_percentiles.items()
            },
        }


class MonteCarloSimulator:
    """
    Monte Carlo Simulator for trading strategy validation.

    Generates multiple possible equity curves by randomizing trade
    sequences to estimate confidence intervals and risk metrics.
    """

    def __init__(
        self,
        trades: Optional[List[dict]] = None,
        pnl_values: Optional[np.ndarray] = None,
        initial_capital: float = 10000.0,
        ruin_threshold: float = 0.5,  # 50% of initial capital
    ):
        """
        Initialize Monte Carlo Simulator.

        Args:
            trades: List of trade dictionaries with 'pnl' field
            pnl_values: Array of PnL values (alternative to trades)
            initial_capital: Starting capital
            ruin_threshold: Fraction of capital considered as ruin
        """
        if trades is not None:
            self.pnl_values = np.array([t.get("pnl", 0) for t in trades])
        elif pnl_values is not None:
            self.pnl_values = np.array(pnl_values)
        else:
            raise ValueError("Must provide either trades or pnl_values")

        self.initial_capital = initial_capital
        self.ruin_threshold = ruin_threshold
        self.ruin_level = initial_capital * ruin_threshold
        self.n_trades = len(self.pnl_values)

        logger.debug(
            f"MonteCarloSimulator initialized: {self.n_trades} trades, "
            f"initial={initial_capital}, ruin_level={self.ruin_level}"
        )

    def run_simulation(
        self,
        n_simulations: int = 10000,
        method: SimulationMethod = SimulationMethod.TRADE_SHUFFLE,
        block_size: int = 5,
        confidence_levels: List[float] = None,
        seed: Optional[int] = None,
        store_raw: bool = False,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.

        Args:
            n_simulations: Number of simulations to run
            method: Simulation method to use
            block_size: Block size for block bootstrap
            confidence_levels: Confidence levels for intervals
            seed: Random seed for reproducibility
            store_raw: Whether to store raw simulation data

        Returns:
            MonteCarloResult with statistics
        """
        if self.n_trades < 2:
            logger.warning("Not enough trades for Monte Carlo simulation")
            return self._empty_result(n_simulations, method)

        if confidence_levels is None:
            confidence_levels = [0.90, 0.95, 0.99]

        if seed is not None:
            np.random.seed(seed)

        logger.info(
            f"Running {n_simulations} Monte Carlo simulations "
            f"(method={method.value}, trades={self.n_trades})"
        )

        # Run simulations based on method
        if method == SimulationMethod.TRADE_SHUFFLE:
            final_equities, max_drawdowns, sharpes = self._simulate_shuffle(
                n_simulations
            )
        elif method == SimulationMethod.BOOTSTRAP:
            final_equities, max_drawdowns, sharpes = self._simulate_bootstrap(
                n_simulations
            )
        elif method == SimulationMethod.BLOCK_BOOTSTRAP:
            final_equities, max_drawdowns, sharpes = self._simulate_block_bootstrap(
                n_simulations, block_size
            )
        elif method == SimulationMethod.PARAMETRIC:
            final_equities, max_drawdowns, sharpes = self._simulate_parametric(
                n_simulations
            )
        else:
            raise ValueError(f"Unknown method: {method}")

        # Calculate statistics
        result = self._calculate_statistics(
            final_equities=final_equities,
            max_drawdowns=max_drawdowns,
            sharpes=sharpes,
            n_simulations=n_simulations,
            method=method,
            confidence_levels=confidence_levels,
            store_raw=store_raw,
        )

        logger.info(
            f"Monte Carlo complete: Mean equity=${result.mean_final_equity:.2f}, "
            f"P(profit)={result.probability_of_profit:.1%}"
        )

        return result

    def _simulate_shuffle(
        self, n_simulations: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Simulate by shuffling trade order."""
        final_equities = np.zeros(n_simulations)
        max_drawdowns = np.zeros(n_simulations)
        sharpes = np.zeros(n_simulations)

        for i in range(n_simulations):
            # Shuffle trade order
            shuffled_pnl = np.random.permutation(self.pnl_values)

            # Calculate equity curve
            equity_curve = self.initial_capital + np.cumsum(shuffled_pnl)
            equity_curve = np.insert(equity_curve, 0, self.initial_capital)

            # Final equity
            final_equities[i] = equity_curve[-1]

            # Max drawdown
            max_drawdowns[i] = self._calculate_max_drawdown(equity_curve)

            # Sharpe ratio
            sharpes[i] = self._calculate_sharpe(shuffled_pnl)

        return final_equities, max_drawdowns, sharpes

    def _simulate_bootstrap(
        self, n_simulations: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Simulate by sampling with replacement."""
        final_equities = np.zeros(n_simulations)
        max_drawdowns = np.zeros(n_simulations)
        sharpes = np.zeros(n_simulations)

        for i in range(n_simulations):
            # Sample with replacement
            indices = np.random.randint(0, self.n_trades, size=self.n_trades)
            sampled_pnl = self.pnl_values[indices]

            # Calculate equity curve
            equity_curve = self.initial_capital + np.cumsum(sampled_pnl)
            equity_curve = np.insert(equity_curve, 0, self.initial_capital)

            final_equities[i] = equity_curve[-1]
            max_drawdowns[i] = self._calculate_max_drawdown(equity_curve)
            sharpes[i] = self._calculate_sharpe(sampled_pnl)

        return final_equities, max_drawdowns, sharpes

    def _simulate_block_bootstrap(
        self, n_simulations: int, block_size: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Simulate using block bootstrap to preserve some serial correlation."""
        final_equities = np.zeros(n_simulations)
        max_drawdowns = np.zeros(n_simulations)
        sharpes = np.zeros(n_simulations)

        n_blocks = (self.n_trades + block_size - 1) // block_size

        for i in range(n_simulations):
            # Sample blocks with replacement
            sampled_pnl = []
            for _ in range(n_blocks):
                start_idx = np.random.randint(0, self.n_trades)
                for j in range(block_size):
                    idx = (start_idx + j) % self.n_trades
                    sampled_pnl.append(self.pnl_values[idx])
                    if len(sampled_pnl) >= self.n_trades:
                        break
                if len(sampled_pnl) >= self.n_trades:
                    break

            sampled_pnl = np.array(sampled_pnl[: self.n_trades])

            # Calculate equity curve
            equity_curve = self.initial_capital + np.cumsum(sampled_pnl)
            equity_curve = np.insert(equity_curve, 0, self.initial_capital)

            final_equities[i] = equity_curve[-1]
            max_drawdowns[i] = self._calculate_max_drawdown(equity_curve)
            sharpes[i] = self._calculate_sharpe(sampled_pnl)

        return final_equities, max_drawdowns, sharpes

    def _simulate_parametric(
        self, n_simulations: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Simulate assuming normal distribution of returns."""
        final_equities = np.zeros(n_simulations)
        max_drawdowns = np.zeros(n_simulations)
        sharpes = np.zeros(n_simulations)

        # Fit normal distribution to actual PnL
        mean_pnl = np.mean(self.pnl_values)
        std_pnl = np.std(self.pnl_values)

        for i in range(n_simulations):
            # Generate random PnL from fitted distribution
            random_pnl = np.random.normal(mean_pnl, std_pnl, size=self.n_trades)

            # Calculate equity curve
            equity_curve = self.initial_capital + np.cumsum(random_pnl)
            equity_curve = np.insert(equity_curve, 0, self.initial_capital)

            final_equities[i] = equity_curve[-1]
            max_drawdowns[i] = self._calculate_max_drawdown(equity_curve)
            sharpes[i] = self._calculate_sharpe(random_pnl)

        return final_equities, max_drawdowns, sharpes

    def _calculate_max_drawdown(self, equity_curve: np.ndarray) -> float:
        """Calculate maximum drawdown from equity curve."""
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak
        return float(np.max(drawdown))

    def _calculate_sharpe(
        self, pnl: np.ndarray, annualization_factor: float = np.sqrt(252)
    ) -> float:
        """Calculate Sharpe ratio from PnL series."""
        if len(pnl) < 2 or np.std(pnl) == 0:
            return 0.0
        return float(np.mean(pnl) / np.std(pnl) * annualization_factor)

    def _calculate_statistics(
        self,
        final_equities: np.ndarray,
        max_drawdowns: np.ndarray,
        sharpes: np.ndarray,
        n_simulations: int,
        method: SimulationMethod,
        confidence_levels: List[float],
        store_raw: bool,
    ) -> MonteCarloResult:
        """Calculate comprehensive statistics from simulation results."""

        # Confidence intervals for equity
        equity_ci_90 = self._percentile_ci(final_equities, 0.90)
        equity_ci_95 = self._percentile_ci(final_equities, 0.95)
        equity_ci_99 = self._percentile_ci(final_equities, 0.99)

        # Confidence intervals for drawdown
        drawdown_ci_95 = self._percentile_ci(max_drawdowns, 0.95)
        drawdown_ci_99 = self._percentile_ci(max_drawdowns, 0.99)

        # Sharpe confidence interval
        sharpe_ci_95 = self._percentile_ci(sharpes, 0.95)

        # Risk metrics
        probability_of_ruin = np.mean(final_equities < self.ruin_level)
        probability_of_profit = np.mean(final_equities > self.initial_capital)

        # Value at Risk and Conditional VaR
        returns = (final_equities - self.initial_capital) / self.initial_capital
        var_95 = float(np.percentile(returns, 5))
        cvar_95 = float(np.mean(returns[returns <= var_95]))

        # Percentiles
        percentile_levels = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        equity_percentiles = {
            p: float(np.percentile(final_equities, p)) for p in percentile_levels
        }
        drawdown_percentiles = {
            p: float(np.percentile(max_drawdowns, p)) for p in percentile_levels
        }

        return MonteCarloResult(
            n_simulations=n_simulations,
            method=method,
            n_trades=self.n_trades,
            mean_final_equity=float(np.mean(final_equities)),
            median_final_equity=float(np.median(final_equities)),
            std_final_equity=float(np.std(final_equities)),
            equity_ci_90=equity_ci_90,
            equity_ci_95=equity_ci_95,
            equity_ci_99=equity_ci_99,
            mean_max_drawdown=float(np.mean(max_drawdowns)),
            median_max_drawdown=float(np.median(max_drawdowns)),
            worst_drawdown=float(np.max(max_drawdowns)),
            drawdown_ci_95=drawdown_ci_95,
            drawdown_ci_99=drawdown_ci_99,
            probability_of_ruin=float(probability_of_ruin),
            probability_of_profit=float(probability_of_profit),
            var_95=var_95,
            cvar_95=cvar_95,
            mean_sharpe=float(np.mean(sharpes)),
            sharpe_ci_95=sharpe_ci_95,
            equity_percentiles=equity_percentiles,
            drawdown_percentiles=drawdown_percentiles,
            all_final_equities=final_equities if store_raw else None,
            all_max_drawdowns=max_drawdowns if store_raw else None,
        )

    def _percentile_ci(
        self, values: np.ndarray, confidence: float
    ) -> Tuple[float, float]:
        """Calculate confidence interval using percentiles."""
        lower_pct = (1 - confidence) / 2 * 100
        upper_pct = (1 + confidence) / 2 * 100
        return (
            float(np.percentile(values, lower_pct)),
            float(np.percentile(values, upper_pct)),
        )

    def _empty_result(
        self, n_simulations: int, method: SimulationMethod
    ) -> MonteCarloResult:
        """Return empty result for insufficient data."""
        return MonteCarloResult(
            n_simulations=n_simulations,
            method=method,
            n_trades=self.n_trades,
            mean_final_equity=self.initial_capital,
            median_final_equity=self.initial_capital,
            std_final_equity=0.0,
        )

    def generate_confidence_bands(
        self,
        n_simulations: int = 1000,
        confidence_level: float = 0.95,
        method: SimulationMethod = SimulationMethod.TRADE_SHUFFLE,
    ) -> Dict[str, np.ndarray]:
        """
        Generate confidence bands for equity curve visualization.

        Returns dictionary with:
        - 'mean': Mean equity curve
        - 'upper': Upper confidence band
        - 'lower': Lower confidence band
        - 'percentiles': Dict of percentile curves (5, 25, 50, 75, 95)
        """
        if self.n_trades < 2:
            return {
                "mean": np.array([self.initial_capital]),
                "upper": np.array([self.initial_capital]),
                "lower": np.array([self.initial_capital]),
            }

        # Generate all equity curves
        equity_curves = np.zeros((n_simulations, self.n_trades + 1))
        equity_curves[:, 0] = self.initial_capital

        for i in range(n_simulations):
            if method == SimulationMethod.TRADE_SHUFFLE:
                shuffled_pnl = np.random.permutation(self.pnl_values)
            else:  # Bootstrap
                indices = np.random.randint(0, self.n_trades, size=self.n_trades)
                shuffled_pnl = self.pnl_values[indices]

            equity_curves[i, 1:] = self.initial_capital + np.cumsum(shuffled_pnl)

        # Calculate bands
        lower_pct = (1 - confidence_level) / 2 * 100
        upper_pct = (1 + confidence_level) / 2 * 100

        return {
            "mean": np.mean(equity_curves, axis=0),
            "upper": np.percentile(equity_curves, upper_pct, axis=0),
            "lower": np.percentile(equity_curves, lower_pct, axis=0),
            "percentiles": {
                5: np.percentile(equity_curves, 5, axis=0),
                25: np.percentile(equity_curves, 25, axis=0),
                50: np.percentile(equity_curves, 50, axis=0),
                75: np.percentile(equity_curves, 75, axis=0),
                95: np.percentile(equity_curves, 95, axis=0),
            },
        }


def run_monte_carlo_analysis(
    trades: List[dict],
    initial_capital: float = 10000.0,
    n_simulations: int = 10000,
    methods: Optional[List[SimulationMethod]] = None,
) -> Dict[str, MonteCarloResult]:
    """
    Run comprehensive Monte Carlo analysis with multiple methods.

    Args:
        trades: List of trade dictionaries
        initial_capital: Starting capital
        n_simulations: Simulations per method
        methods: List of methods to use

    Returns:
        Dictionary of method name to MonteCarloResult
    """
    if methods is None:
        methods = [
            SimulationMethod.TRADE_SHUFFLE,
            SimulationMethod.BOOTSTRAP,
            SimulationMethod.BLOCK_BOOTSTRAP,
        ]

    simulator = MonteCarloSimulator(trades=trades, initial_capital=initial_capital)

    results = {}
    for method in methods:
        results[method.value] = simulator.run_simulation(
            n_simulations=n_simulations, method=method
        )

    return results
