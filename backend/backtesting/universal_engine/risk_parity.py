"""
Risk Parity Portfolio Module for Universal Math Engine v2.4.

This module provides advanced portfolio optimization:
1. RiskParityOptimizer - Equal risk contribution portfolio
2. HierarchicalRiskParity - Clustering-based HRP
3. MeanVarianceOptimizer - Classic Markowitz optimization
4. BlackLittermanModel - Bayesian portfolio optimization
5. RiskBudgeting - Custom risk allocation
6. DynamicRebalancer - Adaptive portfolio rebalancing

Author: Universal Math Engine Team
Version: 2.4.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

import numpy as np
from numpy.typing import NDArray
from scipy import optimize
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform

# ============================================================================
# ENUMS AND DATA STRUCTURES
# ============================================================================


class OptimizationObjective(Enum):
    """Portfolio optimization objectives."""

    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    MAX_RETURN = "max_return"
    RISK_PARITY = "risk_parity"
    MIN_CVaR = "min_cvar"
    MAX_DIVERSIFICATION = "max_diversification"


class RebalanceFrequency(Enum):
    """Portfolio rebalance frequency."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    THRESHOLD = "threshold"  # Rebalance when drift exceeds threshold


class ConstraintType(Enum):
    """Optimization constraint types."""

    LONG_ONLY = "long_only"
    BOX = "box"
    GROUP = "group"
    TURNOVER = "turnover"
    SECTOR = "sector"


@dataclass
class Asset:
    """Single asset definition."""

    symbol: str
    name: str
    sector: str = "Unknown"
    expected_return: float = 0.0
    risk_budget: float = 0.0  # Target risk contribution


@dataclass
class PortfolioConstraints:
    """Portfolio optimization constraints."""

    # Position limits
    min_weight: float = 0.0
    max_weight: float = 1.0

    # Long/short
    allow_short: bool = False
    max_short: float = 0.0

    # Leverage
    max_leverage: float = 1.0

    # Turnover
    max_turnover: float = 1.0  # Max turnover per rebalance

    # Sector constraints
    sector_limits: dict[str, tuple[float, float]] = field(default_factory=dict)

    # Number of assets
    min_assets: int = 1
    max_assets: int = 100

    # Concentration
    max_concentration: float = 1.0  # Max weight in single asset


@dataclass
class PortfolioWeights:
    """Portfolio weights result."""

    weights: dict[str, float]
    timestamp: datetime = field(default_factory=datetime.now)
    objective_value: float = 0.0
    risk_contributions: dict[str, float] = field(default_factory=dict)
    expected_return: float = 0.0
    expected_risk: float = 0.0
    sharpe_ratio: float = 0.0
    diversification_ratio: float = 0.0


@dataclass
class RiskMetrics:
    """Portfolio risk metrics."""

    volatility: float
    var_95: float  # Value at Risk 95%
    var_99: float
    cvar_95: float  # Conditional VaR 95%
    cvar_99: float
    max_drawdown: float
    beta: float  # Market beta
    tracking_error: float = 0.0
    information_ratio: float = 0.0


@dataclass
class BacktestResult:
    """Portfolio backtest result."""

    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    sortino_ratio: float
    turnover: float
    equity_curve: NDArray
    weights_history: list[PortfolioWeights]


# ============================================================================
# COVARIANCE ESTIMATION
# ============================================================================


class CovarianceEstimator:
    """Advanced covariance matrix estimation."""

    @staticmethod
    def sample_covariance(returns: NDArray) -> NDArray:
        """Simple sample covariance."""
        return np.cov(returns, rowvar=False)

    @staticmethod
    def ledoit_wolf_shrinkage(returns: NDArray) -> NDArray:
        """
        Ledoit-Wolf shrinkage estimator.
        Shrinks sample covariance toward structured target.
        """
        n, p = returns.shape

        # Sample covariance
        sample_cov = np.cov(returns, rowvar=False)

        # Target: scaled identity matrix
        mu = np.trace(sample_cov) / p
        target = mu * np.eye(p)

        # Compute optimal shrinkage intensity
        delta = sample_cov - target

        # Sum of squared off-diagonal elements
        sum_sq = np.sum(delta**2)

        # Denominator
        x = returns - np.mean(returns, axis=0)
        sum_sq_cross = 0.0
        for t in range(n):
            outer = np.outer(x[t], x[t])
            sum_sq_cross += np.sum((outer - sample_cov) ** 2)

        gamma = sum_sq_cross / (n**2)

        # Shrinkage intensity
        kappa = (gamma - sum_sq / n) / sum_sq if sum_sq > 0 else 0
        shrinkage = max(0, min(1, kappa))

        return shrinkage * target + (1 - shrinkage) * sample_cov

    @staticmethod
    def exponential_weighted(
        returns: NDArray,
        halflife: int = 63,  # ~3 months for daily data
    ) -> NDArray:
        """Exponentially weighted covariance."""
        n, p = returns.shape
        alpha = 1 - np.exp(-np.log(2) / halflife)

        # Compute weights
        weights = np.array([(1 - alpha) ** i for i in range(n - 1, -1, -1)])
        weights /= weights.sum()

        # Weighted mean
        weighted_mean = np.average(returns, axis=0, weights=weights)

        # Weighted covariance
        demeaned = returns - weighted_mean
        weighted_cov = np.zeros((p, p))
        for i in range(n):
            weighted_cov += weights[i] * np.outer(demeaned[i], demeaned[i])

        return weighted_cov

    @staticmethod
    def minimum_covariance_determinant(
        returns: NDArray, support_fraction: float = 0.75
    ) -> NDArray:
        """
        Robust covariance estimation using MCD.
        Removes outliers from covariance calculation.
        """
        n, p = returns.shape
        h = int(support_fraction * n)

        # Simple implementation: iterative reweighting
        # Start with sample covariance
        cov = np.cov(returns, rowvar=False)
        mean = np.mean(returns, axis=0)

        for _ in range(10):  # Iterations
            # Compute Mahalanobis distances
            try:
                cov_inv = np.linalg.inv(cov)
            except np.linalg.LinAlgError:
                cov_inv = np.linalg.pinv(cov)

            distances = np.array(
                [np.sqrt((r - mean) @ cov_inv @ (r - mean)) for r in returns]
            )

            # Select h points with smallest distances
            indices = np.argsort(distances)[:h]
            subset = returns[indices]

            # Recompute
            mean = np.mean(subset, axis=0)
            cov = np.cov(subset, rowvar=False)

            # Ensure positive definite
            if np.any(np.linalg.eigvalsh(cov) <= 0):
                cov += 1e-6 * np.eye(p)

        return cov


# ============================================================================
# RISK PARITY OPTIMIZER
# ============================================================================


class RiskParityOptimizer:
    """
    Risk Parity (Equal Risk Contribution) portfolio optimization.

    In risk parity, each asset contributes equally to portfolio risk.
    """

    def __init__(self, cov_estimator: str = "ledoit_wolf", risk_free_rate: float = 0.0):
        self.cov_estimator = cov_estimator
        self.risk_free_rate = risk_free_rate
        self._cov_matrix: NDArray | None = None
        self._returns: NDArray | None = None

    def fit(self, returns: NDArray) -> "RiskParityOptimizer":
        """
        Fit the optimizer with return data.

        Args:
            returns: T x N array of returns (T periods, N assets)
        """
        self._returns = returns

        # Estimate covariance
        if self.cov_estimator == "sample":
            self._cov_matrix = CovarianceEstimator.sample_covariance(returns)
        elif self.cov_estimator == "ledoit_wolf":
            self._cov_matrix = CovarianceEstimator.ledoit_wolf_shrinkage(returns)
        elif self.cov_estimator == "ewma":
            self._cov_matrix = CovarianceEstimator.exponential_weighted(returns)
        else:
            self._cov_matrix = CovarianceEstimator.sample_covariance(returns)

        return self

    def optimize(
        self,
        risk_budgets: NDArray | None = None,
        constraints: PortfolioConstraints | None = None,
    ) -> PortfolioWeights:
        """
        Find risk parity weights.

        Args:
            risk_budgets: Target risk contributions (default: equal)
            constraints: Portfolio constraints
        """
        if self._cov_matrix is None:
            raise ValueError("Must call fit() first")

        n_assets = self._cov_matrix.shape[0]

        # Default to equal risk budgets
        if risk_budgets is None:
            risk_budgets = np.ones(n_assets) / n_assets
        risk_budgets = np.array(risk_budgets)
        risk_budgets /= risk_budgets.sum()  # Normalize

        # Objective: minimize sum of squared risk contribution differences
        def objective(weights: NDArray) -> float:
            weights = np.maximum(weights, 1e-10)

            # Portfolio volatility
            port_var = weights @ self._cov_matrix @ weights
            port_vol = np.sqrt(port_var)

            # Marginal risk contributions
            mrc = self._cov_matrix @ weights / port_vol

            # Risk contributions
            rc = weights * mrc
            rc_pct = rc / port_vol  # Percentage contributions

            # Squared differences from target
            diff = rc_pct - risk_budgets
            return float(np.sum(diff**2))

        # Initial weights
        x0 = np.ones(n_assets) / n_assets

        # Constraints
        bounds = [(0.0, 1.0)] * n_assets
        if constraints:
            bounds = [(constraints.min_weight, constraints.max_weight)] * n_assets

        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        # Optimize
        result = optimize.minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            options={"ftol": 1e-10, "maxiter": 1000},
        )

        weights = result.x
        weights = np.maximum(weights, 0)
        weights /= weights.sum()

        # Calculate metrics
        port_var = weights @ self._cov_matrix @ weights
        port_vol = np.sqrt(port_var)

        # Risk contributions
        mrc = self._cov_matrix @ weights / port_vol
        rc = weights * mrc

        # Expected return
        mean_returns = (
            np.mean(self._returns, axis=0)
            if self._returns is not None
            else np.zeros(n_assets)
        )
        expected_return = float(weights @ mean_returns * 252)  # Annualized

        # Sharpe ratio
        sharpe = (
            (expected_return - self.risk_free_rate) / (port_vol * np.sqrt(252))
            if port_vol > 0
            else 0
        )

        return PortfolioWeights(
            weights={f"asset_{i}": float(w) for i, w in enumerate(weights)},
            objective_value=float(result.fun),
            risk_contributions={
                f"asset_{i}": float(r / port_vol) for i, r in enumerate(rc)
            },
            expected_return=expected_return,
            expected_risk=float(port_vol * np.sqrt(252)),
            sharpe_ratio=sharpe,
        )

    def get_risk_contributions(self, weights: NDArray) -> NDArray:
        """Calculate risk contributions for given weights."""
        if self._cov_matrix is None:
            raise ValueError("Must call fit() first")

        port_var = weights @ self._cov_matrix @ weights
        port_vol = np.sqrt(port_var)

        mrc = self._cov_matrix @ weights / port_vol
        rc = weights * mrc

        return rc / port_vol


# ============================================================================
# HIERARCHICAL RISK PARITY
# ============================================================================


class HierarchicalRiskParity:
    """
    Hierarchical Risk Parity (HRP) by Marcos Lopez de Prado.

    Uses hierarchical clustering to build portfolio, avoiding
    issues with covariance matrix inversion.
    """

    def __init__(
        self, cov_estimator: str = "ledoit_wolf", linkage_method: str = "single"
    ):
        self.cov_estimator = cov_estimator
        self.linkage_method = linkage_method
        self._cov_matrix: NDArray | None = None
        self._corr_matrix: NDArray | None = None
        self._returns: NDArray | None = None

    def fit(self, returns: NDArray) -> "HierarchicalRiskParity":
        """Fit with return data."""
        self._returns = returns

        # Estimate covariance
        if self.cov_estimator == "ledoit_wolf":
            self._cov_matrix = CovarianceEstimator.ledoit_wolf_shrinkage(returns)
        else:
            self._cov_matrix = CovarianceEstimator.sample_covariance(returns)

        # Correlation matrix
        std = np.sqrt(np.diag(self._cov_matrix))
        self._corr_matrix = self._cov_matrix / np.outer(std, std)
        np.fill_diagonal(self._corr_matrix, 1.0)

        return self

    def _get_cluster_order(self) -> list[int]:
        """Get quasi-diagonal reordering from hierarchical clustering."""
        if self._corr_matrix is None:
            return []

        # Distance matrix from correlation
        dist = np.sqrt((1 - self._corr_matrix) / 2)
        np.fill_diagonal(dist, 0)

        # Hierarchical clustering
        dist_condensed = squareform(dist)
        link = hierarchy.linkage(dist_condensed, method=self.linkage_method)

        # Get leaf order
        return list(hierarchy.leaves_list(link))

    def _get_quasi_diag(self, link: NDArray) -> list[int]:
        """Recursively get quasi-diagonal order."""
        link = link.astype(int)
        sorted_items = [link[-1, 0], link[-1, 1]]

        num_items = link[-1, 3]

        while len(sorted_items) < num_items:
            sorted_items_new = []
            for item in sorted_items:
                if item >= num_items:
                    sorted_items_new.append(link[item - num_items, 0])
                    sorted_items_new.append(link[item - num_items, 1])
                else:
                    sorted_items_new.append(item)
            sorted_items = sorted_items_new

        return sorted_items

    def _get_recursive_bisection(
        self, cov: NDArray, sorted_items: list[int]
    ) -> NDArray:
        """Compute HRP allocation through recursive bisection."""
        n = len(sorted_items)
        weights = np.ones(n)

        items = [sorted_items]

        while items:
            # Split each cluster
            new_items = []
            for cluster in items:
                if len(cluster) > 1:
                    # Split in half
                    mid = len(cluster) // 2
                    left = cluster[:mid]
                    right = cluster[mid:]

                    # Get cluster variances (inverse variance weighting)
                    var_left = self._get_cluster_variance(cov, left)
                    var_right = self._get_cluster_variance(cov, right)

                    # Allocate
                    alpha = 1 - var_left / (var_left + var_right)

                    # Update weights
                    for i in left:
                        weights[sorted_items.index(i)] *= alpha
                    for i in right:
                        weights[sorted_items.index(i)] *= 1 - alpha

                    new_items.extend([left, right])

            items = [c for c in new_items if len(c) > 1]

        return weights

    def _get_cluster_variance(self, cov: NDArray, items: list[int]) -> float:
        """Get cluster variance using inverse-variance portfolio."""
        cov_slice = cov[np.ix_(items, items)]

        # Inverse variance weights within cluster
        ivp = 1 / np.diag(cov_slice)
        ivp /= ivp.sum()

        # Cluster variance
        return float(ivp @ cov_slice @ ivp)

    def optimize(
        self, constraints: PortfolioConstraints | None = None
    ) -> PortfolioWeights:
        """
        Find HRP weights.

        Args:
            constraints: Optional constraints (applied post-optimization)
        """
        if self._cov_matrix is None:
            raise ValueError("Must call fit() first")

        n_assets = self._cov_matrix.shape[0]

        # Get hierarchical order
        sorted_items = self._get_cluster_order()

        # Recursive bisection
        weights = self._get_recursive_bisection(self._cov_matrix, sorted_items)

        # Reorder to original
        ordered_weights = np.zeros(n_assets)
        for i, item in enumerate(sorted_items):
            ordered_weights[item] = weights[i]

        weights = ordered_weights
        weights = np.maximum(weights, 0)
        weights /= weights.sum()

        # Apply constraints if provided
        if constraints:
            weights = np.clip(weights, constraints.min_weight, constraints.max_weight)
            weights /= weights.sum()

        # Calculate metrics
        port_var = weights @ self._cov_matrix @ weights
        port_vol = np.sqrt(port_var)

        mean_returns = (
            np.mean(self._returns, axis=0)
            if self._returns is not None
            else np.zeros(n_assets)
        )
        expected_return = float(weights @ mean_returns * 252)

        return PortfolioWeights(
            weights={f"asset_{i}": float(w) for i, w in enumerate(weights)},
            expected_return=expected_return,
            expected_risk=float(port_vol * np.sqrt(252)),
            sharpe_ratio=expected_return / (port_vol * np.sqrt(252))
            if port_vol > 0
            else 0,
        )


# ============================================================================
# MEAN-VARIANCE OPTIMIZER
# ============================================================================


class MeanVarianceOptimizer:
    """
    Classic Markowitz Mean-Variance Optimization.

    Finds efficient frontier portfolios.
    """

    def __init__(self, cov_estimator: str = "ledoit_wolf", risk_free_rate: float = 0.0):
        self.cov_estimator = cov_estimator
        self.risk_free_rate = risk_free_rate
        self._cov_matrix: NDArray | None = None
        self._expected_returns: NDArray | None = None

    def fit(
        self, returns: NDArray, expected_returns: NDArray | None = None
    ) -> "MeanVarianceOptimizer":
        """
        Fit with return data.

        Args:
            returns: Historical returns
            expected_returns: Forward-looking expected returns (optional)
        """
        # Estimate covariance
        if self.cov_estimator == "ledoit_wolf":
            self._cov_matrix = CovarianceEstimator.ledoit_wolf_shrinkage(returns)
        else:
            self._cov_matrix = CovarianceEstimator.sample_covariance(returns)

        # Expected returns
        if expected_returns is not None:
            self._expected_returns = expected_returns
        else:
            self._expected_returns = np.mean(returns, axis=0)

        return self

    def optimize(
        self,
        objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE,
        target_return: float | None = None,
        target_risk: float | None = None,
        constraints: PortfolioConstraints | None = None,
    ) -> PortfolioWeights:
        """
        Optimize portfolio.

        Args:
            objective: Optimization objective
            target_return: Target return (for MIN_VARIANCE with return constraint)
            target_risk: Target risk (for MAX_RETURN with risk constraint)
            constraints: Portfolio constraints
        """
        if self._cov_matrix is None or self._expected_returns is None:
            raise ValueError("Must call fit() first")

        n_assets = len(self._expected_returns)

        # Bounds
        if constraints:
            bounds = [(constraints.min_weight, constraints.max_weight)] * n_assets
        else:
            bounds = [(0.0, 1.0)] * n_assets

        # Constraints list
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        if target_return is not None:
            daily_target = target_return / 252
            cons.append(
                {
                    "type": "eq",
                    "fun": lambda w, t=daily_target: w @ self._expected_returns - t,
                }
            )

        if target_risk is not None:
            daily_risk = target_risk / np.sqrt(252)
            cons.append(
                {
                    "type": "ineq",
                    "fun": lambda w, t=daily_risk: t**2 - w @ self._cov_matrix @ w,
                }
            )

        # Objective functions
        def min_variance(weights: NDArray) -> float:
            return float(weights @ self._cov_matrix @ weights)

        def neg_sharpe(weights: NDArray) -> float:
            ret = weights @ self._expected_returns * 252
            vol = np.sqrt(weights @ self._cov_matrix @ weights * 252)
            return -(ret - self.risk_free_rate) / vol if vol > 0 else 0

        def neg_return(weights: NDArray) -> float:
            return -float(weights @ self._expected_returns)

        # Select objective
        if objective == OptimizationObjective.MIN_VARIANCE:
            obj_func = min_variance
        elif objective == OptimizationObjective.MAX_SHARPE:
            obj_func = neg_sharpe
        elif objective == OptimizationObjective.MAX_RETURN:
            obj_func = neg_return
        else:
            obj_func = min_variance

        # Initial weights
        x0 = np.ones(n_assets) / n_assets

        # Optimize
        result = optimize.minimize(
            obj_func,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            options={"ftol": 1e-10, "maxiter": 1000},
        )

        weights = result.x
        weights = np.maximum(weights, 0)
        weights /= weights.sum()

        # Metrics
        port_var = weights @ self._cov_matrix @ weights
        port_vol = np.sqrt(port_var) * np.sqrt(252)
        expected_return = float(weights @ self._expected_returns * 252)
        sharpe = (
            (expected_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0
        )

        return PortfolioWeights(
            weights={f"asset_{i}": float(w) for i, w in enumerate(weights)},
            objective_value=float(result.fun),
            expected_return=expected_return,
            expected_risk=port_vol,
            sharpe_ratio=sharpe,
        )

    def efficient_frontier(
        self, n_points: int = 50, constraints: PortfolioConstraints | None = None
    ) -> list[PortfolioWeights]:
        """Generate efficient frontier portfolios."""
        if self._expected_returns is None:
            return []

        # Find return range
        min_ret = float(np.min(self._expected_returns) * 252)
        max_ret = float(np.max(self._expected_returns) * 252)

        target_returns = np.linspace(min_ret, max_ret, n_points)

        frontier = []
        for target in target_returns:
            try:
                portfolio = self.optimize(
                    objective=OptimizationObjective.MIN_VARIANCE,
                    target_return=target,
                    constraints=constraints,
                )
                frontier.append(portfolio)
            except Exception:
                continue

        return frontier


# ============================================================================
# BLACK-LITTERMAN MODEL
# ============================================================================


class BlackLittermanModel:
    """
    Black-Litterman portfolio optimization.

    Combines market equilibrium with investor views.
    """

    def __init__(self, risk_aversion: float = 2.5, tau: float = 0.05):
        self.risk_aversion = risk_aversion  # δ
        self.tau = tau  # Uncertainty in prior
        self._cov_matrix: NDArray | None = None
        self._market_weights: NDArray | None = None
        self._implied_returns: NDArray | None = None

    def fit(self, returns: NDArray, market_weights: NDArray) -> "BlackLittermanModel":
        """
        Fit model with market equilibrium.

        Args:
            returns: Historical returns
            market_weights: Market capitalization weights
        """
        # Covariance matrix
        self._cov_matrix = CovarianceEstimator.ledoit_wolf_shrinkage(returns)
        self._market_weights = market_weights

        # Implied equilibrium returns: π = δ * Σ * w_mkt
        self._implied_returns = self.risk_aversion * self._cov_matrix @ market_weights

        return self

    def add_views(
        self,
        P: NDArray,  # View matrix (k x n)
        Q: NDArray,  # View returns (k,)
        omega: NDArray | None = None,  # View uncertainty (k x k)
    ) -> NDArray:
        """
        Incorporate investor views using Black-Litterman formula.

        Args:
            P: View picking matrix (which assets each view involves)
            Q: Expected returns from views
            omega: Uncertainty in views (diagonal)

        Returns:
            Updated expected returns
        """
        if self._cov_matrix is None or self._implied_returns is None:
            raise ValueError("Must call fit() first")

        # Default omega: proportional to variance of view portfolios
        if omega is None:
            omega = np.diag(np.diag(self.tau * P @ self._cov_matrix @ P.T))

        # Black-Litterman formula
        tau_sigma = self.tau * self._cov_matrix

        # M = [(τΣ)^(-1) + P'Ω^(-1)P]^(-1)
        inv_tau_sigma = np.linalg.inv(tau_sigma)
        inv_omega = np.linalg.inv(omega)

        M = np.linalg.inv(inv_tau_sigma + P.T @ inv_omega @ P)

        # μ_BL = M @ [(τΣ)^(-1)π + P'Ω^(-1)Q]
        bl_returns = M @ (inv_tau_sigma @ self._implied_returns + P.T @ inv_omega @ Q)

        return bl_returns

    def optimize(
        self,
        views_P: NDArray | None = None,
        views_Q: NDArray | None = None,
        constraints: PortfolioConstraints | None = None,
    ) -> PortfolioWeights:
        """
        Optimize portfolio with optional views.

        Args:
            views_P: View picking matrix
            views_Q: View expected returns
            constraints: Portfolio constraints
        """
        if self._cov_matrix is None:
            raise ValueError("Must call fit() first")

        # Get expected returns
        if views_P is not None and views_Q is not None:
            expected_returns = self.add_views(views_P, views_Q)
        else:
            expected_returns = self._implied_returns

        # Optimize using mean-variance
        mv_optimizer = MeanVarianceOptimizer()
        mv_optimizer._cov_matrix = self._cov_matrix
        mv_optimizer._expected_returns = expected_returns

        return mv_optimizer.optimize(
            objective=OptimizationObjective.MAX_SHARPE, constraints=constraints
        )


# ============================================================================
# RISK BUDGETING
# ============================================================================


class RiskBudgeting:
    """
    Custom risk budget allocation.

    Allows specifying exact risk contribution per asset.
    """

    def __init__(self, cov_estimator: str = "ledoit_wolf"):
        self.cov_estimator = cov_estimator
        self._cov_matrix: NDArray | None = None

    def fit(self, returns: NDArray) -> "RiskBudgeting":
        """Fit with return data."""
        if self.cov_estimator == "ledoit_wolf":
            self._cov_matrix = CovarianceEstimator.ledoit_wolf_shrinkage(returns)
        else:
            self._cov_matrix = CovarianceEstimator.sample_covariance(returns)
        return self

    def optimize(
        self,
        risk_budgets: dict[str, float],
        assets: list[str],
        constraints: PortfolioConstraints | None = None,
    ) -> PortfolioWeights:
        """
        Optimize with custom risk budgets.

        Args:
            risk_budgets: {asset: target_risk_contribution}
            assets: List of asset names
            constraints: Portfolio constraints
        """
        if self._cov_matrix is None:
            raise ValueError("Must call fit() first")

        n_assets = len(assets)
        budgets = np.array([risk_budgets.get(a, 1.0 / n_assets) for a in assets])
        budgets /= budgets.sum()

        # Use risk parity with custom budgets
        rp = RiskParityOptimizer(cov_estimator=self.cov_estimator)
        rp._cov_matrix = self._cov_matrix

        result = rp.optimize(risk_budgets=budgets, constraints=constraints)

        # Rename assets
        result.weights = {
            a: result.weights.get(f"asset_{i}", 0) for i, a in enumerate(assets)
        }
        result.risk_contributions = {
            a: result.risk_contributions.get(f"asset_{i}", 0)
            for i, a in enumerate(assets)
        }

        return result


# ============================================================================
# DYNAMIC REBALANCER
# ============================================================================


class DynamicRebalancer:
    """
    Dynamic portfolio rebalancing with multiple strategies.
    """

    def __init__(
        self,
        optimizer: object,  # Any optimizer with optimize() method
        frequency: RebalanceFrequency = RebalanceFrequency.MONTHLY,
        threshold: float = 0.05,  # 5% drift threshold
        transaction_cost: float = 0.001,  # 10 bps
    ):
        self.optimizer = optimizer
        self.frequency = frequency
        self.threshold = threshold
        self.transaction_cost = transaction_cost
        self._current_weights: NDArray | None = None
        self._rebalance_dates: list[datetime] = []

    def should_rebalance(
        self,
        current_weights: NDArray,
        target_weights: NDArray,
        current_date: datetime,
        last_rebalance: datetime | None = None,
    ) -> bool:
        """Determine if rebalancing is needed."""
        # Threshold-based
        if self.frequency == RebalanceFrequency.THRESHOLD:
            drift = np.max(np.abs(current_weights - target_weights))
            return drift > self.threshold

        # Calendar-based
        if last_rebalance is None:
            return True

        days_since = (current_date - last_rebalance).days

        if self.frequency == RebalanceFrequency.DAILY:
            return days_since >= 1
        elif self.frequency == RebalanceFrequency.WEEKLY:
            return days_since >= 7
        elif self.frequency == RebalanceFrequency.MONTHLY:
            return days_since >= 30
        elif self.frequency == RebalanceFrequency.QUARTERLY:
            return days_since >= 90

        return False

    def rebalance(
        self,
        current_weights: NDArray,
        returns_window: NDArray,
        constraints: PortfolioConstraints | None = None,
    ) -> tuple[NDArray, float]:
        """
        Execute rebalancing.

        Returns:
            (new_weights, transaction_cost)
        """
        # Fit optimizer with recent returns
        self.optimizer.fit(returns_window)

        # Get target weights
        target_portfolio = self.optimizer.optimize(constraints=constraints)
        target_weights = np.array(list(target_portfolio.weights.values()))

        # Calculate turnover
        turnover = np.sum(np.abs(target_weights - current_weights)) / 2

        # Transaction cost
        cost = turnover * self.transaction_cost

        return target_weights, cost

    def backtest(
        self,
        returns: NDArray,
        lookback_window: int = 252,
        initial_weights: NDArray | None = None,
        constraints: PortfolioConstraints | None = None,
    ) -> BacktestResult:
        """
        Backtest rebalancing strategy.

        Args:
            returns: Full return series
            lookback_window: Window for optimization
            initial_weights: Starting weights
            constraints: Portfolio constraints

        Returns:
            Backtest results
        """
        n_periods, n_assets = returns.shape

        if initial_weights is None:
            initial_weights = np.ones(n_assets) / n_assets

        weights = initial_weights.copy()
        equity = [1.0]
        weights_history = []
        total_turnover = 0.0
        last_rebalance_idx = 0

        for t in range(lookback_window, n_periods):
            # Portfolio return
            port_return = float(np.sum(weights * returns[t]))

            # Update weights for price changes
            new_values = weights * (1 + returns[t])
            weights = new_values / new_values.sum()

            # Check rebalancing
            # Get target weights
            returns_window = returns[t - lookback_window : t]
            self.optimizer.fit(returns_window)
            target_portfolio = self.optimizer.optimize(constraints=constraints)
            target_weights = np.array(list(target_portfolio.weights.values()))

            current_date = datetime.now()  # Placeholder
            last_date = datetime.now() - timedelta(days=t - last_rebalance_idx)

            if self.should_rebalance(weights, target_weights, current_date, last_date):
                # Rebalance
                turnover = np.sum(np.abs(target_weights - weights)) / 2
                cost = turnover * self.transaction_cost
                total_turnover += turnover

                # Apply cost
                port_return -= cost

                weights = target_weights.copy()
                last_rebalance_idx = t

                weights_history.append(
                    PortfolioWeights(
                        weights={f"asset_{i}": float(w) for i, w in enumerate(weights)}
                    )
                )

            equity.append(equity[-1] * (1 + port_return))

        equity_arr = np.array(equity)

        # Calculate metrics
        total_return = equity_arr[-1] / equity_arr[0] - 1
        ann_return = (1 + total_return) ** (252 / len(equity_arr)) - 1

        daily_returns = np.diff(equity_arr) / equity_arr[:-1]
        volatility = float(np.std(daily_returns) * np.sqrt(252))

        sharpe = ann_return / volatility if volatility > 0 else 0

        # Max drawdown
        peak = np.maximum.accumulate(equity_arr)
        drawdown = (peak - equity_arr) / peak
        max_dd = float(np.max(drawdown))

        calmar = ann_return / max_dd if max_dd > 0 else 0

        # Sortino
        neg_returns = daily_returns[daily_returns < 0]
        downside_vol = (
            float(np.std(neg_returns) * np.sqrt(252))
            if len(neg_returns) > 0
            else volatility
        )
        sortino = ann_return / downside_vol if downside_vol > 0 else 0

        return BacktestResult(
            total_return=total_return,
            annualized_return=ann_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            calmar_ratio=calmar,
            sortino_ratio=sortino,
            turnover=total_turnover,
            equity_curve=equity_arr,
            weights_history=weights_history,
        )


# ============================================================================
# PORTFOLIO RISK CALCULATOR
# ============================================================================


class PortfolioRiskCalculator:
    """Calculate comprehensive portfolio risk metrics."""

    def __init__(self, confidence_levels: list[float] | None = None):
        if confidence_levels is None:
            self.confidence_levels = [0.95, 0.99]
        else:
            self.confidence_levels = confidence_levels

    def calculate_var(
        self, returns: NDArray, weights: NDArray, confidence: float = 0.95
    ) -> float:
        """
        Calculate Value at Risk.

        Args:
            returns: Historical returns
            weights: Portfolio weights
            confidence: Confidence level

        Returns:
            VaR (positive number representing loss)
        """
        portfolio_returns = returns @ weights
        var = -float(np.percentile(portfolio_returns, (1 - confidence) * 100))
        return var

    def calculate_cvar(
        self, returns: NDArray, weights: NDArray, confidence: float = 0.95
    ) -> float:
        """
        Calculate Conditional Value at Risk (Expected Shortfall).
        """
        portfolio_returns = returns @ weights
        var = np.percentile(portfolio_returns, (1 - confidence) * 100)
        cvar = -float(np.mean(portfolio_returns[portfolio_returns <= var]))
        return cvar

    def calculate_all_metrics(
        self,
        returns: NDArray,
        weights: NDArray,
        benchmark_returns: NDArray | None = None,
    ) -> RiskMetrics:
        """Calculate all risk metrics."""
        portfolio_returns = returns @ weights

        # Volatility
        volatility = float(np.std(portfolio_returns) * np.sqrt(252))

        # VaR
        var_95 = self.calculate_var(returns, weights, 0.95)
        var_99 = self.calculate_var(returns, weights, 0.99)

        # CVaR
        cvar_95 = self.calculate_cvar(returns, weights, 0.95)
        cvar_99 = self.calculate_cvar(returns, weights, 0.99)

        # Max Drawdown
        cum_returns = np.cumprod(1 + portfolio_returns)
        peak = np.maximum.accumulate(cum_returns)
        drawdown = (peak - cum_returns) / peak
        max_dd = float(np.max(drawdown))

        # Beta and tracking error
        beta = 1.0
        tracking_error = 0.0
        information_ratio = 0.0

        if benchmark_returns is not None:
            cov_pb = np.cov(portfolio_returns, benchmark_returns)[0, 1]
            var_b = np.var(benchmark_returns)
            beta = cov_pb / var_b if var_b > 0 else 1.0

            excess_returns = portfolio_returns - benchmark_returns
            tracking_error = float(np.std(excess_returns) * np.sqrt(252))
            information_ratio = (
                float(np.mean(excess_returns) * 252) / tracking_error
                if tracking_error > 0
                else 0
            )

        return RiskMetrics(
            volatility=volatility,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            max_drawdown=max_dd,
            beta=beta,
            tracking_error=tracking_error,
            information_ratio=information_ratio,
        )


# ============================================================================
# PORTFOLIO FACTORY
# ============================================================================


class PortfolioFactory:
    """Factory for creating portfolio optimizers."""

    @staticmethod
    def create_optimizer(method: str, **kwargs) -> object:
        """
        Create portfolio optimizer.

        Args:
            method: Optimization method
                - "risk_parity": Risk Parity
                - "hrp": Hierarchical Risk Parity
                - "mean_variance": Mean-Variance
                - "black_litterman": Black-Litterman
                - "risk_budget": Risk Budgeting

        Returns:
            Optimizer instance
        """
        if method == "risk_parity":
            return RiskParityOptimizer(**kwargs)
        elif method == "hrp":
            return HierarchicalRiskParity(**kwargs)
        elif method == "mean_variance":
            return MeanVarianceOptimizer(**kwargs)
        elif method == "black_litterman":
            return BlackLittermanModel(**kwargs)
        elif method == "risk_budget":
            return RiskBudgeting(**kwargs)
        else:
            raise ValueError(f"Unknown optimization method: {method}")

    @staticmethod
    def get_available_methods() -> list[str]:
        """Get list of available optimization methods."""
        return ["risk_parity", "hrp", "mean_variance", "black_litterman", "risk_budget"]


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def create_risk_parity_portfolio(
    returns: NDArray,
    asset_names: list[str] | None = None,
    constraints: PortfolioConstraints | None = None,
) -> PortfolioWeights:
    """
    Quick function to create risk parity portfolio.

    Args:
        returns: T x N array of returns
        asset_names: Optional asset names
        constraints: Portfolio constraints

    Returns:
        Optimized portfolio weights
    """
    optimizer = RiskParityOptimizer()
    optimizer.fit(returns)
    result = optimizer.optimize(constraints=constraints)

    if asset_names:
        result.weights = {
            name: result.weights.get(f"asset_{i}", 0)
            for i, name in enumerate(asset_names)
        }

    return result


def create_hrp_portfolio(
    returns: NDArray,
    asset_names: list[str] | None = None,
    constraints: PortfolioConstraints | None = None,
) -> PortfolioWeights:
    """Quick function to create HRP portfolio."""
    optimizer = HierarchicalRiskParity()
    optimizer.fit(returns)
    result = optimizer.optimize(constraints=constraints)

    if asset_names:
        result.weights = {
            name: result.weights.get(f"asset_{i}", 0)
            for i, name in enumerate(asset_names)
        }

    return result


def create_max_sharpe_portfolio(
    returns: NDArray,
    asset_names: list[str] | None = None,
    risk_free_rate: float = 0.0,
    constraints: PortfolioConstraints | None = None,
) -> PortfolioWeights:
    """Quick function to create maximum Sharpe ratio portfolio."""
    optimizer = MeanVarianceOptimizer(risk_free_rate=risk_free_rate)
    optimizer.fit(returns)
    result = optimizer.optimize(
        objective=OptimizationObjective.MAX_SHARPE, constraints=constraints
    )

    if asset_names:
        result.weights = {
            name: result.weights.get(f"asset_{i}", 0)
            for i, name in enumerate(asset_names)
        }

    return result


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Data structures
    "Asset",
    "BacktestResult",
    "BlackLittermanModel",
    "ConstraintType",
    # Covariance estimation
    "CovarianceEstimator",
    # Rebalancing
    "DynamicRebalancer",
    "HierarchicalRiskParity",
    "MeanVarianceOptimizer",
    # Enums
    "OptimizationObjective",
    "PortfolioConstraints",
    # Factory
    "PortfolioFactory",
    # Risk
    "PortfolioRiskCalculator",
    "PortfolioWeights",
    "RebalanceFrequency",
    "RiskBudgeting",
    "RiskMetrics",
    # Optimizers
    "RiskParityOptimizer",
    "create_hrp_portfolio",
    "create_max_sharpe_portfolio",
    # Convenience functions
    "create_risk_parity_portfolio",
]
