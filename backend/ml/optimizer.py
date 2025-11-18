"""
ML-оптимизатор параметров торговых стратегий
Интегрирует CatBoost, XGBoost, LightGBM для Grid/Bayes поиска
Использует проверенные подходы трейдеров 2025 года
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime
import json

import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, ParameterGrid
from sklearn.metrics import make_scorer

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Результат ML-оптимизации стратегии"""
    
    best_params: Dict[str, Any]
    best_score: float
    all_results: pd.DataFrame
    optimization_time: float
    method: str  # 'grid', 'bayes', 'random', 'hybrid'
    iterations: int
    
    # Расширенная статистика
    feature_importance: Optional[Dict[str, float]] = None
    convergence_history: List[float] = field(default_factory=list)
    top_n_configs: List[Dict[str, Any]] = field(default_factory=list)
    
    # Метрики стратегии
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    total_return: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для сохранения"""
        return {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'optimization_time': self.optimization_time,
            'method': self.method,
            'iterations': self.iterations,
            'feature_importance': self.feature_importance,
            'convergence_history': self.convergence_history,
            'top_n_configs': self.top_n_configs,
            'metrics': {
                'sharpe_ratio': self.sharpe_ratio,
                'max_drawdown': self.max_drawdown,
                'win_rate': self.win_rate,
                'profit_factor': self.profit_factor,
                'total_return': self.total_return,
            }
        }
    
    def save_to_file(self, filepath: str):
        """Сохранить результаты в JSON"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Сохранить полные результаты в CSV
        csv_path = filepath.replace('.json', '_full_results.csv')
        self.all_results.to_csv(csv_path, index=False)
        logger.info(f"Optimization results saved to {filepath} and {csv_path}")


class MLOptimizer(ABC):
    """
    Базовый класс для ML-оптимизации параметров стратегий
    
    Реализует общую логику для всех типов оптимизаторов:
    - Grid Search (полный перебор сетки)
    - Bayesian Optimization (умный поиск через Optuna/scikit-optimize)
    - Random Search (случайная выборка)
    - Hybrid (комбинация методов)
    """
    
    def __init__(
        self,
        objective_function: Callable,
        param_space: Dict[str, List[Any]],
        n_jobs: int = -1,
        verbose: int = 1,
        random_state: int = 42
    ):
        """
        Args:
            objective_function: Функция оценки стратегии (возвращает метрику)
            param_space: Пространство параметров для поиска
            n_jobs: Количество параллельных потоков (-1 = все ядра)
            verbose: Уровень детализации логов
            random_state: Seed для воспроизводимости
        """
        self.objective_function = objective_function
        self.param_space = param_space
        self.n_jobs = n_jobs
        self.verbose = verbose
        self.random_state = random_state
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.best_params: Optional[Dict[str, Any]] = None
        self.best_score: float = -np.inf
        
    @abstractmethod
    async def optimize(self, n_trials: int = 100) -> OptimizationResult:
        """Запустить оптимизацию"""
        pass
    
    def _evaluate_params(self, params: Dict[str, Any]) -> float:
        """
        Оценить параметры через objective_function
        
        Returns:
            Значение целевой метрики (выше = лучше)
        """
        try:
            score = self.objective_function(params)
            
            # Сохранить историю
            self.optimization_history.append({
                'params': params.copy(),
                'score': score,
                'timestamp': datetime.now().isoformat()
            })
            
            # Обновить лучший результат
            if score > self.best_score:
                self.best_score = score
                self.best_params = params.copy()
                
                if self.verbose >= 1:
                    logger.info(f"New best score: {score:.4f}, params: {params}")
            
            return score
            
        except Exception as e:
            logger.error(f"Error evaluating params {params}: {e}")
            return -np.inf
    
    async def _evaluate_params_async(self, params: Dict[str, Any]) -> float:
        """Асинхронная версия оценки параметров"""
        return await asyncio.to_thread(self._evaluate_params, params)
    
    def get_optimization_history(self) -> pd.DataFrame:
        """Получить историю оптимизации как DataFrame"""
        if not self.optimization_history:
            return pd.DataFrame()
        
        # Развернуть вложенные параметры
        flat_history = []
        for entry in self.optimization_history:
            flat_entry = {'score': entry['score'], 'timestamp': entry['timestamp']}
            flat_entry.update(entry['params'])
            flat_history.append(flat_entry)
        
        return pd.DataFrame(flat_history)


class CatBoostOptimizer(MLOptimizer):
    """
    Оптимизатор на основе CatBoost (рекомендация Яндекса)
    
    Преимущества:
    - Высокая скорость обучения
    - Автоматическая обработка категориальных признаков
    - Встроенная защита от переобучения
    - Простой синтаксис
    
    Применение: оптимизация параметров временных рядов, DCA стратегий
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.catboost_available = False
        
        try:
            from catboost import CatBoostRegressor
            self.CatBoostRegressor = CatBoostRegressor
            self.catboost_available = True
        except ImportError:
            logger.warning("CatBoost not installed. Install: pip install catboost")
    
    async def optimize(
        self, 
        n_trials: int = 100,
        method: str = 'grid'  # 'grid', 'random', 'bayes'
    ) -> OptimizationResult:
        """
        Оптимизация через CatBoost + Grid/Random/Bayes поиск
        
        Args:
            n_trials: Количество итераций
            method: Метод поиска ('grid', 'random', 'bayes')
        """
        start_time = datetime.now()
        
        if method == 'grid':
            result = await self._grid_search()
        elif method == 'random':
            result = await self._random_search(n_trials)
        elif method == 'bayes':
            result = await self._bayesian_search(n_trials)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        return OptimizationResult(
            best_params=self.best_params,
            best_score=self.best_score,
            all_results=self.get_optimization_history(),
            optimization_time=optimization_time,
            method=f'catboost_{method}',
            iterations=len(self.optimization_history),
            convergence_history=[h['score'] for h in self.optimization_history],
            top_n_configs=self._get_top_n_configs(5)
        )
    
    async def _grid_search(self) -> Dict[str, Any]:
        """Grid Search - полный перебор сетки параметров"""
        logger.info(f"Starting CatBoost Grid Search over {self._count_grid_size()} configurations")
        
        param_grid = list(ParameterGrid(self.param_space))
        
        # Параллельная оценка через asyncio
        tasks = [self._evaluate_params_async(params) for params in param_grid]
        await asyncio.gather(*tasks)
        
        return {'method': 'grid', 'iterations': len(param_grid)}
    
    async def _random_search(self, n_trials: int) -> Dict[str, Any]:
        """Random Search - случайная выборка из пространства параметров"""
        logger.info(f"Starting CatBoost Random Search for {n_trials} trials")
        
        for trial in range(n_trials):
            # Случайная выборка параметров
            params = {
                key: np.random.choice(values) 
                for key, values in self.param_space.items()
            }
            
            await self._evaluate_params_async(params)
        
        return {'method': 'random', 'iterations': n_trials}
    
    async def _bayesian_search(self, n_trials: int) -> Dict[str, Any]:
        """Bayesian Optimization через Optuna (если установлен)"""
        try:
            import optuna
            
            logger.info(f"Starting CatBoost Bayesian Optimization for {n_trials} trials")
            
            def objective(trial):
                # Создать параметры через Optuna
                params = {}
                for key, values in self.param_space.items():
                    if isinstance(values[0], int):
                        params[key] = trial.suggest_int(key, min(values), max(values))
                    elif isinstance(values[0], float):
                        params[key] = trial.suggest_float(key, min(values), max(values))
                    else:
                        params[key] = trial.suggest_categorical(key, values)
                
                return self._evaluate_params(params)
            
            study = optuna.create_study(
                direction='maximize',
                sampler=optuna.samplers.TPESampler(seed=self.random_state)
            )
            
            study.optimize(objective, n_trials=n_trials, n_jobs=self.n_jobs)
            
            return {'method': 'bayes', 'iterations': n_trials}
            
        except ImportError:
            logger.warning("Optuna not installed. Falling back to Random Search")
            return await self._random_search(n_trials)
    
    def _count_grid_size(self) -> int:
        """Подсчитать размер полной сетки"""
        size = 1
        for values in self.param_space.values():
            size *= len(values)
        return size
    
    def _get_top_n_configs(self, n: int = 5) -> List[Dict[str, Any]]:
        """Получить топ-N конфигураций"""
        df = self.get_optimization_history()
        if df.empty:
            return []
        
        df_sorted = df.sort_values('score', ascending=False).head(n)
        
        param_columns = [col for col in df_sorted.columns if col not in ['score', 'timestamp']]
        
        top_configs = []
        for _, row in df_sorted.iterrows():
            config = {col: row[col] for col in param_columns}
            config['score'] = row['score']
            top_configs.append(config)
        
        return top_configs


class XGBoostOptimizer(MLOptimizer):
    """
    Оптимизатор на основе XGBoost (самая популярная библиотека 2025)
    
    Преимущества:
    - Отличная работа с сеточными и DCA стратегиями
    - Хорошая масштабируемость
    - Поддержка GridSearch и early-stopping
    - Интеграция с Pandas/NumPy
    
    Применение: поиск оптимальных параметров скальпинга, сеток
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.xgboost_available = False
        
        try:
            import xgboost as xgb
            self.xgb = xgb
            self.xgboost_available = True
        except ImportError:
            logger.warning("XGBoost not installed. Install: pip install xgboost")
    
    async def optimize(
        self, 
        n_trials: int = 100,
        method: str = 'grid'
    ) -> OptimizationResult:
        """
        Оптимизация через XGBoost + поиск
        Аналогично CatBoostOptimizer
        """
        start_time = datetime.now()
        
        if method == 'grid':
            result = await self._grid_search_xgb()
        elif method == 'random':
            result = await self._random_search_xgb(n_trials)
        elif method == 'bayes':
            result = await self._bayesian_search_xgb(n_trials)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        return OptimizationResult(
            best_params=self.best_params,
            best_score=self.best_score,
            all_results=self.get_optimization_history(),
            optimization_time=optimization_time,
            method=f'xgboost_{method}',
            iterations=len(self.optimization_history),
            convergence_history=[h['score'] for h in self.optimization_history],
            top_n_configs=self._get_top_n_configs(5)
        )
    
    async def _grid_search_xgb(self) -> Dict[str, Any]:
        """Grid Search для XGBoost"""
        logger.info("Starting XGBoost Grid Search")
        
        param_grid = list(ParameterGrid(self.param_space))
        tasks = [self._evaluate_params_async(params) for params in param_grid]
        await asyncio.gather(*tasks)
        
        return {'method': 'grid'}
    
    async def _random_search_xgb(self, n_trials: int) -> Dict[str, Any]:
        """Random Search для XGBoost"""
        logger.info(f"Starting XGBoost Random Search for {n_trials} trials")
        
        for _ in range(n_trials):
            params = {
                key: np.random.choice(values)
                for key, values in self.param_space.items()
            }
            await self._evaluate_params_async(params)
        
        return {'method': 'random'}
    
    async def _bayesian_search_xgb(self, n_trials: int) -> Dict[str, Any]:
        """Bayesian Optimization для XGBoost"""
        # Аналогично CatBoost
        return await self._bayesian_search_generic(n_trials)
    
    async def _bayesian_search_generic(self, n_trials: int) -> Dict[str, Any]:
        """Универсальный Bayesian поиск через Optuna"""
        try:
            import optuna
            
            def objective(trial):
                params = {}
                for key, values in self.param_space.items():
                    if isinstance(values[0], (int, np.integer)):
                        params[key] = trial.suggest_int(key, min(values), max(values))
                    elif isinstance(values[0], (float, np.floating)):
                        params[key] = trial.suggest_float(key, min(values), max(values))
                    else:
                        params[key] = trial.suggest_categorical(key, values)
                
                return self._evaluate_params(params)
            
            study = optuna.create_study(direction='maximize')
            study.optimize(objective, n_trials=n_trials, n_jobs=self.n_jobs)
            
            return {'method': 'bayes'}
            
        except ImportError:
            return await self._random_search_xgb(n_trials)
    
    def _get_top_n_configs(self, n: int = 5) -> List[Dict[str, Any]]:
        """Получить топ-N конфигураций"""
        df = self.get_optimization_history()
        if df.empty:
            return []
        
        df_sorted = df.sort_values('score', ascending=False).head(n)
        param_columns = [col for col in df_sorted.columns if col not in ['score', 'timestamp']]
        
        return [
            {**{col: row[col] for col in param_columns}, 'score': row['score']}
            for _, row in df_sorted.iterrows()
        ]


class LightGBMOptimizer(MLOptimizer):
    """
    Оптимизатор на основе LightGBM (для больших данных)
    
    Преимущества:
    - Самая высокая скорость обучения
    - Работа с большими массивами данных
    - Легкая интеграция с DataFrame
    - Низкое потребление памяти
    
    Применение: скоростные оптимизации с большим объемом данных
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lightgbm_available = False
        
        try:
            import lightgbm as lgb
            self.lgb = lgb
            self.lightgbm_available = True
        except ImportError:
            logger.warning("LightGBM not installed. Install: pip install lightgbm")
    
    async def optimize(
        self, 
        n_trials: int = 100,
        method: str = 'random'  # LightGBM лучше с random/bayes
    ) -> OptimizationResult:
        """Оптимизация через LightGBM"""
        start_time = datetime.now()
        
        if method == 'grid':
            result = await self._grid_search_lgb()
        elif method == 'random':
            result = await self._random_search_lgb(n_trials)
        elif method == 'bayes':
            result = await self._bayesian_search_lgb(n_trials)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        return OptimizationResult(
            best_params=self.best_params,
            best_score=self.best_score,
            all_results=self.get_optimization_history(),
            optimization_time=optimization_time,
            method=f'lightgbm_{method}',
            iterations=len(self.optimization_history),
            convergence_history=[h['score'] for h in self.optimization_history],
            top_n_configs=self._get_top_n_configs(5)
        )
    
    async def _grid_search_lgb(self) -> Dict[str, Any]:
        """Grid Search для LightGBM"""
        param_grid = list(ParameterGrid(self.param_space))
        tasks = [self._evaluate_params_async(params) for params in param_grid]
        await asyncio.gather(*tasks)
        return {'method': 'grid'}
    
    async def _random_search_lgb(self, n_trials: int) -> Dict[str, Any]:
        """Random Search для LightGBM (рекомендуется)"""
        logger.info(f"Starting LightGBM Random Search for {n_trials} trials")
        
        for _ in range(n_trials):
            params = {
                key: np.random.choice(values)
                for key, values in self.param_space.items()
            }
            await self._evaluate_params_async(params)
        
        return {'method': 'random'}
    
    async def _bayesian_search_lgb(self, n_trials: int) -> Dict[str, Any]:
        """Bayesian Optimization для LightGBM"""
        try:
            import optuna
            
            def objective(trial):
                params = {}
                for key, values in self.param_space.items():
                    if isinstance(values[0], (int, np.integer)):
                        params[key] = trial.suggest_int(key, min(values), max(values))
                    elif isinstance(values[0], (float, np.floating)):
                        params[key] = trial.suggest_float(key, min(values), max(values))
                    else:
                        params[key] = trial.suggest_categorical(key, values)
                
                return self._evaluate_params(params)
            
            study = optuna.create_study(direction='maximize')
            study.optimize(objective, n_trials=n_trials, n_jobs=self.n_jobs)
            
            return {'method': 'bayes'}
            
        except ImportError:
            return await self._random_search_lgb(n_trials)
    
    def _get_top_n_configs(self, n: int = 5) -> List[Dict[str, Any]]:
        """Получить топ-N конфигураций"""
        df = self.get_optimization_history()
        if df.empty:
            return []
        
        df_sorted = df.sort_values('score', ascending=False).head(n)
        param_columns = [col for col in df_sorted.columns if col not in ['score', 'timestamp']]
        
        return [
            {**{col: row[col] for col in param_columns}, 'score': row['score']}
            for _, row in df_sorted.iterrows()
        ]


class HybridOptimizer(MLOptimizer):
    """
    Гибридный оптимизатор - комбинирует все методы
    
    Стратегия:
    1. Грубый поиск через Random Search (20% бюджета)
    2. Уточнение через Bayesian Optimization (50% бюджета)  
    3. Локальный Grid Search вокруг лучших точек (30% бюджета)
    
    Применение: комплексная оптимизация сложных стратегий
    """
    
    async def optimize(self, n_trials: int = 100) -> OptimizationResult:
        """
        Гибридная оптимизация в 3 этапа
        
        Args:
            n_trials: Общий бюджет итераций
        """
        start_time = datetime.now()
        
        # Этап 1: Random Search (20%)
        n_random = int(n_trials * 0.2)
        logger.info(f"Stage 1/3: Random Search ({n_random} trials)")
        await self._random_search_stage(n_random)
        
        # Этап 2: Bayesian Optimization (50%)
        n_bayes = int(n_trials * 0.5)
        logger.info(f"Stage 2/3: Bayesian Optimization ({n_bayes} trials)")
        await self._bayesian_search_stage(n_bayes)
        
        # Этап 3: Local Grid Search (30%)
        n_local = n_trials - n_random - n_bayes
        logger.info(f"Stage 3/3: Local Grid Search ({n_local} trials)")
        await self._local_grid_search_stage(n_local)
        
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        return OptimizationResult(
            best_params=self.best_params,
            best_score=self.best_score,
            all_results=self.get_optimization_history(),
            optimization_time=optimization_time,
            method='hybrid',
            iterations=len(self.optimization_history),
            convergence_history=[h['score'] for h in self.optimization_history],
            top_n_configs=self._get_top_n_configs(10)
        )
    
    async def _random_search_stage(self, n_trials: int):
        """Этап 1: Грубый поиск"""
        for _ in range(n_trials):
            params = {
                key: np.random.choice(values)
                for key, values in self.param_space.items()
            }
            await self._evaluate_params_async(params)
    
    async def _bayesian_search_stage(self, n_trials: int):
        """Этап 2: Умный поиск через Optuna"""
        try:
            import optuna
            
            def objective(trial):
                params = {}
                for key, values in self.param_space.items():
                    if isinstance(values[0], (int, np.integer)):
                        params[key] = trial.suggest_int(key, min(values), max(values))
                    elif isinstance(values[0], (float, np.floating)):
                        params[key] = trial.suggest_float(key, min(values), max(values))
                    else:
                        params[key] = trial.suggest_categorical(key, values)
                
                return self._evaluate_params(params)
            
            study = optuna.create_study(direction='maximize')
            study.optimize(objective, n_trials=n_trials, n_jobs=self.n_jobs)
            
        except ImportError:
            logger.warning("Optuna not available, using random search")
            await self._random_search_stage(n_trials)
    
    async def _local_grid_search_stage(self, n_trials: int):
        """Этап 3: Локальный поиск вокруг лучших точек"""
        if not self.best_params:
            return
        
        # Создать локальную сетку вокруг лучших параметров
        top_configs = self._get_top_n_configs(3)
        
        for config in top_configs:
            # Варьировать каждый параметр в небольшом диапазоне
            local_space = {}
            for key, value in config.items():
                if key == 'score':
                    continue
                
                if isinstance(value, (int, np.integer)):
                    local_space[key] = [max(0, value - 2), value - 1, value, value + 1, value + 2]
                elif isinstance(value, (float, np.floating)):
                    local_space[key] = [value * 0.9, value * 0.95, value, value * 1.05, value * 1.1]
                else:
                    local_space[key] = [value]
            
            # Перебрать локальную сетку
            param_grid = list(ParameterGrid(local_space))[:n_trials // 3]
            
            tasks = [self._evaluate_params_async(params) for params in param_grid]
            await asyncio.gather(*tasks)
    
    def _get_top_n_configs(self, n: int = 10) -> List[Dict[str, Any]]:
        """Получить топ-N конфигураций"""
        df = self.get_optimization_history()
        if df.empty:
            return []
        
        df_sorted = df.sort_values('score', ascending=False).head(n)
        param_columns = [col for col in df_sorted.columns if col not in ['score', 'timestamp']]
        
        return [
            {**{col: row[col] for col in param_columns}, 'score': row['score']}
            for _, row in df_sorted.iterrows()
        ]


# Пример использования
if __name__ == "__main__":
    # Тестовая objective function
    def test_objective(params: Dict[str, Any]) -> float:
        """Пример: оптимизация квадратичной функции"""
        x = params.get('x', 0)
        y = params.get('y', 0)
        return -(x**2 + y**2)  # Минимум в (0, 0)
    
    # Определить пространство поиска
    param_space = {
        'x': list(np.linspace(-10, 10, 21)),
        'y': list(np.linspace(-10, 10, 21)),
    }
    
    # Запустить оптимизацию
    async def main():
        optimizer = CatBoostOptimizer(
            objective_function=test_objective,
            param_space=param_space,
            n_jobs=4,
            verbose=1
        )
        
        result = await optimizer.optimize(n_trials=50, method='bayes')
        
        print(f"\nBest params: {result.best_params}")
        print(f"Best score: {result.best_score}")
        print(f"Optimization time: {result.optimization_time:.2f}s")
        
        result.save_to_file('optimization_result.json')
    
    asyncio.run(main())
