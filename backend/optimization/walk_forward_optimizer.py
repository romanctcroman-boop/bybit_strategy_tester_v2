"""
Walk-Forward Optimization - Единая консолидированная реализация

Соответствие ТЗ 3.5.2:
- Защита от переобучения через скользящую оптимизацию
- Параметры в барах (in_sample_size, out_sample_size, step_size)
- Parameter stability метрика (ТЗ требует, была отсутствующей)
- Aggregated metrics
- Доступен на Продвинутом уровне

Алгоритм:
1. Разделяем данные на периоды (in-sample + out-of-sample)
2. На in-sample оптимизируем параметры (Grid Search)
3. На out-of-sample тестируем найденные параметры
4. Сдвигаем окно и повторяем
5. Рассчитываем parameter_stability (std/mean для каждого параметра)
6. Агрегируем результаты всех периодов

Создано: 25 октября 2025 (Фаза 1, Задача 1)
Консолидирует:
- backend/optimization/walk_forward.py
- backend/core/walk_forward_optimizer.py
- backend/tasks/optimize_tasks.py (walk_forward_task)
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from itertools import product
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger


class WFOMode(str, Enum):
    """Режим Walk-Forward оптимизации"""
    ROLLING = "rolling"    # Скользящее окно фиксированного размера
    ANCHORED = "anchored"  # Начало фиксировано, расширяем вперед


@dataclass
class WFOPeriod:
    """Результат одного периода Walk-Forward"""
    
    period_num: int
    
    # Временные границы (индексы баров)
    in_sample_start: int
    in_sample_end: int
    out_sample_start: int
    out_sample_end: int
    
    # Оптимизация на in-sample
    best_params: dict[str, Any]
    is_sharpe: float  # In-sample Sharpe
    is_net_profit: float
    is_total_trades: int
    is_max_drawdown: float
    
    # Тест на out-of-sample
    oos_sharpe: float  # Out-of-sample Sharpe
    oos_net_profit: float
    oos_total_trades: int
    oos_max_drawdown: float
    oos_win_rate: float
    oos_profit_factor: float
    
    # Метрики стабильности
    efficiency: float      # OOS/IS performance ratio
    degradation: float     # IS Sharpe - OOS Sharpe
    
    def to_dict(self) -> dict:
        """Конвертирует в словарь для JSON сериализации"""
        return asdict(self)


class WalkForwardOptimizer:
    """
    ТЗ 3.5.2 - Защита от переобучения через скользящую оптимизацию
    Доступен на Продвинутом уровне
    
    Параметры:
    - in_sample_size: int - количество баров для оптимизации (train)
    - out_sample_size: int - количество баров для тестирования (test)
    - step_size: int - шаг сдвига окна (stride)
    
    Пример:
        optimizer = WalkForwardOptimizer(
            in_sample_size=252,   # 1 год дневных данных
            out_sample_size=63,   # 3 месяца
            step_size=63          # сдвиг на 3 месяца
        )
        
        results = optimizer.run(
            data=df,
            param_space={'tp': [1.0, 2.0, 3.0], 'sl': [0.5, 1.0]},
            strategy_config={'type': 'ema_crossover'},
            metric='sharpe_ratio'
        )
    """
    
    def __init__(
        self,
        in_sample_size: int,   # ТЗ требует параметры в барах
        out_sample_size: int,
        step_size: int,
        mode: WFOMode = WFOMode.ROLLING,
        initial_capital: float = 10000.0,
        commission: float = 0.0006,
        slippage_pct: float = 0.05,
    ):
        """
        Args:
            in_sample_size: Количество баров для оптимизации
            out_sample_size: Количество баров для тестирования
            step_size: Шаг сдвига окна (в барах)
            mode: Режим (rolling или anchored)
            initial_capital: Начальный капитал
            commission: Комиссия
            slippage_pct: Проскальзывание в %
        """
        self.in_sample_size = in_sample_size
        self.out_sample_size = out_sample_size
        self.step_size = step_size
        self.mode = mode
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage_pct = slippage_pct
        
        logger.info(
            f"WalkForwardOptimizer initialized: IS={in_sample_size}, "
            f"OOS={out_sample_size}, step={step_size}, mode={mode.value}"
        )
    
    def run(
        self,
        data: pd.DataFrame,
        param_space: dict[str, list],
        strategy_config: dict[str, Any],
        metric: str = "sharpe_ratio"
    ) -> dict[str, Any]:
        """
        Запуск Walk-Forward оптимизации
        
        Args:
            data: DataFrame с OHLCV данными
            param_space: Пространство параметров для оптимизации
                Пример: {'tp_pct': [1.0, 2.0, 3.0], 'sl_pct': [0.5, 1.0]}
            strategy_config: Базовая конфигурация стратегии
            metric: Метрика для оптимизации
        
        Returns:
            {
                'walk_results': list[dict],      # Результат каждого периода
                'aggregated_metrics': dict,      # Общие метрики
                'parameter_stability': dict      # ✅ NEW: Стабильность параметров
            }
        """
        logger.info(f"Starting Walk-Forward Optimization with {metric} metric")
        
        # Calculate number of walks
        total_bars = len(data)
        
        if self.mode == WFOMode.ROLLING:
            num_walks = (total_bars - self.in_sample_size - self.out_sample_size) // self.step_size + 1
        else:  # ANCHORED
            num_walks = (total_bars - self.in_sample_size - self.out_sample_size) // self.step_size + 1
        
        if num_walks < 1:
            logger.error(
                f"Insufficient data: total={total_bars}, IS={self.in_sample_size}, "
                f"OOS={self.out_sample_size}. Need at least {self.in_sample_size + self.out_sample_size} bars"
            )
            return self._empty_result()
        
        logger.info(f"Will run {num_walks} walk-forward iterations")
        
        walk_results = []
        all_best_params = []  # ✅ NEW: Для расчета parameter_stability
        
        for walk_idx in range(num_walks):
            if self.mode == WFOMode.ROLLING:
                # Rolling window: окно фиксированного размера двигается
                start_idx = walk_idx * self.step_size
            else:
                # Anchored: начало фиксировано, расширяем вперед
                start_idx = 0
            
            is_end = start_idx + self.in_sample_size
            oos_start = is_end
            oos_end = oos_start + self.out_sample_size
            
            if oos_end > total_bars:
                logger.warning(f"Walk {walk_idx+1}: OOS end ({oos_end}) exceeds data length ({total_bars}), stopping")
                break
            
            # In-Sample data
            is_data = data.iloc[start_idx:is_end].copy()
            
            # Out-of-Sample data
            oos_data = data.iloc[oos_start:oos_end].copy()
            
            logger.info(
                f"Walk {walk_idx+1}/{num_walks}: "
                f"IS [{start_idx}:{is_end}] ({len(is_data)} bars), "
                f"OOS [{oos_start}:{oos_end}] ({len(oos_data)} bars)"
            )
            
            # Optimize on IS
            best_params, is_metrics = self._optimize_on_is(
                is_data, param_space, strategy_config, metric
            )
            
            # Test on OOS
            oos_metrics = self._test_on_oos(
                oos_data, best_params, strategy_config
            )
            
            # Calculate stability metrics
            efficiency = oos_metrics['sharpe_ratio'] / is_metrics['sharpe_ratio'] if is_metrics['sharpe_ratio'] != 0 else 0
            degradation = is_metrics['sharpe_ratio'] - oos_metrics['sharpe_ratio']
            
            period = WFOPeriod(
                period_num=walk_idx + 1,
                in_sample_start=start_idx,
                in_sample_end=is_end,
                out_sample_start=oos_start,
                out_sample_end=oos_end,
                best_params=best_params,
                is_sharpe=is_metrics['sharpe_ratio'],
                is_net_profit=is_metrics['net_profit'],
                is_total_trades=is_metrics['total_trades'],
                is_max_drawdown=is_metrics['max_drawdown'],
                oos_sharpe=oos_metrics['sharpe_ratio'],
                oos_net_profit=oos_metrics['net_profit'],
                oos_total_trades=oos_metrics['total_trades'],
                oos_max_drawdown=oos_metrics['max_drawdown'],
                oos_win_rate=oos_metrics['win_rate'],
                oos_profit_factor=oos_metrics['profit_factor'],
                efficiency=efficiency,
                degradation=degradation
            )
            
            walk_results.append(period.to_dict())
            all_best_params.append(best_params)
            
            logger.info(
                f"  IS: Sharpe={is_metrics['sharpe_ratio']:.3f}, Profit={is_metrics['net_profit']:.2f}, Trades={is_metrics['total_trades']}"
            )
            logger.info(
                f"  OOS: Sharpe={oos_metrics['sharpe_ratio']:.3f}, Profit={oos_metrics['net_profit']:.2f}, "
                f"Efficiency={efficiency:.2f}, Degradation={degradation:.3f}"
            )
        
        # Aggregate metrics
        aggregated = self._calculate_aggregated_metrics(walk_results, metric)
        
        # ✅ NEW: Parameter stability (ТЗ 3.5.2 требует)
        parameter_stability = self._calculate_parameter_stability(all_best_params)
        
        logger.info(
            f"WFO completed: {len(walk_results)} periods, "
            f"OOS mean Sharpe={aggregated['oos_mean_sharpe']:.3f}, "
            f"IS/OOS ratio={aggregated['is_oos_ratio']:.2f}"
        )
        
        return {
            'walk_results': walk_results,
            'aggregated_metrics': aggregated,
            'parameter_stability': parameter_stability,  # ✅ NEW
            'num_walks': len(walk_results),
            'mode': self.mode.value
        }
    
    def _optimize_on_is(
        self,
        data: pd.DataFrame,
        param_space: dict[str, list],
        strategy_config: dict,
        metric: str
    ) -> tuple[dict, dict]:
        """
        Grid search на In-Sample данных
        
        Returns:
            (best_params, is_metrics)
        """
        from backend.core.engine_adapter import get_engine
        
        # Generate all combinations
        param_names = list(param_space.keys())
        param_values = [param_space[name] for name in param_names]
        combinations = list(product(*param_values))
        
        logger.debug(f"Testing {len(combinations)} parameter combinations on IS data")
        
        best_score = float('-inf')
        best_params = None
        best_metrics = None
        
        for combo in combinations:
            params = dict(zip(param_names, combo))
            
            # Merge params into strategy_config
            test_config = {**strategy_config, **params}
            
            # Run backtest
            try:
                engine = get_engine(
                    initial_capital=self.initial_capital,
                    commission=self.commission,
                    slippage_pct=self.slippage_pct
                )
                result = engine.run(data, test_config)
                
                score = result.get(metric, float('-inf'))
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_metrics = {
                        'sharpe_ratio': result.get('sharpe_ratio', 0),
                        'net_profit': result.get('total_return', 0) * self.initial_capital,
                        'total_trades': result.get('total_trades', 0),
                        'max_drawdown': result.get('max_drawdown', 0),
                        'win_rate': result.get('win_rate', 0),
                        'profit_factor': result.get('profit_factor', 0)
                    }
            except Exception as e:
                logger.warning(f"Backtest failed for params {params}: {e}")
                continue
        
        if best_params is None:
            logger.error("No valid results from IS optimization")
            best_params = {}
            best_metrics = {
                'sharpe_ratio': 0, 'net_profit': 0, 'total_trades': 0,
                'max_drawdown': 0, 'win_rate': 0, 'profit_factor': 0
            }
        
        return best_params, best_metrics
    
    def _test_on_oos(
        self,
        data: pd.DataFrame,
        params: dict,
        strategy_config: dict
    ) -> dict:
        """
        Тест на Out-of-Sample данных с фиксированными параметрами
        
        Returns:
            oos_metrics dict
        """
        from backend.core.engine_adapter import get_engine
        
        # Merge params into config
        test_config = {**strategy_config, **params}
        
        try:
            engine = get_engine(
                initial_capital=self.initial_capital,
                commission=self.commission,
                slippage_pct=self.slippage_pct
            )
            result = engine.run(data, test_config)
            
            return {
                'sharpe_ratio': result.get('sharpe_ratio', 0),
                'net_profit': result.get('total_return', 0) * self.initial_capital,
                'total_trades': result.get('total_trades', 0),
                'max_drawdown': result.get('max_drawdown', 0),
                'win_rate': result.get('win_rate', 0),
                'profit_factor': result.get('profit_factor', 0)
            }
        except Exception as e:
            logger.error(f"OOS test failed: {e}")
            return {
                'sharpe_ratio': 0, 'net_profit': 0, 'total_trades': 0,
                'max_drawdown': 0, 'win_rate': 0, 'profit_factor': 0
            }
    
    def _calculate_aggregated_metrics(
        self,
        walk_results: list[dict],
        metric: str
    ) -> dict:
        """
        Агрегированные метрики по всем периодам
        
        Returns:
            {
                'is_mean_sharpe': float,
                'is_std_sharpe': float,
                'oos_mean_sharpe': float,
                'oos_std_sharpe': float,
                'is_oos_ratio': float,
                'mean_efficiency': float,
                'mean_degradation': float,
                'num_walks': int
            }
        """
        if not walk_results:
            return {
                'is_mean_sharpe': 0, 'is_std_sharpe': 0,
                'oos_mean_sharpe': 0, 'oos_std_sharpe': 0,
                'is_oos_ratio': 0, 'mean_efficiency': 0,
                'mean_degradation': 0, 'num_walks': 0
            }
        
        is_sharpes = [w['is_sharpe'] for w in walk_results]
        oos_sharpes = [w['oos_sharpe'] for w in walk_results]
        efficiencies = [w['efficiency'] for w in walk_results]
        degradations = [w['degradation'] for w in walk_results]
        
        is_mean = np.mean(is_sharpes)
        oos_mean = np.mean(oos_sharpes)
        
        return {
            'is_mean_sharpe': float(is_mean),
            'is_std_sharpe': float(np.std(is_sharpes)),
            'oos_mean_sharpe': float(oos_mean),
            'oos_std_sharpe': float(np.std(oos_sharpes)),
            'is_oos_ratio': float(oos_mean / is_mean) if is_mean != 0 else 0,
            'mean_efficiency': float(np.mean(efficiencies)),
            'mean_degradation': float(np.mean(degradations)),
            'num_walks': len(walk_results)
        }
    
    def _calculate_parameter_stability(self, all_params: list[dict]) -> dict:
        """
        ✅ NEW: Стабильность параметров (ТЗ 3.5.2)
        
        Рассчитывает std deviation каждого параметра по всем периодам.
        Низкий std = стабильные параметры = хорошо.
        Высокий std = параметры "скачут" = переобучение.
        
        Args:
            all_params: Список best_params из каждого периода
        
        Returns:
            {
                'param_name': {
                    'mean': float,
                    'std': float,
                    'min': float,
                    'max': float,
                    'stability_score': float  # 0-1, higher = more stable
                },
                ...
            }
        """
        if not all_params:
            return {}
        
        # Determine all parameter names
        param_names = set()
        for params in all_params:
            param_names.update(params.keys())
        
        stability = {}
        
        for param_name in param_names:
            values = []
            for params in all_params:
                if param_name in params:
                    values.append(params[param_name])
            
            if not values:
                continue
            
            values_array = np.array(values)
            mean_val = np.mean(values_array)
            std_val = np.std(values_array)
            
            # Stability score: inverse of coefficient of variation
            # CV = std / mean (for mean != 0)
            # stability_score = 1 / (1 + CV)
            # Higher score = more stable
            cv = std_val / abs(mean_val) if mean_val != 0 else std_val
            stability_score = 1.0 / (1.0 + cv)
            
            stability[param_name] = {
                'mean': float(mean_val),
                'std': float(std_val),
                'min': float(np.min(values_array)),
                'max': float(np.max(values_array)),
                'coefficient_of_variation': float(cv),
                'stability_score': float(stability_score),  # 0-1, higher is better
                'num_periods': len(values)
            }
        
        logger.info(
            f"Parameter stability calculated for {len(stability)} parameters. "
            f"Average stability: {np.mean([s['stability_score'] for s in stability.values()]):.3f}"
        )
        
        return stability
    
    def _empty_result(self) -> dict:
        """Empty result for error cases"""
        return {
            'walk_results': [],
            'aggregated_metrics': {
                'is_mean_sharpe': 0, 'is_std_sharpe': 0,
                'oos_mean_sharpe': 0, 'oos_std_sharpe': 0,
                'is_oos_ratio': 0, 'mean_efficiency': 0,
                'mean_degradation': 0, 'num_walks': 0
            },
            'parameter_stability': {},
            'num_walks': 0,
            'mode': self.mode.value
        }
