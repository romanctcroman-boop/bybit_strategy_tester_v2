"""
🧬 Genetic Algorithm Optimizer — Main Optimizer

Главный класс генетического алгоритма оптимизации.

@version: 1.1.0
@date: 2026-02-27
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from .crossover import ArithmeticCrossover, CrossoverOperator
from .fitness import FitnessFunction, MultiObjectiveFitness, SharpeRatioFitness
from .models import Chromosome, EvolutionHistory, Individual, Population
from .mutation import GaussianMutation, MutationOperator
from .selection import SelectionStrategy, TournamentSelection

logger = logging.getLogger(__name__)


@dataclass
class GeneticOptimizationResult:
    """
    Результат генетической оптимизации.

    Attributes:
        best_individual: Лучшая особь
        population: Финальная популяция
        history: История эволюции
        n_evaluations: Количество вычислений fitness
        execution_time: Время выполнения (сек)
        pareto_front: Pareto front (для multi-objective)
    """

    best_individual: Individual
    population: Population
    history: EvolutionHistory
    n_evaluations: int = 0
    execution_time: float = 0.0
    pareto_front: list[Individual] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)  # События эволюции

    def to_dict(self) -> dict[str, Any]:
        """Конвертация в словарь"""
        return {
            "best_individual": self.best_individual.to_dict(),
            "best_fitness": self.best_individual.fitness,
            "best_params": self.best_individual.chromosome.to_dict(),
            "n_evaluations": self.n_evaluations,
            "execution_time": self.execution_time,
            "generations": len(self.history.best_fitness_per_gen),
            "improvement_percent": self.history.get_improvement(),
            "history": self.history.to_dict(),
            "pareto_front": [ind.to_dict() for ind in self.pareto_front],
        }


class GeneticOptimizer:
    """
    Генетический алгоритм оптимизации.

    Пример использования:
    ```python
    optimizer = GeneticOptimizer(
        population_size=50,
        n_generations=100,
        selection='tournament',
        crossover='arithmetic',
        mutation='gaussian',
    )

    result = optimizer.optimize(
        strategy_class=RSIStrategy,
        param_ranges={'period': (5, 30), 'overbought': (60, 80), 'oversold': (20, 40)},
        data=data,
        backtest_engine=engine,
    )
    ```
    """

    def __init__(
        self,
        population_size: int = 50,
        n_generations: int = 100,
        selection: SelectionStrategy = None,
        crossover: CrossoverOperator = None,
        mutation: MutationOperator = None,
        fitness_function: FitnessFunction = None,
        elitism_rate: float = 0.1,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.1,
        early_stopping: bool = True,
        patience: int = 20,
        min_diversity: float = 0.01,
        n_workers: int = 1,
        random_state: int | None = None,
        use_caching: bool = True,
        use_processes: bool = False,
        cancel_event: threading.Event | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ):
        """
        Args:
            population_size: Размер популяции
            n_generations: Количество поколений
            selection: Стратегия селекции (или строка 'tournament', 'roulette', etc.)
            crossover: Оператор кроссовера (или строка 'arithmetic', 'uniform', etc.)
            mutation: Оператор мутации (или строка 'gaussian', 'adaptive', etc.)
            fitness_function: Fitness функция
            elitism_rate: Доля лучших особей для сохранения (0.0-1.0)
            crossover_rate: Вероятность кроссовера (0.0-1.0)
            mutation_rate: Вероятность мутации (0.0-1.0)
            early_stopping: Ранняя остановка при отсутствии улучшений
            patience: Количество поколений без улучшений для остановки
            min_diversity: Минимальное разнообразие для продолжения
            n_workers: Количество потоков/процессов для параллельного бэктеста
            random_state: Seed для воспроизводимости
            use_caching: Кэшировать fitness значения
            use_processes: Использовать ProcessPoolExecutor (вместо ThreadPoolExecutor)
            cancel_event: Событие для отмены оптимизации
            progress_callback: Callback для уведомления о прогрессе
        """
        self.population_size = population_size
        self.n_generations = n_generations

        # Инициализация операторов
        from .crossover import CrossoverFactory
        from .mutation import MutationFactory
        from .selection import SelectionFactory

        if isinstance(selection, str):
            self.selection = SelectionFactory.create(selection)
        elif selection is None:
            self.selection = TournamentSelection(tournament_size=3)
        else:
            self.selection = selection

        if isinstance(crossover, str):
            self.crossover = CrossoverFactory.create(crossover)
        elif crossover is None:
            self.crossover = ArithmeticCrossover(alpha=0.5)
        else:
            self.crossover = crossover

        if isinstance(mutation, str):
            self.mutation = MutationFactory.create(mutation)
        elif mutation is None:
            self.mutation = GaussianMutation(sigma=0.1)
        else:
            self.mutation = mutation

        self.fitness_function = fitness_function or SharpeRatioFitness()

        self.elitism_rate = elitism_rate
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.early_stopping = early_stopping
        self.patience = patience
        self.min_diversity = min_diversity
        self.n_workers = n_workers
        self.random_state = random_state
        self.use_caching = use_caching
        self.use_processes = use_processes
        self.cancel_event = cancel_event
        self.progress_callback = progress_callback

        # Fitness кэш
        self._fitness_cache: dict[str, float] = {}

        if random_state is not None:
            np.random.seed(random_state)

    def _create_initial_population(self, param_ranges: dict[str, tuple[float, float]]) -> Population:
        """
        Создать начальную популяцию.

        Args:
            param_ranges: Диапазоны параметров

        Returns:
            Population со случайными особями
        """
        individuals = []

        for _ in range(self.population_size):
            chromosome = Chromosome.random(param_ranges)
            individual = Individual(chromosome=chromosome, generation=0)
            individuals.append(individual)

        return Population(individuals=individuals, generation=0, param_ranges=param_ranges)

    def _get_chromosome_hash(self, chromosome: Chromosome) -> str:
        """Создать хэш хромосомы для кэширования"""
        return chromosome.get_hash()

    def _evaluate_individual(
        self,
        individual: Individual,
        strategy_class: type,
        data: pd.DataFrame,
        backtest_engine: Any,
        backtest_config: dict,
    ) -> float:
        """
        Вычислить fitness особи.

        Args:
            individual: Особь для оценки
            strategy_class: Класс стратегии
            data: Данные для бэктеста
            backtest_engine: Движок бэктеста
            backtest_config: Конфигурация бэктеста

        Returns:
            Fitness значение
        """
        try:
            # Проверка кэша
            if self.use_caching:
                chrom_hash = self._get_chromosome_hash(individual.chromosome)
                if chrom_hash in self._fitness_cache:
                    individual.fitness = self._fitness_cache[chrom_hash]
                    return individual.fitness

            # Создание стратегии с параметрами особи
            params = individual.chromosome.to_dict()
            strategy = strategy_class(**params)

            # Запуск бэктеста
            backtest_config["strategy"] = strategy
            results = backtest_engine.run(data, backtest_config)

            # Сохранение результатов в особи
            individual.backtest_results = results

            # Вычисление fitness
            if isinstance(self.fitness_function, MultiObjectiveFitness):
                individual.fitness_multi = self.fitness_function.calculate_multi(results)
                individual.fitness = self.fitness_function.calculate(results)
            else:
                individual.fitness = self.fitness_function.calculate(results)

            # Сохранение в кэш
            if self.use_caching:
                chrom_hash = self._get_chromosome_hash(individual.chromosome)
                self._fitness_cache[chrom_hash] = individual.fitness

            return individual.fitness

        except Exception as e:
            logger.warning(f"Evaluation error: {e}")
            individual.fitness = 0.0
            return 0.0

    def _evaluate_population(
        self,
        population: Population,
        strategy_class: type,
        data: pd.DataFrame,
        backtest_engine: Any,
        backtest_config: dict,
    ) -> int:
        """
        Вычислить fitness всей популяции.

        Args:
            population: Популяция
            strategy_class: Класс стратегии
            data: Данные
            backtest_engine: Движок
            backtest_config: Конфиг

        Returns:
            Количество вычисленных особей
        """
        n_evaluated = 0

        # Получаем особей для оценки
        individuals_to_eval = [ind for ind in population.individuals if not ind.is_evaluated()]

        if not individuals_to_eval:
            return 0

        if self.n_workers > 1:
            # Параллельное вычисление
            ExecutorClass = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor

            with ExecutorClass(max_workers=self.n_workers) as executor:
                # Создаем копии для потоков/процессов
                futures = {
                    executor.submit(
                        self._evaluate_individual,
                        ind.copy(),  # Копия для потока!
                        strategy_class,
                        data,
                        backtest_engine,
                        backtest_config,
                    ): ind
                    for ind in individuals_to_eval
                }

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        # Обновляем оригинальную особь
                        original = futures[future]
                        original.set_fitness(result)
                        n_evaluated += 1
                    except Exception as e:
                        logger.error(f"Parallel evaluation error: {e}")
        else:
            # Последовательное вычисление
            for individual in individuals_to_eval:
                if not individual.is_evaluated():
                    self._evaluate_individual(individual, strategy_class, data, backtest_engine, backtest_config)
                    n_evaluated += 1

        # Refresh population statistics after evaluation
        population.update_statistics()

        return n_evaluated

    def _select_parents(self, population: Population) -> list[Individual]:
        """
        Выбрать родителей для размножения.

        Args:
            population: Текущая популяция

        Returns:
            Список родителей
        """
        n_parents = self.population_size - int(self.population_size * self.elitism_rate)
        return self.selection.select(population, n_parents)

    def _create_offspring(self, parents: list[Individual]) -> list[Individual]:
        """
        Создать потомков из родителей.

        Args:
            parents: Список родителей

        Returns:
            Список потомков
        """
        offspring = []

        # Скрещивание родителей
        for i in range(0, len(parents) - 1, 2):
            parent1 = parents[i]
            parent2 = parents[i + 1] if i + 1 < len(parents) else parents[i]

            # Кроссовер с вероятностью
            if np.random.random() < self.crossover_rate:
                child1, child2 = self.crossover.crossover(parent1, parent2)
            else:
                child1, child2 = parent1.copy(), parent2.copy()

            offspring.extend([child1, child2])

        # Мутация потомков
        for child in offspring:
            child = self.mutation.mutate(child, self.mutation_rate)

        return offspring[: len(parents)]

    def _apply_elitism(self, population: Population, offspring: list[Individual]) -> list[Individual]:
        """
        Применить элитизм — сохранить лучших особей.

        Args:
            population: Текущая популяция
            offspring: Потомки

        Returns:
            Новая популяция
        """
        n_elite = int(self.population_size * self.elitism_rate)
        elite = population.get_best(n_elite)

        # Объединение элиты и потомков
        new_population = elite + offspring[: self.population_size - n_elite]

        return new_population

    def _check_early_stopping(self, history: EvolutionHistory) -> bool:
        """
        Проверить условие ранней остановки.

        Args:
            history: История эволюции

        Returns:
            True для остановки
        """
        if not self.early_stopping:
            return False

        if len(history.best_fitness_per_gen) < self.patience + 1:
            return False

        # Проверка улучшений за последние patience поколений
        recent_best = history.best_fitness_per_gen[-self.patience :]

        if len(recent_best) < 2:
            return False

        # Если нет улучшений
        if max(recent_best) <= recent_best[0]:
            logger.info(f"Early stopping: no improvement for {self.patience} generations")
            return True

        return False

    def optimize(
        self,
        strategy_class: type,
        param_ranges: dict[str, tuple[float, float]],
        data: pd.DataFrame,
        backtest_engine: Any,
        backtest_config: dict | None = None,
    ) -> GeneticOptimizationResult:
        """
        Запустить генетическую оптимизацию.

        Args:
            strategy_class: Класс стратегии для оптимизации
            param_ranges: Диапазоны параметров {name: (min, max)}
            data: Данные для бэктеста
            backtest_engine: Движок бэктеста
            backtest_config: Конфигурация бэктеста

        Returns:
            GeneticOptimizationResult с результатами
        """
        start_time = datetime.now()
        n_total_evaluations = 0
        events = []  # События эволюции

        logger.info(
            f"Starting genetic optimization: {self.population_size} individuals, {self.n_generations} generations"
        )

        # Событие: старт
        events.append(
            {
                "type": "optimization_start",
                "timestamp": start_time.isoformat(),
                "config": {
                    "population_size": self.population_size,
                    "n_generations": self.n_generations,
                },
            }
        )

        # Создание начальной популяции
        population = self._create_initial_population(param_ranges)
        history = EvolutionHistory()

        # Бэктест конфигурация
        if backtest_config is None:
            backtest_config = {}

        # Главный цикл эволюции
        for generation in range(self.n_generations):
            # Проверка отмены
            if self.cancel_event and self.cancel_event.is_set():
                logger.info(f"Optimization cancelled at generation {generation}")
                events.append(
                    {
                        "type": "optimization_cancelled",
                        "timestamp": datetime.now().isoformat(),
                        "generation": generation,
                    }
                )
                break

            population.generation = generation

            logger.info(
                f"Generation {generation}: "
                f"avg_fitness={population.avg_fitness:.4f}, "
                f"diversity={population.diversity:.4f}"
            )

            # Вычисление fitness популяции
            n_evaluated = self._evaluate_population(population, strategy_class, data, backtest_engine, backtest_config)
            n_total_evaluations += n_evaluated

            # Запись в историю
            history.record_generation(population)

            # Событие: поколение завершено
            events.append(
                {
                    "type": "generation_complete",
                    "timestamp": datetime.now().isoformat(),
                    "generation": generation,
                    "best_fitness": population.best_individual.fitness if population.best_individual else None,
                    "avg_fitness": population.avg_fitness,
                    "diversity": population.diversity,
                }
            )

            # Progress callback
            if self.progress_callback:
                self.progress_callback(
                    {
                        "generation": generation,
                        "best_fitness": population.best_individual.fitness if population.best_individual else None,
                        "avg_fitness": population.avg_fitness,
                        "diversity": population.diversity,
                        "progress": (generation + 1) / self.n_generations * 100,
                    }
                )

            # Обновление адаптивной мутации
            if hasattr(self.mutation, "set_diversity"):
                self.mutation.set_diversity(population.diversity)
            if hasattr(self.mutation, "set_generation"):
                self.mutation.set_generation(generation, self.n_generations)

            # Проверка ранней остановки
            if self._check_early_stopping(history):
                logger.info(f"Early stopping at generation {generation}")
                break

            # Проверка минимального разнообразия
            if population.diversity < self.min_diversity:
                logger.info(f"Low diversity ({population.diversity:.4f}), stopping")
                break

            # Создание следующего поколения
            if generation < self.n_generations - 1:
                # Выбор родителей
                parents = self._select_parents(population)

                # Создание потомков
                offspring = self._create_offspring(parents)

                # Применение элитизма
                new_individuals = self._apply_elitism(population, offspring)

                # Обновление популяции
                population = Population(
                    individuals=new_individuals, generation=generation + 1, param_ranges=param_ranges
                )

        # Финальные результаты
        execution_time = (datetime.now() - start_time).total_seconds()

        result = GeneticOptimizationResult(
            best_individual=population.best_individual if population.best_individual else population.individuals[0],
            population=population,
            history=history,
            n_evaluations=n_total_evaluations,
            execution_time=execution_time,
            events=events,
        )

        # Multi-objective: вычисление Pareto front
        if isinstance(self.fitness_function, MultiObjectiveFitness):
            result.pareto_front = self._compute_pareto_front(population)

        best_fitness_str = f"{result.best_individual.fitness:.4f}" if result.best_individual else "N/A"
        logger.info(f"Optimization complete: best_fitness={best_fitness_str}, time={execution_time:.2f}s")

        # Событие: завершение
        events.append(
            {
                "type": "optimization_complete",
                "timestamp": datetime.now().isoformat(),
                "best_fitness": best_fitness_str,
                "execution_time": execution_time,
            }
        )

        return result

    def _compute_pareto_front(self, population: Population) -> list[Individual]:
        """
        Вычислить Pareto front для multi-objective оптимизации.

        Args:
            population: Популяция

        Returns:
            Список особей на Pareto front
        """
        evaluated = [ind for ind in population.individuals if ind.fitness_multi]

        if not evaluated:
            return []

        pareto_front = []

        for ind in evaluated:
            is_dominated = False

            for other in evaluated:
                if ind.id == other.id:
                    continue

                # Проверка доминирования
                dominates = True
                strictly_better = False

                for metric in ind.fitness_multi:
                    val_ind = ind.fitness_multi.get(metric, 0)
                    val_other = other.fitness_multi.get(metric, 0)

                    if val_other < val_ind:
                        dominates = False
                        break
                    elif val_other > val_ind:
                        strictly_better = True

                if dominates and strictly_better:
                    is_dominated = True
                    break

            if not is_dominated:
                pareto_front.append(ind)

        return pareto_front
