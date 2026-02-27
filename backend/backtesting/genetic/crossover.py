"""
🧬 Genetic Algorithm Optimizer — Crossover Operators

Операторы кроссовера для создания потомков.

@version: 1.0.0
@date: 2026-02-26
"""

from abc import ABC, abstractmethod
from typing import List, Tuple

import numpy as np

from .models import Chromosome, Individual


class CrossoverOperator(ABC):
    """Базовый класс для операторов кроссовера"""

    @abstractmethod
    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """
        Создать потомков из двух родителей.

        Args:
            parent1: Первый родитель
            parent2: Второй родитель

        Returns:
            Кортеж (child1, child2)
        """
        pass


class SinglePointCrossover(CrossoverOperator):
    """
    Одноточечный кроссовер.

    Разбивает хромосому в одной точке и обменивается частями.

    Преимущества:
    - Простая реализация
    - Сохраняет блоки генов

    Недостатки:
    - Ограниченное разнообразие
    """

    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        genes1 = parent1.chromosome.genes.copy()
        genes2 = parent2.chromosome.genes.copy()

        gene_names = list(genes1.keys())

        if len(gene_names) < 2:
            # Слишком мало генов для кроссовера
            return parent1.copy(), parent2.copy()

        # Выбор точки кроссовера
        crossover_point = np.random.randint(1, len(gene_names))

        # Обмен генами после точки кроссовера
        for i in range(crossover_point, len(gene_names)):
            gene_name = gene_names[i]
            genes1[gene_name], genes2[gene_name] = genes2[gene_name], genes1[gene_name]

        # Создание потомков
        child1 = Individual(
            chromosome=Chromosome(genes=genes1, param_ranges=parent1.chromosome.param_ranges),
            generation=max(parent1.generation, parent2.generation) + 1,
            parents=(parent1.id, parent2.id),
        )

        child2 = Individual(
            chromosome=Chromosome(genes=genes2, param_ranges=parent2.chromosome.param_ranges),
            generation=max(parent1.generation, parent2.generation) + 1,
            parents=(parent1.id, parent2.id),
        )

        return child1, child2


class TwoPointCrossover(CrossoverOperator):
    """
    Двухточечный кроссовер.

    Разбивает хромосому в двух точках и обменивается средней частью.

    Преимущества:
    - Больше разнообразия чем single-point
    - Сохраняет блоки генов
    """

    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        genes1 = parent1.chromosome.genes.copy()
        genes2 = parent2.chromosome.genes.copy()

        gene_names = list(genes1.keys())

        if len(gene_names) < 3:
            # Слишком мало генов
            return parent1.copy(), parent2.copy()

        # Выбор двух точек
        point1 = np.random.randint(1, len(gene_names) - 1)
        point2 = np.random.randint(point1 + 1, len(gene_names))

        # Обмен генами между точками
        for i in range(point1, point2 + 1):
            gene_name = gene_names[i]
            genes1[gene_name], genes2[gene_name] = genes2[gene_name], genes1[gene_name]

        # Создание потомков
        child1 = Individual(
            chromosome=Chromosome(genes=genes1, param_ranges=parent1.chromosome.param_ranges),
            generation=max(parent1.generation, parent2.generation) + 1,
            parents=(parent1.id, parent2.id),
        )

        child2 = Individual(
            chromosome=Chromosome(genes=genes2, param_ranges=parent2.chromosome.param_ranges),
            generation=max(parent1.generation, parent2.generation) + 1,
            parents=(parent1.id, parent2.id),
        )

        return child1, child2


class UniformCrossover(CrossoverOperator):
    """
    Равномерный кроссовер.

    Каждый ген выбирается случайно от одного из родителей.

    Преимущества:
    - Максимальное разнообразие
    - Не зависит от порядка генов

    Недостатки:
    - Разрушает блоки генов
    """

    def __init__(self, exchange_probability: float = 0.5):
        """
        Args:
            exchange_probability: Вероятность обмена гена (0.0-1.0)
        """
        self.exchange_probability = exchange_probability

    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        genes1 = parent1.chromosome.genes.copy()
        genes2 = parent2.chromosome.genes.copy()

        gene_names = list(genes1.keys())

        # Для каждого гена решаем, обменивать или нет
        for gene_name in gene_names:
            if np.random.random() < self.exchange_probability:
                genes1[gene_name], genes2[gene_name] = genes2[gene_name], genes1[gene_name]

        # Создание потомков
        child1 = Individual(
            chromosome=Chromosome(genes=genes1, param_ranges=parent1.chromosome.param_ranges),
            generation=max(parent1.generation, parent2.generation) + 1,
            parents=(parent1.id, parent2.id),
        )

        child2 = Individual(
            chromosome=Chromosome(genes=genes2, param_ranges=parent2.chromosome.param_ranges),
            generation=max(parent1.generation, parent2.generation) + 1,
            parents=(parent1.id, parent2.id),
        )

        return child1, child2


class ArithmeticCrossover(CrossoverOperator):
    """
    Арифмететический кроссовер.

    Создает потомков как линейную комбинацию родителей.

    Формула:
        child1 = alpha * parent1 + (1 - alpha) * parent2
        child2 = (1 - alpha) * parent1 + alpha * parent2

    Преимущества:
    - Работает с непрерывными параметрами
    - Создает потомков в пространстве между родителями

    Недостатки:
    - Не работает с дискретными параметрами
    """

    def __init__(self, alpha: float = 0.5):
        """
        Args:
            alpha: Коэффициент смешивания (0.0-1.0)
                   0.5 = равный вклад родителей
                   alpha = фиксированный
        """
        self.alpha = alpha

    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        genes1 = {}
        genes2 = {}

        gene_names = list(parent1.chromosome.genes.keys())

        # Вычисление потомков
        for gene_name in gene_names:
            val1 = parent1.chromosome.genes[gene_name]
            val2 = parent2.chromosome.genes[gene_name]

            # Арифметический кроссовер с фиксированным alpha
            alpha = self.alpha

            # Арифметический кроссовер
            genes1[gene_name] = alpha * val1 + (1 - alpha) * val2
            genes2[gene_name] = (1 - alpha) * val1 + alpha * val2

        # Создание потомков
        child1 = Individual(
            chromosome=Chromosome(genes=genes1, param_ranges=parent1.chromosome.param_ranges),
            generation=max(parent1.generation, parent2.generation) + 1,
            parents=(parent1.id, parent2.id),
        )

        child2 = Individual(
            chromosome=Chromosome(genes=genes2, param_ranges=parent2.chromosome.param_ranges),
            generation=max(parent1.generation, parent2.generation) + 1,
            parents=(parent1.id, parent2.id),
        )

        return child1, child2


class BlendCrossover(CrossoverOperator):
    """
    BLX-α (Blend Crossover).

    Создает потомков в расширенном диапазоне родителей.

    Формула:
        d = |parent1 - parent2|
        child = random(parent1 - α*d, parent2 + α*d)

    Преимущества:
    - Расширяет поисковое пространство
    - Хорош для непрерывной оптимизации
    """

    def __init__(self, alpha: float = 0.5):
        """
        Args:
            alpha: Коэффициент расширения диапазона
        """
        self.alpha = alpha

    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        genes1 = {}
        genes2 = {}

        gene_names = list(parent1.chromosome.genes.keys())

        for gene_name in gene_names:
            val1 = parent1.chromosome.genes[gene_name]
            val2 = parent2.chromosome.genes[gene_name]

            # Вычисление расширенного диапазона
            d = abs(val1 - val2)
            min_val = min(val1, val2) - self.alpha * d
            max_val = max(val1, val2) + self.alpha * d

            # Случайный выбор в диапазоне
            genes1[gene_name] = np.random.uniform(min_val, max_val)
            genes2[gene_name] = np.random.uniform(min_val, max_val)

        # Создание потомков
        child1 = Individual(
            chromosome=Chromosome(genes=genes1, param_ranges=parent1.chromosome.param_ranges),
            generation=max(parent1.generation, parent2.generation) + 1,
            parents=(parent1.id, parent2.id),
        )

        child2 = Individual(
            chromosome=Chromosome(genes=genes2, param_ranges=parent2.chromosome.param_ranges),
            generation=max(parent1.generation, parent2.generation) + 1,
            parents=(parent1.id, parent2.id),
        )

        return child1, child2


class CrossoverFactory:
    """Фабрика для создания операторов кроссовера"""

    _registry = {
        "single_point": SinglePointCrossover,
        "two_point": TwoPointCrossover,
        "uniform": UniformCrossover,
        "arithmetic": ArithmeticCrossover,
        "blend": BlendCrossover,
    }

    @classmethod
    def create(cls, crossover_type: str, **kwargs) -> CrossoverOperator:
        """
        Создать оператор кроссовера.

        Args:
            crossover_type: Тип оператора
            **kwargs: Аргументы для конструктора

        Returns:
            CrossoverOperator экземпляр
        """
        if crossover_type not in cls._registry:
            raise ValueError(f"Unknown crossover type: {crossover_type}. Available: {list(cls._registry.keys())}")

        return cls._registry[crossover_type](**kwargs)

    @classmethod
    def register(cls, name: str, operator_class: type):
        """Зарегистрировать новый оператор"""
        cls._registry[name] = operator_class
