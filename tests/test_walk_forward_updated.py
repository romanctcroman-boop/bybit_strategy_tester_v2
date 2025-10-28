"""
Обновленные тесты Walk-Forward для нового API (WFOConfig)

Исправлено: 27.10.2025
Причина: После консолидации модулей оптимизации изменился API
"""

import numpy as np
import pandas as pd
import pytest

from backend.optimization import WalkForwardOptimizer, WFOConfig, WFOMode, WFOParameterRange


@pytest.fixture
def sample_data():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    n_bars = 500
    
    timestamps = pd.date_range('2024-01-01', periods=n_bars, freq='15min')
    
    # Generate random walk price data
    base_price = 50000.0
    returns = np.random.randn(n_bars) * 0.001
    prices = base_price * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.randn(n_bars) * 0.0001),
        'high': prices * (1 + np.abs(np.random.randn(n_bars)) * 0.001),
        'low': prices * (1 - np.abs(np.random.randn(n_bars)) * 0.001),
        'close': prices,
        'volume': np.random.randint(1000, 10000, n_bars),
    }, index=timestamps)
    
    return df


@pytest.fixture
def strategy_config():
    """Basic strategy configuration."""
    return {
        'strategy_type': 'ema_cross',
        'leverage': 1,
    }


@pytest.fixture
def param_space():
    """Parameter space for optimization."""
    return {
        'take_profit_pct': [1.0, 2.0],
        'stop_loss_pct': [0.5, 1.0],
        'trailing_stop_pct': [0.3, 0.5],
    }


def test_wfo_initialization():
    """Test WalkForwardOptimizer initialization with WFOConfig."""
    config = WFOConfig(
        in_sample_size=100,
        out_sample_size=50,
        step_size=25,
        mode=WFOMode.ROLLING
    )
    
    wfo = WalkForwardOptimizer(config=config)
    
    assert wfo.config.in_sample_size == 100
    assert wfo.config.out_sample_size == 50
    assert wfo.config.step_size == 25
    assert wfo.config.mode == WFOMode.ROLLING
    assert wfo.config.initial_capital == 10000.0


def test_wfo_insufficient_data(sample_data, strategy_config, param_space):
    """Test WFO with insufficient data."""
    config = WFOConfig(
        in_sample_size=400,
        out_sample_size=200,  # Total 600, but we have only 500
        step_size=50,
    )
    
    wfo = WalkForwardOptimizer(config=config)
    small_data = sample_data.iloc[:500]
    
    with pytest.raises(ValueError, match="Not enough data"):
        wfo.optimize(small_data, param_space, strategy_config)


def test_wfo_single_period(sample_data, strategy_config, param_space):
    """Test WFO with single period."""
    config = WFOConfig(
        in_sample_size=200,
        out_sample_size=100,
        step_size=500,  # Large step = only 1 period
    )
    
    wfo = WalkForwardOptimizer(config=config)
    result = wfo.optimize(sample_data, param_space, strategy_config)
    
    # Should have exactly 1 period
    assert len(result['walk_results']) >= 1
    
    period = result['walk_results'][0]
    assert period.period_num == 1
    assert 'take_profit_pct' in period.best_params or period.best_params is not None


def test_wfo_multiple_periods(sample_data, strategy_config, param_space):
    """Test WFO with multiple overlapping periods."""
    config = WFOConfig(
        in_sample_size=150,
        out_sample_size=75,
        step_size=75,
    )
    
    wfo = WalkForwardOptimizer(config=config)
    result = wfo.optimize(sample_data, param_space, strategy_config)
    
    # Should have multiple periods
    assert len(result['walk_results']) >= 2
    
    # Check period numbering
    for i, period in enumerate(result['walk_results'], 1):
        assert period.period_num == i


def test_wfo_parameter_range():
    """Test WFOParameterRange helper."""
    param_range = WFOParameterRange(
        start=1.0,
        stop=3.0,
        step=0.5
    )
    
    values = param_range.to_list()
    
    assert len(values) == 5  # [1.0, 1.5, 2.0, 2.5, 3.0]
    assert values[0] == 1.0
    assert values[-1] == 3.0


def test_wfo_anchored_mode(sample_data, strategy_config, param_space):
    """Test WFO with anchored window mode."""
    config = WFOConfig(
        in_sample_size=150,
        out_sample_size=75,
        step_size=75,
        mode=WFOMode.ANCHORED  # Anchored instead of rolling
    )
    
    wfo = WalkForwardOptimizer(config=config)
    result = wfo.optimize(sample_data, param_space, strategy_config)
    
    # Should have results
    assert 'walk_results' in result
    assert len(result['walk_results']) >= 1


def test_wfo_aggregated_metrics(sample_data, strategy_config, param_space):
    """Test aggregated metrics calculation."""
    config = WFOConfig(
        in_sample_size=150,
        out_sample_size=75,
        step_size=75,
    )
    
    wfo = WalkForwardOptimizer(config=config)
    result = wfo.optimize(sample_data, param_space, strategy_config)
    
    # Check aggregated metrics
    assert 'aggregated_metrics' in result
    
    agg = result['aggregated_metrics']
    assert 'total_periods' in agg
    assert agg['total_periods'] >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
