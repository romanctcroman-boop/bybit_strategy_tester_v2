"""
Walk-Forward Optimization (ТЗ 3.5.2)

Защита от переобучения через скользящую оптимизацию.

Алгоритм:
1. Разделяем данные на периоды (in-sample + out-of-sample)
2. На in-sample оптимизируем параметры (Grid Search)
3. На out-of-sample тестируем найденные параметры
4. Сдвигаем окно и повторяем (Rolling или Anchored)
5. Агрегируем результаты всех периодов

Режимы:
- Rolling: Окно фиксированного размера сдвигается
- Anchored: Начало фиксировано, конец двигается

Метрики стабильности:
- Efficiency: OOS/IS ratio
- Degradation: IS Sharpe - OOS Sharpe
- Parameter Consistency: std/mean для каждого параметра
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from itertools import product
from typing import Any, Optional

import numpy as np
import pandas as pd


class WFOMode(str, Enum):
    """Режим Walk-Forward оптимизации"""
    ROLLING = "rolling"  # Скользящее окно фиксированного размера
    ANCHORED = "anchored"  # Начало фиксировано, расширяем вперед


@dataclass
class ParameterRange:
    """Диапазон значений параметра для оптимизации"""
    start: float
    stop: float
    step: float
    
    def to_list(self) -> list[float]:
        """Конвертирует диапазон в список значений"""
        values = []
        current = self.start
        while current <= self.stop:
            values.append(round(current, 4))
            current += self.step
        return values


@dataclass
class WFOPeriod:
    """Результат одного периода Walk-Forward"""
    
    period_num: int
    
    # Временные границы
    in_sample_start: datetime
    in_sample_end: datetime
    out_sample_start: datetime
    out_sample_end: datetime
    
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
    
    # Метрики стабильности
    efficiency: float  # OOS/IS performance ratio
    degradation: float  # IS Sharpe - OOS Sharpe
    
    def to_dict(self) -> dict:
        """Конвертирует в словарь для JSON сериализации"""
        d = asdict(self)
        # Конвертируем datetime в ISO строки
        for key in ['in_sample_start', 'in_sample_end', 'out_sample_start', 'out_sample_end']:
            if isinstance(d[key], datetime):
                d[key] = d[key].isoformat()
        return d


@dataclass
class WFOConfig:
    """Конфигурация Walk-Forward оптимизации"""
    
    in_sample_size: int = 252  # Размер обучающего окна (баров)
    out_sample_size: int = 63  # Размер тестового окна (баров)
    step_size: int = 63  # Шаг сдвига окна
    mode: WFOMode = WFOMode.ROLLING  # Режим (rolling/anchored)
    
    min_trades: int = 30  # Минимум сделок для валидации
    max_drawdown: float = 0.50  # Максимальная просадка (50%)
    
    initial_capital: float = 10000.0
    commission: float = 0.00075
    slippage_pct: float = 0.05


class WalkForwardOptimizer:
    """
    Walk-Forward Optimization для защиты от переобучения.
    
    Поддерживает два режима:
    - Rolling Window: Окно фиксированного размера скользит по данным
    - Anchored Window: Начало фиксировано, конец расширяется
    
    Пример использования:
    ```python
    wfo = WalkForwardOptimizer(config=WFOConfig(
        in_sample_size=252,
        out_sample_size=63,
        step_size=63,
        mode=WFOMode.ROLLING
    ))
    
    results = wfo.optimize(
        data=df,
        param_ranges={
            'tp_pct': ParameterRange(1.0, 5.0, 0.5),
            'sl_pct': ParameterRange(0.5, 3.0, 0.5),
        },
        strategy_config={'strategy_type': 'trend_following'},
        metric='sharpe_ratio'
    )
    ```
    """
    
    def __init__(self, config: Optional[WFOConfig] = None):
        self.config = config or WFOConfig()
        
    def optimize(
        self,
        data: pd.DataFrame,
        param_ranges: dict[str, ParameterRange | list],
        strategy_config: dict[str, Any],
        metric: str = "sharpe_ratio",
        backtest_engine = None,
    ) -> dict[str, Any]:
        """
        Запустить Walk-Forward Optimization.
        
        Args:
            data: DataFrame с OHLCV данными (индекс = timestamp)
            param_ranges: Диапазоны параметров для оптимизации
                Пример: {
                    'tp_pct': ParameterRange(1.0, 5.0, 0.5),
                    'sl_pct': [0.5, 1.0, 1.5, 2.0],
                }
            strategy_config: Базовая конфигурация стратегии
            metric: Метрика для оптимизации (sharpe_ratio, profit_factor, net_profit)
            backtest_engine: Опциональный BacktestEngine (для dependency injection)
        
        Returns:
            {
                'walk_results': list[WFOPeriod],
                'aggregated_metrics': dict,
                'parameter_stability': dict,
                'summary': dict,
            }
        """
        
        # Конвертируем list[dict] в DataFrame если необходимо
        if isinstance(data, list):
            data = pd.DataFrame(data)
            if 'timestamp' in data.columns:
                data['timestamp'] = pd.to_datetime(data['timestamp'], unit='s', errors='coerce')
                data.set_index('timestamp', inplace=True)
        
        # Конвертируем ParameterRange в списки
        param_space = {}
        for name, range_def in param_ranges.items():
            if isinstance(range_def, ParameterRange):
                param_space[name] = range_def.to_list()
            else:
                param_space[name] = range_def
        
        total_bars = len(data)
        min_required = self.config.in_sample_size + self.config.out_sample_size
        
        if total_bars < min_required:
            raise ValueError(
                f"Not enough data: {total_bars} bars, need at least {min_required} "
                f"(in_sample={self.config.in_sample_size} + out_sample={self.config.out_sample_size})"
            )
        
        walk_results = []
        period_num = 0
        
        # Определяем начальную позицию в зависимости от режима
        if self.config.mode == WFOMode.ROLLING:
            start_idx = 0
        else:  # ANCHORED
            start_idx = 0  # Начало всегда с первого бара
        
        # Скользящее окно
        while True:
            period_num += 1
            
            # Определяем границы периодов в зависимости от режима
            if self.config.mode == WFOMode.ROLLING:
                is_start = start_idx
                is_end = start_idx + self.config.in_sample_size
                oos_start = is_end
                oos_end = min(oos_start + self.config.out_sample_size, total_bars)
                
                # Проверка выхода за границы
                if is_end > total_bars or oos_start >= total_bars:
                    break
                    
            else:  # ANCHORED
                is_start = 0  # Всегда с начала
                is_end = start_idx + self.config.in_sample_size
                oos_start = is_end
                oos_end = min(oos_start + self.config.out_sample_size, total_bars)
                
                # Проверка выхода за границы
                if oos_end > total_bars:
                    break
            
            # Данные для in-sample и out-of-sample
            is_data = data.iloc[is_start:is_end]
            oos_data = data.iloc[oos_start:oos_end]
            
            if len(oos_data) == 0:
                break
            
            print(f"\n🔄 Period {period_num} ({self.config.mode.value}):")
            print(f"   In-Sample: {len(is_data)} bars ({is_data.index[0]} to {is_data.index[-1]})")
            print(f"   Out-of-Sample: {len(oos_data)} bars ({oos_data.index[0]} to {oos_data.index[-1]})")
            
            # 1. Оптимизация на in-sample
            best_params, is_metrics = self._optimize_period(
                is_data, param_space, strategy_config, metric, backtest_engine
            )
            
            if not best_params:
                print(f"   ⚠️  No valid results on IS period, skipping...")
                start_idx += self.config.step_size
                continue
            
            print(f"   ✅ Best params: {best_params}")
            print(f"   IS {metric}: {is_metrics.get(metric, 0):.3f}")
            
            # 2. Тест на out-of-sample с лучшими параметрами
            oos_metrics = self._test_period(oos_data, best_params, strategy_config, backtest_engine)
            
            if oos_metrics is None:
                print(f"   ⚠️  OOS test failed, skipping...")
                start_idx += self.config.step_size
                continue
            
            print(f"   OOS {metric}: {oos_metrics.get(metric, 0):.3f}")
            
            # 3. Расчёт метрик стабильности
            is_value = is_metrics.get(metric, 0)
            oos_value = oos_metrics.get(metric, 0)
            
            # Efficiency: OOS/IS ratio
            if is_value != 0:
                efficiency = oos_value / is_value
            else:
                efficiency = 0.0
            
            # Degradation: IS - OOS (для Sharpe)
            if metric == 'sharpe_ratio':
                degradation = is_metrics.get('sharpe_ratio', 0) - oos_metrics.get('sharpe_ratio', 0)
            else:
                degradation = 0.0
            
            print(f"   Efficiency: {efficiency:.2%}")
            print(f"   Degradation: {degradation:.3f}")
            
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
                is_max_drawdown=is_metrics.get('max_drawdown', 0),
                oos_sharpe=oos_metrics.get('sharpe_ratio', 0),
                oos_net_profit=oos_metrics.get('metrics', {}).get('net_profit', 0),
                oos_total_trades=oos_metrics.get('total_trades', 0),
                oos_max_drawdown=oos_metrics.get('max_drawdown', 0),
                oos_win_rate=oos_metrics.get('win_rate', 0),
                efficiency=efficiency,
                degradation=degradation,
            )
            
            walk_results.append(period_result)
            
            # Сдвигаем окно
            start_idx += self.config.step_size
        
        if not walk_results:
            raise ValueError("No valid walk-forward periods generated")
        
        # Агрегируем результаты
        aggregated = self._aggregate_results(walk_results)
        
        # Анализ стабильности параметров
        stability = self._analyze_parameter_stability(walk_results)
        
        # Общая сводка
        summary = self._generate_summary(walk_results, aggregated, stability)
        
        return {
            'walk_results': [p.to_dict() for p in walk_results],
            'aggregated_metrics': aggregated,
            'parameter_stability': stability,
            'summary': summary,
        }
    
    def _optimize_period(
        self,
        data: pd.DataFrame,
        param_space: dict[str, list],
        base_config: dict[str, Any],
        metric: str,
        backtest_engine = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Оптимизация на in-sample периоде (Grid Search).
        
        Returns:
            (best_params, best_metrics)
        """
        from backend.core.backtest_engine import BacktestEngine
        
        # Генерируем все комбинации параметров
        param_names = list(param_space.keys())
        param_values = list(param_space.values())
        combinations = list(product(*param_values))
        
        print(f"      🔍 Testing {len(combinations)} combinations...")
        
        best_score = float('-inf')
        best_params = {}
        best_metrics = {}
        valid_count = 0
        
        for combo in combinations:
            # Создаём конфигурацию с текущими параметрами
            test_config = base_config.copy()
            for name, value in zip(param_names, combo):
                test_config[name] = value
            
            # Запускаем бэктест
            try:
                if backtest_engine:
                    engine = backtest_engine
                else:
                    engine = BacktestEngine(
                        initial_capital=self.config.initial_capital,
                        commission=self.config.commission,
                        slippage_pct=self.config.slippage_pct,
                    )
                
                results = engine.run(data, test_config)
                
                # Валидация результатов
                total_trades = results.get('total_trades', 0)
                max_dd = results.get('max_drawdown', 0)
                
                if total_trades < self.config.min_trades:
                    continue
                    
                if abs(max_dd) > self.config.max_drawdown:
                    continue
                
                valid_count += 1
                
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
        
        print(f"      ✅ {valid_count}/{len(combinations)} valid results")
        
        return best_params, best_metrics
    
    def _test_period(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        base_config: dict[str, Any],
        backtest_engine = None,
    ) -> Optional[dict[str, Any]]:
        """
        Тест на out-of-sample периоде с найденными параметрами.
        
        Returns:
            metrics или None при ошибке
        """
        from backend.core.backtest_engine import BacktestEngine
        
        # Применяем найденные параметры
        test_config = base_config.copy()
        test_config.update(params)
        
        try:
            # Запускаем бэктест
            if backtest_engine:
                engine = backtest_engine
            else:
                engine = BacktestEngine(
                    initial_capital=self.config.initial_capital,
                    commission=self.config.commission,
                    slippage_pct=self.config.slippage_pct,
                )
            
            results = engine.run(data, test_config)
            return results
        except Exception as e:
            print(f"      ❌ OOS test error: {e}")
            return None
    
    def _aggregate_results(self, periods: list[WFOPeriod]) -> dict[str, Any]:
        """
        Агрегирует результаты всех периодов.
        
        Returns:
            {
                'total_periods': int,
                'avg_efficiency': float,
                'avg_degradation': float,
                'oos_total_return': float,
                'oos_avg_sharpe': float,
                'oos_total_trades': int,
                'oos_avg_win_rate': float,
                'oos_avg_drawdown': float,
                'consistency_score': float,
            }
        """
        
        if not periods:
            return {}
        
        total_oos_profit = sum(p.oos_net_profit for p in periods)
        avg_efficiency = np.mean([p.efficiency for p in periods])
        avg_degradation = np.mean([p.degradation for p in periods])
        avg_oos_sharpe = np.mean([p.oos_sharpe for p in periods])
        total_oos_trades = sum(p.oos_total_trades for p in periods)
        avg_oos_win_rate = np.mean([p.oos_win_rate for p in periods])
        avg_oos_drawdown = np.mean([abs(p.oos_max_drawdown) for p in periods])
        
        # Consistency score: процент периодов с положительным OOS profit
        profitable_periods = sum(1 for p in periods if p.oos_net_profit > 0)
        consistency_score = profitable_periods / len(periods)
        
        return {
            'total_periods': len(periods),
            'avg_efficiency': float(avg_efficiency),
            'avg_degradation': float(avg_degradation),
            'oos_total_return_pct': float((total_oos_profit / self.config.initial_capital) * 100),
            'oos_avg_sharpe': float(avg_oos_sharpe),
            'oos_total_trades': int(total_oos_trades),
            'oos_avg_win_rate': float(avg_oos_win_rate),
            'oos_avg_drawdown': float(avg_oos_drawdown),
            'consistency_score': float(consistency_score),
        }
    
    def _analyze_parameter_stability(
        self, periods: list[WFOPeriod]
    ) -> dict[str, dict]:
        """
        Анализ стабильности параметров по периодам.
        
        Returns:
            {
                'parameter_name': {
                    'mean': float,
                    'std': float,
                    'min': float,
                    'max': float,
                    'stability_score': float,  # 1 - (std/mean), чем выше, тем стабильнее
                    'values': list[float],
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
            
            # Stability score: 1 = идеально стабильно, 0 = нестабильно
            if mean != 0:
                # Coefficient of variation (inverted)
                cv = std / abs(mean)
                stability_score = max(0, 1 - cv)
            else:
                stability_score = 0.0
            
            stability[param_name] = {
                'mean': float(mean),
                'std': float(std),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'stability_score': float(stability_score),
                'values': [float(v) for v in values],
            }
        
        return stability
    
    def _generate_summary(
        self,
        periods: list[WFOPeriod],
        aggregated: dict,
        stability: dict,
    ) -> dict[str, Any]:
        """
        Генерирует общую сводку по результатам WFO.
        
        Returns:
            {
                'recommendation': str,
                'robustness_score': float,  # 0-100
                'key_findings': list[str],
            }
        """
        
        # Рассчитываем Robustness Score (0-100)
        # Компоненты:
        # 1. Efficiency (40%)
        # 2. Consistency (30%)
        # 3. Parameter Stability (30%)
        
        efficiency_score = min(aggregated['avg_efficiency'] * 100, 100)
        consistency_score = aggregated['consistency_score'] * 100
        
        # Средний stability score по всем параметрам
        if stability:
            avg_stability = np.mean([s['stability_score'] for s in stability.values()])
            stability_score = avg_stability * 100
        else:
            stability_score = 0
        
        robustness = (
            efficiency_score * 0.4 +
            consistency_score * 0.3 +
            stability_score * 0.3
        )
        
        # Рекомендация
        if robustness >= 70:
            recommendation = "✅ Strategy shows good robustness. Safe to deploy."
        elif robustness >= 50:
            recommendation = "⚠️ Strategy shows moderate robustness. Use with caution."
        else:
            recommendation = "❌ Strategy shows poor robustness. Re-optimize or discard."
        
        # Key findings
        findings = []
        findings.append(f"Average OOS Sharpe: {aggregated['oos_avg_sharpe']:.2f}")
        findings.append(f"Efficiency: {aggregated['avg_efficiency']:.1%}")
        findings.append(f"Consistency: {aggregated['consistency_score']:.1%}")
        findings.append(f"Degradation: {aggregated['avg_degradation']:.3f}")
        
        return {
            'recommendation': recommendation,
            'robustness_score': float(robustness),
            'key_findings': findings,
        }
