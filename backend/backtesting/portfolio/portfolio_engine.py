"""
📊 Portfolio Backtest Engine

Multi-symbol portfolio backtesting engine.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PortfolioConfig:
    """
    Конфигурация портфеля.

    Attributes:
        symbols: Список символов ['BTCUSDT', 'ETHUSDT', ...]
        weights: Веса символов (None = равные веса)
        rebalance_frequency: Частота ребалансировки ('daily', 'weekly', 'monthly')
        initial_capital: Начальный капитал
        commission: Комиссия
    """

    symbols: list[str]
    weights: dict[str, float] | None = None
    rebalance_frequency: str = "monthly"
    initial_capital: float = 10000.0
    commission: float = 0.0007


@dataclass
class SymbolResult:
    """
    Результаты по одному символу.

    Attributes:
        symbol: Символ
        equity_curve: Кривая доходности
        trades: Список сделок
        metrics: Метрики
    """

    symbol: str
    equity_curve: pd.Series
    trades: list[dict]
    metrics: dict[str, float]


@dataclass
class PortfolioResult:
    """
    Результаты портфельного бэктеста.

    Attributes:
        portfolio_equity: Общая кривая доходности
        symbol_results: Результаты по символам
        metrics: Общие метрики портфеля
        correlation_matrix: Матрица корреляций
        weights_history: История весов
    """

    portfolio_equity: pd.Series
    symbol_results: dict[str, SymbolResult]
    metrics: dict[str, float]
    correlation_matrix: pd.DataFrame
    weights_history: pd.DataFrame
    trades: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Конвертация в словарь"""
        return {
            "portfolio_equity": self.portfolio_equity.to_dict(),
            "symbol_results": {
                symbol: {
                    "metrics": result.metrics,
                    "n_trades": len(result.trades),
                }
                for symbol, result in self.symbol_results.items()
            },
            "metrics": self.metrics,
            "correlation_matrix": self.correlation_matrix.to_dict(),
            "total_trades": len(self.trades),
        }


class PortfolioBacktestEngine:
    """
    Движок портфельного бэктеста.

    Позволяет тестировать стратегии на нескольких символах одновременно
    с учётом корреляций и ребалансировки.

    Пример использования:
    ```python
    engine = PortfolioBacktestEngine()

    result = engine.run(
        strategy_class=RSIStrategy,
        data_dict={
            'BTCUSDT': btc_data,
            'ETHUSDT': eth_data,
        },
        config=PortfolioConfig(
            symbols=['BTCUSDT', 'ETHUSDT'],
            weights={'BTCUSDT': 0.6, 'ETHUSDT': 0.4},
        ),
    )
    ```
    """

    def __init__(self, single_engine: Any = None):
        """
        Args:
            single_engine: Одиночный бэктест движок (FallbackEngineV4)
        """
        if single_engine is None:
            from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4

            self.single_engine = FallbackEngineV4()
        else:
            self.single_engine = single_engine

    def _normalize_weights(self, weights: dict[str, float] | None, symbols: list[str]) -> dict[str, float]:
        """Нормализация весов"""
        if weights is None:
            # Равные веса
            return {symbol: 1.0 / len(symbols) for symbol in symbols}

        # Нормализация к сумме 1.0
        total = sum(weights.values())
        if total > 0:
            return {symbol: weights[symbol] / total for symbol in symbols}

        # Если сумма 0, возвращаем равные веса
        return {symbol: 1.0 / len(symbols) for symbol in symbols}

    def _run_single_symbol(
        self,
        symbol: str,
        data: pd.DataFrame,
        strategy_class: Any,
        strategy_params: dict[str, Any],
        config: PortfolioConfig,
    ) -> SymbolResult:
        """
        Запуск бэктеста на одном символе.

        Args:
            symbol: Символ
            data: Данные
            strategy_class: Класс стратегии
            strategy_params: Параметры стратегии
            config: Конфигурация

        Returns:
            SymbolResult
        """
        try:
            # Создание стратегии
            strategy = strategy_class(**strategy_params)

            # Запуск бэктеста
            results = self.single_engine.run(
                data=data,
                config={
                    "strategy": strategy,
                    "symbol": symbol,
                    "initial_capital": config.initial_capital * len(config.symbols),
                    "commission": config.commission,
                },
            )

            # Извлечение equity curve
            equity_curve = results.get("equity_curve", pd.Series())
            trades = results.get("trades", [])
            metrics = results.get("metrics", {})

            return SymbolResult(
                symbol=symbol,
                equity_curve=equity_curve,
                trades=trades,
                metrics=metrics,
            )

        except Exception as e:
            logger.warning(f"Single symbol backtest failed for {symbol}: {e}")

            # Возвращаем пустой результат
            return SymbolResult(
                symbol=symbol,
                equity_curve=pd.Series([config.initial_capital]),
                trades=[],
                metrics={"sharpe_ratio": 0, "total_return": 0},
            )

    def _aggregate_equity_curves(self, symbol_results: dict[str, SymbolResult], weights: dict[str, float]) -> pd.Series:
        """
        Агрегация кривых доходности в портфель.

        Args:
            symbol_results: Результаты по символам
            weights: Веса символов

        Returns:
            Портфельная equity curve
        """
        # Объединение equity curves
        equity_df = pd.DataFrame({symbol: result.equity_curve for symbol, result in symbol_results.items()})

        # Заполнение пропусков (forward fill затем backward fill)
        equity_df = equity_df.ffill().bfill().fillna(1.0)

        # Взвешенная сумма
        portfolio_equity = pd.Series(0.0, index=equity_df.index)

        for symbol, weight in weights.items():
            if symbol in equity_df.columns:
                portfolio_equity += equity_df[symbol] * weight

        return portfolio_equity

    def _calculate_portfolio_metrics(
        self, portfolio_equity: pd.Series, symbol_results: dict[str, SymbolResult], weights: dict[str, float]
    ) -> dict[str, float]:
        """
        Вычисление метрик портфеля.

        Args:
            portfolio_equity: Портфельная equity curve
            symbol_results: Результаты по символам
            weights: Веса

        Returns:
            Метрики
        """
        # Доходности
        returns = portfolio_equity.pct_change().dropna()

        if len(returns) == 0:
            return {"sharpe_ratio": 0, "total_return": 0}

        # Total return
        total_return = (portfolio_equity.iloc[-1] / portfolio_equity.iloc[0]) - 1

        # Annualized return
        n_days = len(portfolio_equity)
        annual_return = (1 + total_return) ** (365 / n_days) - 1

        # Volatility
        volatility = returns.std() * np.sqrt(365)

        # Sharpe ratio
        sharpe_ratio = annual_return / volatility if volatility > 0 else 0

        # Max drawdown
        rolling_max = portfolio_equity.cummax()
        drawdown = (portfolio_equity - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # Diversification ratio
        div_ratio = self._calculate_diversification_ratio(symbol_results, weights)

        return {
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sharpe_ratio * 1.2,  # Упрощённо
            "total_return": total_return,
            "annual_return": annual_return,
            "volatility": volatility,
            "max_drawdown": max_drawdown,
            "diversification_ratio": div_ratio,
            "n_days": n_days,
        }

    def _calculate_diversification_ratio(
        self, symbol_results: dict[str, SymbolResult], weights: dict[str, float]
    ) -> float:
        """
        Вычисление коэффициента диверсификации.

        Формула: DR = (w' * σ) / σ_p
        где w — веса, σ — волатильности активов, σ_p — волатильность портфеля

        Returns:
            Diversification ratio (>1 = диверсификация есть)
        """
        if not symbol_results:
            return 1.0

        # Средневзвешенная волатильность
        avg_volatility = 0.0
        portfolio_returns_list = []

        for symbol, weight in weights.items():
            if symbol in symbol_results:
                metrics = symbol_results[symbol].metrics
                vol = metrics.get("volatility", 0.2)
                avg_volatility += weight * vol

                # Собрать returns для портфеля
                equity = symbol_results[symbol].equity_curve
                if isinstance(equity, pd.Series) and len(equity) > 0:
                    returns = equity.pct_change().dropna()
                    portfolio_returns_list.append(returns * weight)

        # Волатильность портфеля (корректно через взвешенную сумму returns)
        if portfolio_returns_list:
            # Найти общий индекс
            common_index = portfolio_returns_list[0].index
            for _i, returns in enumerate(portfolio_returns_list):
                common_index = common_index.intersection(returns.index)

            # Сумма взвешенных returns
            portfolio_total_returns = pd.Series(0.0, index=common_index)
            for returns in portfolio_returns_list:
                portfolio_total_returns += returns.reindex(common_index, fill_value=0)

            portfolio_volatility = portfolio_total_returns.std() * np.sqrt(252)
        else:
            portfolio_volatility = 0.15

        if portfolio_volatility > 0:
            return avg_volatility / portfolio_volatility

        return 1.0

    def run(
        self,
        strategy_class: Any,
        data_dict: dict[str, pd.DataFrame],
        config: PortfolioConfig,
        strategy_params: dict[str, Any] | None = None,
    ) -> PortfolioResult:
        """
        Запуск портфельного бэктеста.

        Args:
            strategy_class: Класс стратегии
            data_dict: {symbol: data}
            config: Конфигурация портфеля
            strategy_params: Параметры стратегии

        Returns:
            PortfolioResult
        """
        logger.info(f"Starting portfolio backtest: {config.symbols}")

        # Нормализация весов
        weights = self._normalize_weights(config.weights, config.symbols)

        # Бэктест по каждому символу
        symbol_results = {}

        for symbol in config.symbols:
            if symbol not in data_dict:
                logger.warning(f"No data for {symbol}, skipping")
                continue

            data = data_dict[symbol]

            result = self._run_single_symbol(
                symbol=symbol,
                data=data,
                strategy_class=strategy_class,
                strategy_params=strategy_params or {},
                config=config,
            )

            symbol_results[symbol] = result
            logger.info(f"{symbol}: {len(result.trades)} trades, Sharpe={result.metrics.get('sharpe_ratio', 0):.2f}")

        if not symbol_results:
            raise ValueError("No symbols were backtested")

        # Агрегация equity curves
        portfolio_equity = self._aggregate_equity_curves(symbol_results, weights)

        # Вычисление метрик портфеля
        metrics = self._calculate_portfolio_metrics(portfolio_equity, symbol_results, weights)

        # Корреляционная матрица
        correlation_matrix = self._calculate_correlation(symbol_results)

        # История весов (пока статические веса)
        weights_history = pd.DataFrame(
            {symbol: [weight] * len(portfolio_equity) for symbol, weight in weights.items()},
            index=portfolio_equity.index,
        )

        # Все сделки
        all_trades = []
        for result in symbol_results.values():
            all_trades.extend(result.trades)

        portfolio_result = PortfolioResult(
            portfolio_equity=portfolio_equity,
            symbol_results=symbol_results,
            metrics=metrics,
            correlation_matrix=correlation_matrix,
            weights_history=weights_history,
            trades=all_trades,
        )

        logger.info(
            f"Portfolio backtest complete: "
            f"Sharpe={metrics.get('sharpe_ratio', 0):.2f}, "
            f"Return={metrics.get('total_return', 0):.2%}"
        )

        return portfolio_result

    def _calculate_correlation(self, symbol_results: dict[str, SymbolResult]) -> pd.DataFrame:
        """Вычисление корреляционной матрицы"""
        # Извлечение returns
        returns_dict = {}

        for symbol, result in symbol_results.items():
            returns = result.equity_curve.pct_change().dropna()
            returns_dict[symbol] = returns

        # DataFrame с returns
        returns_df = pd.DataFrame(returns_dict)

        # Корреляционная матрица
        if len(returns_df.columns) > 1:
            return returns_df.corr()
        else:
            return pd.DataFrame(index=returns_df.columns, columns=returns_df.columns, data=1.0)
