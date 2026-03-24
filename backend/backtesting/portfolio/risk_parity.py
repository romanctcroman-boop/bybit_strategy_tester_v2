"""
📊 Risk Parity Allocation

Аллокация капитала на основе risk parity подхода.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, minimize

logger = logging.getLogger(__name__)


@dataclass
class RiskParityResult:
    """
    Результаты risk parity аллокации.

    Attributes:
        weights: Оптимальные веса
        risk_contributions: Вклад каждого актива в риск
        total_risk: Общий риск портфеля
        diversification_ratio: Коэффициент диверсификации
    """

    weights: dict[str, float]
    risk_contributions: dict[str, float]
    total_risk: float
    diversification_ratio: float


class RiskParityAllocator:
    """
    Risk parity аллокатор.

    Risk parity — подход к аллокации, где каждый актив
    вносит одинаковый вклад в общий риск портфеля.

    Преимущества:
    - Лучшая диверсификация чем market-cap weighting
    - Меньшая концентрация риска
    - Устойчивость к кризисам
    """

    def __init__(
        self,
        target_risk: float | None = None,
        max_weight: float = 0.4,
        min_weight: float = 0.0,
        risk_free_rate: float = 0.0,
    ):
        """
        Args:
            target_risk: Целевой риск портфеля (None = минимизировать)
            max_weight: Максимальный вес актива
            min_weight: Минимальный вес актива
            risk_free_rate: Безрисковая ставка
        """
        self.target_risk = target_risk
        self.max_weight = max_weight
        self.min_weight = min_weight
        self.risk_free_rate = risk_free_rate

    def _calculate_risk_contribution(self, weights: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """
        Вычислить вклад каждого актива в риск.

        Args:
            weights: Веса активов
            cov_matrix: Ковариационная матрица

        Returns:
            Risk contributions
        """
        # Портфельная волатильность
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)

        # Маржинальный вклад в риск
        marginal_risk = (cov_matrix @ weights) / portfolio_vol

        # Вклад каждого актива
        risk_contrib = weights * marginal_risk

        return risk_contrib

    def _risk_parity_objective(self, weights: np.ndarray, cov_matrix: np.ndarray) -> float:
        """
        Objective функция для risk parity.

        Минимизируем отклонение от равного вклада в риск.
        """
        n_assets = len(weights)
        target_risk_contrib = 1.0 / n_assets

        risk_contrib = self._calculate_risk_contribution(weights, cov_matrix)

        # Нормализованный вклад
        risk_contrib_pct = risk_contrib / risk_contrib.sum()

        # Квадратичное отклонение от цели
        mse = np.sum((risk_contrib_pct - target_risk_contrib) ** 2)

        return mse

    def _sharpe_objective(self, weights: np.ndarray, expected_returns: np.ndarray, cov_matrix: np.ndarray) -> float:
        """
        Objective функция для максимизации Sharpe.
        """
        # Портфельная доходность
        portfolio_return = weights @ expected_returns

        # Портфельная волатильность
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)

        # Sharpe ratio (отрицательный для минимизации)
        sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0

        return -sharpe  # Минимизируем

    def allocate(self, returns: pd.DataFrame, method: str = "risk_parity") -> RiskParityResult:
        """
        Вычислить оптимальные веса.

        Args:
            returns: Доходности активов (columns = symbols)
            method: 'risk_parity', 'sharpe', 'min_volatility'

        Returns:
            RiskParityResult
        """
        symbols = returns.columns.tolist()
        n_assets = len(symbols)

        # Проверка валидности данных
        if returns.empty:
            raise ValueError("Returns DataFrame is empty")

        # Удалить активы с полными NaN
        valid_columns = returns.columns[~returns.isnull().all()]
        if len(valid_columns) == 0:
            raise ValueError("No valid assets for optimization")

        returns = returns[valid_columns]
        symbols = returns.columns.tolist()
        n_assets = len(symbols)

        if n_assets < 2:
            raise ValueError("At least 2 assets required for optimization")

        # Ковариационная матрица
        cov_matrix = returns.cov().values * 252  # Annualized

        # Ожидаемые доходности
        expected_returns = returns.mean().values * 252

        # Начальные веса (равные)
        x0 = np.array([1.0 / n_assets] * n_assets)

        # Ограничения
        bounds = Bounds(lb=[self.min_weight] * n_assets, ub=[self.max_weight] * n_assets)

        # Сумма весов = 1
        sum_constraint = LinearConstraint(A=np.ones(n_assets), lb=1.0, ub=1.0)

        # Оптимизация
        if method == "risk_parity":
            result = minimize(
                fun=self._risk_parity_objective,
                x0=x0,
                args=(cov_matrix,),
                method="SLSQP",
                bounds=bounds,
                constraints=[sum_constraint],
            )
        elif method == "sharpe":
            result = minimize(
                fun=self._sharpe_objective,
                x0=x0,
                args=(expected_returns, cov_matrix),
                method="SLSQP",
                bounds=bounds,
                constraints=[sum_constraint],
            )
        elif method == "min_volatility":
            result = minimize(
                fun=lambda x: np.sqrt(x @ cov_matrix @ x),
                x0=x0,
                method="SLSQP",
                bounds=bounds,
                constraints=[sum_constraint],
            )
        else:
            raise ValueError(f"Unknown method: {method}")

        if not result.success:
            logger.warning(f"Optimization failed: {result.message}")

        # Оптимальные веса
        optimal_weights = result.x

        # Нормализация (на случай если сумма != 1)
        optimal_weights = optimal_weights / optimal_weights.sum()

        # Risk contributions
        risk_contrib = self._calculate_risk_contribution(optimal_weights, cov_matrix)

        # Total risk
        total_risk = np.sqrt(optimal_weights @ cov_matrix @ optimal_weights)

        # Diversification ratio
        avg_vol = np.sum(optimal_weights * np.sqrt(np.diag(cov_matrix)))
        div_ratio = avg_vol / total_risk if total_risk > 0 else 1.0

        # Словари
        weights_dict = {symbols[i]: optimal_weights[i] for i in range(n_assets)}
        risk_contrib_dict = {symbols[i]: risk_contrib[i] for i in range(n_assets)}

        return RiskParityResult(
            weights=weights_dict,
            risk_contributions=risk_contrib_dict,
            total_risk=total_risk,
            diversification_ratio=div_ratio,
        )

    def allocate_hierarchical(self, returns: pd.DataFrame, clusters: dict[str, str]) -> RiskParityResult:
        """
        Иерархическая risk parity аллокация.

        Сначала аллоцируем между кластерами, потом внутри кластеров.

        Args:
            returns: Доходности активов
            clusters: {symbol: cluster_name}

        Returns:
            RiskParityResult
        """
        symbols = returns.columns.tolist()

        # Группировка по кластерам
        cluster_symbols: dict[str, list[str]] = {}

        for symbol in symbols:
            cluster = clusters.get(symbol, "default")
            if cluster not in cluster_symbols:
                cluster_symbols[cluster] = []
            cluster_symbols[cluster].append(symbol)

        # Аллокация между кластерами
        cluster_returns = {}

        for cluster, cluster_syms in cluster_symbols.items():
            # Средняя доходность по кластеру
            cluster_returns[cluster] = returns[cluster_syms].mean(axis=1)

        cluster_returns_df = pd.DataFrame(cluster_returns)

        # Risk parity между кластерами
        cluster_result = self.allocate(cluster_returns_df, method="risk_parity")

        # Аллокация внутри кластеров
        final_weights: dict[str, float] = {}

        for cluster, weight in cluster_result.weights.items():
            cluster_syms = cluster_symbols[cluster]
            cluster_data = returns[cluster_syms]

            # Risk parity внутри кластера
            inner_result = self.allocate(cluster_data, method="risk_parity")

            # Масштабирование весов
            for symbol, inner_weight in inner_result.weights.items():
                final_weights[symbol] = weight * inner_weight

        # Вычисление risk contributions
        cov_matrix = returns.cov().values * 252
        symbols = list(final_weights.keys())
        weights_array = np.array([final_weights[s] for s in symbols])

        risk_contrib = self._calculate_risk_contribution(weights_array, cov_matrix)
        risk_contrib_dict = {symbols[i]: risk_contrib[i] for i in range(len(symbols))}

        total_risk = np.sqrt(weights_array @ cov_matrix @ weights_array)
        avg_vol = np.sum(weights_array * np.sqrt(np.diag(cov_matrix)))
        div_ratio = avg_vol / total_risk if total_risk > 0 else 1.0

        return RiskParityResult(
            weights=final_weights,
            risk_contributions=risk_contrib_dict,
            total_risk=total_risk,
            diversification_ratio=div_ratio,
        )

    def efficient_frontier(
        self, returns: pd.DataFrame, n_points: int = 50
    ) -> tuple[list[float], list[float], list[dict[str, float]]]:
        """
        Построить эффективную границу.

        Args:
            returns: Доходности активов
            n_points: Количество точек

        Returns:
            (volatilities, returns, weights_list)
        """
        symbols = returns.columns.tolist()
        n_assets = len(symbols)

        cov_matrix = returns.cov().values * 252
        expected_returns = returns.mean().values * 252

        volatilities = []
        portfolio_returns = []
        weights_list = []

        # Минимальная и максимальная волатильность
        min_vol_result = self.allocate(returns, method="min_volatility")
        min_vol = min_vol_result.total_risk

        max_vol = np.sqrt(np.max(np.diag(cov_matrix)))

        # Точки на эффективной границе
        for target_vol in np.linspace(min_vol, max_vol, n_points):
            # Оптимизация с ограничением на волатильность
            def objective(weights):
                return -weights @ expected_returns

            constraints = [
                {"type": "eq", "fun": lambda x: np.sum(x) - 1},
                {"type": "ineq", "fun": lambda x, tv=target_vol: tv - np.sqrt(x @ cov_matrix @ x)},
            ]

            x0 = np.array([1.0 / n_assets] * n_assets)
            bounds = Bounds(lb=[self.min_weight] * n_assets, ub=[self.max_weight] * n_assets)

            result = minimize(fun=objective, x0=x0, method="SLSQP", bounds=bounds, constraints=constraints)

            weights = result.x if result.success else np.array([1.0 / n_assets] * n_assets)

            vol = np.sqrt(weights @ cov_matrix @ weights)
            ret = weights @ expected_returns

            volatilities.append(vol)
            portfolio_returns.append(ret)
            weights_list.append({symbols[i]: weights[i] for i in range(n_assets)})

        return volatilities, portfolio_returns, weights_list
