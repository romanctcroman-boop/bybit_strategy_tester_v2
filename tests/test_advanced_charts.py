"""
Tests for Advanced Chart Visualizations (ТЗ 3.7.2)

Tests all chart creation functions:
- Equity curve with drawdown overlay
- PnL distribution histograms
- Parameter heatmaps for optimization results
"""

import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

from backend.visualization.advanced_charts import (
    create_equity_curve,
    create_drawdown_overlay,
    create_pnl_distribution,
    create_parameter_heatmap,
)


@pytest.fixture
def sample_equity():
    """Create sample equity curve with realistic pattern."""
    dates = pd.date_range('2025-01-01', periods=100, freq='1h')
    
    # Create realistic equity curve: uptrend with volatility and drawdowns
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, size=100)  # Mean positive return
    returns[20:25] = -0.03  # First drawdown
    returns[60:68] = -0.02  # Second drawdown
    
    equity = 10000 * (1 + returns).cumprod()
    
    return pd.Series(equity, index=dates, name='equity')


@pytest.fixture
def sample_trades():
    """Create sample trades with PnL."""
    np.random.seed(42)
    
    # Mix of winning and losing trades
    pnl_values = np.concatenate([
        np.random.normal(50, 30, size=30),   # Winning trades
        np.random.normal(-30, 20, size=20),  # Losing trades
    ])
    
    return pd.DataFrame({
        'pnl': pnl_values,
        'entry_time': pd.date_range('2025-01-01', periods=50, freq='1h'),
        'side': ['long'] * 25 + ['short'] * 25,
    })


@pytest.fixture
def sample_optimization_results():
    """Create sample optimization results grid."""
    ma_fast_values = [5, 10, 15, 20]
    ma_slow_values = [20, 30, 40, 50]
    
    results = []
    np.random.seed(42)
    
    for ma_fast in ma_fast_values:
        for ma_slow in ma_slow_values:
            if ma_fast < ma_slow:  # Only valid combinations
                # Simulate better performance for certain parameter ranges
                base_return = 0.05 + (ma_fast / 100) - (ma_slow / 1000)
                noise = np.random.normal(0, 0.02)
                
                results.append({
                    'ma_fast': ma_fast,
                    'ma_slow': ma_slow,
                    'total_return': base_return + noise,
                    'sharpe_ratio': (base_return + noise) * 10,
                    'max_drawdown': abs(np.random.normal(0.15, 0.05)),
                })
    
    return pd.DataFrame(results)


# ============================================================================
# Equity Curve Tests
# ============================================================================

def test_create_equity_curve_basic(sample_equity):
    """Test basic equity curve creation."""
    fig = create_equity_curve(sample_equity, show_drawdown=False)
    
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1  # Only equity trace
    assert fig.data[0].name == 'Equity'
    assert len(fig.data[0].x) == 100
    assert len(fig.data[0].y) == 100


def test_create_equity_curve_with_drawdown(sample_equity):
    """Test equity curve with drawdown subplot."""
    fig = create_equity_curve(sample_equity, show_drawdown=True)
    
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2  # Equity + Drawdown
    assert fig.data[0].name == 'Equity'
    assert fig.data[1].name == 'Drawdown'
    
    # Check drawdown values are negative or zero
    drawdown_values = fig.data[1].y
    assert all(val <= 0 for val in drawdown_values)


def test_create_equity_curve_from_dataframe(sample_equity):
    """Test equity curve creation from DataFrame."""
    df = pd.DataFrame({'equity': sample_equity})
    
    fig = create_equity_curve(df, show_drawdown=True)
    
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_create_equity_curve_custom_height(sample_equity):
    """Test custom height parameter."""
    custom_height = 800
    fig = create_equity_curve(sample_equity, height=custom_height)
    
    assert fig.layout.height == custom_height


def test_create_equity_curve_custom_title(sample_equity):
    """Test custom title."""
    custom_title = "My Custom Equity Curve"
    fig = create_equity_curve(sample_equity, title=custom_title, show_drawdown=False)
    
    assert custom_title in fig.layout.title.text


def test_create_equity_curve_invalid_dataframe():
    """Test error handling for invalid DataFrame."""
    df = pd.DataFrame({'wrong_column': [1, 2, 3]})
    
    with pytest.raises(ValueError, match="must have 'equity' column"):
        create_equity_curve(df)


# ============================================================================
# Drawdown Overlay Tests
# ============================================================================

def test_create_drawdown_overlay_basic(sample_equity):
    """Test drawdown overlay creation."""
    fig = create_drawdown_overlay(sample_equity)
    
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2  # Equity + Drawdown on same chart
    assert fig.data[0].name == 'Equity'
    assert fig.data[1].name == 'Drawdown'


def test_create_drawdown_overlay_dual_yaxis(sample_equity):
    """Test dual y-axis configuration."""
    fig = create_drawdown_overlay(sample_equity)
    
    # Check that layout has secondary y-axis
    assert 'yaxis2' in fig.layout


def test_create_drawdown_overlay_from_dataframe(sample_equity):
    """Test drawdown overlay from DataFrame."""
    df = pd.DataFrame({'equity': sample_equity})
    
    fig = create_drawdown_overlay(df)
    
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_create_drawdown_overlay_custom_title(sample_equity):
    """Test custom title for drawdown overlay."""
    custom_title = "Advanced Drawdown Analysis"
    fig = create_drawdown_overlay(sample_equity, title=custom_title)
    
    assert custom_title in fig.layout.title.text


# ============================================================================
# PnL Distribution Tests
# ============================================================================

def test_create_pnl_distribution_from_dataframe(sample_trades):
    """Test PnL distribution from DataFrame."""
    fig = create_pnl_distribution(sample_trades, pnl_column='pnl')
    
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1  # Histogram
    assert fig.data[0].type == 'histogram'
    assert len(fig.data[0].x) == 50  # 50 trades


def test_create_pnl_distribution_from_list():
    """Test PnL distribution from list."""
    pnl_list = [100, -50, 75, 200, -25, 150, -80, 120]
    
    fig = create_pnl_distribution(pnl_list)
    
    assert isinstance(fig, go.Figure)
    assert len(fig.data[0].x) == 8


def test_create_pnl_distribution_statistics(sample_trades):
    """Test that statistics are correctly displayed."""
    fig = create_pnl_distribution(sample_trades)
    
    # Calculate expected statistics
    pnl_values = sample_trades['pnl'].values
    expected_mean = np.mean(pnl_values)
    
    # Check vertical lines for mean
    vlines = [shape for shape in fig.layout.shapes if shape.type == 'line']
    assert len(vlines) >= 2  # At least mean and median lines
    
    # Check annotations
    annotations = fig.layout.annotations
    assert len(annotations) > 0


def test_create_pnl_distribution_custom_bins(sample_trades):
    """Test custom number of bins."""
    custom_bins = 50
    fig = create_pnl_distribution(sample_trades, bins=custom_bins)
    
    assert isinstance(fig, go.Figure)
    # nbinsx is set, actual bins may vary slightly


def test_create_pnl_distribution_invalid_column():
    """Test error handling for invalid column."""
    df = pd.DataFrame({'wrong_column': [1, 2, 3]})
    
    with pytest.raises(ValueError, match="must have 'pnl' column"):
        create_pnl_distribution(df, pnl_column='pnl')


def test_create_pnl_distribution_empty_data():
    """Test error handling for empty data."""
    with pytest.raises(ValueError, match="No PnL values"):
        create_pnl_distribution([])


# ============================================================================
# Parameter Heatmap Tests
# ============================================================================

def test_create_parameter_heatmap_basic(sample_optimization_results):
    """Test basic parameter heatmap creation."""
    fig = create_parameter_heatmap(
        sample_optimization_results,
        param_x='ma_fast',
        param_y='ma_slow',
        metric='total_return',
    )
    
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2  # Heatmap + best point marker
    assert fig.data[0].type == 'heatmap'
    assert fig.data[1].type == 'scatter'  # Best point marker


def test_create_parameter_heatmap_custom_metric(sample_optimization_results):
    """Test heatmap with different metric."""
    fig = create_parameter_heatmap(
        sample_optimization_results,
        param_x='ma_fast',
        param_y='ma_slow',
        metric='sharpe_ratio',
    )
    
    assert isinstance(fig, go.Figure)
    # Check that heatmap trace has colorbar with correct title
    heatmap_trace = fig.data[0]
    assert heatmap_trace.type == 'heatmap'
    assert 'sharpe' in heatmap_trace.colorbar.title.text.lower()


def test_create_parameter_heatmap_custom_title(sample_optimization_results):
    """Test custom title."""
    custom_title = "MA Optimization Results"
    fig = create_parameter_heatmap(
        sample_optimization_results,
        param_x='ma_fast',
        param_y='ma_slow',
        metric='total_return',
        title=custom_title,
    )
    
    assert custom_title in fig.layout.title.text


def test_create_parameter_heatmap_auto_title(sample_optimization_results):
    """Test auto-generated title."""
    fig = create_parameter_heatmap(
        sample_optimization_results,
        param_x='ma_fast',
        param_y='ma_slow',
        metric='total_return',
    )
    
    assert 'ma_fast' in fig.layout.title.text.lower()
    assert 'ma_slow' in fig.layout.title.text.lower()


def test_create_parameter_heatmap_best_point_marker(sample_optimization_results):
    """Test that best point is correctly marked."""
    fig = create_parameter_heatmap(
        sample_optimization_results,
        param_x='ma_fast',
        param_y='ma_slow',
        metric='total_return',
    )
    
    # Second trace should be the best point marker
    best_marker = fig.data[1]
    assert best_marker.mode == 'markers'
    assert best_marker.marker.symbol == 'star'
    assert len(best_marker.x) == 1  # Single point
    assert len(best_marker.y) == 1


def test_create_parameter_heatmap_custom_dimensions(sample_optimization_results):
    """Test custom height and width."""
    custom_height = 700
    custom_width = 900
    
    fig = create_parameter_heatmap(
        sample_optimization_results,
        param_x='ma_fast',
        param_y='ma_slow',
        metric='total_return',
        height=custom_height,
        width=custom_width,
    )
    
    assert fig.layout.height == custom_height
    assert fig.layout.width == custom_width


def test_create_parameter_heatmap_missing_columns():
    """Test error handling for missing columns."""
    df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
    
    with pytest.raises(ValueError, match="Missing columns"):
        create_parameter_heatmap(df, 'param_x', 'param_y', 'metric')


def test_create_parameter_heatmap_with_duplicates():
    """Test heatmap handles duplicate parameter combinations."""
    df = pd.DataFrame({
        'ma_fast': [5, 5, 10, 10],
        'ma_slow': [20, 20, 30, 30],
        'total_return': [0.05, 0.06, 0.08, 0.07],  # Duplicates
    })
    
    fig = create_parameter_heatmap(
        df,
        param_x='ma_fast',
        param_y='ma_slow',
        metric='total_return',
    )
    
    assert isinstance(fig, go.Figure)
    # Should use mean aggregation for duplicates


# ============================================================================
# Integration Tests
# ============================================================================

def test_all_charts_return_plotly_figure(sample_equity, sample_trades, sample_optimization_results):
    """Test that all chart functions return Plotly Figure objects."""
    charts = [
        create_equity_curve(sample_equity),
        create_drawdown_overlay(sample_equity),
        create_pnl_distribution(sample_trades),
        create_parameter_heatmap(sample_optimization_results, 'ma_fast', 'ma_slow', 'total_return'),
    ]
    
    for chart in charts:
        assert isinstance(chart, go.Figure)
        assert hasattr(chart, 'data')
        assert hasattr(chart, 'layout')


def test_charts_are_serializable(sample_equity, sample_trades, sample_optimization_results):
    """Test that charts can be serialized to JSON (for web frontend)."""
    charts = [
        create_equity_curve(sample_equity),
        create_pnl_distribution(sample_trades),
        create_parameter_heatmap(sample_optimization_results, 'ma_fast', 'ma_slow', 'total_return'),
    ]
    
    for chart in charts:
        json_str = chart.to_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0
        assert '{' in json_str  # Valid JSON


def test_charts_have_responsive_layout(sample_equity):
    """Test that charts have responsive layout configuration."""
    fig = create_equity_curve(sample_equity)
    
    # Check template is set
    assert 'template' in fig.layout
    
    # Check margins are defined
    assert hasattr(fig.layout, 'margin')
    assert fig.layout.margin.l > 0
    assert fig.layout.margin.r > 0
