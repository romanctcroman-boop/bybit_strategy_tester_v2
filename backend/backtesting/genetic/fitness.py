"""
🧬 Genetic Algorithm Optimizer — Fitness Functions

Fitness functions для оценки особей.

@version: 1.0.0
@date: 2026-02-26
"""

from abc import ABC, abstractmethod


class FitnessFunction(ABC):
    """Базовый класс для fitness функций"""

    @abstractmethod
    def calculate(self, backtest_results: dict) -> float:
        """
        Вычислить fitness значение.

        Args:
            backtest_results: Результаты бэктеста

        Returns:
            Fitness значение (чем больше, тем лучше)
        """
        pass

    def validate_results(self, results: dict) -> bool:
        """Проверка валидности результатов"""
        return results is not None and "metrics" in results


class SharpeRatioFitness(FitnessFunction):
    """
    Fitness на основе Sharpe ratio.

    Преимущества:
    - Учитывает риск-скорректированную доходность
    - Стандартная метрика в трейдинге
    """

    def __init__(self, risk_free_rate: float = 0.0):
        self.risk_free_rate = risk_free_rate

    def calculate(self, backtest_results: dict) -> float:
        if not self.validate_results(backtest_results):
            return 0.0

        metrics = backtest_results.get("metrics", {})
        sharpe = metrics.get("sharpe_ratio", 0.0)

        # Штраф за недостаточное количество сделок
        total_trades = metrics.get("total_trades", 0)
        if total_trades < 10:
            sharpe *= total_trades / 10

        return sharpe


class SortinoRatioFitness(FitnessFunction):
    """Fitness на основе Sortino ratio"""

    def calculate(self, backtest_results: dict) -> float:
        if not self.validate_results(backtest_results):
            return 0.0

        metrics = backtest_results.get("metrics", {})
        sortino = metrics.get("sortino_ratio", 0.0)

        # Штраф за недостаточное количество сделок
        total_trades = metrics.get("total_trades", 0)
        if total_trades < 10:
            sortino *= total_trades / 10

        return sortino


class TotalReturnFitness(FitnessFunction):
    """Fitness на основе общей доходности"""

    def calculate(self, backtest_results: dict) -> float:
        if not self.validate_results(backtest_results):
            return 0.0

        metrics = backtest_results.get("metrics", {})
        total_return = metrics.get("total_return", 0.0)

        return total_return


class CalmarRatioFitness(FitnessFunction):
    """
    Fitness на основе Calmar ratio (Return / Max DD).

    Преимущества:
    - Учитывает максимальную просадку
    - Хорошая метрика для риск-менеджмента
    """

    def calculate(self, backtest_results: dict) -> float:
        if not self.validate_results(backtest_results):
            return 0.0

        metrics = backtest_results.get("metrics", {})
        calmar = metrics.get("calmar_ratio", 0.0)

        return calmar


class MultiObjectiveFitness(FitnessFunction):
    """
    Multi-objective fitness функция.

    Комбинирует несколько метрик с весами:
    - Sharpe ratio (риск-скорректированная доходность)
    - Win rate (процент прибыльных сделок)
    - Max drawdown (штраф за просадку)
    - Total return (общая доходность)
    """

    def __init__(self, weights: dict[str, float] | None = None, normalize: bool = True):
        """
        Args:
            weights: Веса метрик {metric_name: weight}
            normalize: Нормализовать ли метрики
        """
        self.weights = weights or {
            "sharpe_ratio": 0.4,
            "win_rate": 0.2,
            "max_drawdown": 0.2,  # Минимизируем
            "total_return": 0.2,
        }
        self.normalize = normalize

        # Нормализация весов
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            self.weights = {k: v / total_weight for k, v in self.weights.items()}

    def _normalize_value(
        self, value: float, metric_name: str, min_vals: dict[str, float], max_vals: dict[str, float]
    ) -> float:
        """Нормализация значения к [0, 1]"""
        if metric_name not in min_vals or metric_name not in max_vals:
            return value

        min_val = min_vals[metric_name]
        max_val = max_vals[metric_name]

        if max_val - min_val == 0:
            return 0.5

        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))

    def calculate(
        self, backtest_results: dict, min_vals: dict[str, float] | None = None, max_vals: dict[str, float] | None = None
    ) -> float:
        if not self.validate_results(backtest_results):
            return 0.0

        metrics = backtest_results.get("metrics", {})
        fitness = 0.0

        for metric_name, weight in self.weights.items():
            value = metrics.get(metric_name, 0.0)

            # Для max_drawdown инвертируем знак (минимизируем просадку)
            if metric_name == "max_drawdown":
                value = -abs(value)

            # Нормализация
            if self.normalize and min_vals and max_vals:
                value = self._normalize_value(value, metric_name, min_vals, max_vals)

            fitness += value * weight

        # Штраф за недостаточное количество сделок
        total_trades = metrics.get("total_trades", 0)
        if total_trades < 10:
            fitness *= total_trades / 10

        return fitness

    def calculate_multi(self, backtest_results: dict) -> dict[str, float]:
        """
        Вычислить все метрики для multi-objective анализа.

        Returns:
            Словарь {metric_name: value}
        """
        if not self.validate_results(backtest_results):
            return {}

        metrics = backtest_results.get("metrics", {})

        return {
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
            "sortino_ratio": metrics.get("sortino_ratio", 0.0),
            "win_rate": metrics.get("win_rate", 0.0),
            "max_drawdown": -abs(metrics.get("max_drawdown", 0.0)),
            "total_return": metrics.get("total_return", 0.0),
            "calmar_ratio": metrics.get("calmar_ratio", 0.0),
            "profit_factor": metrics.get("profit_factor", 0.0),
        }


class CustomFitness(FitnessFunction):
    """
    Пользовательская fitness функция.

    Позволяет задать произвольную формулу через callable.
    """

    def __init__(self, fitness_fn):
        """
        Args:
            fitness_fn: Функция (Dict) -> float
        """
        self.fitness_fn = fitness_fn

    def calculate(self, backtest_results: dict) -> float:
        if not self.validate_results(backtest_results):
            return 0.0

        try:
            return self.fitness_fn(backtest_results)
        except Exception as e:
            print(f"Custom fitness calculation error: {e}")
            return 0.0


class RiskAdjustedFitness(FitnessFunction):
    """
    Fitness с учётом риска.

    Формула: (Return - Risk Free) / (Volatility + Penalty)
    """

    def __init__(self, risk_free_rate: float = 0.0, volatility_penalty: float = 0.1):
        self.risk_free_rate = risk_free_rate
        self.volatility_penalty = volatility_penalty

    def calculate(self, backtest_results: dict) -> float:
        if not self.validate_results(backtest_results):
            return 0.0

        metrics = backtest_results.get("metrics", {})

        total_return = metrics.get("total_return", 0.0)
        volatility = metrics.get("volatility", 1.0)

        # Risk-adjusted return
        excess_return = total_return - self.risk_free_rate
        risk = volatility + self.volatility_penalty

        if risk == 0:
            return excess_return

        return excess_return / risk


class FitnessFactory:
    """Фабрика для создания fitness функций"""

    _registry = {
        "sharpe": SharpeRatioFitness,
        "sortino": SortinoRatioFitness,
        "total_return": TotalReturnFitness,
        "calmar": CalmarRatioFitness,
        "multi_objective": MultiObjectiveFitness,
        "risk_adjusted": RiskAdjustedFitness,
    }

    @classmethod
    def create(cls, fitness_type: str, **kwargs) -> FitnessFunction:
        """
        Создать fitness функцию.

        Args:
            fitness_type: Тип функции ('sharpe', 'sortino', 'multi_objective', etc.)
            **kwargs: Аргументы для конструктора

        Returns:
            FitnessFunction экземпляр
        """
        if fitness_type not in cls._registry:
            raise ValueError(f"Unknown fitness type: {fitness_type}. Available: {list(cls._registry.keys())}")

        return cls._registry[fitness_type](**kwargs)

    @classmethod
    def register(cls, name: str, fitness_class: type):
        """Зарегистрировать новую fitness функцию"""
        cls._registry[name] = fitness_class
