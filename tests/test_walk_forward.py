"""
Tests for Walk-Forward Optimization.
"""

import numpy as np
import pandas as pd
import pytest

from backend.core.walk_forward_optimizer import WalkForwardOptimizer


@pytest.fixture
def sample_data():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    n_bars = 500
    
    timestamps = pd.date_range('2024-01-01', periods=n_bars, freq='15min')
    
    # Generate random walk price data
    base_price = 50000.0
    price_changes = np.random.normal(0, 100, n_bars).cumsum()
    close_prices = base_price + price_changes
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': close_prices * (1 + np.random.uniform(-0.001, 0.001, n_bars)),
        'high': close_prices * (1 + np.random.uniform(0, 0.002, n_bars)),
        'low': close_prices * (1 - np.random.uniform(0, 0.002, n_bars)),
        'close': close_prices,
        'volume': np.random.uniform(100, 1000, n_bars),
    })
    
    return df


@pytest.fixture
def strategy_config():
    """Base strategy configuration."""
    return {
        'ema_fast': 12,
        'ema_slow': 26,
        'direction': 'both',
        'leverage': 1,
        'order_size_usd': None,
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
    """Test WalkForwardOptimizer initialization."""
    wfo = WalkForwardOptimizer(
        in_sample_size=100,
        out_sample_size=50,
        step_size=25,
    )
    
    assert wfo.in_sample_size == 100
    assert wfo.out_sample_size == 50
    assert wfo.step_size == 25
    assert wfo.initial_capital == 10000.0
    assert wfo.commission == 0.00075


def test_wfo_insufficient_data(sample_data, strategy_config, param_space):
    """Test WFO with insufficient data."""
    wfo = WalkForwardOptimizer(
        in_sample_size=400,
        out_sample_size=200,  # Total 600, but we have only 500
        step_size=50,
    )
    
    small_data = sample_data.iloc[:500]
    
    with pytest.raises(ValueError, match="Not enough data"):
        wfo.run(small_data, param_space, strategy_config)


def test_wfo_single_period(sample_data, strategy_config, param_space):
    """Test WFO with single period."""
    wfo = WalkForwardOptimizer(
        in_sample_size=200,
        out_sample_size=100,
        step_size=500,  # Large step = only 1 period
    )
    
    result = wfo.run(sample_data, param_space, strategy_config)
    
    # Should have exactly 1 period
    assert len(result['walk_results']) == 1
    
    period = result['walk_results'][0]
    assert period.period_num == 1
    assert 'take_profit_pct' in period.best_params
    assert 'stop_loss_pct' in period.best_params
    assert period.is_sharpe is not None
    assert period.oos_sharpe is not None
    assert period.efficiency is not None


def test_wfo_multiple_periods(sample_data, strategy_config, param_space):
    """Test WFO with multiple overlapping periods."""
    wfo = WalkForwardOptimizer(
        in_sample_size=150,
        out_sample_size=75,
        step_size=75,  # Should give multiple periods
    )
    
    result = wfo.run(sample_data, param_space, strategy_config)
    
    # Should have multiple periods
    assert len(result['walk_results']) >= 2
    
    # Check period numbering
    for i, period in enumerate(result['walk_results'], 1):
        assert period.period_num == i
    
    # Check aggregated metrics
    agg = result['aggregated_metrics']
    assert 'total_periods' in agg
    assert 'avg_efficiency' in agg
    assert 'oos_total_return' in agg
    assert 'oos_avg_sharpe' in agg
    assert agg['total_periods'] == len(result['walk_results'])


def test_wfo_parameter_stability(sample_data, strategy_config, param_space):
    """Test parameter stability analysis."""
    wfo = WalkForwardOptimizer(
        in_sample_size=150,
        out_sample_size=75,
        step_size=75,
    )
    
    result = wfo.run(sample_data, param_space, strategy_config)
    
    stability = result['parameter_stability']
    
    # Should have stats for each parameter
    assert 'take_profit_pct' in stability
    assert 'stop_loss_pct' in stability
    assert 'trailing_stop_pct' in stability
    
    # Check stats structure
    for param_name, stats in stability.items():
        assert 'mean' in stats
        assert 'std' in stats
        assert 'min' in stats
        assert 'max' in stats
        assert 'stability_score' in stats
        assert 'values' in stats
        
        # Stability score should be non-negative
        assert stats['stability_score'] >= 0
        
        # Values should match number of periods
        assert len(stats['values']) == len(result['walk_results'])


def test_wfo_with_different_metrics(sample_data, strategy_config, param_space):
    """Test WFO with different optimization metrics."""
    wfo = WalkForwardOptimizer(
        in_sample_size=150,
        out_sample_size=75,
        step_size=150,
    )
    
    # Test with Sharpe ratio
    result_sharpe = wfo.run(sample_data, param_space, strategy_config, metric='sharpe_ratio')
    assert len(result_sharpe['walk_results']) >= 1
    
    # Test with profit factor
    result_pf = wfo.run(sample_data, param_space, strategy_config, metric='profit_factor')
    assert len(result_pf['walk_results']) >= 1
    
    # Results might differ because different metrics are optimized
    # (This is expected behavior)


def test_wfo_efficiency_calculation(sample_data, strategy_config, param_space):
    """Test efficiency ratio calculation."""
    wfo = WalkForwardOptimizer(
        in_sample_size=150,
        out_sample_size=75,
        step_size=150,
    )
    
    result = wfo.run(sample_data, param_space, strategy_config)
    
    for period in result['walk_results']:
        # Efficiency should be OOS/IS ratio
        if period.is_sharpe != 0:
            expected_efficiency = period.oos_sharpe / period.is_sharpe
            assert abs(period.efficiency - expected_efficiency) < 0.001
        else:
            # If IS sharpe is 0, efficiency should be 0
            assert period.efficiency == 0.0


def test_wfo_aggregated_metrics(sample_data, strategy_config, param_space):
    """Test aggregated metrics calculation."""
    wfo = WalkForwardOptimizer(
        in_sample_size=150,
        out_sample_size=75,
        step_size=75,
    )
    
    result = wfo.run(sample_data, param_space, strategy_config)
    
    agg = result['aggregated_metrics']
    periods = result['walk_results']
    
    # Verify total periods
    assert agg['total_periods'] == len(periods)
    
    # Verify average efficiency
    expected_avg_eff = np.mean([p.efficiency for p in periods])
    assert abs(agg['avg_efficiency'] - expected_avg_eff) < 0.001
    
    # Verify average Sharpe
    expected_avg_sharpe = np.mean([p.oos_sharpe for p in periods])
    assert abs(agg['oos_avg_sharpe'] - expected_avg_sharpe) < 0.001
    
    # Verify total trades
    expected_total_trades = sum(p.oos_total_trades for p in periods)
    assert agg['oos_total_trades'] == expected_total_trades


def test_wfo_period_data_separation(sample_data, strategy_config, param_space):
    """Test that in-sample and out-of-sample periods don't overlap."""
    wfo = WalkForwardOptimizer(
        in_sample_size=150,
        out_sample_size=75,
        step_size=75,
    )
    
    result = wfo.run(sample_data, param_space, strategy_config)
    
    for period in result['walk_results']:
        # OOS should start after IS ends
        assert period.out_sample_start >= period.in_sample_end
        
        # OOS end should be after OOS start
        assert period.out_sample_end > period.out_sample_start


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
