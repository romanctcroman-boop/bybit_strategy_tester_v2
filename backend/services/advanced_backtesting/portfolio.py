"""
Portfolio Backtesting Module

Provides multi-asset portfolio backtesting:
- Asset allocation strategies
- Correlation analysis
- Portfolio rebalancing
- Risk parity and efficient frontier
- Cross-asset momentum

Usage:
    from backend.services.advanced_backtesting.portfolio import (
        PortfolioBacktester,
        AssetAllocation,
        RebalanceStrategy,
    )

    backtester = PortfolioBacktester(assets=['BTCUSDT', 'ETHUSDT'])
    results = backtester.run(data, allocation)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class RebalanceFrequency(Enum):
    """Rebalancing frequency options."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    THRESHOLD = "threshold"  # Rebalance when drift exceeds threshold
    NEVER = "never"


class AllocationMethod(Enum):
    """Asset allocation methods."""

    EQUAL_WEIGHT = "equal_weight"
    MARKET_CAP = "market_cap"
    RISK_PARITY = "risk_parity"
    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    CVXPORTFOLIO = "cvxportfolio"  # Cvxportfolio convex optimization (optional)
    MOMENTUM = "momentum"
    CUSTOM = "custom"


@dataclass
class AssetAllocation:
    """Asset allocation configuration."""

    # Weights by asset
    weights: dict[str, float] = field(default_factory=dict)

    # Method used
    method: AllocationMethod = AllocationMethod.EQUAL_WEIGHT

    # Constraints
    min_weight: float = 0.0
    max_weight: float = 1.0
    target_volatility: float | None = None

    # Risk parity params
    risk_budget: dict[str, float] | None = None

    # Momentum params
    lookback_period: int = 30  # days

    def normalize(self):
        """Normalize weights to sum to 1."""
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "method": self.method.value,
            "min_weight": self.min_weight,
            "max_weight": self.max_weight,
            "target_volatility": self.target_volatility,
        }


@dataclass
class RebalanceStrategy:
    """Portfolio rebalancing strategy."""

    frequency: RebalanceFrequency = RebalanceFrequency.MONTHLY
    threshold: float = 0.05  # 5% drift threshold for threshold-based

    # Costs
    rebalance_cost: float = 0.001  # 0.1% per rebalance
    min_trade_size: float = 100.0  # Minimum trade in USD

    # Execution
    execution_delay: int = 0  # Bars delay for execution

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "frequency": self.frequency.value,
            "threshold": self.threshold,
            "rebalance_cost": self.rebalance_cost,
            "min_trade_size": self.min_trade_size,
        }


@dataclass
class CorrelationAnalysis:
    """Correlation analysis results."""

    # Correlation matrix
    correlation_matrix: dict[str, dict[str, float]] = field(default_factory=dict)

    # Rolling correlations
    rolling_correlations: dict[str, list[float]] = field(default_factory=dict)

    # Key metrics
    avg_correlation: float = 0.0
    max_correlation: float = 0.0
    min_correlation: float = 0.0

    # Pairs
    most_correlated_pair: tuple[str, str] = ("", "")
    least_correlated_pair: tuple[str, str] = ("", "")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        out: dict[str, Any] = {
            "correlation_matrix": self.correlation_matrix,
            "statistics": {
                "avg_correlation": round(self.avg_correlation, 4),
                "max_correlation": round(self.max_correlation, 4),
                "min_correlation": round(self.min_correlation, 4),
            },
            "pairs": {
                "most_correlated": list(self.most_correlated_pair),
                "least_correlated": list(self.least_correlated_pair),
            },
        }
        if self.rolling_correlations:
            out["rolling_correlations"] = self.rolling_correlations
        return out


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics."""

    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0

    # Risk
    volatility: float = 0.0
    max_drawdown: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Portfolio specific
    diversification_ratio: float = 0.0
    concentration_ratio: float = 0.0  # Herfindahl index
    turnover: float = 0.0

    # By asset
    asset_contributions: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "returns": {
                "total_return_pct": round(self.total_return * 100, 2),
                "annualized_return_pct": round(self.annualized_return * 100, 2),
            },
            "risk": {
                "volatility_pct": round(self.volatility * 100, 2),
                "max_drawdown_pct": round(self.max_drawdown * 100, 2),
                "var_95_pct": round(self.var_95 * 100, 2),
                "cvar_95_pct": round(self.cvar_95 * 100, 2),
            },
            "risk_adjusted": {
                "sharpe_ratio": round(self.sharpe_ratio, 3),
                "sortino_ratio": round(self.sortino_ratio, 3),
                "calmar_ratio": round(self.calmar_ratio, 3),
            },
            "portfolio": {
                "diversification_ratio": round(self.diversification_ratio, 3),
                "concentration_ratio": round(self.concentration_ratio, 3),
                "turnover_pct": round(self.turnover * 100, 2),
            },
            "asset_contributions": {
                k: round(v * 100, 2) for k, v in self.asset_contributions.items()
            },
        }


class PortfolioBacktester:
    """
    Multi-asset portfolio backtester.

    Features:
    - Multiple allocation methods
    - Automatic rebalancing
    - Correlation analysis
    - Risk metrics calculation
    - Attribution analysis
    """

    def __init__(
        self,
        assets: list[str],
        initial_capital: float = 10000.0,
        commission: float = 0.0007,  # 0.07% TradingView parity
    ):
        """
        Initialize portfolio backtester.

        Args:
            assets: List of asset symbols
            initial_capital: Starting capital
            commission: Trading commission rate
        """
        self.assets = assets
        self.initial_capital = initial_capital
        self.commission = commission

        # State
        self.capital = initial_capital
        self.positions: dict[str, float] = dict.fromkeys(assets, 0.0)
        self.weights: dict[str, float] = dict.fromkeys(assets, 0.0)

        # Tracking
        self.equity_curve: list[float] = []
        self.weight_history: list[dict[str, float]] = []
        self.rebalance_events: list[dict] = []
        self.trade_log: list[dict] = []

        logger.info(f"PortfolioBacktester initialized with {len(assets)} assets")

    def reset(self):
        """Reset backtester state."""
        self.capital = self.initial_capital
        self.positions = dict.fromkeys(self.assets, 0.0)
        self.weights = dict.fromkeys(self.assets, 0.0)
        self.equity_curve.clear()
        self.weight_history.clear()
        self.rebalance_events.clear()
        self.trade_log.clear()

    def run(
        self,
        data: dict[str, list[dict]],  # Asset -> candles
        allocation: AssetAllocation,
        rebalance_strategy: RebalanceStrategy | None = None,
    ) -> dict[str, Any]:
        """
        Run portfolio backtest.

        Args:
            data: Dictionary mapping asset symbols to candle lists
            allocation: Initial asset allocation
            rebalance_strategy: Rebalancing strategy

        Returns:
            Backtest results
        """
        self.reset()
        rebalance_strategy = rebalance_strategy or RebalanceStrategy()

        start_time = datetime.now()

        # Validate data
        if not self._validate_data(data):
            return {"error": "Invalid or misaligned data"}

        # Get aligned length
        min_length = min(len(candles) for candles in data.values())

        # Initialize allocation
        if allocation.method != AllocationMethod.CUSTOM:
            allocation = self._calculate_allocation(data, allocation.method)

        allocation.normalize()
        self._execute_initial_allocation(allocation, data)

        # Track rebalance timing
        last_rebalance = 0
        rebalance_interval = self._get_rebalance_interval(rebalance_strategy.frequency)

        # Run backtest
        for i in range(min_length):
            # Get current prices
            prices = {asset: data[asset][i].get("close", 0) for asset in self.assets}

            # Update portfolio value
            portfolio_value = self._calculate_portfolio_value(prices)
            self.equity_curve.append(portfolio_value)

            # Update current weights
            self._update_weights(prices, portfolio_value)
            self.weight_history.append(self.weights.copy())

            # Check for rebalance
            should_rebalance = self._should_rebalance(
                i, last_rebalance, rebalance_interval, rebalance_strategy, allocation
            )

            if should_rebalance:
                self._rebalance(allocation, prices, i, rebalance_strategy)
                last_rebalance = i

        # Calculate final metrics
        duration = (datetime.now() - start_time).total_seconds()

        # Get return series
        returns = self._calculate_returns()

        # Correlation analysis
        correlation = self.analyze_correlations(data)

        # Portfolio metrics (pass data for diversification ratio)
        metrics = self._calculate_metrics(returns, data)

        return {
            "status": "completed",
            "config": {
                "assets": self.assets,
                "initial_capital": self.initial_capital,
                "allocation_method": allocation.method.value,
                "rebalance_frequency": rebalance_strategy.frequency.value,
            },
            "performance": metrics.to_dict(),
            "allocation": {
                "initial": allocation.to_dict(),
                "final": {k: round(v, 4) for k, v in self.weights.items()},
            },
            "correlation": correlation.to_dict(),
            "rebalance_events": self.rebalance_events,
            "equity_curve": self.equity_curve,
            "weight_history": self.weight_history[-100:],  # Last 100
            "duration_seconds": round(duration, 2),
        }

    def _validate_data(self, data: dict[str, list[dict]]) -> bool:
        """Validate input data."""
        if not data:
            return False

        for asset in self.assets:
            if asset not in data:
                logger.error(f"Missing data for asset: {asset}")
                return False
            if not data[asset]:
                logger.error(f"Empty data for asset: {asset}")
                return False

        return True

    def _calculate_allocation(
        self,
        data: dict[str, list[dict]],
        method: AllocationMethod,
    ) -> AssetAllocation:
        """Calculate allocation based on method."""
        allocation = AssetAllocation(method=method)

        if method == AllocationMethod.EQUAL_WEIGHT:
            weight = 1.0 / len(self.assets)
            allocation.weights = dict.fromkeys(self.assets, weight)

        elif method == AllocationMethod.RISK_PARITY:
            # Calculate volatilities
            volatilities = {}
            for asset, candles in data.items():
                returns = self._calculate_asset_returns(candles)
                volatilities[asset] = np.std(returns) if len(returns) > 0 else 0.02

            # Inverse volatility weights
            total_inv_vol = sum(1 / v for v in volatilities.values() if v > 0)
            allocation.weights = {
                asset: (1 / vol) / total_inv_vol if vol > 0 else 0
                for asset, vol in volatilities.items()
            }

        elif method == AllocationMethod.MIN_VARIANCE:
            allocation = self._min_variance_allocation(data, allocation)

        elif method == AllocationMethod.MAX_SHARPE:
            allocation = self._max_sharpe_allocation(data, allocation)

        elif method == AllocationMethod.CVXPORTFOLIO:
            allocation = self._cvxportfolio_allocation(data, allocation)

        elif method == AllocationMethod.MOMENTUM:
            # Calculate momentum scores
            momentum_scores = {}
            for asset, candles in data.items():
                if len(candles) > allocation.lookback_period:
                    old_price = candles[-allocation.lookback_period].get("close", 1)
                    new_price = candles[-1].get("close", 1)
                    momentum_scores[asset] = (new_price / old_price) - 1
                else:
                    momentum_scores[asset] = 0

            # Weight by momentum (positive only)
            positive_momentum = {k: max(0, v) for k, v in momentum_scores.items()}
            total = sum(positive_momentum.values())

            if total > 0:
                allocation.weights = {
                    asset: score / total for asset, score in positive_momentum.items()
                }
            else:
                # Fall back to equal weight
                weight = 1.0 / len(self.assets)
                allocation.weights = dict.fromkeys(self.assets, weight)

        else:
            # Default to equal weight
            weight = 1.0 / len(self.assets)
            allocation.weights = dict.fromkeys(self.assets, weight)

        return allocation

    def _min_variance_allocation(
        self,
        data: dict[str, list[dict]],
        allocation: AssetAllocation,
    ) -> AssetAllocation:
        """Calculate minimum-variance portfolio weights."""
        returns_matrix, assets_list = self._build_returns_matrix(data)
        if returns_matrix is None or len(assets_list) < 2:
            weight = 1.0 / len(self.assets)
            allocation.weights = dict.fromkeys(self.assets, weight)
            return allocation

        cov = np.cov(returns_matrix.T)
        cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
        n = len(assets_list)

        try:
            from scipy.optimize import minimize

            def objective(w: np.ndarray) -> float:
                return float(w @ cov @ w)

            constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
            bounds = [(allocation.min_weight, allocation.max_weight)] * n
            x0 = np.ones(n) / n

            res = minimize(
                objective,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
            )
            if res.success:
                allocation.weights = dict(zip(assets_list, res.x, strict=False))
        except Exception:
            weight = 1.0 / n
            allocation.weights = dict.fromkeys(assets_list, weight)
        return allocation

    def _max_sharpe_allocation(
        self,
        data: dict[str, list[dict]],
        allocation: AssetAllocation,
    ) -> AssetAllocation:
        """Calculate maximum-Sharpe portfolio weights (mean-variance)."""
        returns_matrix, assets_list = self._build_returns_matrix(data)
        if returns_matrix is None or len(assets_list) < 2:
            weight = 1.0 / len(self.assets)
            allocation.weights = dict.fromkeys(self.assets, weight)
            return allocation

        mean_returns = np.mean(returns_matrix, axis=0)
        cov = np.cov(returns_matrix.T)
        cov = np.nan_to_num(cov, nan=0.01, posinf=0.01, neginf=0.01)
        np.fill_diagonal(cov, np.maximum(np.diag(cov), 1e-8))
        n = len(assets_list)

        try:
            from scipy.optimize import minimize

            def neg_sharpe(w: np.ndarray) -> float:
                port_ret = float(w @ mean_returns)
                port_vol = float(np.sqrt(w @ cov @ w))
                if port_vol < 1e-10:
                    return 0.0
                return -port_ret / port_vol

            constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
            bounds = [(allocation.min_weight, allocation.max_weight)] * n
            x0 = np.ones(n) / n

            res = minimize(
                neg_sharpe,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
            )
            if res.success:
                allocation.weights = dict(zip(assets_list, res.x, strict=False))
            else:
                weight = 1.0 / n
                allocation.weights = dict.fromkeys(assets_list, weight)
        except Exception:
            weight = 1.0 / n
            allocation.weights = dict.fromkeys(assets_list, weight)
        return allocation

    def _cvxportfolio_allocation(
        self,
        data: dict[str, list[dict]],
        allocation: AssetAllocation,
    ) -> AssetAllocation:
        """
        Max-Sharpe via cvxpy (convex reformulation). Falls back to scipy if cvxpy unavailable.
        """
        returns_matrix, assets_list = self._build_returns_matrix(data)
        if returns_matrix is None or len(assets_list) < 2:
            weight = 1.0 / len(self.assets)
            allocation.weights = dict.fromkeys(self.assets, weight)
            return allocation

        mean_returns = np.mean(returns_matrix, axis=0)
        cov = np.cov(returns_matrix.T)
        cov = np.nan_to_num(cov, nan=0.01, posinf=0.01, neginf=0.01)
        np.fill_diagonal(cov, np.maximum(np.diag(cov), 1e-8))
        n = len(assets_list)
        mu = np.asarray(mean_returns, dtype=float)

        try:
            import cvxpy as cp

            # Convex reformulation: min y'Sigma y s.t. mu'y=1, y>=0; then w = y/sum(y)
            y = cp.Variable(n)
            prob = cp.Problem(
                cp.Minimize(cp.quad_form(y, cov)),
                [
                    mu @ y == 1,
                    y >= allocation.min_weight,
                    y <= allocation.max_weight * 10,  # Relax upper for y
                ],
            )
            prob.solve(solver=cp.ECOS, verbose=False)
            if prob.status in ("optimal", "optimal_inaccurate") and y.value is not None:
                x = np.maximum(0, np.asarray(y.value).flatten())
                if np.sum(x) > 1e-10:
                    x = x / np.sum(x)
                    x = np.clip(x, allocation.min_weight, allocation.max_weight)
                    x = x / np.sum(x)
                    allocation.weights = dict(zip(assets_list, x, strict=False))
                    return allocation
        except ImportError:
            pass
        except Exception:
            logger.debug("Cvxpy optimization failed, using scipy fallback")

        return self._max_sharpe_allocation(data, allocation)

    def _build_returns_matrix(
        self,
        data: dict[str, list[dict]],
    ) -> tuple[np.ndarray | None, list[str]]:
        """Build returns matrix (T x N) and asset list for optimization."""
        asset_returns = {}
        min_length = float("inf")
        for asset in self.assets:
            if asset not in data:
                continue
            rets = self._calculate_asset_returns(data[asset])
            asset_returns[asset] = rets
            min_length = min(min_length, len(rets))

        if min_length < 2 or len(asset_returns) < 2:
            return None, list(self.assets)

        assets_list = list(asset_returns.keys())
        truncated = [asset_returns[a][: int(min_length)] for a in assets_list]
        return np.column_stack(truncated), assets_list

    def _calculate_asset_returns(self, candles: list[dict]) -> list[float]:
        """Calculate returns from candles."""
        closes = [c.get("close", 0) for c in candles]
        if len(closes) < 2:
            return []

        returns = []
        for i in range(1, len(closes)):
            if closes[i - 1] > 0:
                returns.append((closes[i] - closes[i - 1]) / closes[i - 1])

        return returns

    def _execute_initial_allocation(
        self,
        allocation: AssetAllocation,
        data: dict[str, list[dict]],
    ):
        """Execute initial portfolio allocation."""
        for asset, weight in allocation.weights.items():
            if weight > 0 and data[asset]:
                price = data[asset][0].get("close", 0)
                if price > 0:
                    value = self.initial_capital * weight
                    cost = value * self.commission
                    self.positions[asset] = (value - cost) / price
                    self.capital -= value

        self.weights = allocation.weights.copy()

    def _calculate_portfolio_value(self, prices: dict[str, float]) -> float:
        """Calculate total portfolio value."""
        position_value = sum(
            self.positions[asset] * prices.get(asset, 0) for asset in self.assets
        )
        return self.capital + position_value

    def _update_weights(self, prices: dict[str, float], total_value: float):
        """Update current weights based on prices."""
        if total_value <= 0:
            return

        for asset in self.assets:
            position_value = self.positions[asset] * prices.get(asset, 0)
            self.weights[asset] = position_value / total_value

    def _get_rebalance_interval(self, frequency: RebalanceFrequency) -> int:
        """Get rebalance interval in bars."""
        intervals = {
            RebalanceFrequency.DAILY: 1,
            RebalanceFrequency.WEEKLY: 7,
            RebalanceFrequency.MONTHLY: 30,
            RebalanceFrequency.QUARTERLY: 90,
            RebalanceFrequency.THRESHOLD: 1,  # Check every bar
            RebalanceFrequency.NEVER: float("inf"),
        }
        return intervals.get(frequency, 30)

    def _should_rebalance(
        self,
        current_bar: int,
        last_rebalance: int,
        interval: int,
        strategy: RebalanceStrategy,
        target: AssetAllocation,
    ) -> bool:
        """Determine if rebalancing should occur."""
        if strategy.frequency == RebalanceFrequency.NEVER:
            return False

        if strategy.frequency == RebalanceFrequency.THRESHOLD:
            # Check if any weight has drifted beyond threshold
            for asset in self.assets:
                current_weight = self.weights.get(asset, 0)
                target_weight = target.weights.get(asset, 0)
                drift = abs(current_weight - target_weight)
                if drift > strategy.threshold:
                    return True
            return False

        # Time-based rebalancing
        return current_bar - last_rebalance >= interval

    def _rebalance(
        self,
        target: AssetAllocation,
        prices: dict[str, float],
        bar_index: int,
        strategy: RebalanceStrategy,
    ):
        """Execute portfolio rebalancing."""
        portfolio_value = self._calculate_portfolio_value(prices)
        total_cost = 0.0

        trades = []
        for asset in self.assets:
            target_value = portfolio_value * target.weights.get(asset, 0)
            current_value = self.positions[asset] * prices.get(asset, 0)
            diff = target_value - current_value

            # Skip small trades
            if abs(diff) < strategy.min_trade_size:
                continue

            price = prices.get(asset, 0)
            if price <= 0:
                continue

            # Execute trade
            trade_size = diff / price
            trade_cost = abs(diff) * strategy.rebalance_cost

            self.positions[asset] += trade_size
            self.capital -= diff + trade_cost
            total_cost += trade_cost

            trades.append(
                {
                    "asset": asset,
                    "side": "buy" if diff > 0 else "sell",
                    "size": abs(trade_size),
                    "value": abs(diff),
                    "cost": trade_cost,
                }
            )

        # Record rebalance event
        if trades:
            self.rebalance_events.append(
                {
                    "bar_index": bar_index,
                    "portfolio_value": round(portfolio_value, 2),
                    "total_cost": round(total_cost, 4),
                    "trades": trades,
                    "weights_before": self.weights.copy(),
                    "weights_after": target.weights.copy(),
                }
            )

        self.weights = target.weights.copy()

    def _compute_diversification_ratio(
        self,
        data: dict[str, list[dict]],
        portfolio_returns: np.ndarray,
    ) -> float:
        """Diversification ratio = weighted_avg_vol / portfolio_vol."""
        returns_matrix, assets_list = self._build_returns_matrix(data)
        if returns_matrix is None or len(assets_list) < 2:
            return 1.0
        cov = np.cov(returns_matrix.T)
        cov = np.nan_to_num(cov, nan=0.01, posinf=0.01, neginf=0.01)
        np.fill_diagonal(cov, np.maximum(np.diag(cov), 1e-8))
        vols = np.sqrt(np.diag(cov))
        w = np.array([self.weights.get(a, 0) for a in assets_list])
        w = w / (w.sum() or 1.0)
        weighted_vol = float(w @ vols)
        port_vol = float(np.sqrt(w @ cov @ w))
        if port_vol < 1e-10:
            return 1.0
        return weighted_vol / port_vol

    def _calculate_returns(self) -> list[float]:
        """Calculate portfolio returns."""
        if len(self.equity_curve) < 2:
            return []

        returns = []
        for i in range(1, len(self.equity_curve)):
            if self.equity_curve[i - 1] > 0:
                ret = (
                    self.equity_curve[i] - self.equity_curve[i - 1]
                ) / self.equity_curve[i - 1]
                returns.append(ret)

        return returns

    def _calculate_metrics(
        self,
        returns: list[float],
        data: dict[str, list[dict]] | None = None,
    ) -> PortfolioMetrics:
        """Calculate portfolio metrics."""
        metrics = PortfolioMetrics()

        if not returns:
            return metrics

        returns_arr = np.array(returns)

        # Returns
        metrics.total_return = (self.equity_curve[-1] / self.initial_capital) - 1
        metrics.annualized_return = (1 + metrics.total_return) ** (
            365 / len(returns)
        ) - 1

        # Risk
        metrics.volatility = np.std(returns_arr) * np.sqrt(365)

        # Drawdown
        equity = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max
        metrics.max_drawdown = np.max(drawdowns)

        # VaR/CVaR
        sorted_returns = np.sort(returns_arr)
        var_idx = int(0.05 * len(sorted_returns))
        metrics.var_95 = sorted_returns[var_idx] if var_idx < len(sorted_returns) else 0
        metrics.cvar_95 = np.mean(sorted_returns[: max(1, var_idx)])

        # Sharpe
        mean_return = np.mean(returns_arr)
        std_return = np.std(returns_arr)
        if std_return > 0:
            metrics.sharpe_ratio = mean_return / std_return * np.sqrt(365)

        # Sortino - TradingView formula: DD = sqrt(sum(min(0, Xi))^2 / N)
        downside_sq = np.minimum(0, returns_arr) ** 2
        downside_dev = np.sqrt(downside_sq.sum() / len(returns_arr))
        if downside_dev > 0:
            metrics.sortino_ratio = mean_return / downside_dev * np.sqrt(365)

        # Calmar
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = metrics.annualized_return / metrics.max_drawdown

        # Concentration (Herfindahl index)
        weights = list(self.weights.values())
        metrics.concentration_ratio = sum(w**2 for w in weights)

        # Diversification ratio: weighted_avg_vol / portfolio_vol
        if data and len(self.assets) >= 2:
            metrics.diversification_ratio = self._compute_diversification_ratio(
                data, returns_arr
            )

        # Turnover (simplified)
        if self.rebalance_events:
            total_traded = sum(
                sum(t["value"] for t in event["trades"])
                for event in self.rebalance_events
            )
            metrics.turnover = total_traded / (
                self.initial_capital * len(returns) / 365
            )

        # Asset contributions (simplified)
        for asset in self.assets:
            metrics.asset_contributions[asset] = (
                self.weights.get(asset, 0) * metrics.total_return
            )

        return metrics

    def analyze_correlations(self, data: dict[str, list[dict]]) -> CorrelationAnalysis:
        """Analyze asset correlations."""
        analysis = CorrelationAnalysis()

        if len(self.assets) < 2:
            return analysis

        # Calculate returns for each asset
        asset_returns = {}
        min_length = float("inf")

        for asset, candles in data.items():
            returns = self._calculate_asset_returns(candles)
            asset_returns[asset] = returns
            min_length = min(min_length, len(returns))

        if min_length < 2:
            return analysis

        # Truncate to same length
        for asset in asset_returns:
            asset_returns[asset] = asset_returns[asset][: int(min_length)]

        # Calculate correlation matrix
        assets_list = list(self.assets)
        correlations = []

        for i, asset1 in enumerate(assets_list):
            row = {}
            for j, asset2 in enumerate(assets_list):
                if i == j:
                    corr = 1.0
                else:
                    r1 = np.array(asset_returns[asset1])
                    r2 = np.array(asset_returns[asset2])
                    corr = float(np.corrcoef(r1, r2)[0, 1]) if len(r1) > 0 and len(r2) > 0 else 0.0
                row[asset2] = round(corr, 4)

                if asset1 != asset2:
                    correlations.append(corr)

            analysis.correlation_matrix[asset1] = row

        # Statistics
        if correlations:
            analysis.avg_correlation = np.mean(correlations)
            analysis.max_correlation = np.max(correlations)
            analysis.min_correlation = np.min(correlations)

            # Find pairs
            max_corr = -2
            min_corr = 2
            for i, asset1 in enumerate(assets_list):
                for j, asset2 in enumerate(assets_list):
                    if i < j:
                        corr = analysis.correlation_matrix[asset1][asset2]
                        if corr > max_corr:
                            max_corr = corr
                            analysis.most_correlated_pair = (asset1, asset2)
                        if corr < min_corr:
                            min_corr = corr
                            analysis.least_correlated_pair = (asset1, asset2)

        # Rolling correlations (window=20, first pair)
        if len(assets_list) >= 2 and min_length >= 25:
            r1 = np.array(asset_returns[assets_list[0]])
            r2 = np.array(asset_returns[assets_list[1]])
            window = 20
            rolling = []
            for i in range(window, len(r1)):
                c = np.corrcoef(r1[i - window : i], r2[i - window : i])[0, 1]
                rolling.append(float(c) if not np.isnan(c) else 0.0)
            pair_key = f"{assets_list[0]}_{assets_list[1]}"
            analysis.rolling_correlations[pair_key] = [
                round(x, 4) for x in rolling[-100:]
            ]

        return analysis


def aggregate_multi_symbol_equity(
    equity_curves: dict[str, list[float]],
) -> list[float]:
    """
    Aggregate per-symbol equity curves into a combined portfolio equity.

    Handles misaligned lengths by using the last known value when a symbol
    has no data for a given bar index. Useful for combining backtest results
    from multiple symbols with different bar counts.

    Args:
        equity_curves: Mapping symbol -> list of equity values

    Returns:
        Combined equity curve (length = max of all input lengths)
    """
    if not equity_curves:
        return []
    max_len = max(len(ec) for ec in equity_curves.values())
    portfolio_equity = []
    for i in range(max_len):
        total = 0.0
        for _symbol, curve in equity_curves.items():
            if i < len(curve):
                total += curve[i]
            else:
                total += curve[-1] if curve else 0.0
        portfolio_equity.append(total)
    return portfolio_equity


def run_portfolio_backtest(
    data: dict[str, list[dict]],
    allocation_method: str = "equal_weight",
    rebalance_frequency: str = "monthly",
    initial_capital: float = 10000.0,
) -> dict[str, Any]:
    """
    Convenience function to run portfolio backtest.

    Args:
        data: Asset price data
        allocation_method: Allocation method name
        rebalance_frequency: Rebalancing frequency
        initial_capital: Starting capital

    Returns:
        Backtest results
    """
    assets = list(data.keys())
    backtester = PortfolioBacktester(assets, initial_capital)

    allocation = AssetAllocation(method=AllocationMethod(allocation_method))

    rebalance = RebalanceStrategy(frequency=RebalanceFrequency(rebalance_frequency))

    return backtester.run(data, allocation, rebalance)
