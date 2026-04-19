# 🧬 Genetic Algorithm Optimizer — План реализации

**Дата:** 2026-02-26
**Задача:** P1-10
**Оценка:** 2 дня (16 часов)
**Статус:** ⏳ В работе

---

## 🎯 Цель

Реализовать генетический алгоритм оптимизации как альтернативу Grid Search и Optuna:
- Multi-objective optimization (Sharpe + Win Rate + Max DD)
- Tournament selection + Adaptive mutation
- Elitism + различные crossover операторы
- Pareto front для multi-objective результатов

---

## 📁 Структура модуля

```
backend/backtesting/genetic/
├── __init__.py                 # Экспорты
├── models.py                   # Individual, Population, Chromosome
├── selection.py                # Selection strategies
├── crossover.py                # Crossover operators
├── mutation.py                 # Mutation operators
├── fitness.py                  # Fitness functions
├── optimizer.py                # GeneticOptimizer (главный класс)
├── pareto.py                   # Pareto front analysis
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_selection.py
    ├── test_crossover.py
    ├── test_mutation.py
    ├── test_fitness.py
    └── test_optimizer.py
```

---

## 🏗️ Архитектура

### 1. Модели данных

```python
@dataclass
class Individual:
    """Особь с хромосомой (параметры) и fitness"""
    chromosome: Dict[str, float]
    fitness: Optional[float] = None
    fitness_multi: Optional[Dict[str, float]] = None
    generation: int = 0
    id: str = field(default_factory=uuid4)

@dataclass
class Population:
    """Популяция особей"""
    individuals: List[Individual]
    generation: int = 0
    best_individual: Optional[Individual] = None
    avg_fitness: float = 0.0
    diversity: float = 0.0
```

### 2. Стратегии селекции

```python
class SelectionStrategy(ABC):
    @abstractmethod
    def select(self, population: Population, n_parents: int) -> List[Individual]:
        pass

class TournamentSelection(SelectionStrategy):
    """Tournament selection с заданным размером турнира"""

class RouletteSelection(SelectionStrategy):
    """Roulette wheel selection (fitness-proportional)"""

class RankSelection(SelectionStrategy):
    """Rank-based selection"""
```

### 3. Операторы кроссовера

```python
class CrossoverOperator(ABC):
    @abstractmethod
    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        pass

class SinglePointCrossover(CrossoverOperator):
    """Одноточечный кроссовер"""

class TwoPointCrossover(CrossoverOperator):
    """Двухточечный кроссовер"""

class UniformCrossover(CrossoverOperator):
    """Равномерный кроссовер"""

class ArithmeticCrossover(CrossoverOperator):
    """Арифмететический кроссовер (для float параметров)"""
```

### 4. Операторы мутации

```python
class MutationOperator(ABC):
    @abstractmethod
    def mutate(self, individual: Individual, rate: float) -> Individual:
        pass

class GaussianMutation(MutationOperator):
    """Мутация гауссовским шумом"""

class UniformMutation(MutationOperator):
    """Равномерная мутация"""

class AdaptiveMutation(MutationOperator):
    """Адаптивная мутация (зависит от diversity)"""
```

### 5. Fitness функции

```python
class FitnessFunction(ABC):
    @abstractmethod
    def calculate(self, backtest_results: Dict) -> float:
        pass

class SharpeRatioFitness(FitnessFunction):
    """Оптимизация по Sharpe ratio"""

class MultiObjectiveFitness(FitnessFunction):
    """Multi-objective: Sharpe + Win Rate - Max DD"""

class CustomFitness(FitnessFunction):
    """Пользовательская комбинация метрик"""
```

### 6. Главный оптимизатор

```python
class GeneticOptimizer:
    def __init__(
        self,
        population_size: int = 50,
        n_generations: int = 100,
        selection: SelectionStrategy = TournamentSelection(),
        crossover: CrossoverOperator = ArithmeticCrossover(),
        mutation: MutationOperator = GaussianMutation(),
        elitism_rate: float = 0.1,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.1,
        fitness_function: FitnessFunction = SharpeRatioFitness(),
        early_stopping: bool = True,
        patience: int = 20,
    ):
        pass
    
    def optimize(
        self,
        strategy_class: Type[BaseStrategy],
        param_ranges: Dict[str, Tuple[float, float]],
        data: pd.DataFrame,
        backtest_engine: BacktestEngine,
    ) -> OptimizationResult:
        pass
```

---

## 📝 План работ

### Этап 1: Базовые классы (4 часа)

- [x] Шаг 1.1: Создать структуру директорий
- [ ] Шаг 1.2: `models.py` — Individual, Population
- [ ] Шаг 1.3: `fitness.py` — Fitness functions
- [ ] Шаг 1.4: Тесты на models и fitness

### Этап 2: Генетические операторы (4 часа)

- [ ] Шаг 2.1: `selection.py` — Tournament, Roulette, Rank
- [ ] Шаг 2.2: `crossover.py` — 4 оператора
- [ ] Шаг 2.3: `mutation.py` — 3 оператора
- [ ] Шаг 2.4: Тесты на операторы

### Этап 3: Главный оптимизатор (4 часа)

- [ ] Шаг 3.1: `optimizer.py` — GeneticOptimizer
- [ ] Шаг 3.2: Elitism + early stopping
- [ ] Шаг 3.3: Adaptive mutation rate
- [ ] Шаг 3.4: Тесты на оптимизатор

### Этап 4: Интеграция (2 часа)

- [ ] Шаг 4.1: `pareto.py` — Pareto front analysis
- [ ] Шаг 4.2: Интеграция с BacktestEngine
- [ ] Шаг 4.3: API endpoint
- [ ] Шаг 4.4: UI в optimization-results.html

### Этап 5: Тесты и документация (2 часа)

- [ ] Шаг 5.1: Интеграционные тесты
- [ ] Шаг 5.2: Документация
- [ ] Шаг 5.3: Примеры использования

---

## 🔧 Конфигурация

### Параметры по умолчанию

```python
DEFAULT_CONFIG = {
    "population_size": 50,      # Размер популяции
    "n_generations": 100,       # Количество поколений
    "elitism_rate": 0.1,        # 10% лучших сохраняются
    "crossover_rate": 0.8,      # 80% скрещиваются
    "mutation_rate": 0.1,       # 10% мутируют
    "tournament_size": 3,       # Размер турнира
    "early_stopping": True,     # Ранняя остановка
    "patience": 20,             # Поколений без улучшений
}
```

### Multi-objective веса

```python
MULTI_OBJECTIVE_WEIGHTS = {
    "sharpe_ratio": 0.4,
    "win_rate": 0.3,
    "max_drawdown": 0.3,  # Минимизируем
    "total_return": 0.0,  # Можно добавить
}
```

---

## 🧪 Тесты

### Unit тесты

```python
class TestIndividual:
    def test_create_individual(self): ...
    def test_fitness_calculation(self): ...

class TestSelection:
    def test_tournament_selection(self): ...
    def test_roulette_selection(self): ...

class TestCrossover:
    def test_single_point_crossover(self): ...
    def test_arithmetic_crossover(self): ...

class TestMutation:
    def test_gaussian_mutation(self): ...
    def test_adaptive_mutation(self): ...
```

### Интеграционные тесты

```python
class TestGeneticOptimizer:
    def test_optimize_rsi_strategy(self): ...
    def test_multi_objective_optimization(self): ...
    def test_early_stopping(self): ...
    def test_pareto_front(self): ...
```

---

## 📊 Ожидаемые результаты

### Производительность

| Метрика | Grid Search | Optuna | Genetic |
|---------|-------------|--------|---------|
| Скорость | 1x | 20-40x | 10-30x |
| Качество | 100% | 95-98% | 90-95% |
| Multi-objective | ❌ | ✅ | ✅ |
| Pareto front | ❌ | ⚠️ | ✅ |

### Преимущества

- ✅ Multi-objective оптимизация "из коробки"
- ✅ Pareto front для анализа компромиссов
- ✅ Меньше застреваний в локальных оптимумах
- ✅ Визуализация эволюции популяции

---

## 🎨 UI компоненты

### optimization-results.html

**Добавить:**
1. Вкладка "Genetic Evolution"
   - График fitness по поколениям
   - Heatmap параметров
   - Pareto front (для multi-objective)

2. Настройки генетического алгоритма:
   ```html
   <select id="selectionStrategy">
     <option value="tournament">Tournament</option>
     <option value="roulette">Roulette</option>
     <option value="rank">Rank</option>
   </select>
   
   <input type="number" id="populationSize" min="10" max="200" value="50">
   <input type="number" id="nGenerations" min="10" max="500" value="100">
   ```

---

## 📚 Документация

### Создать:

1. `docs/genetic_optimizer/PLAN.md` — этот документ ✅
2. `docs/genetic_optimizer/IMPLEMENTATION.md` — реализация
3. `docs/genetic_optimizer/API.md` — API reference
4. `docs/genetic_optimizer/EXAMPLES.md` — примеры использования
5. `docs/genetic_optimizer/MULTI_OBJECTIVE.md` — multi-objective guide

---

## ✅ Критерии приёмки

- [ ] Все unit тесты проходят (>80% coverage)
- [ ] Интеграционные тесты проходят
- [ ] API endpoint работает
- [ ] UI отображает результаты
- [ ] Документация полная
- [ ] Примеры работают
- [ ] Performance > Grid Search (10x+)

---

*План создан: 2026-02-26*
*Следующий шаг: Реализация моделей (models.py)*
