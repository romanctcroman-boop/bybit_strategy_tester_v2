"""
Walk-Forward Optimization

Защита от переобучения через скользящую оптимизацию.
Согласно ТЗ Раздел 3.5.2.

Алгоритм:
1. Разделяем данные на периоды (in-sample + out-of-sample)
2. На in-sample оптимизируем параметры (Grid Search)
3. На out-of-sample тестируем найденные параметры
4. Сдвигаем окно и повторяем
5. Агрегируем результаты всех периодов
"""

from dataclasses import dataclass
from datetime import datetime
from itertools import product
from typing import Any

import numpy as np
import pandas as pd

from backend.core.backtest_engine import BacktestEngine


@dataclass
class WFOPeriod:
    """Результат одного периода Walk-Forward"""
    
    period_num: int
    in_sample_start: datetime
    in_sample_end: datetime
    out_sample_start: datetime
    out_sample_end: datetime
    
    # Оптимизация на in-sample
    best_params: dict[str, Any]
    is_sharpe: float  # In-sample Sharpe
    is_net_profit: float
    is_total_trades: int
    
    # Тест на out-of-sample
    oos_sharpe: float  # Out-of-sample Sharpe
    oos_net_profit: float
    oos_total_trades: int
    oos_max_drawdown: float
    oos_win_rate: float
    
    # Метрики стабильности
    efficiency: float  # OOS/IS performance ratio


class WalkForwardOptimizer:
    """
    Walk-Forward Optimization для защиты от переобучения.
    
    Параметры:
    - in_sample_size: int - количество баров для оптимизации (train)
    - out_sample_size: int - количество баров для тестирования (test)
    - step_size: int - шаг сдвига окна (stride)
    
    Пример:
    - in_sample_size = 252 (1 год дневных данных)
    - out_sample_size = 63 (3 месяца)
    - step_size = 63 (сдвиг на 3 месяца)
    """
    
    def __init__(
        self,
        in_sample_size: int = 252,
        out_sample_size: int = 63,
        step_size: int = 63,
        initial_capital: float = 10000.0,
        commission: float = 0.00075,
        slippage_pct: float = 0.05,
    ):
        self.in_sample_size = in_sample_size
        self.out_sample_size = out_sample_size
        self.step_size = step_size
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage_pct = slippage_pct
        
    def run(
        self,
        data: pd.DataFrame,
        param_space: dict[str, list],
        strategy_config: dict[str, Any],
        metric: str = "sharpe_ratio",
    ) -> dict[str, Any]:
        """
        Запустить Walk-Forward Optimization.
        
        Args:
            data: DataFrame с OHLCV данными
            param_space: Пространство параметров для оптимизации
                Пример: {
                    'take_profit_pct': [1.0, 2.0, 3.0],
                    'stop_loss_pct': [0.5, 1.0, 1.5],
                    'trailing_stop_pct': [0.3, 0.5, 0.7],
                }
            strategy_config: Базовая конфигурация стратегии
            metric: Метрика для оптимизации (sharpe_ratio, net_profit, profit_factor)
        
        Returns:
            {
                'walk_results': list[WFOPeriod],
                'aggregated_metrics': dict,
                'parameter_stability': dict,
            }
        """
        
        total_bars = len(data)
        min_required = self.in_sample_size + self.out_sample_size
        
        if total_bars < min_required:
            raise ValueError(
                f"Not enough data: {total_bars} bars, need at least {min_required} "
                f"(in_sample={self.in_sample_size} + out_sample={self.out_sample_size})"
            )
        
        walk_results = []
        period_num = 0
        
        # Скользящее окно
        start_idx = 0
        while start_idx + min_required <= total_bars:
            period_num += 1
            
            # Определяем границы периодов
            is_start = start_idx
            is_end = start_idx + self.in_sample_size
            oos_start = is_end
            oos_end = min(oos_start + self.out_sample_size, total_bars)
            
            # Данные для in-sample и out-of-sample
            is_data = data.iloc[is_start:is_end]
            oos_data = data.iloc[oos_start:oos_end]
            
            print(f"\n🔄 Period {period_num}:")
            print(f"   In-Sample: {len(is_data)} bars")
            print(f"   Out-of-Sample: {len(oos_data)} bars")
            
            # 1. Оптимизация на in-sample
            best_params, is_metrics = self._optimize_period(
                is_data, param_space, strategy_config, metric
            )
            
            print(f"   ✅ Best params: {best_params}")
            print(f"   IS {metric}: {is_metrics.get(metric, 0):.3f}")
            
            # 2. Тест на out-of-sample с лучшими параметрами
            oos_metrics = self._test_period(oos_data, best_params, strategy_config)
            
            print(f"   OOS {metric}: {oos_metrics.get(metric, 0):.3f}")
            
            # 3. Расчёт efficiency (OOS/IS ratio)
            is_value = is_metrics.get(metric, 0)
            oos_value = oos_metrics.get(metric, 0)
            
            if is_value != 0:
                efficiency = oos_value / is_value
            else:
                efficiency = 0.0
            
            print(f"   Efficiency: {efficiency:.2%}")
            
            # Сохраняем результат периода
            period_result = WFOPeriod(
                period_num=period_num,
                in_sample_start=is_data.index[0],
                in_sample_end=is_data.index[-1],
                out_sample_start=oos_data.index[0],
                out_sample_end=oos_data.index[-1],
                best_params=best_params,
                is_sharpe=is_metrics.get('sharpe_ratio', 0),
                is_net_profit=is_metrics.get('metrics', {}).get('net_profit', 0),
                is_total_trades=is_metrics.get('total_trades', 0),
                oos_sharpe=oos_metrics.get('sharpe_ratio', 0),
                oos_net_profit=oos_metrics.get('metrics', {}).get('net_profit', 0),
                oos_total_trades=oos_metrics.get('total_trades', 0),
                oos_max_drawdown=oos_metrics.get('max_drawdown', 0),
                oos_win_rate=oos_metrics.get('win_rate', 0),
                efficiency=efficiency,
            )
            
            walk_results.append(period_result)
            
            # Сдвигаем окно
            start_idx += self.step_size
        
        # Агрегируем результаты
        aggregated = self._aggregate_results(walk_results)
        
        # Анализ стабильности параметров
        stability = self._analyze_parameter_stability(walk_results)
        
        return {
            'walk_results': walk_results,
            'aggregated_metrics': aggregated,
            'parameter_stability': stability,
        }
    
    def _optimize_period(
        self,
        data: pd.DataFrame,
        param_space: dict[str, list],
        base_config: dict[str, Any],
        metric: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Оптимизация на in-sample периоде (Grid Search).
        
        Returns:
            (best_params, best_metrics)
        """
        
        # Генерируем все комбинации параметров
        param_names = list(param_space.keys())
        param_values = list(param_space.values())
        combinations = list(product(*param_values))
        
        print(f"      🔍 Testing {len(combinations)} combinations...")
        
        best_score = float('-inf')
        best_params = {}
        best_metrics = {}
        
        for combo in combinations:
            # Создаём конфигурацию с текущими параметрами
            test_config = base_config.copy()
            for name, value in zip(param_names, combo):
                test_config[name] = value
            
            # Запускаем бэктест
            try:
                engine = BacktestEngine(
                    initial_capital=self.initial_capital,
                    commission=self.commission,
                    slippage_pct=self.slippage_pct,
                )
                
                results = engine.run(data, test_config)
                
                # Получаем значение метрики
                score = results.get(metric, 0)
                
                # Обновляем лучший результат
                if score > best_score:
                    best_score = score
                    best_params = {name: value for name, value in zip(param_names, combo)}
                    best_metrics = results
                    
            except Exception as e:
                # Пропускаем комбинации с ошибками
                continue
        
        return best_params, best_metrics
    
    def _test_period(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        base_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Тест на out-of-sample периоде с найденными параметрами.
        
        Returns:
            metrics
        """
        
        # Применяем найденные параметры
        test_config = base_config.copy()
        test_config.update(params)
        
        # Запускаем бэктест
        engine = BacktestEngine(
            initial_capital=self.initial_capital,
            commission=self.commission,
            slippage_pct=self.slippage_pct,
        )
        
        results = engine.run(data, test_config)
        
        return results
    
    def _aggregate_results(self, periods: list[WFOPeriod]) -> dict[str, Any]:
        """
        Агрегирует результаты всех периодов.
        
        Returns:
            {
                'total_periods': int,
                'avg_efficiency': float,
                'oos_total_return': float,
                'oos_avg_sharpe': float,
                'oos_total_trades': int,
                'oos_avg_win_rate': float,
            }
        """
        
        if not periods:
            return {}
        
        total_oos_profit = sum(p.oos_net_profit for p in periods)
        avg_efficiency = np.mean([p.efficiency for p in periods])
        avg_oos_sharpe = np.mean([p.oos_sharpe for p in periods])
        total_oos_trades = sum(p.oos_total_trades for p in periods)
        avg_oos_win_rate = np.mean([p.oos_win_rate for p in periods])
        
        return {
            'total_periods': len(periods),
            'avg_efficiency': avg_efficiency,
            'oos_total_return': (total_oos_profit / self.initial_capital) * 100,
            'oos_avg_sharpe': avg_oos_sharpe,
            'oos_total_trades': total_oos_trades,
            'oos_avg_win_rate': avg_oos_win_rate,
            'oos_avg_drawdown': np.mean([p.oos_max_drawdown for p in periods]),
        }
    
    def _analyze_parameter_stability(
        self, periods: list[WFOPeriod]
    ) -> dict[str, Any]:
        """
        Анализ стабильности параметров по периодам.
        
        Returns:
            {
                'parameter_name': {
                    'mean': float,
                    'std': float,
                    'min': float,
                    'max': float,
                    'stability_score': float  # 1 - std/mean (lower is better)
                }
            }
        """
        
        if not periods:
            return {}
        
        # Собираем значения каждого параметра
        param_values = {}
        for period in periods:
            for param_name, param_value in period.best_params.items():
                if param_name not in param_values:
                    param_values[param_name] = []
                param_values[param_name].append(param_value)
        
        # Рассчитываем статистику
        stability = {}
        for param_name, values in param_values.items():
            mean = np.mean(values)
            std = np.std(values)
            
            # Stability score: 0 = идеально стабильно, 1 = нестабильно
            if mean != 0:
                stability_score = std / abs(mean)
            else:
                stability_score = 0.0
            
            stability[param_name] = {
                'mean': mean,
                'std': std,
                'min': np.min(values),
                'max': np.max(values),
                'stability_score': stability_score,
                'values': values,  # Для визуализации
            }
        
        return stability
