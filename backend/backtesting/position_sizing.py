"""
Advanced Position Sizing Strategies.

Includes:
- KellyCalculator: Enhanced Kelly Criterion with fees and exponential weighting
- VolatilityPositionSizer: Volatility-adjusted position sizing
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class TradeResult:
    """Minimal trade result for position sizing calculations."""

    pnl: float
    entry_price: float
    exit_price: float
    size: float
    entry_fee: float = 0.0
    exit_fee: float = 0.0


class KellyCalculator:
    """
    Enhanced Kelly Criterion calculator with:
    - Fee-adjusted PnL
    - Exponential weighting (recent trades matter more)
    - Minimum trade requirement for statistical significance
    - Half-Kelly for safety
    - Configurable maximum position size
    """

    def __init__(
        self,
        min_trades: int = 50,
        lookback_trades: int = 100,
        use_exponential_weights: bool = True,
        decay_factor: float = 0.95,
        kelly_fraction: float = 0.5,  # Half-Kelly by default
        max_position_size: float = 0.25,  # Max 25% of capital
        min_position_size: float = 0.01,  # Min 1% of capital
    ):
        """
        Initialize Kelly Calculator.

        Args:
            min_trades: Minimum trades required for Kelly calculation
            lookback_trades: Number of recent trades to consider
            use_exponential_weights: Use exponential weighting for recent trades
            decay_factor: Decay factor for exponential weights (0.9-0.99)
            kelly_fraction: Fraction of Kelly to use (0.5 = Half-Kelly)
            max_position_size: Maximum position size as fraction of capital
            min_position_size: Minimum position size as fraction of capital
        """
        self.min_trades = min_trades
        self.lookback_trades = lookback_trades
        self.use_exponential_weights = use_exponential_weights
        self.decay_factor = decay_factor
        self.kelly_fraction = kelly_fraction
        self.max_position_size = max_position_size
        self.min_position_size = min_position_size

    def calculate(
        self,
        trades: list[TradeResult],
        taker_fee: float = 0.0007,
        default_size: float = 0.1,
    ) -> float:
        """
        Calculate optimal position size using enhanced Kelly Criterion.

        Args:
            trades: List of historical trades
            taker_fee: Taker fee rate (default 0.07% for Bybit)
            default_size: Default position size if not enough trades

        Returns:
            Optimal position size as fraction of capital
        """
        if len(trades) < self.min_trades:
            return default_size

        # Take recent trades
        recent_trades = trades[-self.lookback_trades :]

        # Calculate fee-adjusted PnLs
        adjusted_pnls = []
        for trade in recent_trades:
            # Calculate fees if not already included
            if trade.entry_fee == 0 and trade.exit_fee == 0:
                entry_fee = trade.size * trade.entry_price * taker_fee
                exit_fee = trade.size * trade.exit_price * taker_fee
                adjusted_pnl = trade.pnl - entry_fee - exit_fee
            else:
                adjusted_pnl = trade.pnl - trade.entry_fee - trade.exit_fee
            adjusted_pnls.append(adjusted_pnl)

        adjusted_pnls = np.array(adjusted_pnls)

        # Calculate weights
        if self.use_exponential_weights:
            n = len(adjusted_pnls)
            weights = np.array([self.decay_factor**i for i in range(n - 1, -1, -1)])
            weights = weights / weights.sum()
        else:
            weights = np.ones(len(adjusted_pnls)) / len(adjusted_pnls)

        # Separate wins and losses
        wins_mask = adjusted_pnls > 0
        losses_mask = adjusted_pnls <= 0

        if not np.any(wins_mask) or not np.any(losses_mask):
            # Can't calculate Kelly without both wins and losses
            return default_size

        # Weighted win rate
        win_weights = weights[wins_mask]
        loss_weights = weights[losses_mask]
        weighted_win_rate = win_weights.sum()

        # Weighted average win and loss
        wins = adjusted_pnls[wins_mask]
        losses = np.abs(adjusted_pnls[losses_mask])

        # Normalize weights for each group
        win_weights_norm = (
            win_weights / win_weights.sum() if win_weights.sum() > 0 else win_weights
        )
        loss_weights_norm = (
            loss_weights / loss_weights.sum()
            if loss_weights.sum() > 0
            else loss_weights
        )

        avg_win = np.sum(wins * win_weights_norm)
        avg_loss = np.sum(losses * loss_weights_norm)

        if avg_loss < 0.001:
            avg_loss = 0.001  # Prevent division by zero

        # Win/Loss ratio
        win_loss_ratio = avg_win / avg_loss

        # Kelly Formula: K = W - (1-W)/R
        # Where W = win rate, R = win/loss ratio
        kelly = weighted_win_rate - (1 - weighted_win_rate) / win_loss_ratio

        # Apply Kelly fraction (Half-Kelly)
        kelly = kelly * self.kelly_fraction

        # Clamp to valid range
        kelly = max(self.min_position_size, min(kelly, self.max_position_size))

        return kelly

    def get_kelly_stats(
        self,
        trades: list[TradeResult],
        taker_fee: float = 0.0007,
    ) -> dict:
        """
        Get detailed Kelly statistics for analysis.

        Args:
            trades: List of historical trades
            taker_fee: Taker fee rate

        Returns:
            Dictionary with detailed statistics
        """
        if len(trades) < self.min_trades:
            return {
                "kelly_fraction": None,
                "full_kelly": None,
                "half_kelly": None,
                "win_rate": None,
                "win_loss_ratio": None,
                "trades_analyzed": len(trades),
                "min_trades_required": self.min_trades,
                "sufficient_data": False,
            }

        recent_trades = trades[-self.lookback_trades :]

        # Calculate fee-adjusted PnLs
        adjusted_pnls = []
        for trade in recent_trades:
            if trade.entry_fee == 0 and trade.exit_fee == 0:
                entry_fee = trade.size * trade.entry_price * taker_fee
                exit_fee = trade.size * trade.exit_price * taker_fee
                adjusted_pnl = trade.pnl - entry_fee - exit_fee
            else:
                adjusted_pnl = trade.pnl - trade.entry_fee - trade.exit_fee
            adjusted_pnls.append(adjusted_pnl)

        adjusted_pnls = np.array(adjusted_pnls)

        wins = adjusted_pnls[adjusted_pnls > 0]
        losses = np.abs(adjusted_pnls[adjusted_pnls <= 0])

        if len(wins) == 0 or len(losses) == 0:
            return {
                "kelly_fraction": 0,
                "full_kelly": 0,
                "half_kelly": 0,
                "win_rate": len(wins) / len(adjusted_pnls)
                if len(adjusted_pnls) > 0
                else 0,
                "win_loss_ratio": None,
                "trades_analyzed": len(recent_trades),
                "sufficient_data": False,
            }

        win_rate = len(wins) / len(adjusted_pnls)
        avg_win = np.mean(wins)
        avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
        win_loss_ratio = avg_win / max(avg_loss, 0.001)

        full_kelly = win_rate - (1 - win_rate) / win_loss_ratio
        half_kelly = full_kelly * 0.5

        return {
            "kelly_fraction": self.calculate(trades, taker_fee),
            "full_kelly": max(0, min(full_kelly, 1.0)),
            "half_kelly": max(0, min(half_kelly, 0.5)),
            "win_rate": win_rate,
            "win_loss_ratio": win_loss_ratio,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "trades_analyzed": len(recent_trades),
            "sufficient_data": True,
        }


class MonteCarloAnalyzer:
    """
    Monte Carlo simulation for strategy robustness analysis.

    Uses bootstrap resampling of historical trades to estimate:
    - Confidence intervals for key metrics
    - Probability of achieving targets
    - Risk of ruin
    """

    def __init__(
        self,
        n_simulations: int = 1000,
        confidence_level: float = 0.95,
        random_seed: int | None = None,
    ):
        """
        Initialize Monte Carlo Analyzer.

        Args:
            n_simulations: Number of Monte Carlo simulations
            confidence_level: Confidence level for intervals (0.95 = 95%)
            random_seed: Random seed for reproducibility
        """
        self.n_simulations = n_simulations
        self.confidence_level = confidence_level
        self.random_seed = random_seed

        if random_seed is not None:
            np.random.seed(random_seed)

    def run_simulation(
        self,
        trades: list[TradeResult],
        initial_capital: float = 10000.0,
        target_return: float = 0.5,  # 50% target return
        max_drawdown_limit: float = 0.3,  # 30% max drawdown limit
    ) -> dict:
        """
        Run Monte Carlo simulation on historical trades.

        Args:
            trades: List of historical trades
            initial_capital: Starting capital
            target_return: Target return percentage for probability calculation
            max_drawdown_limit: Max drawdown limit for risk of ruin

        Returns:
            Dictionary with simulation results
        """
        if len(trades) < 10:
            return {
                "error": "Insufficient trades for Monte Carlo simulation (min 10)",
                "trades_count": len(trades),
            }

        # Extract PnLs
        pnls = np.array([t.pnl for t in trades])
        n_trades = len(pnls)

        # Run simulations
        final_returns = []
        max_drawdowns = []
        sharpe_ratios = []
        win_rates = []

        for _ in range(self.n_simulations):
            # Bootstrap resample trades with replacement
            sampled_indices = np.random.choice(n_trades, size=n_trades, replace=True)
            sampled_pnls = pnls[sampled_indices]

            # Calculate equity curve
            equity = initial_capital + np.cumsum(sampled_pnls)
            equity = np.insert(equity, 0, initial_capital)

            # Final return
            final_return = (equity[-1] - initial_capital) / initial_capital
            final_returns.append(final_return)

            # Max drawdown
            peak = np.maximum.accumulate(equity)
            drawdown = (peak - equity) / peak
            max_dd = np.max(drawdown)
            max_drawdowns.append(max_dd)

            # Win rate
            sampled_wins = np.sum(sampled_pnls > 0)
            win_rate = sampled_wins / n_trades
            win_rates.append(win_rate)

            # Sharpe ratio (simplified, daily-like returns)
            if len(sampled_pnls) > 1 and np.std(sampled_pnls) > 0:
                sharpe = np.mean(sampled_pnls) / np.std(sampled_pnls) * np.sqrt(252)
            else:
                sharpe = 0
            sharpe_ratios.append(sharpe)

        final_returns = np.array(final_returns)
        max_drawdowns = np.array(max_drawdowns)
        sharpe_ratios = np.array(sharpe_ratios)
        win_rates = np.array(win_rates)

        # Calculate confidence intervals
        alpha = 1 - self.confidence_level
        lower_pct = alpha / 2 * 100
        upper_pct = (1 - alpha / 2) * 100

        return {
            "n_simulations": self.n_simulations,
            "confidence_level": self.confidence_level,
            "trades_count": n_trades,
            "initial_capital": initial_capital,
            # Return statistics
            "return_mean": float(np.mean(final_returns)),
            "return_median": float(np.median(final_returns)),
            "return_std": float(np.std(final_returns)),
            "return_ci_lower": float(np.percentile(final_returns, lower_pct)),
            "return_ci_upper": float(np.percentile(final_returns, upper_pct)),
            "return_5th_percentile": float(np.percentile(final_returns, 5)),
            "return_95th_percentile": float(np.percentile(final_returns, 95)),
            # Drawdown statistics
            "max_drawdown_mean": float(np.mean(max_drawdowns)),
            "max_drawdown_median": float(np.median(max_drawdowns)),
            "max_drawdown_ci_lower": float(np.percentile(max_drawdowns, lower_pct)),
            "max_drawdown_ci_upper": float(np.percentile(max_drawdowns, upper_pct)),
            "max_drawdown_worst": float(np.max(max_drawdowns)),
            # Sharpe statistics
            "sharpe_mean": float(np.mean(sharpe_ratios)),
            "sharpe_median": float(np.median(sharpe_ratios)),
            "sharpe_ci_lower": float(np.percentile(sharpe_ratios, lower_pct)),
            "sharpe_ci_upper": float(np.percentile(sharpe_ratios, upper_pct)),
            # Win rate statistics
            "win_rate_mean": float(np.mean(win_rates)),
            "win_rate_ci_lower": float(np.percentile(win_rates, lower_pct)),
            "win_rate_ci_upper": float(np.percentile(win_rates, upper_pct)),
            # Probability metrics
            "probability_of_profit": float(np.mean(final_returns > 0)),
            "probability_of_target": float(np.mean(final_returns >= target_return)),
            "risk_of_ruin": float(np.mean(max_drawdowns >= max_drawdown_limit)),
            # VaR and CVaR
            "var_95": float(np.percentile(final_returns, 5)),
            "cvar_95": float(
                np.mean(final_returns[final_returns <= np.percentile(final_returns, 5)])
            ),
        }

    def run_path_simulation(
        self,
        trades: list[TradeResult],
        initial_capital: float = 10000.0,
        n_paths: int = 100,
    ) -> dict:
        """
        Run Monte Carlo path simulation for equity curve analysis.

        Args:
            trades: List of historical trades
            initial_capital: Starting capital
            n_paths: Number of equity paths to generate

        Returns:
            Dictionary with equity path statistics
        """
        if len(trades) < 10:
            return {"error": "Insufficient trades"}

        pnls = np.array([t.pnl for t in trades])
        n_trades = len(pnls)

        # Generate equity paths
        paths = []
        for _ in range(n_paths):
            sampled_indices = np.random.choice(n_trades, size=n_trades, replace=True)
            sampled_pnls = pnls[sampled_indices]
            equity = initial_capital + np.cumsum(sampled_pnls)
            equity = np.insert(equity, 0, initial_capital)
            paths.append(equity)

        paths = np.array(paths)

        # Calculate percentile bands at each trade
        return {
            "n_paths": n_paths,
            "n_trades": n_trades,
            "path_median": paths[:, -1].tolist(),
            "equity_5th_percentile": np.percentile(paths, 5, axis=0).tolist(),
            "equity_25th_percentile": np.percentile(paths, 25, axis=0).tolist(),
            "equity_50th_percentile": np.percentile(paths, 50, axis=0).tolist(),
            "equity_75th_percentile": np.percentile(paths, 75, axis=0).tolist(),
            "equity_95th_percentile": np.percentile(paths, 95, axis=0).tolist(),
            "final_equity_range": [
                float(np.min(paths[:, -1])),
                float(np.max(paths[:, -1])),
            ],
        }


class IndicatorCache:
    """
    Cache for indicator calculations to speed up optimization.

    Caches indicators based on input parameters (period, data hash).
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize indicator cache.

        Args:
            max_size: Maximum number of cached items
        """
        self.cache = {}
        self.max_size = max_size
        self.access_order = []

    def _get_data_hash(self, data: np.ndarray) -> int:
        """Get hash of numpy array for caching."""
        return hash((data.tobytes(), data.shape))

    def _make_key(self, indicator_name: str, data_hash: int, **params) -> str:
        """Create cache key from indicator name and parameters."""
        param_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{indicator_name}_{data_hash}_{param_str}"

    def get(
        self,
        indicator_name: str,
        data: np.ndarray,
        compute_func,
        **params,
    ) -> np.ndarray:
        """
        Get indicator value from cache or compute and cache it.

        Args:
            indicator_name: Name of the indicator
            data: Input data array
            compute_func: Function to compute indicator if not cached
            **params: Parameters for the indicator

        Returns:
            Computed indicator values
        """
        data_hash = self._get_data_hash(data)
        key = self._make_key(indicator_name, data_hash, **params)

        if key in self.cache:
            # Move to end of access order (LRU)
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]

        # Compute indicator
        result = compute_func(data, **params)

        # Evict oldest if at capacity
        if len(self.cache) >= self.max_size:
            oldest_key = self.access_order.pop(0)
            del self.cache[oldest_key]

        # Cache result
        self.cache[key] = result
        self.access_order.append(key)

        return result

    def clear(self):
        """Clear the cache."""
        self.cache.clear()
        self.access_order.clear()

    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "keys": list(self.cache.keys()),
        }
