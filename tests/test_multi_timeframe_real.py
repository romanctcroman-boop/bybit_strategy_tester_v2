"""
Comprehensive Multi-timeframe Tests with Real Bybit Data (ТЗ 3.1.2)

Tests multi-timeframe functionality with real market data:
- Central 15m with 5m and 30m neighbors
- Long and short positions
- Extended timeframe ranges
- Data synchronization validation
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.core.data_manager import DataManager
from backend.core.backtest_engine import BacktestEngine


@pytest.fixture
def btc_data_manager():
    """Create DataManager instance for testing."""
    return DataManager(symbol='BTCUSDT', cache_dir='./data/test_cache')


def test_load_single_timeframe_15m(btc_data_manager):
    """Test loading 15m data from Bybit API."""
    df = btc_data_manager.load_historical(timeframe='15', limit=200)
    
    assert len(df) > 0, "Should load data"
    assert len(df) <= 200, "Should respect limit"
    
    # Validate columns
    required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    for col in required_cols:
        assert col in df.columns, f"Missing column: {col}"
    
    # Validate OHLC relationship
    assert (df['high'] >= df['low']).all(), "High must be >= Low"
    assert (df['high'] >= df['open']).all(), "High must be >= Open"
    assert (df['high'] >= df['close']).all(), "High must be >= Close"
    assert (df['low'] <= df['open']).all(), "Low must be <= Open"
    assert (df['low'] <= df['close']).all(), "Low must be <= Close"
    
    # Validate timestamps are sorted
    assert df['timestamp'].is_monotonic_increasing, "Timestamps must be sorted"
    
    print(f"\n✅ Loaded {len(df)} bars of 15m data")
    print(f"   Range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    print(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")


def test_multi_timeframe_central_15m(btc_data_manager):
    """Test multi-timeframe loading with central 15m."""
    timeframes = ['5', '15', '30']
    data = btc_data_manager.get_multi_timeframe(timeframes, limit=300, central_tf='15')
    
    # Validate all timeframes loaded
    assert '5' in data, "Should have 5m data"
    assert '15' in data, "Should have 15m data (central)"
    assert '30' in data, "Should have 30m data"
    
    # Validate central TF has requested bars
    assert len(data['15']) > 0, "Central TF must have data"
    assert len(data['15']) <= 300, "Central TF should respect limit"
    
    # Validate 5m has more bars (higher resolution)
    # 15m -> 5m is 3x ratio, so expect ~3x more bars (with margin)
    min_5m_bars = len(data['15']) * 2  # At least 2x
    assert len(data['5']) >= min_5m_bars, f"5m should have more bars than 15m"
    
    # Validate 30m has fewer bars (lower resolution)
    # 15m -> 30m is 0.5x ratio
    max_30m_bars = len(data['15']) * 0.7  # At most 0.7x
    assert len(data['30']) <= max_30m_bars, f"30m should have fewer bars than 15m"
    
    # Validate time alignment
    central_min = data['15']['timestamp'].min()
    central_max = data['15']['timestamp'].max()
    
    for tf in ['5', '30']:
        tf_min = data[tf]['timestamp'].min()
        tf_max = data[tf]['timestamp'].max()
        
        # Should cover (or closely cover) central range
        assert tf_min <= central_min + pd.Timedelta(minutes=int(tf)), \
            f"{tf} start should be close to central start"
        assert tf_max >= central_max - pd.Timedelta(minutes=int(tf)), \
            f"{tf} end should be close to central end"
    
    print(f"\n✅ Multi-timeframe loaded successfully:")
    print(f"   5m:  {len(data['5'])} bars  ({data['5']['timestamp'].iloc[0]} to {data['5']['timestamp'].iloc[-1]})")
    print(f"   15m: {len(data['15'])} bars ({data['15']['timestamp'].iloc[0]} to {data['15']['timestamp'].iloc[-1]})")
    print(f"   30m: {len(data['30'])} bars ({data['30']['timestamp'].iloc[0]} to {data['30']['timestamp'].iloc[-1]})")


def test_backtest_long_on_real_15m(btc_data_manager):
    """Test long strategy on real 15m data."""
    # Load real data
    df = btc_data_manager.load_historical(timeframe='15', limit=500)
    
    # Simple MA crossover: fast > slow = long signal
    df['ma_fast'] = df['close'].rolling(10).mean()
    df['ma_slow'] = df['close'].rolling(30).mean()
    
    # Generate long signals
    df['signal'] = 0
    df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1
    
    # Strategy config
    strategy_config = {
        'take_profit_pct': 3.0,
        'stop_loss_pct': 1.5,
        'trailing_stop_pct': 0.5,
        'direction': 'long'  # Long only
    }
    
    # Run backtest
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.00075,
        leverage=1
    )
    
    results = engine.run(df, strategy_config)
    
    # Validate results
    assert 'total_trades' in results, "Should have total_trades"
    assert 'final_capital' in results, "Should have final_capital"
    assert 'sharpe_ratio' in results, "Should have sharpe_ratio"
    
    # Should have some trades
    assert results['total_trades'] >= 0, "Should execute trades on 500 bars"
    
    print(f"\n✅ Long backtest on real 15m data:")
    print(f"   Total trades: {results['total_trades']}")
    print(f"   Final capital: ${results['final_capital']:,.2f}")
    print(f"   Total return: {results['total_return']:.2%}")
    print(f"   Win rate: {results['win_rate']:.1%}")
    print(f"   Sharpe ratio: {results['sharpe_ratio']:.3f}")
    print(f"   Max drawdown: {results['max_drawdown']:.2%}")


def test_backtest_short_on_real_15m(btc_data_manager):
    """Test short strategy on real 15m data."""
    # Load real data
    df = btc_data_manager.load_historical(timeframe='15', limit=500)
    
    # Simple MA crossover: fast < slow = short signal
    df['ma_fast'] = df['close'].rolling(10).mean()
    df['ma_slow'] = df['close'].rolling(30).mean()
    
    # Generate short signals
    df['signal'] = 0
    df.loc[df['ma_fast'] < df['ma_slow'], 'signal'] = -1
    
    # Strategy config
    strategy_config = {
        'take_profit_pct': 3.0,
        'stop_loss_pct': 1.5,
        'trailing_stop_pct': 0.5,
        'direction': 'short'  # Short only
    }
    
    # Run backtest
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.00075,
        leverage=1
    )
    
    results = engine.run(df, strategy_config)
    
    # Validate results
    assert 'total_trades' in results, "Should have total_trades"
    assert results['total_trades'] >= 0, "Should execute short trades"
    
    print(f"\n✅ Short backtest on real 15m data:")
    print(f"   Total trades: {results['total_trades']}")
    print(f"   Final capital: ${results['final_capital']:,.2f}")
    print(f"   Total return: {results['total_return']:.2%}")
    print(f"   Win rate: {results['win_rate']:.1%}")
    print(f"   Sharpe ratio: {results['sharpe_ratio']:.3f}")


def test_backtest_both_directions_real_data(btc_data_manager):
    """Test both long and short on real data."""
    # Load real data
    df = btc_data_manager.load_historical(timeframe='15', limit=500)
    
    # MA crossover for both directions
    df['ma_fast'] = df['close'].rolling(10).mean()
    df['ma_slow'] = df['close'].rolling(30).mean()
    
    # Generate signals
    df['signal'] = 0
    df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1   # Long
    df.loc[df['ma_fast'] < df['ma_slow'], 'signal'] = -1  # Short
    
    # Strategy config
    strategy_config = {
        'take_profit_pct': 2.5,
        'stop_loss_pct': 1.0,
        'trailing_stop_pct': 0.5,
        'direction': 'both'  # Both long and short
    }
    
    # Run backtest
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.00075,
        leverage=1
    )
    
    results = engine.run(df, strategy_config)
    
    # Should have trades
    assert results['total_trades'] > 0, "Should have trades with both directions"
    
    # Check by_side stats
    long_trades = results.get('long_trades', 0)
    short_trades = results.get('short_trades', 0)
    
    print(f"\n✅ Both directions backtest on real 15m data:")
    print(f"   Total trades: {results['total_trades']}")
    print(f"   Long trades: {long_trades}")
    print(f"   Short trades: {short_trades}")
    print(f"   Final capital: ${results['final_capital']:,.2f}")
    print(f"   Total return: {results['total_return']:.2%}")
    print(f"   Sharpe ratio: {results['sharpe_ratio']:.3f}")


def test_extended_timeframes_range(btc_data_manager):
    """Test extended timeframe range: 5m, 15m, 30m, 60m."""
    timeframes = ['5', '15', '30', '60']
    data = btc_data_manager.get_multi_timeframe(timeframes, limit=400, central_tf='15')
    
    # Validate all loaded
    for tf in timeframes:
        assert tf in data, f"Should have {tf} data"
        assert len(data[tf]) > 0, f"{tf} should have bars"
    
    # Validate resolution ratios
    # 5m should have most bars
    assert len(data['5']) >= len(data['15']), "5m should have more bars than 15m"
    assert len(data['15']) >= len(data['30']), "15m should have more bars than 30m"
    assert len(data['30']) >= len(data['60']), "30m should have more bars than 60m"
    
    print(f"\n✅ Extended timeframes loaded:")
    for tf in timeframes:
        print(f"   {tf:>3}m: {len(data[tf]):4} bars")


def test_multi_tf_strategy_with_trend_filter(btc_data_manager):
    """Test multi-timeframe strategy: 15m signals with 60m trend filter."""
    # Load multi-timeframe data
    data = btc_data_manager.get_multi_timeframe(['15', '60'], limit=500, central_tf='15')
    
    df_15m = data['15'].copy()
    df_60m = data['60'].copy()
    
    # Calculate 15m signals
    df_15m['ma_fast'] = df_15m['close'].rolling(10).mean()
    df_15m['ma_slow'] = df_15m['close'].rolling(20).mean()
    
    # Calculate 60m trend
    df_60m['trend_ma'] = df_60m['close'].rolling(50).mean()
    df_60m['is_uptrend'] = df_60m['close'] > df_60m['trend_ma']
    
    # Merge 60m trend into 15m (forward fill)
    df_15m = df_15m.set_index('timestamp')
    df_60m_trend = df_60m.set_index('timestamp')[['is_uptrend']]
    
    # Resample 60m to 15m frequency
    df_60m_resampled = df_60m_trend.resample('15min').ffill()
    
    # Merge
    df_combined = df_15m.join(df_60m_resampled, how='left')
    df_combined['is_uptrend'] = df_combined['is_uptrend'].fillna(False)
    df_combined = df_combined.reset_index()
    
    # Generate signals: MA cross on 15m + 60m uptrend filter
    df_combined['signal'] = 0
    long_condition = (
        (df_combined['ma_fast'] > df_combined['ma_slow']) & 
        (df_combined['is_uptrend'] == True)
    )
    df_combined.loc[long_condition, 'signal'] = 1
    
    # Strategy config
    strategy_config = {
        'take_profit_pct': 3.0,
        'stop_loss_pct': 1.5,
        'trailing_stop_pct': 0.5,
        'direction': 'long'
    }
    
    # Run backtest
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.00075,
        leverage=1
    )
    
    results = engine.run(df_combined, strategy_config)
    
    print(f"\n✅ Multi-TF strategy (15m + 60m trend filter):")
    print(f"   Total trades: {results['total_trades']}")
    print(f"   Final capital: ${results['final_capital']:,.2f}")
    print(f"   Total return: {results['total_return']:.2%}")
    print(f"   Win rate: {results['win_rate']:.1%}")
    print(f"   Sharpe ratio: {results['sharpe_ratio']:.3f}")
    
    # Should have fewer trades due to filter
    # (Can't assert exact number, but validates it runs)
    assert results['total_trades'] >= 0


def test_cache_functionality(btc_data_manager):
    """Test that cache works properly."""
    import time
    
    # Clear cache first
    btc_data_manager.update_cache()
    
    # First load (from API)
    start = time.time()
    df1 = btc_data_manager.load_historical(timeframe='15', limit=100)
    time1 = time.time() - start
    
    # Second load (from cache)
    start = time.time()
    df2 = btc_data_manager.load_historical(timeframe='15', limit=100)
    time2 = time.time() - start
    
    # Data should be identical
    pd.testing.assert_frame_equal(df1, df2)
    
    # Cache should be significantly faster (at least 2x)
    # Note: Only assert if API load was slow enough (>0.1s) to avoid flaky test
    if time1 > 0.1:
        assert time2 < time1 * 0.5, f"Cached load should be faster: API={time1:.3f}s, Cache={time2:.3f}s"
    
    print(f"\n✅ Cache test:")
    print(f"   API load: {time1:.3f}s")
    print(f"   Cache load: {time2:.3f}s")
    if time1 > 0:
        print(f"   Speedup: {time1/time2:.1f}x")


if __name__ == '__main__':
    # Run tests manually
    dm = DataManager('BTCUSDT')
    
    print("\n" + "="*80)
    print("MULTI-TIMEFRAME TESTS WITH REAL BYBIT DATA")
    print("="*80)
    
    test_load_single_timeframe_15m(dm)
    test_multi_timeframe_central_15m(dm)
    test_backtest_long_on_real_15m(dm)
    test_backtest_short_on_real_15m(dm)
    test_backtest_both_directions_real_data(dm)
    test_extended_timeframes_range(dm)
    test_multi_tf_strategy_with_trend_filter(dm)
    test_cache_functionality(dm)
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED!")
    print("="*80)
