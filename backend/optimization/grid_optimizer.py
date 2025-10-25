"""
Grid Optimizer - Модуль оптимизации параметров стратегии (ТЗ 3.5.1)

Реализует простой grid search для оптимизации параметров:
- Take Profit (%)
- Stop Loss (%)
- Trailing Stop (activation %, distance %)

Алгоритм:
1. Генерация всех комбинаций параметров (декартово произведение)
2. Запуск BacktestEngine для каждой комбинации
3. Ранжирование результатов по score function
4. Экспорт топ-N результатов в CSV
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path
import itertools
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

# Optional tqdm for progress bars
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    def tqdm(iterable, **kwargs):
        """Fallback if tqdm not installed"""
        return iterable

logger = logging.getLogger(__name__)


@dataclass
class ParameterRange:
    """Диапазон значений для одного параметра."""
    name: str
    start: float
    stop: float
    step: float
    description: str = ""
    
    def values(self) -> List[float]:
        """Генерация всех значений в диапазоне."""
        # Используем linspace для точного контроля количества точек
        num_steps = int((self.stop - self.start) / self.step) + 1
        return [round(v, 4) for v in np.linspace(self.start, self.stop, num_steps)]


@dataclass
class OptimizationConfig:
    """Конфигурация оптимизации."""
    # Параметры для оптимизации
    parameters: List[ParameterRange]
    
    # Базовая конфигурация стратегии (фиксированные параметры)
    base_strategy: Dict[str, Any]
    
    # Функция оценки (по умолчанию Sharpe Ratio)
    score_function: str = "sharpe"  # "sharpe", "profit_factor", "custom"
    
    # Ограничения
    min_trades: int = 10  # Минимальное количество сделок для валидности
    max_drawdown_limit: float = 0.25  # Макс просадка 25%
    
    # Параллелизация
    max_workers: int = 4
    
    # Output
    top_n_results: int = 20
    export_csv: bool = True
    csv_path: Optional[str] = None


@dataclass
class OptimizationResult:
    """Результат одной комбинации параметров."""
    parameters: Dict[str, float]
    metrics: Dict[str, float]
    score: float
    rank: int = 0
    valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для JSON/CSV."""
        return {
            **self.parameters,
            **{f"metric_{k}": v for k, v in self.metrics.items()},
            'score': self.score,
            'rank': self.rank,
            'valid': self.valid,
            'errors': '; '.join(self.validation_errors) if self.validation_errors else ''
        }


class GridOptimizer:
    """
    Grid Search оптимизатор для параметров стратегии.
    
    Использование:
    ```python
    optimizer = GridOptimizer(
        backtest_engine=engine,
        data=ohlcv_data,
        config=optimization_config
    )
    
    results = optimizer.optimize()
    optimizer.export_results(results, "optimization_results.csv")
    ```
    """
    
    def __init__(
        self,
        backtest_engine: Any,  # BacktestEngine instance
        data: pd.DataFrame,
        config: OptimizationConfig
    ):
        self.engine = backtest_engine
        self.data = data
        self.config = config
        
        # Статистика
        self.total_combinations = 0
        self.valid_results = 0
        self.invalid_results = 0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
    def _generate_parameter_grid(self) -> List[Dict[str, float]]:
        """Генерация всех комбинаций параметров (декартово произведение)."""
        param_names = [p.name for p in self.config.parameters]
        param_values = [p.values() for p in self.config.parameters]
        
        # Декартово произведение всех значений
        combinations = list(itertools.product(*param_values))
        
        # Конвертация в список словарей
        grid = [
            dict(zip(param_names, combo))
            for combo in combinations
        ]
        
        self.total_combinations = len(grid)
        logger.info(f"Generated {self.total_combinations} parameter combinations")
        
        return grid
    
    def _build_strategy_config(self, params: Dict[str, float]) -> Dict[str, Any]:
        """Построение конфигурации стратегии с оптимизируемыми параметрами."""
        config = self.config.base_strategy.copy()
        
        # Обновляем параметры выхода
        if 'exit' not in config:
            config['exit'] = {}
        
        # Take Profit
        if 'tp_percent' in params:
            config['exit']['take_profit'] = {
                'enabled': True,
                'percent': params['tp_percent']
            }
        
        # Stop Loss
        if 'sl_percent' in params:
            config['exit']['stop_loss'] = {
                'enabled': True,
                'percent': params['sl_percent']
            }
        
        # Trailing Stop
        if 'trail_activation' in params and 'trail_distance' in params:
            config['exit']['trailing_stop'] = {
                'enabled': True,
                'activation': params['trail_activation'],
                'distance': params['trail_distance']
            }
        
        return config
    
    def _run_single_backtest(self, params: Dict[str, float]) -> OptimizationResult:
        """Запуск одного бэктеста с заданными параметрами."""
        try:
            # Построение конфигурации
            strategy_config = self._build_strategy_config(params)
            
            # Запуск бэктеста
            results = self.engine.run(self.data, strategy_config)
            
            # Валидация результатов
            validation_errors = []
            valid = True
            
            # Проверка минимального количества сделок
            if results['total_trades'] < self.config.min_trades:
                validation_errors.append(
                    f"Too few trades: {results['total_trades']} < {self.config.min_trades}"
                )
                valid = False
            
            # Проверка максимальной просадки
            if results['max_drawdown'] > self.config.max_drawdown_limit:
                validation_errors.append(
                    f"Drawdown too high: {results['max_drawdown']:.1%} > {self.config.max_drawdown_limit:.1%}"
                )
                valid = False
            
            # Расчет score
            score = self._calculate_score(results)
            
            # Извлечение ключевых метрик
            metrics = {
                'total_trades': results['total_trades'],
                'win_rate': results['win_rate'],
                'sharpe_ratio': results['sharpe_ratio'],
                'sortino_ratio': results['sortino_ratio'],
                'profit_factor': results['profit_factor'],
                'max_drawdown': results['max_drawdown'],
                'total_return': results['total_return'],
                'final_capital': results['final_capital'],
            }
            
            return OptimizationResult(
                parameters=params,
                metrics=metrics,
                score=score,
                valid=valid,
                validation_errors=validation_errors
            )
            
        except Exception as e:
            logger.error(f"Error running backtest with params {params}: {e}")
            return OptimizationResult(
                parameters=params,
                metrics={},
                score=-np.inf,
                valid=False,
                validation_errors=[f"Backtest error: {str(e)}"]
            )
    
    def _calculate_score(self, results: Dict[str, Any]) -> float:
        """
        Расчет score функции для ранжирования результатов.
        
        Опции:
        - sharpe: Sharpe Ratio (риск-скорректированная доходность)
        - profit_factor: Gross Profit / Gross Loss
        - custom: (Total Return / Max DD) * Sharpe * sqrt(Win Rate)
        """
        if self.config.score_function == "sharpe":
            return results['sharpe_ratio']
        
        elif self.config.score_function == "profit_factor":
            return results['profit_factor']
        
        elif self.config.score_function == "custom":
            # Комбинированная метрика
            total_return = results['total_return']
            max_dd = max(results['max_drawdown'], 0.01)  # Avoid division by zero
            sharpe = results['sharpe_ratio']
            win_rate = results['win_rate'] / 100.0
            
            # Формула: (Return / DD) * Sharpe * sqrt(WinRate)
            score = (total_return / max_dd) * sharpe * np.sqrt(win_rate)
            return score
        
        else:
            raise ValueError(f"Unknown score function: {self.config.score_function}")
    
    def optimize(self, parallel: bool = True) -> List[OptimizationResult]:
        """
        Запуск оптимизации.
        
        Args:
            parallel: Использовать параллельную обработку (ProcessPoolExecutor)
        
        Returns:
            Отсортированный список результатов (лучшие первые)
        """
        self.start_time = datetime.now()
        logger.info(f"Starting Grid Optimization at {self.start_time}")
        
        # Генерация параметров
        parameter_grid = self._generate_parameter_grid()
        
        results: List[OptimizationResult] = []
        
        if parallel and self.config.max_workers > 1:
            # Параллельная обработка
            logger.info(f"Running {len(parameter_grid)} backtests in parallel (workers={self.config.max_workers})")
            
            with ProcessPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {
                    executor.submit(self._run_single_backtest, params): params
                    for params in parameter_grid
                }
                
                # Progress bar
                with tqdm(total=len(futures), desc="Optimization") as pbar:
                    for future in as_completed(futures):
                        result = future.result()
                        results.append(result)
                        
                        if result.valid:
                            self.valid_results += 1
                        else:
                            self.invalid_results += 1
                        
                        pbar.update(1)
        
        else:
            # Последовательная обработка
            logger.info(f"Running {len(parameter_grid)} backtests sequentially")
            
            for params in tqdm(parameter_grid, desc="Optimization"):
                result = self._run_single_backtest(params)
                results.append(result)
                
                if result.valid:
                    self.valid_results += 1
                else:
                    self.invalid_results += 1
        
        # Сортировка по score (descending)
        results.sort(key=lambda r: r.score if r.valid else -np.inf, reverse=True)
        
        # Присвоение рангов
        for i, result in enumerate(results, start=1):
            result.rank = i
        
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        logger.info(f"Optimization completed in {duration:.1f}s")
        logger.info(f"Valid results: {self.valid_results}/{self.total_combinations}")
        logger.info(f"Invalid results: {self.invalid_results}/{self.total_combinations}")
        
        if results:
            best = results[0]
            logger.info(f"Best result: Score={best.score:.4f}, Params={best.parameters}")
        
        return results
    
    def export_results(
        self,
        results: List[OptimizationResult],
        filepath: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> Optional[str]:
        """
        Экспорт результатов в CSV.
        
        Args:
            results: Список результатов оптимизации
            filepath: Путь к файлу (опционально, по умолчанию из config)
            top_n: Количество лучших результатов (опционально, по умолчанию из config)
        
        Returns:
            Путь к созданному файлу или None если нет валидных результатов
        """
        if top_n is None:
            top_n = self.config.top_n_results
        
        if filepath is None:
            filepath = self.config.csv_path or f"optimization_results_{datetime.now():%Y%m%d_%H%M%S}.csv"
        
        # Фильтрация только валидных результатов
        valid_results = [r for r in results if r.valid][:top_n]
        
        if not valid_results:
            logger.warning("No valid results to export")
            return None
        
        # Конвертация в DataFrame
        data = [r.to_dict() for r in valid_results]
        df = pd.DataFrame(data)
        
        # Сортировка колонок
        param_cols = [p.name for p in self.config.parameters]
        metric_cols = [c for c in df.columns if c.startswith('metric_')]
        other_cols = ['rank', 'score', 'valid', 'errors']
        
        col_order = param_cols + metric_cols + other_cols
        df = df[[c for c in col_order if c in df.columns]]
        
        # Экспорт
        df.to_csv(filepath, index=False, float_format='%.4f')
        logger.info(f"Exported {len(df)} results to {filepath}")
        
        return filepath
    
    def get_summary(self, results: List[OptimizationResult]) -> Dict[str, Any]:
        """Сводная статистика оптимизации."""
        valid_results = [r for r in results if r.valid]
        
        if not valid_results:
            return {
                'total_combinations': self.total_combinations,
                'valid_results': 0,
                'invalid_results': self.invalid_results,
                'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.end_time else 0,
                'best_score': None,
            }
        
        scores = [r.score for r in valid_results]
        
        return {
            'total_combinations': self.total_combinations,
            'valid_results': self.valid_results,
            'invalid_results': self.invalid_results,
            'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.end_time else 0,
            'best_score': valid_results[0].score,
            'worst_score': valid_results[-1].score if len(valid_results) > 0 else None,
            'mean_score': np.mean(scores),
            'std_score': np.std(scores),
            'best_parameters': valid_results[0].parameters,
        }
