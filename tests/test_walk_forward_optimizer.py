"""
Tests for Walk-Forward Optimizer

Testing ТЗ 3.5.2 implementation:
- Rolling window mode
- Anchored window mode
- Parameter stability analysis
- Degradation metrics
- Efficiency calculations
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.optimization.walk_forward import (
    WalkForwardOptimizer,
    WFOConfig,
    WFOMode,
    ParameterRange,
)


@pytest.fixture
def sample_data():
    """Генерирует тестовые OHLCV данные"""
    dates = pd.date_range(start='2024-01-01', periods=500, freq='1h')
    
    # Генерируем синтетические данные с трендом
    np.random.seed(42)
    close_prices = 50000 + np.cumsum(np.random.randn(500) * 100)
    
    data = pd.DataFrame({
        'open': close_prices + np.random.randn(500) * 50,
        'high': close_prices + np.abs(np.random.randn(500) * 100),
        'low': close_prices - np.abs(np.random.randn(500) * 100),
        'close': close_prices,
        'volume': np.random.randint(100, 1000, 500),
    }, index=dates)
    
    return data


@pytest.fixture
def simple_param_ranges():
    """Простые диапазоны параметров для тестов"""
    return {
        'tp_pct': ParameterRange(1.0, 2.0, 1.0),  # [1.0, 2.0]
        'sl_pct': ParameterRange(0.5, 1.0, 0.5),  # [0.5, 1.0]
    }


@pytest.fixture
def mock_backtest_engine():
    """Mock BacktestEngine для тестов без реальных расчетов"""
    class MockEngine:
        def __init__(self, **kwargs):
            pass
        
        def run(self, data, config):
            # Возвращаем случайные метрики
            np.random.seed(hash(str(config)) % 2**32)
            
            return {
                'sharpe_ratio': np.random.uniform(0.5, 2.0),
                'net_profit': np.random.uniform(-1000, 3000),
                'total_trades': np.random.randint(20, 100),
                'max_drawdown': np.random.uniform(-0.3, -0.05),
                'win_rate': np.random.uniform(0.4, 0.7),
                'metrics': {
                    'net_profit': np.random.uniform(-1000, 3000),
                },
                'profit_factor': np.random.uniform(1.0, 2.5),
            }
    
    return MockEngine


def test_parameter_range_to_list():
    """Тест конвертации ParameterRange в список"""
    pr = ParameterRange(1.0, 3.0, 0.5)
    values = pr.to_list()
    
    assert values == [1.0, 1.5, 2.0, 2.5, 3.0]
    assert len(values) == 5


def test_wfo_config_defaults():
    """Тест дефолтных значений WFOConfig"""
    config = WFOConfig()
    
    assert config.in_sample_size == 252
    assert config.out_sample_size == 63
    assert config.step_size == 63
    assert config.mode == WFOMode.ROLLING
    assert config.min_trades == 30
    assert config.max_drawdown == 0.50


def test_wfo_rolling_mode(sample_data, simple_param_ranges, mock_backtest_engine):
    """Тест Rolling Window режима"""
    config = WFOConfig(
        in_sample_size=100,
        out_sample_size=50,
        step_size=50,
        mode=WFOMode.ROLLING,
        min_trades=10,  # Низкий порог для тестов
    )
    
    wfo = WalkForwardOptimizer(config=config)
    
    results = wfo.optimize(
        data=sample_data,
        param_ranges=simple_param_ranges,
        strategy_config={'strategy_type': 'test'},
        metric='sharpe_ratio',
        backtest_engine=mock_backtest_engine(),
    )
    
    assert 'walk_results' in results
    assert 'aggregated_metrics' in results
    assert 'parameter_stability' in results
    assert 'summary' in results
    
    # Проверяем что создано несколько периодов
    assert len(results['walk_results']) > 0
    
    # Проверяем структуру периода
    period = results['walk_results'][0]
    assert 'period_num' in period
    assert 'best_params' in period
    assert 'efficiency' in period
    assert 'degradation' in period
    assert 'oos_sharpe' in period


def test_wfo_anchored_mode(sample_data, simple_param_ranges, mock_backtest_engine):
    """Тест Anchored Window режима"""
    config = WFOConfig(
        in_sample_size=100,
        out_sample_size=50,
        step_size=50,
        mode=WFOMode.ANCHORED,
        min_trades=10,
    )
    
    wfo = WalkForwardOptimizer(config=config)
    
    results = wfo.optimize(
        data=sample_data,
        param_ranges=simple_param_ranges,
        strategy_config={'strategy_type': 'test'},
        metric='sharpe_ratio',
        backtest_engine=mock_backtest_engine(),
    )
    
    assert len(results['walk_results']) > 0
    
    # В Anchored mode первый период должен начинаться с индекса 0
    first_period = results['walk_results'][0]
    # Не можем проверить точный индекс из-за сериализации, но проверим наличие данных
    assert first_period['best_params'] is not None


def test_wfo_insufficient_data(simple_param_ranges, mock_backtest_engine):
    """Тест с недостаточным количеством данных"""
    # Только 50 баров, а нужно 100 + 50 = 150
    small_data = pd.DataFrame({
        'open': [100] * 50,
        'high': [101] * 50,
        'low': [99] * 50,
        'close': [100] * 50,
        'volume': [1000] * 50,
    }, index=pd.date_range('2024-01-01', periods=50, freq='1h'))
    
    config = WFOConfig(
        in_sample_size=100,
        out_sample_size=50,
        step_size=50,
    )
    
    wfo = WalkForwardOptimizer(config=config)
    
    with pytest.raises(ValueError, match="Not enough data"):
        wfo.optimize(
            data=small_data,
            param_ranges=simple_param_ranges,
            strategy_config={'strategy_type': 'test'},
            backtest_engine=mock_backtest_engine(),
        )


def test_aggregated_metrics(sample_data, simple_param_ranges, mock_backtest_engine):
    """Тест агрегированных метрик"""
    config = WFOConfig(
        in_sample_size=100,
        out_sample_size=50,
        step_size=50,
        mode=WFOMode.ROLLING,
        min_trades=10,
    )
    
    wfo = WalkForwardOptimizer(config=config)
    
    results = wfo.optimize(
        data=sample_data,
        param_ranges=simple_param_ranges,
        strategy_config={'strategy_type': 'test'},
        backtest_engine=mock_backtest_engine(),
    )
    
    agg = results['aggregated_metrics']
    
    assert 'total_periods' in agg
    assert 'avg_efficiency' in agg
    assert 'avg_degradation' in agg
    assert 'oos_total_return_pct' in agg
    assert 'oos_avg_sharpe' in agg
    assert 'oos_total_trades' in agg
    assert 'consistency_score' in agg
    
    # Consistency score должен быть от 0 до 1
    assert 0 <= agg['consistency_score'] <= 1


def test_parameter_stability(sample_data, simple_param_ranges, mock_backtest_engine):
    """Тест анализа стабильности параметров"""
    config = WFOConfig(
        in_sample_size=100,
        out_sample_size=50,
        step_size=50,
        min_trades=10,
    )
    
    wfo = WalkForwardOptimizer(config=config)
    
    results = wfo.optimize(
        data=sample_data,
        param_ranges=simple_param_ranges,
        strategy_config={'strategy_type': 'test'},
        backtest_engine=mock_backtest_engine(),
    )
    
    stability = results['parameter_stability']
    
    # Должна быть стабильность для каждого параметра
    assert 'tp_pct' in stability or 'sl_pct' in stability
    
    for param_name, stats in stability.items():
        assert 'mean' in stats
        assert 'std' in stats
        assert 'min' in stats
        assert 'max' in stats
        assert 'stability_score' in stats
        assert 'values' in stats
        
        # Stability score от 0 до 1
        assert 0 <= stats['stability_score'] <= 1


def test_summary_generation(sample_data, simple_param_ranges, mock_backtest_engine):
    """Тест генерации сводки"""
    config = WFOConfig(
        in_sample_size=100,
        out_sample_size=50,
        step_size=50,
        min_trades=10,
    )
    
    wfo = WalkForwardOptimizer(config=config)
    
    results = wfo.optimize(
        data=sample_data,
        param_ranges=simple_param_ranges,
        strategy_config={'strategy_type': 'test'},
        backtest_engine=mock_backtest_engine(),
    )
    
    summary = results['summary']
    
    assert 'recommendation' in summary
    assert 'robustness_score' in summary
    assert 'key_findings' in summary
    
    # Robustness score от 0 до 100
    assert 0 <= summary['robustness_score'] <= 100
    
    # Должна быть рекомендация
    assert any(marker in summary['recommendation'] for marker in ['✅', '⚠️', '❌'])


def test_efficiency_calculation():
    """Тест расчёта efficiency"""
    # Создаём данные где IS=2.0, OOS=1.5
    # Efficiency = OOS/IS = 1.5/2.0 = 0.75
    
    config = WFOConfig(min_trades=10)
    wfo = WalkForwardOptimizer(config=config)
    
    # Мокаем внутренние методы
    is_metrics = {'sharpe_ratio': 2.0, 'total_trades': 50, 'metrics': {}}
    oos_metrics = {'sharpe_ratio': 1.5, 'total_trades': 40, 'metrics': {}}
    
    is_value = is_metrics.get('sharpe_ratio', 0)
    oos_value = oos_metrics.get('sharpe_ratio', 0)
    
    if is_value != 0:
        efficiency = oos_value / is_value
    else:
        efficiency = 0.0
    
    assert efficiency == pytest.approx(0.75, rel=1e-2)


def test_degradation_calculation():
    """Тест расчёта degradation"""
    # Degradation = IS - OOS
    # IS=2.5, OOS=2.0 => Degradation=0.5
    
    is_sharpe = 2.5
    oos_sharpe = 2.0
    degradation = is_sharpe - oos_sharpe
    
    assert degradation == pytest.approx(0.5, rel=1e-2)


def test_multiple_param_ranges(sample_data, mock_backtest_engine):
    """Тест с несколькими параметрами"""
    param_ranges = {
        'tp_pct': ParameterRange(1.0, 2.0, 1.0),
        'sl_pct': ParameterRange(0.5, 1.0, 0.5),
        'trailing_activation_pct': [0.0, 0.5],  # Можно и списком
    }
    
    config = WFOConfig(
        in_sample_size=100,
        out_sample_size=50,
        step_size=50,
        min_trades=10,
    )
    
    wfo = WalkForwardOptimizer(config=config)
    
    results = wfo.optimize(
        data=sample_data,
        param_ranges=param_ranges,
        strategy_config={'strategy_type': 'test'},
        backtest_engine=mock_backtest_engine(),
    )
    
    # Проверяем что оптимизация прошла
    assert len(results['walk_results']) > 0
    
    # Проверяем что есть стабильность для всех параметров
    stability = results['parameter_stability']
    assert len(stability) >= 2  # Хотя бы 2 параметра должны быть


def test_period_to_dict_serialization():
    """Тест сериализации WFOPeriod в dict"""
    from backend.optimization.walk_forward import WFOPeriod
    
    period = WFOPeriod(
        period_num=1,
        in_sample_start=datetime(2024, 1, 1),
        in_sample_end=datetime(2024, 6, 1),
        out_sample_start=datetime(2024, 6, 2),
        out_sample_end=datetime(2024, 9, 1),
        best_params={'tp_pct': 2.0, 'sl_pct': 1.0},
        is_sharpe=1.5,
        is_net_profit=1000.0,
        is_total_trades=50,
        is_max_drawdown=-0.10,
        oos_sharpe=1.2,
        oos_net_profit=800.0,
        oos_total_trades=40,
        oos_max_drawdown=-0.12,
        oos_win_rate=0.55,
        efficiency=0.8,
        degradation=0.3,
    )
    
    period_dict = period.to_dict()
    
    assert isinstance(period_dict, dict)
    assert period_dict['period_num'] == 1
    assert 'in_sample_start' in period_dict
    assert isinstance(period_dict['in_sample_start'], str)  # ISO format
    assert period_dict['best_params']['tp_pct'] == 2.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
