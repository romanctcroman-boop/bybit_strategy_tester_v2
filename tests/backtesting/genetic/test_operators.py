"""
🧬 Tests for Genetic Algorithm Optimizer — Operators

Tests for Selection, Crossover, Mutation operators.
"""

import numpy as np
import pytest

from backend.backtesting.genetic.crossover import (
    ArithmeticCrossover,
    CrossoverFactory,
    SinglePointCrossover,
    UniformCrossover,
)
from backend.backtesting.genetic.models import Chromosome, Individual, Population
from backend.backtesting.genetic.mutation import (
    AdaptiveMutation,
    GaussianMutation,
    MutationFactory,
    UniformMutation,
)
from backend.backtesting.genetic.selection import (
    RankSelection,
    RouletteSelection,
    SelectionFactory,
    TournamentSelection,
)


class TestTournamentSelection:
    """Tests for TournamentSelection"""

    def test_tournament_select(self):
        """Test tournament selection"""
        individuals = [Individual(chromosome=Chromosome(genes={"p": i}), fitness=i) for i in range(1, 11)]
        pop = Population(individuals=individuals)

        selector = TournamentSelection(tournament_size=3)
        parents = selector.select(pop, n_parents=5)

        assert len(parents) == 5
        # Best individuals should be selected more often
        assert all(p.fitness >= 5 for p in parents)

    def test_tournament_size(self):
        """Test different tournament sizes"""
        individuals = [Individual(chromosome=Chromosome(genes={"p": i}), fitness=i) for i in range(1, 6)]
        pop = Population(individuals=individuals)

        # Larger tournament = stronger selection pressure
        selector_small = TournamentSelection(tournament_size=2)
        selector_large = TournamentSelection(tournament_size=4)

        parents_small = selector_small.select(pop, n_parents=10)
        parents_large = selector_large.select(pop, n_parents=10)

        avg_small = np.mean([p.fitness for p in parents_small])
        avg_large = np.mean([p.fitness for p in parents_large])

        # Larger tournament should select better individuals on average
        assert avg_large >= avg_small


class TestRouletteSelection:
    """Tests for RouletteSelection"""

    def test_roulette_select(self):
        """Test roulette wheel selection"""
        individuals = [Individual(chromosome=Chromosome(genes={"p": i}), fitness=i * 10) for i in range(1, 6)]
        pop = Population(individuals=individuals)

        selector = RouletteSelection()
        parents = selector.select(pop, n_parents=10)

        assert len(parents) == 10

        # Best individual should be selected most often
        fitness_counts = {}
        for p in parents:
            fitness_counts[p.fitness] = fitness_counts.get(p.fitness, 0) + 1

        # Highest fitness should be selected at least once
        assert 50 in fitness_counts


class TestRankSelection:
    """Tests for RankSelection"""

    def test_rank_select(self):
        """Test rank-based selection"""
        individuals = [Individual(chromosome=Chromosome(genes={"p": i}), fitness=i) for i in range(1, 11)]
        pop = Population(individuals=individuals)

        selector = RankSelection(selective_pressure=2.0)
        parents = selector.select(pop, n_parents=5)

        assert len(parents) == 5


class TestSelectionFactory:
    """Tests for SelectionFactory"""

    def test_create_selection(self):
        """Test creating selection strategies"""
        strategies = ["tournament", "roulette", "rank", "sus", "truncation"]

        for strategy in strategies:
            selector = SelectionFactory.create(strategy)
            assert selector is not None

    def test_invalid_selection(self):
        """Test invalid selection type"""
        with pytest.raises(ValueError):
            SelectionFactory.create("invalid_strategy")


class TestSinglePointCrossover:
    """Tests for SinglePointCrossover"""

    def test_single_point_crossover(self):
        """Test single-point crossover"""
        parent1 = Individual(chromosome=Chromosome(genes={"p1": 1.0, "p2": 2.0, "p3": 3.0}))
        parent2 = Individual(chromosome=Chromosome(genes={"p1": 4.0, "p2": 5.0, "p3": 6.0}))

        crossover = SinglePointCrossover()
        child1, child2 = crossover.crossover(parent1, parent2)

        # Children should have different genes from parents
        assert (
            child1.chromosome.genes != parent1.chromosome.genes or child1.chromosome.genes != parent2.chromosome.genes
        )

        # Children should have valid genes
        assert len(child1.chromosome.genes) == 3
        assert len(child2.chromosome.genes) == 3

    def test_single_point_crossover_few_genes(self):
        """Test crossover with too few genes"""
        parent1 = Individual(chromosome=Chromosome(genes={"p1": 1.0}))
        parent2 = Individual(chromosome=Chromosome(genes={"p1": 2.0}))

        crossover = SinglePointCrossover()
        child1, child2 = crossover.crossover(parent1, parent2)

        # Should return copies
        assert child1.chromosome.genes == parent1.chromosome.genes


class TestUniformCrossover:
    """Tests for UniformCrossover"""

    def test_uniform_crossover(self):
        """Test uniform crossover"""
        parent1 = Individual(chromosome=Chromosome(genes={"p1": 1.0, "p2": 2.0, "p3": 3.0}))
        parent2 = Individual(chromosome=Chromosome(genes={"p1": 4.0, "p2": 5.0, "p3": 6.0}))

        crossover = UniformCrossover(exchange_probability=0.5)
        child1, child2 = crossover.crossover(parent1, parent2)

        # Each gene has 50% chance of being exchanged
        assert len(child1.chromosome.genes) == 3


class TestArithmeticCrossover:
    """Tests for ArithmeticCrossover"""

    def test_arithmetic_crossover(self):
        """Test arithmetic crossover"""
        parent1 = Individual(chromosome=Chromosome(genes={"p1": 1.0, "p2": 2.0}))
        parent2 = Individual(chromosome=Chromosome(genes={"p1": 3.0, "p2": 4.0}))

        crossover = ArithmeticCrossover(alpha=0.5)
        child1, child2 = crossover.crossover(parent1, parent2)

        # Children should be linear combinations
        # child1 = 0.5 * parent1 + 0.5 * parent2
        assert abs(child1.chromosome.genes["p1"] - 2.0) < 0.01
        assert abs(child1.chromosome.genes["p2"] - 3.0) < 0.01


class TestCrossoverFactory:
    """Tests for CrossoverFactory"""

    def test_create_crossover(self):
        """Test creating crossover operators"""
        operators = ["single_point", "two_point", "uniform", "arithmetic", "blend"]

        for op in operators:
            crossover = CrossoverFactory.create(op)
            assert crossover is not None

    def test_invalid_crossover(self):
        """Test invalid crossover type"""
        with pytest.raises(ValueError):
            CrossoverFactory.create("invalid_operator")


class TestGaussianMutation:
    """Tests for GaussianMutation"""

    def test_gaussian_mutation(self):
        """Test Gaussian mutation"""
        individual = Individual(chromosome=Chromosome(genes={"p1": 1.0, "p2": 2.0}))

        mutator = GaussianMutation(sigma=0.1)
        mutant = mutator.mutate(individual, rate=1.0)

        # Genes should be mutated
        assert mutant.chromosome.genes != individual.chromosome.genes or abs(mutant.chromosome.genes["p1"] - 1.0) < 0.3

    def test_gaussian_mutation_rate(self):
        """Test mutation rate"""
        individual = Individual(chromosome=Chromosome(genes={"p1": 1.0, "p2": 2.0, "p3": 3.0}))

        mutator = GaussianMutation(sigma=0.1)
        mutant = mutator.mutate(individual, rate=0.0)

        # No mutation should occur
        assert mutant.chromosome.genes == individual.chromosome.genes


class TestUniformMutation:
    """Tests for UniformMutation"""

    def test_uniform_mutation(self):
        """Test uniform mutation"""
        param_ranges = {"p1": (0, 10), "p2": (0, 10)}
        individual = Individual(chromosome=Chromosome(genes={"p1": 5.0, "p2": 5.0}, param_ranges=param_ranges))

        mutator = UniformMutation(range_fraction=0.1)
        mutant = mutator.mutate(individual, rate=1.0)

        # Genes should be within range
        assert 0 <= mutant.chromosome.genes["p1"] <= 10
        assert 0 <= mutant.chromosome.genes["p2"] <= 10


class TestAdaptiveMutation:
    """Tests for AdaptiveMutation"""

    def test_adaptive_mutation_low_diversity(self):
        """Test adaptive mutation with low diversity"""
        individual = Individual(chromosome=Chromosome(genes={"p1": 1.0, "p2": 2.0}))

        mutator = AdaptiveMutation(base_sigma=0.1, diversity_threshold=0.5)

        # Low diversity = high mutation
        mutant = mutator.mutate(individual, rate=1.0, diversity=0.1)

        # Should have larger mutations
        assert mutant.chromosome.genes != individual.chromosome.genes

    def test_adaptive_mutation_high_diversity(self):
        """Test adaptive mutation with high diversity"""
        individual = Individual(chromosome=Chromosome(genes={"p1": 1.0, "p2": 2.0}))

        mutator = AdaptiveMutation(base_sigma=0.1, diversity_threshold=0.5)

        # High diversity = low mutation
        mutant = mutator.mutate(individual, rate=1.0, diversity=0.8)

        # Should have smaller mutations
        assert abs(mutant.chromosome.genes["p1"] - 1.0) < 0.5


class TestMutationFactory:
    """Tests for MutationFactory"""

    def test_create_mutation(self):
        """Test creating mutation operators"""
        operators = ["gaussian", "uniform", "adaptive", "boundary", "non_uniform"]

        for op in operators:
            mutator = MutationFactory.create(op)
            assert mutator is not None

    def test_invalid_mutation(self):
        """Test invalid mutation type"""
        with pytest.raises(ValueError):
            MutationFactory.create("invalid_operator")
