"""
🧬 Genetic Algorithm Optimizer — Models

Core data models for genetic algorithm optimization.

@version: 1.1.0
@date: 2026-02-27
"""

import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import numpy as np


@dataclass
class Chromosome:
    """
    Хромосома — набор параметров стратегии.

    Attributes:
        genes: Словарь {имя_параметра: значение}
        param_ranges: Диапазоны параметров {name: (min, max)}
    """

    genes: dict[str, float]
    param_ranges: dict[str, tuple] = field(default_factory=dict)

    def __post_init__(self):
        """Валидация генов"""
        for name, value in self.genes.items():
            if name in self.param_ranges:
                min_val, max_val = self.param_ranges[name]
                if not (min_val <= value <= max_val):
                    raise ValueError(f"Gene '{name}' value {value} out of range [{min_val}, {max_val}]")

    def copy(self) -> "Chromosome":
        """Глубокое копирование"""
        return Chromosome(genes=self.genes.copy(), param_ranges=self.param_ranges.copy())

    def to_dict(self) -> dict[str, float]:
        """Конвертация в словарь"""
        return self.genes.copy()

    @classmethod
    def random(cls, param_ranges: dict[str, tuple]) -> "Chromosome":
        """
        Создать случайную хромосому в заданных диапазонах.

        Args:
            param_ranges: {name: (min, max)}

        Returns:
            Chromosome со случайными генами
        """
        genes = {}
        for name, (min_val, max_val) in param_ranges.items():
            # Проверка на целочисленные параметры
            if isinstance(min_val, int) and isinstance(max_val, int):
                genes[name] = np.random.randint(min_val, max_val + 1)
            else:
                genes[name] = np.random.uniform(min_val, max_val)

        return cls(genes=genes, param_ranges=param_ranges)

    def __len__(self) -> int:
        return len(self.genes)

    def __getitem__(self, key: str) -> float:
        return self.genes[key]

    def __setitem__(self, key: str, value: float):
        if key in self.param_ranges:
            min_val, max_val = self.param_ranges[key]
            value = max(min_val, min(max_val, value))
        self.genes[key] = value

    def get_hash(self) -> str:
        """Создать хэш хромосомы для кэширования"""
        genes_str = str(sorted(self.genes.items()))
        return hashlib.md5(genes_str.encode()).hexdigest()


@dataclass
class Individual:
    """
    Особь — индивидуум в популяции с хромосомой и fitness.

    Attributes:
        chromosome: Хромосома с параметрами
        fitness: Единственное значение fitness (для single-objective)
        fitness_multi: Словарь метрик (для multi-objective)
        generation: Поколение, в котором создана особь
        id: Уникальный идентификатор
        parents: ID родителей (для отслеживания родословной)
    """

    chromosome: Chromosome
    fitness: float | None = None
    fitness_multi: dict[str, float] | None = None
    generation: int = 0
    id: UUID = field(default_factory=uuid4)
    parents: tuple[str, str] | None = None  # UUID как строки для сериализации
    backtest_results: dict | None = None  # Результаты бэктеста
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def copy(self) -> "Individual":
        """Глубокое копирование"""
        return Individual(
            chromosome=self.chromosome.copy(),
            fitness=self.fitness,
            fitness_multi=self.fitness_multi.copy() if self.fitness_multi else None,
            generation=self.generation,
            id=uuid4(),  # Новый ID для копии
            parents=(str(self.id),) if self.id else None,  # Конвертация в строку
            backtest_results=self.backtest_results.copy() if self.backtest_results else None,
        )

    def is_evaluated(self) -> bool:
        """Проверка, вычислен ли fitness"""
        return self.fitness is not None

    def set_fitness(self, value: float):
        """Потокобезопасная установка fitness"""
        with self._lock:
            self.fitness = value

    def get_fitness(self, fitness_key: str = "fitness") -> float:
        """
        Получить fitness значение.

        Args:
            fitness_key: Ключ для multi-objective ('sharpe', 'win_rate', etc.)

        Returns:
            Fitness значение
        """
        with self._lock:
            if self.fitness is not None:
                return self.fitness

            if self.fitness_multi and fitness_key in self.fitness_multi:
                return self.fitness_multi[fitness_key]

            raise ValueError("Individual not evaluated yet")

    def to_dict(self) -> dict[str, Any]:
        """Конвертация в словарь"""
        return {
            "id": str(self.id),
            "chromosome": self.chromosome.to_dict(),
            "fitness": self.fitness,
            "fitness_multi": self.fitness_multi,
            "generation": self.generation,
            "parents": [str(p) for p in self.parents] if self.parents else None,
        }

    def __lt__(self, other: "Individual") -> bool:
        """Сравнение по fitness (для сортировки)"""
        if self.fitness is None or other.fitness is None:
            return False
        return self.fitness < other.fitness


@dataclass
class Population:
    """
    Популяция особей.

    Attributes:
        individuals: Список особей
        generation: Текущее поколение
        best_individual: Лучшая особь
        avg_fitness: Средний fitness
        diversity: Мера разнообразия популяции
    """

    individuals: list[Individual]
    generation: int = 0
    best_individual: Individual | None = None
    avg_fitness: float = 0.0
    diversity: float = 0.0
    param_ranges: dict[str, tuple] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def __post_init__(self):
        """Инициализация статистики после создания"""
        self.update_statistics()

    def update_statistics(self):
        """Обновить статистику популяции (потокобезопасно)"""
        with self._lock:
            if not self.individuals:
                return

            # Найдем лучшую особь
            evaluated = [ind for ind in self.individuals if ind.is_evaluated()]
            if evaluated:
                self.best_individual = max(evaluated, key=lambda x: x.fitness if x.fitness else 0)
                self.avg_fitness = np.mean([ind.fitness for ind in evaluated if ind.fitness])

            # Вычислим разнообразие (среднее расстояние между хромосомами)
            self.diversity = self._calculate_diversity()

    def _calculate_diversity(self) -> float:
        """
        Вычислить разнообразие популяции.

        Returns:
            Среднее евклидово расстояние между хромосомами
        """
        if len(self.individuals) < 2:
            return 0.0

        chromosomes = [ind.chromosome for ind in self.individuals]
        distances = []

        for i in range(len(chromosomes)):
            for j in range(i + 1, len(chromosomes)):
                dist = self._chromosome_distance(chromosomes[i], chromosomes[j])
                distances.append(dist)

        return np.mean(distances) if distances else 0.0

    def _chromosome_distance(self, c1: Chromosome, c2: Chromosome) -> float:
        """
        Евклидово расстояние между хромосомами.

        Args:
            c1: Первая хромосома
            c2: Вторая хромосома

        Returns:
            Расстояние
        """
        # Нормализуем параметры по диапазонам
        distance = 0.0
        count = 0

        for gene_name in c1.genes:
            if gene_name in c2.genes and gene_name in self.param_ranges:
                min_val, max_val = self.param_ranges[gene_name]
                range_size = max_val - min_val

                if range_size > 0:
                    norm1 = (c1.genes[gene_name] - min_val) / range_size
                    norm2 = (c2.genes[gene_name] - min_val) / range_size
                    distance += (norm1 - norm2) ** 2
                    count += 1

        return np.sqrt(distance / count) if count > 0 else 0.0

    def add(self, individual: Individual):
        """Добавить особь в популяцию (потокобезопасно)"""
        with self._lock:
            self.individuals.append(individual)
            self.update_statistics()

    def remove(self, individual_id: UUID):
        """Удалить особь из популяции (потокобезопасно)"""
        with self._lock:
            self.individuals = [ind for ind in self.individuals if ind.id != individual_id]
            self.update_statistics()

    def get_best(self, n: int = 1) -> list[Individual]:
        """
        Получить лучших особей (потокобезопасно).

        Args:
            n: Количество особей

        Returns:
            Список лучших особей
        """
        with self._lock:
            evaluated = [ind for ind in self.individuals if ind.is_evaluated()]
            evaluated.sort(key=lambda x: x.fitness if x.fitness else 0, reverse=True)
            return evaluated[:n]

    def get_worst(self, n: int = 1) -> list[Individual]:
        """Получить худших особей (потокобезопасно)"""
        with self._lock:
            evaluated = [ind for ind in self.individuals if ind.is_evaluated()]
            evaluated.sort(key=lambda x: x.fitness if x.fitness else 0)
            return evaluated[:n]

    def sample(self, n: int, exclude: UUID | None = None) -> list[Individual]:
        """
        Случайная выборка особей (потокобезопасно).

        Args:
            n: Размер выборки
            exclude: ID особи для исключения

        Returns:
            Список особей
        """
        with self._lock:
            pool = [ind for ind in self.individuals if ind.id != exclude]
            return np.random.choice(pool, size=min(n, len(pool)), replace=False).tolist()

    def to_dict(self) -> dict[str, Any]:
        """Конвертация в словарь"""
        return {
            "generation": self.generation,
            "size": len(self.individuals),
            "best_fitness": self.best_individual.fitness if self.best_individual else None,
            "avg_fitness": self.avg_fitness,
            "diversity": self.diversity,
            "individuals": [ind.to_dict() for ind in self.individuals],
        }

    def __len__(self) -> int:
        return len(self.individuals)

    def __iter__(self):
        return iter(self.individuals)

    def __getitem__(self, index: int) -> Individual:
        return self.individuals[index]


@dataclass
class EvolutionHistory:
    """
    История эволюции популяции.

    Attributes:
        best_fitness_per_gen: Лучший fitness по поколениям
        avg_fitness_per_gen: Средний fitness по поколениям
        diversity_per_gen: Разнообразие по поколениям
        pareto_front: Pareto front (для multi-objective)
        max_history_length: Максимальная длина истории (защита от переполнения памяти)
    """

    best_fitness_per_gen: list[float] = field(default_factory=list)
    avg_fitness_per_gen: list[float] = field(default_factory=list)
    diversity_per_gen: list[float] = field(default_factory=list)
    pareto_front: list[Individual] = field(default_factory=list)
    max_history_length: int = 1000

    def record_generation(self, population: Population):
        """
        Записать статистику поколения.

        Args:
            population: Текущая популяция
        """
        # Ограничение истории для защиты от переполнения памяти
        if len(self.best_fitness_per_gen) >= self.max_history_length:
            half = self.max_history_length // 2
            self.best_fitness_per_gen = self.best_fitness_per_gen[-half:]
            self.avg_fitness_per_gen = self.avg_fitness_per_gen[-half:]
            self.diversity_per_gen = self.diversity_per_gen[-half:]

        self.best_fitness_per_gen.append(population.best_individual.fitness if population.best_individual else 0)
        self.avg_fitness_per_gen.append(population.avg_fitness)
        self.diversity_per_gen.append(population.diversity)

    def get_improvement(self) -> float:
        """
        Получить общее улучшение fitness.

        Returns:
            Процент улучшения
        """
        if len(self.best_fitness_per_gen) < 2:
            return 0.0

        initial = self.best_fitness_per_gen[0]
        final = self.best_fitness_per_gen[-1]

        if initial == 0:
            return final

        return ((final - initial) / abs(initial)) * 100

    def to_dict(self) -> dict[str, Any]:
        """Конвертация в словарь"""
        return {
            "best_fitness_per_gen": self.best_fitness_per_gen,
            "avg_fitness_per_gen": self.avg_fitness_per_gen,
            "diversity_per_gen": self.diversity_per_gen,
            "pareto_front": [ind.to_dict() for ind in self.pareto_front],
            "improvement_percent": self.get_improvement(),
        }
