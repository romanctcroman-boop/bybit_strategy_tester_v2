"""
Monte Carlo Simulation Service for Strategy Backtesting.

Provides statistical analysis of strategy robustness through:
- Trade sequence shuffling (permutation tests)
- Return distribution bootstrapping
- Drawdown probability estimation
- Confidence interval calculation
- Risk metrics (VaR, CVaR, worst-case scenarios)

Usage:
    from backend.services.monte_carlo import MonteCarloSimulator

    simulator = MonteCarloSimulator(n_simulations=10000)
    results = simulator.analyze_strategy(backtest_results)

    # Get probability of achieving 20% return
    prob = results.probability_of_return(0.20)

    # Get 95% confidence interval for max drawdown
    dd_ci = results.drawdown_confidence_interval(0.95)
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Single trade result."""

    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    side: str  # 'long' or 'short'
    pnl: float
    pnl_pct: float

    @classmethod
    def from_dict(cls, d: dict) -> "Trade":
        """Create Trade from dictionary."""
        return cls(
            entry_time=d.get("entry_time", datetime.now(UTC)),
            exit_time=d.get("exit_time", datetime.now(UTC)),
            entry_price=float(d.get("entry_price", 0)),
            exit_price=float(d.get("exit_price", 0)),
            size=float(d.get("size", 0)),
            side=d.get("side", "long"),
            pnl=float(d.get("pnl", 0)),
            pnl_pct=float(d.get("pnl_pct", d.get("return_pct", 0))),
        )


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""

    n_simulations: int
    original_return: float
    original_sharpe: float
    original_max_drawdown: float

    # Simulated distributions
    simulated_returns: np.ndarray = field(repr=False)
    simulated_sharpes: np.ndarray = field(repr=False)
    simulated_max_drawdowns: np.ndarray = field(repr=False)
    simulated_final_capitals: np.ndarray = field(repr=False)

    # Statistics
    mean_return: float = 0.0
    std_return: float = 0.0
    median_return: float = 0.0

    mean_sharpe: float = 0.0
    mean_max_drawdown: float = 0.0

    # Risk metrics
    var_95: float = 0.0  # Value at Risk (5th percentile)
    var_99: float = 0.0  # Value at Risk (1st percentile)
    cvar_95: float = 0.0  # Conditional VaR (Expected Shortfall)

    # Probabilities
    prob_positive_return: float = 0.0
    prob_beat_benchmark: float = 0.0

    # Confidence intervals
    return_ci_95: tuple[float, float] = (0.0, 0.0)
    drawdown_ci_95: tuple[float, float] = (0.0, 0.0)

    # Worst/Best case
    worst_case_return: float = 0.0
    best_case_return: float = 0.0
    worst_case_drawdown: float = 0.0

    # Metadata
    simulation_time_ms: float = 0.0
    method: str = "permutation"

    def probability_of_return(self, target_return: float) -> float:
        """Calculate probability of achieving at least target_return."""
        if len(self.simulated_returns) == 0:
            return 0.0
        return float(np.mean(self.simulated_returns >= target_return))

    def probability_of_drawdown_less_than(self, max_dd: float) -> float:
        """Calculate probability of max drawdown being less than threshold."""
        if len(self.simulated_max_drawdowns) == 0:
            return 0.0
        return float(np.mean(np.abs(self.simulated_max_drawdowns) <= abs(max_dd)))

    def return_percentile(self, percentile: float) -> float:
        """Get return at given percentile."""
        if len(self.simulated_returns) == 0:
            return 0.0
        return float(np.percentile(self.simulated_returns, percentile))

    def drawdown_percentile(self, percentile: float) -> float:
        """Get max drawdown at given percentile."""
        if len(self.simulated_max_drawdowns) == 0:
            return 0.0
        return float(np.percentile(np.abs(self.simulated_max_drawdowns), percentile))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "n_simulations": self.n_simulations,
            "method": self.method,
            "simulation_time_ms": round(self.simulation_time_ms, 2),
            "original": {
                "return": round(self.original_return * 100, 2),
                "sharpe": round(self.original_sharpe, 3),
                "max_drawdown": round(self.original_max_drawdown * 100, 2),
            },
            "statistics": {
                "mean_return_pct": round(self.mean_return * 100, 2),
                "std_return_pct": round(self.std_return * 100, 2),
                "median_return_pct": round(self.median_return * 100, 2),
                "mean_sharpe": round(self.mean_sharpe, 3),
                "mean_max_drawdown_pct": round(self.mean_max_drawdown * 100, 2),
            },
            "risk_metrics": {
                "var_95_pct": round(self.var_95 * 100, 2),
                "var_99_pct": round(self.var_99 * 100, 2),
                "cvar_95_pct": round(self.cvar_95 * 100, 2),
            },
            "probabilities": {
                "positive_return": round(self.prob_positive_return * 100, 2),
                "beat_benchmark": round(self.prob_beat_benchmark * 100, 2),
            },
            "confidence_intervals": {
                "return_95_pct": [round(x * 100, 2) for x in self.return_ci_95],
                "drawdown_95_pct": [round(x * 100, 2) for x in self.drawdown_ci_95],
            },
            "scenarios": {
                "worst_case_return_pct": round(self.worst_case_return * 100, 2),
                "best_case_return_pct": round(self.best_case_return * 100, 2),
                "worst_case_drawdown_pct": round(self.worst_case_drawdown * 100, 2),
            },
        }


class MonteCarloSimulator:
    """
    Monte Carlo simulator for strategy backtesting analysis.

    Supports multiple simulation methods:
    - 'permutation': Shuffle trade sequence to test path-dependency
    - 'bootstrap': Sample trades with replacement
    - 'block_bootstrap': Preserve some time-series structure
    """

    def __init__(
        self,
        n_simulations: int = 10000,
        random_seed: int | None = None,
        block_size: int = 10,
    ):
        """
        Initialize Monte Carlo simulator.

        Args:
            n_simulations: Number of simulations to run
            random_seed: Random seed for reproducibility
            block_size: Block size for block bootstrap method
        """
        self.n_simulations = n_simulations
        self.random_seed = random_seed
        self.block_size = block_size

        if random_seed is not None:
            np.random.seed(random_seed)
            random.seed(random_seed)

    def analyze_strategy(
        self,
        backtest_results: dict[str, Any],
        initial_capital: float = 10000.0,
        benchmark_return: float = 0.0,
        method: str = "permutation",
    ) -> MonteCarloResult:
        """
        Run Monte Carlo analysis on backtest results.

        Args:
            backtest_results: Dictionary with backtest results including 'trades' list
            initial_capital: Starting capital
            benchmark_return: Benchmark return to compare against
            method: Simulation method ('permutation', 'bootstrap', 'block_bootstrap')

        Returns:
            MonteCarloResult with statistical analysis
        """
        import time

        start_time = time.perf_counter()

        # Extract trades
        trades_data = backtest_results.get("trades", [])
        if not trades_data:
            logger.warning("No trades in backtest results, using returns array")
            # Try to get daily returns instead
            returns = backtest_results.get("daily_returns", [])
            if not returns:
                # Generate synthetic trades from summary stats
                return self._analyze_from_summary(
                    backtest_results, initial_capital, benchmark_return
                )
            return self._analyze_from_returns(
                returns, initial_capital, benchmark_return, method
            )

        # Convert to Trade objects
        trades = [Trade.from_dict(t) if isinstance(t, dict) else t for t in trades_data]

        # Extract PnL values
        pnl_values = np.array([t.pnl for t in trades])
        pnl_pct_values = np.array([t.pnl_pct for t in trades])

        # Calculate original metrics
        original_return = float(np.sum(pnl_values) / initial_capital)
        original_sharpe = self._calculate_sharpe(pnl_pct_values)
        original_max_dd = self._calculate_max_drawdown_from_pnl(
            pnl_values, initial_capital
        )

        # Run simulations
        simulated_returns = np.zeros(self.n_simulations)
        simulated_sharpes = np.zeros(self.n_simulations)
        simulated_max_dds = np.zeros(self.n_simulations)
        simulated_finals = np.zeros(self.n_simulations)

        for i in range(self.n_simulations):
            if method == "permutation":
                sim_pnl = np.random.permutation(pnl_values)
                sim_pnl_pct = np.random.permutation(pnl_pct_values)
            elif method == "bootstrap":
                indices = np.random.choice(
                    len(pnl_values), size=len(pnl_values), replace=True
                )
                sim_pnl = pnl_values[indices]
                sim_pnl_pct = pnl_pct_values[indices]
            elif method == "block_bootstrap":
                sim_pnl, sim_pnl_pct = self._block_bootstrap(pnl_values, pnl_pct_values)
            else:
                raise ValueError(f"Unknown method: {method}")

            simulated_returns[i] = np.sum(sim_pnl) / initial_capital
            simulated_finals[i] = initial_capital + np.sum(sim_pnl)
            simulated_sharpes[i] = self._calculate_sharpe(sim_pnl_pct)
            simulated_max_dds[i] = self._calculate_max_drawdown_from_pnl(
                sim_pnl, initial_capital
            )

        # Calculate statistics
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return MonteCarloResult(
            n_simulations=self.n_simulations,
            original_return=original_return,
            original_sharpe=original_sharpe,
            original_max_drawdown=original_max_dd,
            simulated_returns=simulated_returns,
            simulated_sharpes=simulated_sharpes,
            simulated_max_drawdowns=simulated_max_dds,
            simulated_final_capitals=simulated_finals,
            mean_return=float(np.mean(simulated_returns)),
            std_return=float(np.std(simulated_returns)),
            median_return=float(np.median(simulated_returns)),
            mean_sharpe=float(np.mean(simulated_sharpes)),
            mean_max_drawdown=float(np.mean(simulated_max_dds)),
            var_95=float(np.percentile(simulated_returns, 5)),
            var_99=float(np.percentile(simulated_returns, 1)),
            cvar_95=float(
                np.mean(
                    simulated_returns[
                        simulated_returns <= np.percentile(simulated_returns, 5)
                    ]
                )
            ),
            prob_positive_return=float(np.mean(simulated_returns > 0)),
            prob_beat_benchmark=float(np.mean(simulated_returns > benchmark_return)),
            return_ci_95=(
                float(np.percentile(simulated_returns, 2.5)),
                float(np.percentile(simulated_returns, 97.5)),
            ),
            drawdown_ci_95=(
                float(np.percentile(np.abs(simulated_max_dds), 2.5)),
                float(np.percentile(np.abs(simulated_max_dds), 97.5)),
            ),
            worst_case_return=float(np.min(simulated_returns)),
            best_case_return=float(np.max(simulated_returns)),
            worst_case_drawdown=float(np.max(np.abs(simulated_max_dds))),
            simulation_time_ms=elapsed_ms,
            method=method,
        )

    def _analyze_from_returns(
        self,
        returns: list[float],
        initial_capital: float,
        benchmark_return: float,
        method: str,
    ) -> MonteCarloResult:
        """Analyze from array of returns (e.g., daily returns)."""
        import time

        start_time = time.perf_counter()

        returns_arr = np.array(returns)

        # Original metrics
        original_return = float(np.prod(1 + returns_arr) - 1)
        original_sharpe = self._calculate_sharpe(returns_arr)
        original_max_dd = self._calculate_max_drawdown_from_returns(returns_arr)

        # Simulations
        simulated_returns = np.zeros(self.n_simulations)
        simulated_sharpes = np.zeros(self.n_simulations)
        simulated_max_dds = np.zeros(self.n_simulations)
        simulated_finals = np.zeros(self.n_simulations)

        for i in range(self.n_simulations):
            if method == "permutation":
                sim_ret = np.random.permutation(returns_arr)
            else:
                indices = np.random.choice(
                    len(returns_arr), size=len(returns_arr), replace=True
                )
                sim_ret = returns_arr[indices]

            simulated_returns[i] = np.prod(1 + sim_ret) - 1
            simulated_finals[i] = initial_capital * (1 + simulated_returns[i])
            simulated_sharpes[i] = self._calculate_sharpe(sim_ret)
            simulated_max_dds[i] = self._calculate_max_drawdown_from_returns(sim_ret)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return self._create_result(
            original_return,
            original_sharpe,
            original_max_dd,
            simulated_returns,
            simulated_sharpes,
            simulated_max_dds,
            simulated_finals,
            benchmark_return,
            elapsed_ms,
            method,
        )

    def _analyze_from_summary(
        self,
        backtest_results: dict,
        initial_capital: float,
        benchmark_return: float,
    ) -> MonteCarloResult:
        """
        Analyze from summary statistics when no trade details available.
        Uses parametric bootstrap based on mean/std of returns.
        """
        import time

        start_time = time.perf_counter()

        # Extract what we can from summary
        total_return = backtest_results.get("total_return", 0)
        win_rate = backtest_results.get("win_rate", 0.5)
        total_trades = backtest_results.get("total_trades", 100)
        sharpe = backtest_results.get("sharpe_ratio", 0)
        max_dd = backtest_results.get("max_drawdown", 0)

        # Estimate per-trade return statistics
        avg_win = backtest_results.get("avg_win", 0.02)
        avg_loss = backtest_results.get("avg_loss", -0.01)

        if avg_win == 0:
            avg_win = total_return / max(total_trades * win_rate, 1)
        if avg_loss == 0:
            avg_loss = -abs(avg_win) * 0.5

        # Generate synthetic trades
        simulated_returns = np.zeros(self.n_simulations)
        simulated_sharpes = np.zeros(self.n_simulations)
        simulated_max_dds = np.zeros(self.n_simulations)
        simulated_finals = np.zeros(self.n_simulations)

        for i in range(self.n_simulations):
            # Generate random trades based on win rate
            wins = np.random.binomial(total_trades, win_rate)
            losses = total_trades - wins

            # Generate PnL with some variance
            win_pnl = wins * avg_win * np.random.normal(1, 0.2)
            loss_pnl = losses * avg_loss * np.random.normal(1, 0.2)

            sim_return = win_pnl + loss_pnl
            simulated_returns[i] = sim_return
            simulated_finals[i] = initial_capital * (1 + sim_return)

            # Estimate metrics
            daily_vol = abs(sim_return) / np.sqrt(252) if sim_return != 0 else 0.01
            simulated_sharpes[i] = sim_return / daily_vol if daily_vol > 0 else 0
            simulated_max_dds[i] = -abs(max_dd) * np.random.uniform(0.5, 1.5)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return self._create_result(
            total_return,
            sharpe,
            max_dd,
            simulated_returns,
            simulated_sharpes,
            simulated_max_dds,
            simulated_finals,
            benchmark_return,
            elapsed_ms,
            "parametric",
        )

    def _create_result(
        self,
        original_return: float,
        original_sharpe: float,
        original_max_dd: float,
        simulated_returns: np.ndarray,
        simulated_sharpes: np.ndarray,
        simulated_max_dds: np.ndarray,
        simulated_finals: np.ndarray,
        benchmark_return: float,
        elapsed_ms: float,
        method: str,
    ) -> MonteCarloResult:
        """Create MonteCarloResult from computed arrays."""
        return MonteCarloResult(
            n_simulations=self.n_simulations,
            original_return=original_return,
            original_sharpe=original_sharpe,
            original_max_drawdown=original_max_dd,
            simulated_returns=simulated_returns,
            simulated_sharpes=simulated_sharpes,
            simulated_max_drawdowns=simulated_max_dds,
            simulated_final_capitals=simulated_finals,
            mean_return=float(np.mean(simulated_returns)),
            std_return=float(np.std(simulated_returns)),
            median_return=float(np.median(simulated_returns)),
            mean_sharpe=float(np.mean(simulated_sharpes)),
            mean_max_drawdown=float(np.mean(simulated_max_dds)),
            var_95=float(np.percentile(simulated_returns, 5)),
            var_99=float(np.percentile(simulated_returns, 1)),
            cvar_95=float(
                np.mean(
                    simulated_returns[
                        simulated_returns <= np.percentile(simulated_returns, 5)
                    ]
                )
            )
            if len(
                simulated_returns[
                    simulated_returns <= np.percentile(simulated_returns, 5)
                ]
            )
            > 0
            else 0,
            prob_positive_return=float(np.mean(simulated_returns > 0)),
            prob_beat_benchmark=float(np.mean(simulated_returns > benchmark_return)),
            return_ci_95=(
                float(np.percentile(simulated_returns, 2.5)),
                float(np.percentile(simulated_returns, 97.5)),
            ),
            drawdown_ci_95=(
                float(np.percentile(np.abs(simulated_max_dds), 2.5)),
                float(np.percentile(np.abs(simulated_max_dds), 97.5)),
            ),
            worst_case_return=float(np.min(simulated_returns)),
            best_case_return=float(np.max(simulated_returns)),
            worst_case_drawdown=float(np.max(np.abs(simulated_max_dds))),
            simulation_time_ms=elapsed_ms,
            method=method,
        )

    def _block_bootstrap(
        self,
        pnl_values: np.ndarray,
        pnl_pct_values: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Block bootstrap preserving some time-series structure."""
        n = len(pnl_values)
        block_size = min(self.block_size, n)
        n_blocks = int(np.ceil(n / block_size))

        # Sample blocks with replacement
        blocks = []
        pct_blocks = []
        for _ in range(n_blocks):
            start_idx = np.random.randint(0, max(1, n - block_size + 1))
            end_idx = min(start_idx + block_size, n)
            blocks.append(pnl_values[start_idx:end_idx])
            pct_blocks.append(pnl_pct_values[start_idx:end_idx])

        sim_pnl = np.concatenate(blocks)[:n]
        sim_pnl_pct = np.concatenate(pct_blocks)[:n]

        return sim_pnl, sim_pnl_pct

    @staticmethod
    def _calculate_sharpe(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio from returns array."""
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        excess_returns = returns - risk_free_rate / 252  # Assuming daily
        return float(np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252))

    @staticmethod
    def _calculate_max_drawdown_from_pnl(
        pnl_values: np.ndarray, initial_capital: float
    ) -> float:
        """Calculate max drawdown from PnL sequence."""
        equity = initial_capital + np.cumsum(pnl_values)
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        return float(np.min(drawdown)) if len(drawdown) > 0 else 0.0

    @staticmethod
    def _calculate_max_drawdown_from_returns(returns: np.ndarray) -> float:
        """Calculate max drawdown from returns sequence."""
        cumulative = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - peak) / peak
        return float(np.min(drawdown)) if len(drawdown) > 0 else 0.0


# Global instance
_monte_carlo_simulator: MonteCarloSimulator | None = None


def get_monte_carlo_simulator() -> MonteCarloSimulator:
    """Get or create the global Monte Carlo simulator instance."""
    global _monte_carlo_simulator
    if _monte_carlo_simulator is None:
        _monte_carlo_simulator = MonteCarloSimulator()
    return _monte_carlo_simulator


# Convenience function
def run_monte_carlo(
    backtest_results: dict[str, Any],
    n_simulations: int = 10000,
    initial_capital: float = 10000.0,
    method: str = "permutation",
) -> dict[str, Any]:
    """
    Run Monte Carlo simulation on backtest results.

    Returns dictionary suitable for API response.
    """
    simulator = MonteCarloSimulator(n_simulations=n_simulations)
    result = simulator.analyze_strategy(
        backtest_results=backtest_results,
        initial_capital=initial_capital,
        method=method,
    )
    return result.to_dict()
