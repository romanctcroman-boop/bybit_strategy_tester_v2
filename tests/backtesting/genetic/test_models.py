"""
🧬 Tests for Genetic Algorithm Optimizer — Models

Tests for Chromosome, Individual, Population, EvolutionHistory.
"""

import numpy as np
import pytest

from backend.backtesting.genetic.models import (
    Chromosome,
    EvolutionHistory,
    Individual,
    Population,
)


class TestChromosome:
    """Tests for Chromosome class"""

    def test_create_chromosome(self):
        """Test creating a chromosome"""
        genes = {"param1": 0.5, "param2": 10}
        param_ranges = {"param1": (0, 1), "param2": (5, 15)}

        chrom = Chromosome(genes=genes, param_ranges=param_ranges)

        assert chrom.genes == genes
        assert chrom.param_ranges == param_ranges
        assert len(chrom) == 2

    def test_chromosome_validation(self):
        """Test chromosome validates gene ranges"""
        genes = {"param1": 5.0}  # Out of range
        param_ranges = {"param1": (0, 1)}

        with pytest.raises(ValueError):
            Chromosome(genes=genes, param_ranges=param_ranges)

    def test_chromosome_copy(self):
        """Test chromosome deep copy"""
        genes = {"param1": 0.5, "param2": 10}
        chrom = Chromosome(genes=genes)

        copy = chrom.copy()

        assert copy.genes == chrom.genes
        assert copy.genes is not chrom.genes  # Different objects

    def test_chromosome_random(self):
        """Test random chromosome creation"""
        param_ranges = {"int_param": (1, 10), "float_param": (0.0, 1.0)}

        chrom = Chromosome.random(param_ranges)

        assert "int_param" in chrom.genes
        assert "float_param" in chrom.genes
        assert 1 <= chrom.genes["int_param"] <= 10
        assert 0.0 <= chrom.genes["float_param"] <= 1.0

    def test_chromosome_getitem(self):
        """Test chromosome indexing"""
        genes = {"param1": 0.5, "param2": 10}
        chrom = Chromosome(genes=genes)

        assert chrom["param1"] == 0.5
        assert chrom["param2"] == 10

    def test_chromosome_setitem(self):
        """Test chromosome item assignment"""
        genes = {"param1": 0.5}
        param_ranges = {"param1": (0, 1)}
        chrom = Chromosome(genes=genes, param_ranges=param_ranges)

        chrom["param1"] = 0.8
        assert chrom["param1"] == 0.8

        # Should clip to range
        chrom["param1"] = 1.5
        assert chrom["param1"] == 1.0

    def test_chromosome_to_dict(self):
        """Test chromosome to dictionary"""
        genes = {"param1": 0.5, "param2": 10}
        chrom = Chromosome(genes=genes)

        result = chrom.to_dict()

        assert result == genes
        assert result is not genes  # Copy


class TestIndividual:
    """Tests for Individual class"""

    def test_create_individual(self):
        """Test creating an individual"""
        chrom = Chromosome(genes={"param1": 0.5})
        ind = Individual(chromosome=chrom)

        assert ind.chromosome == chrom
        assert ind.fitness is None
        assert ind.generation == 0
        assert ind.id is not None

    def test_individual_copy(self):
        """Test individual deep copy"""
        chrom = Chromosome(genes={"param1": 0.5})
        ind = Individual(chromosome=chrom, fitness=0.8)

        copy = ind.copy()

        assert copy.chromosome.genes == ind.chromosome.genes
        assert copy.fitness == ind.fitness
        assert copy.id != ind.id  # New ID
        assert copy.parents == (ind.id,)  # Parent reference

    def test_individual_is_evaluated(self):
        """Test evaluation check"""
        chrom = Chromosome(genes={"param1": 0.5})
        ind = Individual(chromosome=chrom)

        assert ind.is_evaluated() is False

        ind.fitness = 0.8
        assert ind.is_evaluated() is True

    def test_individual_get_fitness(self):
        """Test fitness retrieval"""
        chrom = Chromosome(genes={"param1": 0.5})
        ind = Individual(chromosome=chrom, fitness=0.8)

        assert ind.get_fitness() == 0.8
        assert ind.get_fitness("sharpe") == 0.8  # Falls back to fitness

    def test_individual_get_fitness_multi(self):
        """Test multi-objective fitness retrieval"""
        chrom = Chromosome(genes={"param1": 0.5})
        ind = Individual(chromosome=chrom, fitness_multi={"sharpe": 1.5, "win_rate": 0.6})

        assert ind.get_fitness("sharpe") == 1.5
        assert ind.get_fitness("win_rate") == 0.6

    def test_individual_comparison(self):
        """Test individual comparison"""
        chrom = Chromosome(genes={"param1": 0.5})
        ind1 = Individual(chromosome=chrom, fitness=0.8)
        ind2 = Individual(chromosome=chrom, fitness=0.9)

        assert ind1 < ind2
        assert ind2 > ind1

    def test_individual_to_dict(self):
        """Test individual to dictionary"""
        chrom = Chromosome(genes={"param1": 0.5})
        ind = Individual(chromosome=chrom, fitness=0.8, generation=5)

        result = ind.to_dict()

        assert result["fitness"] == 0.8
        assert result["generation"] == 5
        assert "chromosome" in result


class TestPopulation:
    """Tests for Population class"""

    def test_create_population(self):
        """Test creating a population"""
        individuals = [
            Individual(chromosome=Chromosome(genes={"p": 0.5}), fitness=0.8),
            Individual(chromosome=Chromosome(genes={"p": 0.6}), fitness=0.9),
        ]

        pop = Population(individuals=individuals)

        assert len(pop) == 2
        assert pop.best_individual.fitness == 0.9
        assert pop.avg_fitness == pytest.approx(0.85)

    def test_population_update_statistics(self):
        """Test statistics update"""
        individuals = [
            Individual(chromosome=Chromosome(genes={"p": 0.5}), fitness=0.5),
            Individual(chromosome=Chromosome(genes={"p": 0.6}), fitness=0.8),
            Individual(chromosome=Chromosome(genes={"p": 0.7}), fitness=0.9),
        ]

        pop = Population(individuals=individuals)

        assert pop.best_individual.fitness == 0.9
        assert abs(pop.avg_fitness - 0.733) < 0.01

    def test_population_add(self):
        """Test adding individual to population"""
        pop = Population(individuals=[])
        ind = Individual(chromosome=Chromosome(genes={"p": 0.5}), fitness=0.8)

        pop.add(ind)

        assert len(pop) == 1
        assert pop.best_individual == ind

    def test_population_remove(self):
        """Test removing individual from population"""
        ind1 = Individual(chromosome=Chromosome(genes={"p": 0.5}), fitness=0.8)
        ind2 = Individual(chromosome=Chromosome(genes={"p": 0.6}), fitness=0.9)

        pop = Population(individuals=[ind1, ind2])
        pop.remove(ind1.id)

        assert len(pop) == 1
        assert pop.individuals[0].id == ind2.id

    def test_population_get_best(self):
        """Test getting best individuals"""
        individuals = [Individual(chromosome=Chromosome(genes={"p": i * 0.1}), fitness=i * 0.1) for i in range(1, 6)]

        pop = Population(individuals=individuals)
        best = pop.get_best(2)

        assert len(best) == 2
        assert best[0].fitness == 0.5
        assert best[1].fitness == 0.4

    def test_population_get_worst(self):
        """Test getting worst individuals"""
        individuals = [Individual(chromosome=Chromosome(genes={"p": i * 0.1}), fitness=i * 0.1) for i in range(1, 6)]

        pop = Population(individuals=individuals)
        worst = pop.get_worst(2)

        assert len(worst) == 2
        assert worst[0].fitness == 0.1
        assert worst[1].fitness == 0.2

    def test_population_sample(self):
        """Test random sampling"""
        individuals = [Individual(chromosome=Chromosome(genes={"p": i * 0.1}), fitness=i * 0.1) for i in range(1, 11)]

        pop = Population(individuals=individuals)
        sample = pop.sample(5)

        assert len(sample) == 5
        assert all(ind in individuals for ind in sample)

    def test_population_diversity(self):
        """Test diversity calculation"""
        # Identical individuals = 0 diversity
        chrom = Chromosome(genes={"p": 0.5})
        individuals = [
            Individual(chromosome=chrom, fitness=0.5),
            Individual(chromosome=chrom, fitness=0.6),
        ]

        pop = Population(individuals=individuals, param_ranges={"p": (0, 1)})
        assert pop.diversity == 0.0

        # Different individuals > 0 diversity
        chrom2 = Chromosome(genes={"p": 0.9})
        individuals2 = [
            Individual(chromosome=chrom, fitness=0.5),
            Individual(chromosome=chrom2, fitness=0.6),
        ]

        pop2 = Population(individuals=individuals2, param_ranges={"p": (0, 1)})
        assert pop2.diversity > 0.0

    def test_population_to_dict(self):
        """Test population to dictionary"""
        individuals = [
            Individual(chromosome=Chromosome(genes={"p": 0.5}), fitness=0.8),
        ]

        pop = Population(individuals=individuals)
        result = pop.to_dict()

        assert result["size"] == 1
        assert result["generation"] == 0
        assert "best_fitness" in result
        assert "avg_fitness" in result


class TestEvolutionHistory:
    """Tests for EvolutionHistory class"""

    def test_create_history(self):
        """Test creating history"""
        history = EvolutionHistory()

        assert history.best_fitness_per_gen == []
        assert history.avg_fitness_per_gen == []
        assert history.diversity_per_gen == []

    def test_record_generation(self):
        """Test recording generation statistics"""
        individuals = [
            Individual(chromosome=Chromosome(genes={"p": 0.5}), fitness=0.8),
        ]
        pop = Population(individuals=individuals)

        history = EvolutionHistory()
        history.record_generation(pop)

        assert len(history.best_fitness_per_gen) == 1
        assert history.best_fitness_per_gen[0] == 0.8

    def test_get_improvement(self):
        """Test improvement calculation"""
        history = EvolutionHistory(best_fitness_per_gen=[0.5, 0.6, 0.8, 1.0])

        improvement = history.get_improvement()

        # From 0.5 to 1.0 = 100% improvement
        assert improvement == 100.0

    def test_get_improvement_no_generations(self):
        """Test improvement with no generations"""
        history = EvolutionHistory()

        assert history.get_improvement() == 0.0

    def test_history_to_dict(self):
        """Test history to dictionary"""
        history = EvolutionHistory(
            best_fitness_per_gen=[0.5, 0.8, 1.0],
            avg_fitness_per_gen=[0.4, 0.6, 0.8],
        )

        result = history.to_dict()

        assert "best_fitness_per_gen" in result
        assert "improvement_percent" in result
        assert result["improvement_percent"] == 100.0
