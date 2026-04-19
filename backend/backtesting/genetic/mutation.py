"""
🧬 Genetic Algorithm Optimizer — Mutation Operators

Операторы мутации для внесения разнообразия.

@version: 1.0.0
@date: 2026-02-26
"""

from abc import ABC, abstractmethod

import numpy as np

from .models import Chromosome, Individual


class MutationOperator(ABC):
    """Базовый класс для операторов мутации"""

    @abstractmethod
    def mutate(self, individual: Individual, rate: float) -> Individual:
        """
        Мутировать особь.

        Args:
            individual: Особь для мутации
            rate: Вероятность мутации гена (0.0-1.0)

        Returns:
            Мутировавшая особь
        """
        pass


class GaussianMutation(MutationOperator):
    """
    Мутация гауссовским шумом.

    Добавляет случайный шум из нормального распределения.

    Формула:
        gene = gene + N(0, sigma)

    Преимущества:
    - Плавные изменения
    - Хорошо для непрерывных параметров
    """

    def __init__(self, sigma: float = 0.1):
        """
        Args:
            sigma: Стандартное отклонение гауссовского шума
        """
        self.sigma = sigma

    def mutate(self, individual: Individual, rate: float) -> Individual:
        genes = individual.chromosome.genes.copy()
        param_ranges = individual.chromosome.param_ranges

        for gene_name in genes:
            if np.random.random() < rate:
                # Гауссовская мутация
                noise = np.random.normal(0, self.sigma)
                genes[gene_name] += noise

                # Ограничение диапазона
                if gene_name in param_ranges:
                    min_val, max_val = param_ranges[gene_name]
                    genes[gene_name] = np.clip(genes[gene_name], min_val, max_val)

        # Создание мутировавшей особи со сброшенным fitness
        mutant = Individual(
            chromosome=Chromosome(genes=genes, param_ranges=param_ranges),
            fitness=None,  # Сброс fitness для повторной оценки
            fitness_multi=None,  # Сброс multi-fitness
            generation=individual.generation,
            parents=individual.parents,
        )

        return mutant


class UniformMutation(MutationOperator):
    """
    Равномерная мутация.

    Заменяет ген на случайное значение из диапазона.

    Преимущества:
    - Сильные изменения
    - Хорош для выхода из локальных оптимумов
    """

    def __init__(self, range_fraction: float = 0.1):
        """
        Args:
            range_fraction: Доля диапазона для мутации
        """
        self.range_fraction = range_fraction

    def mutate(self, individual: Individual, rate: float) -> Individual:
        genes = individual.chromosome.genes.copy()
        param_ranges = individual.chromosome.param_ranges

        for gene_name in genes:
            if np.random.random() < rate:
                if gene_name in param_ranges:
                    min_val, max_val = param_ranges[gene_name]
                    range_size = max_val - min_val

                    # Мутация в пределах доли диапазона
                    mutation_range = range_size * self.range_fraction
                    new_value = genes[gene_name] + np.random.uniform(-mutation_range, mutation_range)

                    # Ограничение диапазона
                    genes[gene_name] = np.clip(new_value, min_val, max_val)
                else:
                    # Нет диапазона — небольшая мутация
                    genes[gene_name] *= np.random.uniform(0.9, 1.1)

        # Создание мутировавшей особи со сброшенным fitness
        mutant = Individual(
            chromosome=Chromosome(genes=genes, param_ranges=param_ranges),
            fitness=None,  # Сброс fitness для повторной оценки
            fitness_multi=None,  # Сброс multi-fitness
            generation=individual.generation,
            parents=individual.parents,
        )

        return mutant


class AdaptiveMutation(MutationOperator):
    """
    Адаптивная мутация.

    Сила мутации зависит от разнообразия популяции.

    Преимущества:
    - Автоматическая настройка силы мутации
    - Сильная мутация при низком разнообразии
    - Слабая мутация при высоком разнообразии
    """

    def __init__(
        self, base_sigma: float = 0.1, min_sigma: float = 0.01, max_sigma: float = 0.5, diversity_threshold: float = 0.3
    ):
        """
        Args:
            base_sigma: Базовое стандартное отклонение
            min_sigma: Минимальное отклонение
            max_sigma: Максимальное отклонение
            diversity_threshold: Порог разнообразия
        """
        self.base_sigma = base_sigma
        self.min_sigma = min_sigma
        self.max_sigma = max_sigma
        self.diversity_threshold = diversity_threshold
        self._current_diversity: float | None = None

    def set_diversity(self, diversity: float):
        """Установить текущее разнообразие популяции"""
        self._current_diversity = diversity

    def _calculate_sigma(self, diversity: float | None = None) -> float:
        """Вычислить адаптивное sigma на основе разнообразия"""
        div = diversity if diversity is not None else self._current_diversity

        if div is None:
            return self.base_sigma

        sigma = self.max_sigma if div < self.diversity_threshold else self.base_sigma
        return sigma

    def mutate(self, individual: Individual, rate: float, diversity: float | None = None) -> Individual:
        # Вычисление адаптивного sigma
        sigma = self._calculate_sigma(diversity)

        genes = individual.chromosome.genes.copy()
        param_ranges = individual.chromosome.param_ranges

        for gene_name in genes:
            if np.random.random() < rate:
                # Адаптивная гауссовская мутация
                noise = np.random.normal(0, sigma)
                genes[gene_name] += noise

                # Ограничение диапазона
                if gene_name in param_ranges:
                    min_val, max_val = param_ranges[gene_name]
                    genes[gene_name] = np.clip(genes[gene_name], min_val, max_val)

        # Создание мутировавшей особи со сброшенным fitness
        mutant = Individual(
            chromosome=Chromosome(genes=genes, param_ranges=param_ranges),
            fitness=None,  # Сброс fitness для повторной оценки
            fitness_multi=None,  # Сброс multi-fitness
            generation=individual.generation,
            parents=individual.parents,
        )

        return mutant


class BoundaryMutation(MutationOperator):
    """
    Мутация к границам диапазона.

    С вероятностью p заменяет ген на минимальное или максимальное значение.

    Преимущества:
    - Исследует границы пространства параметров
    - Хорош для нахождения экстремальных значений
    """

    def __init__(self, boundary_probability: float = 0.5):
        """
        Args:
            boundary_probability: Вероятность выбора границы
        """
        self.boundary_probability = boundary_probability

    def mutate(self, individual: Individual, rate: float) -> Individual:
        genes = individual.chromosome.genes.copy()
        param_ranges = individual.chromosome.param_ranges

        for gene_name in genes:
            if np.random.random() < rate and gene_name in param_ranges:
                min_val, max_val = param_ranges[gene_name]

                # Выбор границы
                if np.random.random() < self.boundary_probability:
                    genes[gene_name] = min_val
                else:
                    genes[gene_name] = max_val

        # Создание мутировавшей особи со сброшенным fitness
        mutant = Individual(
            chromosome=Chromosome(genes=genes, param_ranges=param_ranges),
            fitness=None,  # Сброс fitness для повторной оценки
            fitness_multi=None,  # Сброс multi-fitness
            generation=individual.generation,
            parents=individual.parents,
        )

        return mutant


class NonUniformMutation(MutationOperator):
    """
    Неоднородная мутация.

    Сила мутации уменьшается с поколениями.

    Формула:
        sigma(t) = sigma_0 * (1 - t / T)^b

    где:
        t — текущее поколение
        T — максимальное количество поколений
        b — коэффициент затухания

    Преимущества:
    - Сильная мутация в начале (исследование)
    - Слабая мутация в конце (эксплуатация)
    """

    def __init__(self, base_sigma: float = 0.5, decay_power: float = 2.0):
        """
        Args:
            base_sigma: Базовое стандартное отклонение
            decay_power: Степень затухания
        """
        self.base_sigma = base_sigma
        self.decay_power = decay_power
        self._current_generation: int = 0
        self._max_generations: int = 100

    def set_generation(self, current: int, max_gen: int):
        """Установить текущее поколение"""
        self._current_generation = current
        self._max_generations = max_gen

    def _calculate_sigma(self, current_generation: int | None = None, max_generations: int | None = None) -> float:
        """Вычислить неоднородное sigma"""
        current = current_generation if current_generation is not None else self._current_generation
        max_gen = max_generations if max_generations is not None else self._max_generations

        if max_gen > 0:
            progress = current / max_gen
            sigma = self.base_sigma * (1 - progress) ** self.decay_power
            return max(sigma, 0.001)  # Минимальное sigma для избежания нуля
        else:
            return self.base_sigma

    def mutate(
        self, individual: Individual, rate: float, current_generation: int = 0, max_generations: int = 100
    ) -> Individual:
        # Вычисление неоднородного sigma
        sigma = self._calculate_sigma(current_generation, max_generations)

        genes = individual.chromosome.genes.copy()
        param_ranges = individual.chromosome.param_ranges

        for gene_name in genes:
            if np.random.random() < rate:
                # Неоднородная гауссовская мутация
                noise = np.random.normal(0, sigma)
                genes[gene_name] += noise

                # Ограничение диапазона
                if gene_name in param_ranges:
                    min_val, max_val = param_ranges[gene_name]
                    genes[gene_name] = np.clip(genes[gene_name], min_val, max_val)

        # Создание мутировавшей особи со сброшенным fitness
        mutant = Individual(
            chromosome=Chromosome(genes=genes, param_ranges=param_ranges),
            fitness=None,  # Сброс fitness для повторной оценки
            fitness_multi=None,  # Сброс multi-fitness
            generation=individual.generation,
            parents=individual.parents,
        )

        return mutant


class MutationFactory:
    """Фабрика для создания операторов мутации"""

    _registry = {
        "gaussian": GaussianMutation,
        "uniform": UniformMutation,
        "adaptive": AdaptiveMutation,
        "boundary": BoundaryMutation,
        "non_uniform": NonUniformMutation,
    }

    @classmethod
    def create(cls, mutation_type: str, **kwargs) -> MutationOperator:
        """
        Создать оператор мутации.

        Args:
            mutation_type: Тип оператора
            **kwargs: Аргументы для конструктора

        Returns:
            MutationOperator экземпляр
        """
        if mutation_type not in cls._registry:
            raise ValueError(f"Unknown mutation type: {mutation_type}. Available: {list(cls._registry.keys())}")

        return cls._registry[mutation_type](**kwargs)

    @classmethod
    def register(cls, name: str, operator_class: type):
        """Зарегистрировать новый оператор"""
        cls._registry[name] = operator_class  # type: ignore[assignment]
