"""
🧬 Genetic Algorithm Optimizer — Selection Strategies

Стратегии селекции особей для размножения.

@version: 1.0.0
@date: 2026-02-26
"""

from abc import ABC, abstractmethod

import numpy as np

from .models import Individual, Population


class SelectionStrategy(ABC):
    """Базовый класс для стратегий селекции"""

    @abstractmethod
    def select(self, population: Population, n_parents: int) -> list[Individual]:
        """
        Выбрать родителей из популяции.

        Args:
            population: Популяция
            n_parents: Количество родителей

        Returns:
            Список выбранных особей
        """
        pass


class TournamentSelection(SelectionStrategy):
    """
    Tournament selection.

    Выбирает случайных особей и оставляет лучшую.

    Преимущества:
    - Простая реализация
    - Контролируемое давление отбора (размер турнира)
    - Работает с raw fitness значениями
    """

    def __init__(self, tournament_size: int = 3):
        """
        Args:
            tournament_size: Размер турнира (сколько особей соревнуются)
        """
        self.tournament_size = tournament_size

    def select(self, population: Population, n_parents: int) -> list[Individual]:
        parents = []

        for _ in range(n_parents):
            # Случайная выборка для турнира
            tournament = population.sample(self.tournament_size)

            # Выбор лучшей особи
            if tournament:
                best = max(tournament, key=lambda ind: ind.fitness if ind.fitness else 0)
                parents.append(best)

        return parents


class RouletteSelection(SelectionStrategy):
    """
    Roulette wheel selection (fitness-proportional).

    Вероятность выбора пропорциональна fitness особи.

    Преимущества:
    - Естественный отбор
    - Сохраняет разнообразие

    Недостатки:
    - Требует положительные fitness значения
    - Может привести к преждевременной сходимости
    """

    def __init__(self, min_fitness: float = 0.0):
        """
        Args:
            min_fitness: Минимальное fitness значение (для сдвига)
        """
        self.min_fitness = min_fitness

    def select(self, population: Population, n_parents: int) -> list[Individual]:
        parents = []
        evaluated = [ind for ind in population.individuals if ind.is_evaluated()]

        if not evaluated:
            return parents

        # Вычисление вероятностей с защитой от отрицательных fitness
        fitness_values = [max(ind.fitness if ind.fitness else 0, -1e6) for ind in evaluated]
        min_fitness = min(fitness_values)

        # Сдвиг для гарантии положительных значений
        if min_fitness <= 0:
            fitness_values = [f - min_fitness + 0.001 for f in fitness_values]

        total_fitness = sum(fitness_values)

        if total_fitness == 0:
            # Равномерное распределение если все fitness = 0
            probabilities = [1.0 / len(evaluated)] * len(evaluated)
        else:
            probabilities = [f / total_fitness for f in fitness_values]

        # Выбор родителей
        for _ in range(n_parents):
            idx = np.random.choice(len(evaluated), p=probabilities)
            parents.append(evaluated[idx])

        return parents


class RankSelection(SelectionStrategy):
    """
    Rank-based selection.

    Вероятность выбора зависит от ранга особи, а не от raw fitness.

    Преимущества:
    - Работает с любыми fitness значениями
    - Меньше чувствительна к выбросам
    - Сохраняет давление отбора на протяжении всей эволюции
    """

    def __init__(self, selective_pressure: float = 2.0):
        """
        Args:
            selective_pressure: Давление отбора (1.0 = слабое, 3.0 = сильное)
        """
        self.selective_pressure = selective_pressure

    def select(self, population: Population, n_parents: int) -> list[Individual]:
        parents = []
        evaluated = [ind for ind in population.individuals if ind.is_evaluated()]

        if not evaluated:
            return parents

        # Сортировка по fitness
        evaluated.sort(key=lambda ind: ind.fitness if ind.fitness else 0)

        # Вычисление рангов
        n = len(evaluated)
        ranks = list(range(n))  # 0 = худший, n-1 = лучший

        # Вычисление вероятностей на основе ранга
        probabilities = []
        for rank in ranks:
            prob = rank**self.selective_pressure
            probabilities.append(prob)

        total = sum(probabilities)
        probabilities = [p / total for p in probabilities] if total > 0 else [1.0 / n] * n

        # Выбор родителей
        for _ in range(n_parents):
            idx = np.random.choice(n, p=probabilities)
            parents.append(evaluated[idx])

        return parents


class SUSSelection(SelectionStrategy):
    """
    Stochastic Universal Sampling.

    Улучшенная версия roulette selection с меньшим разбросом.

    Преимущества:
    - Меньший разброс чем roulette
    - Гарантирует представление лучших особей
    """

    def __init__(self, min_fitness: float = 0.0):
        self.min_fitness = min_fitness

    def select(self, population: Population, n_parents: int) -> list[Individual]:
        parents = []
        evaluated = [ind for ind in population.individuals if ind.is_evaluated()]

        if not evaluated:
            return parents

        # Вычисление fitness с защитой от отрицательных значений
        fitness_values = [max(ind.fitness if ind.fitness else 0, -1e6) for ind in evaluated]
        min_fitness = min(fitness_values)

        # Сдвиг для гарантии положительных значений
        if min_fitness <= 0:
            fitness_values = [f - min_fitness + 0.001 for f in fitness_values]

        total_fitness = sum(fitness_values)

        if total_fitness == 0:
            return [evaluated[0]] * n_parents if evaluated else []

        # Вычисление кумулятивной суммы
        cumsum = []
        current = 0
        for f in fitness_values:
            current += f / total_fitness
            cumsum.append(current)

        # Выбор точек
        pointer_distance = 1.0 / n_parents
        start = np.random.uniform(0, pointer_distance)

        pointers = [start + i * pointer_distance for i in range(n_parents)]

        # Выбор особей
        current_idx = 0
        for pointer in pointers:
            while current_idx < len(cumsum) - 1 and cumsum[current_idx] < pointer:
                current_idx += 1
            parents.append(evaluated[current_idx])

        return parents


class TruncationSelection(SelectionStrategy):
    """
    Truncation selection.

    Выбирает только лучших особей (top X%).

    Преимущества:
    - Сильное давление отбора
    - Быстрая сходимость

    Недостатки:
    - Может потерять разнообразие
    - Риск преждевременной сходимости
    """

    def __init__(self, truncation_threshold: float = 0.5):
        """
        Args:
            truncation_threshold: Процент лучших особей (0.0-1.0)
        """
        self.truncation_threshold = truncation_threshold

    def select(self, population: Population, n_parents: int) -> list[Individual]:
        evaluated = [ind for ind in population.individuals if ind.is_evaluated()]

        if not evaluated:
            return []

        # Сортировка
        evaluated.sort(key=lambda ind: ind.fitness if ind.fitness else 0, reverse=True)

        # Выбор топ X%
        n_truncated = max(1, int(len(evaluated) * self.truncation_threshold))
        truncated = evaluated[:n_truncated]

        # Случайный выбор из лучших
        parents = []
        for _ in range(n_parents):
            parents.append(np.random.choice(truncated))

        return parents


class SelectionFactory:
    """Фабрика для создания стратегий селекции"""

    _registry = {
        "tournament": TournamentSelection,
        "roulette": RouletteSelection,
        "rank": RankSelection,
        "sus": SUSSelection,
        "truncation": TruncationSelection,
    }

    @classmethod
    def create(cls, selection_type: str, **kwargs) -> SelectionStrategy:
        """
        Создать стратегию селекции.

        Args:
            selection_type: Тип стратегии
            **kwargs: Аргументы для конструктора

        Returns:
            SelectionStrategy экземпляр
        """
        if selection_type not in cls._registry:
            raise ValueError(f"Unknown selection type: {selection_type}. Available: {list(cls._registry.keys())}")

        return cls._registry[selection_type](**kwargs)

    @classmethod
    def register(cls, name: str, strategy_class: type):
        """Зарегистрировать новую стратегию"""
        cls._registry[name] = strategy_class
