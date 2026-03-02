"""
📊 Correlation Analysis

Анализ корреляций между символами, коинтеграция, rolling correlations.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """
    Результаты корреляционного анализа.

    Attributes:
        correlation_matrix: Матрица корреляций
        rolling_correlations: Rolling корреляции
        cointegration_tests: Тесты на коинтеграцию
        diversification_ratio: Коэффициент диверсификации
    """

    correlation_matrix: pd.DataFrame
    rolling_correlations: dict[str, pd.Series] | None = None
    cointegration_tests: dict[str, float] | None = None
    diversification_ratio: float = 1.0


class CorrelationAnalysis:
    """
    Анализ корреляций для портфельной торговли.

    Методы:
    - Pearson correlation
    - Spearman correlation
    - Rolling correlation
    - Cointegration test (Engle-Granger)
    - Diversification ratio
    """

    def __init__(self, window: int = 30):
        """
        Args:
            window: Окно для rolling correlation
        """
        self.window = window

    def calculate_correlation_matrix(self, returns_dict: dict[str, pd.Series], method: str = "pearson") -> pd.DataFrame:
        """
        Вычисление матрицы корреляций.

        Args:
            returns_dict: {symbol: returns}
            method: 'pearson', 'spearman', 'kendall'

        Returns:
            Correlation matrix
        """
        # DataFrame с returns
        returns_df = pd.DataFrame(returns_dict)

        # Заполнение пропусков
        returns_df = returns_df.fillna(0)

        # Корреляционная матрица
        return returns_df.corr(method=method)

    def calculate_rolling_correlation(
        self, returns1: pd.Series, returns2: pd.Series, window: int | None = None
    ) -> pd.Series:
        """
        Rolling корреляция между двумя сериями.

        Args:
            returns1: Первая серия доходностей
            returns2: Вторая серия доходностей
            window: Окно rolling

        Returns:
            Rolling correlation
        """
        if window is None:
            window = self.window

        # Объединение в DataFrame
        df = pd.DataFrame({"ret1": returns1, "ret2": returns2}).dropna()

        # Rolling корреляция
        rolling_corr = df["ret1"].rolling(window=window).corr(df["ret2"])

        return rolling_corr

    def cointegration_test(
        self, series1: pd.Series, series2: pd.Series, max_lag: int = 10
    ) -> tuple[float, float, bool]:
        """
        Engle-Granger тест на коинтеграцию.

        Args:
            series1: Первая серия (цены)
            series2: Вторая серия (цены)
            max_lag: Максимальный лаг для ADF теста

        Returns:
            (test_statistic, p_value, is_cointegrated)
        """
        try:
            # ADF тест на остатки
            from statsmodels.tsa.stattools import coint

            test_stat, p_value, _ = coint(series1, series2, maxlag=max_lag)

            is_cointegrated = p_value < 0.05

            return test_stat, p_value, is_cointegrated

        except ImportError:
            logger.warning("statsmodels not installed, skipping cointegration test")
            return 0.0, 1.0, False
        except Exception as e:
            logger.warning(f"Cointegration test failed: {e}")
            return 0.0, 1.0, False

    def calculate_diversification_ratio(self, returns_dict: dict[str, pd.Series], weights: dict[str, float]) -> float:
        """
        Вычисление коэффициента диверсификации.

        Формула:
            DR = (w' * σ) / σ_p

        где:
            w — веса
            σ — волатильности активов
            σ_p — волатильность портфеля

        Args:
            returns_dict: {symbol: returns}
            weights: {symbol: weight}

        Returns:
            Diversification ratio (>1 = диверсификация есть)
        """
        symbols = list(weights.keys())

        # Волатильности
        volatilities = np.array([returns_dict[symbol].std() * np.sqrt(252) for symbol in symbols])

        # Веса
        w = np.array([weights[symbol] for symbol in symbols])

        # Средневзвешенная волатильность
        weighted_volatility = np.dot(w, volatilities)

        # Портфельные returns
        portfolio_returns = pd.DataFrame(returns_dict).dot(
            pd.Series({s: weights.get(s, 1 / len(symbols)) for s in symbols})
        )

        # Волатильность портфеля
        portfolio_volatility = portfolio_returns.std() * np.sqrt(252)

        if portfolio_volatility > 0:
            return weighted_volatility / portfolio_volatility

        return 1.0

    def calculate_all(
        self, price_dict: dict[str, pd.Series], weights: dict[str, float] | None = None
    ) -> CorrelationResult:
        """
        Полный корреляционный анализ.

        Args:
            price_dict: {symbol: prices}
            weights: {symbol: weight}

        Returns:
            CorrelationResult
        """
        # Вычисление returns
        returns_dict = {symbol: prices.pct_change().dropna() for symbol, prices in price_dict.items()}

        # Корреляционная матрица
        corr_matrix = self.calculate_correlation_matrix(returns_dict)

        # Rolling корреляции (для пар)
        rolling_corrs = {}
        symbols = list(returns_dict.keys())

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                pair_name = f"{symbols[i]}_{symbols[j]}"
                rolling_corrs[pair_name] = self.calculate_rolling_correlation(
                    returns_dict[symbols[i]], returns_dict[symbols[j]]
                )

        # Тесты на коинтеграцию
        coint_tests = {}

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                pair_name = f"{symbols[i]}_{symbols[j]}"
                _, p_value, _ = self.cointegration_test(price_dict[symbols[i]], price_dict[symbols[j]])
                coint_tests[pair_name] = p_value

        # Diversification ratio
        if weights is None:
            weights = {symbol: 1.0 / len(symbols) for symbol in symbols}

        div_ratio = self.calculate_diversification_ratio(returns_dict, weights)

        return CorrelationResult(
            correlation_matrix=corr_matrix,
            rolling_correlations=rolling_corrs,
            cointegration_tests=coint_tests,
            diversification_ratio=div_ratio,
        )

    def get_low_correlation_pairs(
        self, corr_matrix: pd.DataFrame, threshold: float = 0.5
    ) -> list[tuple[str, str, float]]:
        """
        Найти пары с низкой корреляцией.

        Args:
            corr_matrix: Матрица корреляций
            threshold: Порог корреляции

        Returns:
            Список пар (symbol1, symbol2, correlation)
        """
        pairs = []

        symbols = corr_matrix.columns.tolist()

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                corr = corr_matrix.iloc[i, j]

                if abs(corr) < threshold:
                    pairs.append((symbols[i], symbols[j], corr))

        # Сортировка по абсолютной корреляции
        pairs.sort(key=lambda x: abs(x[2]))

        return pairs

    def get_high_correlation_pairs(
        self, corr_matrix: pd.DataFrame, threshold: float = 0.7
    ) -> list[tuple[str, str, float]]:
        """
        Найти пары с высокой корреляцией.

        Args:
            corr_matrix: Матрица корреляций
            threshold: Порог корреляции

        Returns:
            Список пар (symbol1, symbol2, correlation)
        """
        pairs = []

        symbols = corr_matrix.columns.tolist()

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                corr = corr_matrix.iloc[i, j]

                if abs(corr) > threshold:
                    pairs.append((symbols[i], symbols[j], corr))

        # Сортировка по убыванию корреляции
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)

        return pairs
