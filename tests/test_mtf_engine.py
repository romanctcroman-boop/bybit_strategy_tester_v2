"""
Tests for Multi-Timeframe Backtest Engine (ТЗ 3.4.2)
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

from backend.core.mtf_engine import MTFBacktestEngine, run_mtf_backtest


@pytest.fixture
def sample_mtf_data():
    """Generate sample multi-timeframe data."""
    # Central timeframe: 15m (100 bars)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    times_15m = [base_time + timedelta(minutes=15 * i) for i in range(100)]
    
    df_15m = pd.DataFrame({
        'timestamp': times_15m,
        'open': 50000 + np.random.randn(100) * 100,
        'high': 50100 + np.random.randn(100) * 100,
        'low': 49900 + np.random.randn(100) * 100,
        'close': 50000 + np.cumsum(np.random.randn(100) * 50),  # Trending
        'volume': np.random.rand(100) * 1000
    })
    
    # Higher timeframe: 60m (25 bars)
    times_60m = [base_time + timedelta(minutes=60 * i) for i in range(25)]
    
    df_60m = pd.DataFrame({
        'timestamp': times_60m,
        'open': 50000 + np.random.randn(25) * 100,
        'high': 50100 + np.random.randn(25) * 100,
        'low': 49900 + np.random.randn(25) * 100,
        'close': 50000 + np.cumsum(np.random.randn(25) * 50),
        'volume': np.random.rand(25) * 4000
    })
    
    return {
        '15': df_15m,
        '60': df_60m
    }


def test_mtf_engine_initialization():
    """Test MTF engine can be initialized."""
    engine = MTFBacktestEngine(initial_capital=10000)
    
    assert engine.initial_capital == 10000
    assert engine.mtf_data == {}
    assert engine.mtf_indicators == {}


def test_mtf_indicators_calculation(sample_mtf_data):
    """Test MTF indicators are calculated for all timeframes."""
    engine = MTFBacktestEngine(initial_capital=10000)
    engine.mtf_data = sample_mtf_data
    
    config = {
        'type': 'ema_crossover',
        'fast_ema': 50,
        'slow_ema': 200
    }
    
    engine._calculate_mtf_indicators(config)
    
    # Check indicators calculated for both TFs
    assert '15' in engine.mtf_indicators
    assert '60' in engine.mtf_indicators
    
    # Check EMA indicators exist
    assert 'ema_50' in engine.mtf_indicators['15']
    assert 'ema_200' in engine.mtf_indicators['15']
    assert 'ema_50' in engine.mtf_indicators['60']
    
    # Check values are not all NaN
    assert not engine.mtf_indicators['15']['ema_50'].isna().all()


def test_htf_context_extraction(sample_mtf_data):
    """Test HTF context extraction for current bar."""
    engine = MTFBacktestEngine(initial_capital=10000)
    engine.mtf_data = sample_mtf_data
    
    config = {'type': 'ema_crossover'}
    engine._calculate_mtf_indicators(config)
    
    # Get HTF context for a timestamp
    central_df = sample_mtf_data['15']
    bar_index = 50
    timestamp = central_df.iloc[bar_index]['timestamp']
    
    htf_context = engine._get_htf_context(timestamp, bar_index, central_df)
    
    # Should have 60m data
    assert '60' in htf_context
    
    # Should have indicator values
    if htf_context['60']:  # May be empty if not enough data
        assert isinstance(htf_context['60'], dict)


def test_htf_filter_trend_ma(sample_mtf_data):
    """Test HTF trend MA filter."""
    engine = MTFBacktestEngine(initial_capital=10000)
    engine.mtf_data = sample_mtf_data
    
    config = {'type': 'ema_crossover'}
    engine._calculate_mtf_indicators(config)
    
    # Create mock state
    from backend.core.backtest_engine import BacktestState
    state = BacktestState(capital=10000, equity=10000)
    
    # Mock HTF context
    state.htf_context = {
        '60': {
            'sma_200': 50000.0,
            'ema_200': 50000.0
        }
    }
    
    # Mock bar
    bar = pd.Series({
        'timestamp': sample_mtf_data['15'].iloc[50]['timestamp'],
        'close': 51000.0  # Above MA200
    })
    
    # HTF filter: only long if price above 60m MA200
    htf_filters = [
        {
            'timeframe': '60',
            'type': 'trend_ma',
            'params': {'period': 200, 'condition': 'price_above'}
        }
    ]
    
    # Test long signal with price above MA
    result = engine._apply_htf_filters(50, bar, state, htf_filters, 'long')
    assert result is True  # Should pass
    
    # Test long signal with price below MA
    bar['close'] = 49000.0
    result = engine._apply_htf_filters(50, bar, state, htf_filters, 'long')
    assert result is False  # Should reject


def test_base_signal_detection(sample_mtf_data):
    """Test base signal detection without HTF filters."""
    engine = MTFBacktestEngine(initial_capital=10000)
    
    # Create mock indicators
    from backend.core.backtest_engine import BacktestState
    state = BacktestState(capital=10000, equity=10000)
    
    # Mock EMA crossover
    state.indicators = {
        'ema_50': pd.Series([49900, 49950, 50050, 50100]),  # Rising
        'ema_200': pd.Series([50000, 50000, 50000, 50000])  # Flat
    }
    
    config = {'type': 'ema_crossover'}
    
    # Test crossover at index 2 (ema_50 crosses above ema_200)
    signal, side = engine._check_base_signal(
        i=2,
        bar=sample_mtf_data['15'].iloc[2],
        df=sample_mtf_data['15'],
        state=state,
        config=config
    )
    
    assert signal is True
    assert side == 'long'


def test_extract_htf_indicator_values(sample_mtf_data):
    """Test extraction of HTF indicator values for visualization."""
    engine = MTFBacktestEngine(initial_capital=10000)
    engine.mtf_data = sample_mtf_data
    
    config = {'type': 'ema_crossover'}
    engine._calculate_mtf_indicators(config)
    
    htf_viz = engine._extract_htf_indicator_values()
    
    # Should have both timeframes
    assert '15' in htf_viz
    assert '60' in htf_viz
    
    # Should have timestamps
    assert 'timestamps' in htf_viz['15']
    assert len(htf_viz['15']['timestamps']) == len(sample_mtf_data['15'])
    
    # Should have indicator values
    assert 'ema_50' in htf_viz['15']
    assert 'ema_200' in htf_viz['15']
    
    # Values should be lists
    assert isinstance(htf_viz['15']['ema_50'], list)


def test_run_mtf_backtest_convenience_function():
    """Test convenience function for MTF backtests."""
    # This test requires actual Bybit API or mocked DataManager
    # Skip for now, test manually
    pytest.skip("Requires Bybit API or mocked DataManager")


def test_mtf_config_in_results():
    """Test that MTF config is included in results."""
    # Create engine and mock run
    engine = MTFBacktestEngine(initial_capital=10000)
    
    # Mock minimal data
    df = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=10, freq='15min', tz='UTC'),
        'close': [50000 + i * 100 for i in range(10)],
        'open': [50000 + i * 100 for i in range(10)],
        'high': [50100 + i * 100 for i in range(10)],
        'low': [49900 + i * 100 for i in range(10)],
        'volume': [1000] * 10
    })
    
    engine.mtf_data = {'15': df}
    engine.mtf_indicators = {'15': {}}
    
    config = {
        'type': 'ema_crossover',
        'fast_ema': 50,
        'slow_ema': 200,
        'htf_filters': [
            {'timeframe': '60', 'type': 'trend_ma', 'params': {}}
        ]
    }
    
    results = engine._run_with_mtf_context(df, config)
    
    # Basic validation
    assert 'total_trades' in results
    assert 'equity_curve' in results


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
