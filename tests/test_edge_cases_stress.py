"""
🧪 EDGE CASE & STRESS TESTS - MTF Backtest Engine

Comprehensive testing for extreme scenarios, edge cases, and stress conditions.

Test Categories:
1. Edge Cases: Empty data, single candle, extreme prices
2. Stress Tests: Large datasets, high-frequency data
3. Market Conditions: Flash crashes, low liquidity, gaps
4. Data Quality: Missing values, outliers, corrupted data
5. Performance: Memory limits, CPU usage, response times
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backend.core.mtf_engine import MTFBacktestEngine


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Test extreme and boundary conditions"""
    
    def test_empty_dataframe(self):
        """Test with completely empty dataset"""
        empty_data = pd.DataFrame()
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(empty_data, config)
        
        with pytest.raises(ValueError, match="Empty dataset"):
            engine.run()
    
    def test_single_candle(self):
        """Test with only one candle"""
        single_candle = pd.DataFrame({
            'timestamp': [datetime.now()],
            'open': [50000],
            'high': [50100],
            'low': [49900],
            'close': [50050],
            'volume': [100]
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(single_candle, config)
        
        # Should complete without trades (insufficient data for indicators)
        results = engine.run()
        assert results['total_trades'] == 0
        assert results['total_return'] == 0.0
    
    def test_insufficient_data_for_indicators(self):
        """Test with fewer candles than indicator period"""
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='1H'),
            'open': np.random.uniform(45000, 55000, 10),
            'high': np.random.uniform(46000, 56000, 10),
            'low': np.random.uniform(44000, 54000, 10),
            'close': np.random.uniform(45000, 55000, 10),
            'volume': np.random.uniform(100, 1000, 10)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}  # Requires 20 periods
        }
        
        engine = MTFBacktestEngine(data, config)
        results = engine.run()
        
        # Should complete with no trades
        assert results['total_trades'] == 0
    
    def test_all_zero_prices(self):
        """Test with all zero prices (invalid data)"""
        zero_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1H'),
            'open': np.zeros(100),
            'high': np.zeros(100),
            'low': np.zeros(100),
            'close': np.zeros(100),
            'volume': np.zeros(100)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(zero_data, config)
        
        with pytest.raises(ValueError, match="Invalid prices.*zero"):
            engine.run()
    
    def test_negative_prices(self):
        """Test with negative prices (invalid data)"""
        negative_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1H'),
            'open': np.random.uniform(-100, -10, 100),
            'high': np.random.uniform(-100, -10, 100),
            'low': np.random.uniform(-100, -10, 100),
            'close': np.random.uniform(-100, -10, 100),
            'volume': np.random.uniform(100, 1000, 100)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(negative_data, config)
        
        with pytest.raises(ValueError, match="Negative prices detected"):
            engine.run()
    
    def test_extreme_price_values(self):
        """Test with astronomically high prices"""
        extreme_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1H'),
            'open': np.random.uniform(1e10, 1e11, 100),  # Billions
            'high': np.random.uniform(1e10, 1e11, 100),
            'low': np.random.uniform(1e10, 1e11, 100),
            'close': np.random.uniform(1e10, 1e11, 100),
            'volume': np.random.uniform(100, 1000, 100)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(extreme_data, config)
        results = engine.run()
        
        # Should handle without overflow errors
        assert isinstance(results['total_return'], float)
        assert not np.isnan(results['total_return'])
        assert not np.isinf(results['total_return'])


# ============================================================================
# STRESS TESTS
# ============================================================================

class TestStressConditions:
    """Test with large datasets and high load"""
    
    def test_large_dataset_1_year_1m_candles(self):
        """Test with 1 year of 1-minute candles (~525,600 candles)"""
        # Generate 1 year of 1-minute data
        periods = 365 * 24 * 60  # 525,600 candles
        
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=periods, freq='1min'),
            'open': np.random.uniform(45000, 55000, periods),
            'high': np.random.uniform(46000, 56000, periods),
            'low': np.random.uniform(44000, 54000, periods),
            'close': np.random.uniform(45000, 55000, periods),
            'volume': np.random.uniform(100, 1000, periods)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1min',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        import time
        start_time = time.time()
        
        engine = MTFBacktestEngine(data, config)
        results = engine.run()
        
        execution_time = time.time() - start_time
        
        # Performance requirements
        assert execution_time < 60  # Should complete in under 60 seconds
        assert results['total_trades'] >= 0
        
        # Memory efficiency check
        import psutil
        import os
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        assert memory_mb < 2000  # Should use less than 2GB RAM
    
    def test_high_frequency_trading_10000_trades(self):
        """Test strategy that generates many trades"""
        # Generate data that will trigger many trades
        periods = 50000
        
        # Create oscillating prices to trigger frequent signals
        price_base = 50000
        price_oscillation = price_base + 1000 * np.sin(np.linspace(0, 100 * np.pi, periods))
        
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=periods, freq='1min'),
            'open': price_oscillation,
            'high': price_oscillation + 100,
            'low': price_oscillation - 100,
            'close': price_oscillation,
            'volume': np.random.uniform(100, 1000, periods)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1min',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 10, 'bb_std': 1}  # Aggressive settings
        }
        
        engine = MTFBacktestEngine(data, config)
        results = engine.run()
        
        # Should handle high trade volume
        print(f"Total trades: {results['total_trades']}")
        assert results['total_trades'] > 100  # Many trades expected
        assert isinstance(results['total_return'], float)
    
    def test_extremely_volatile_market(self):
        """Test with extreme price volatility (e.g., 50% swings per hour)"""
        periods = 1000
        
        # Generate highly volatile prices
        price_changes = np.random.uniform(-0.5, 0.5, periods)  # ±50% per period
        prices = 50000 * np.cumprod(1 + price_changes)
        
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=periods, freq='1H'),
            'open': prices,
            'high': prices * 1.05,
            'low': prices * 0.95,
            'close': prices,
            'volume': np.random.uniform(100, 1000, periods)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(data, config)
        results = engine.run()
        
        # Should handle without errors
        assert isinstance(results['max_drawdown'], float)
        assert results['max_drawdown'] <= 100  # Max drawdown is percentage


# ============================================================================
# MARKET CONDITION TESTS
# ============================================================================

class TestExtremeMarketConditions:
    """Test specific extreme market scenarios"""
    
    def test_flash_crash_90_percent_drop(self):
        """Test with sudden 90% price drop (flash crash)"""
        periods = 200
        
        # Normal prices then sudden crash
        prices = np.full(periods, 50000.0)
        prices[100:110] = 5000  # 90% drop over 10 periods
        prices[110:] = 50000  # Recovery
        
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=periods, freq='1H'),
            'open': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.uniform(100, 1000, periods)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(data, config)
        results = engine.run()
        
        # Should handle crash without errors
        assert isinstance(results['total_return'], float)
        # Max drawdown should reflect the crash
        assert results['max_drawdown'] > 50  # At least 50% drawdown
    
    def test_gap_opening_20_percent_gap(self):
        """Test with large price gap (e.g., weekend gap)"""
        periods = 200
        
        prices = np.full(periods, 50000.0)
        prices[100:] = 60000  # 20% gap up
        
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=periods, freq='1H'),
            'open': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.uniform(100, 1000, periods)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(data, config)
        results = engine.run()
        
        # Should handle gap without errors
        assert isinstance(results['total_return'], float)
    
    def test_prolonged_sideways_market(self):
        """Test with flat/sideways market (no trend)"""
        periods = 1000
        
        # Prices oscillate within narrow range
        prices = 50000 + 100 * np.sin(np.linspace(0, 20 * np.pi, periods))
        
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=periods, freq='1H'),
            'open': prices,
            'high': prices + 50,
            'low': prices - 50,
            'close': prices,
            'volume': np.random.uniform(100, 1000, periods)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(data, config)
        results = engine.run()
        
        # In sideways market, mean reversion might perform well or poorly
        assert isinstance(results['total_return'], float)
        # Sharpe ratio should be calculable
        assert isinstance(results.get('sharpe_ratio'), (float, type(None)))
    
    def test_zero_volume_periods(self):
        """Test with periods of zero trading volume"""
        periods = 200
        
        volume = np.random.uniform(100, 1000, periods)
        volume[50:100] = 0  # Zero volume period
        
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=periods, freq='1H'),
            'open': np.random.uniform(45000, 55000, periods),
            'high': np.random.uniform(46000, 56000, periods),
            'low': np.random.uniform(44000, 54000, periods),
            'close': np.random.uniform(45000, 55000, periods),
            'volume': volume
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(data, config)
        results = engine.run()
        
        # Should handle zero volume periods
        assert isinstance(results['total_trades'], int)


# ============================================================================
# DATA QUALITY TESTS
# ============================================================================

class TestDataQuality:
    """Test handling of corrupted or invalid data"""
    
    def test_missing_timestamps(self):
        """Test with missing timestamp values"""
        data = pd.DataFrame({
            'timestamp': [None] * 10 + list(pd.date_range('2024-01-01', periods=90, freq='1H')),
            'open': np.random.uniform(45000, 55000, 100),
            'high': np.random.uniform(46000, 56000, 100),
            'low': np.random.uniform(44000, 54000, 100),
            'close': np.random.uniform(45000, 55000, 100),
            'volume': np.random.uniform(100, 1000, 100)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(data, config)
        
        # Should either clean data or raise informative error
        with pytest.raises(ValueError, match="Missing timestamps"):
            engine.run()
    
    def test_duplicate_timestamps(self):
        """Test with duplicate timestamp entries"""
        timestamps = list(pd.date_range('2024-01-01', periods=100, freq='1H'))
        timestamps[50] = timestamps[49]  # Duplicate
        
        data = pd.DataFrame({
            'timestamp': timestamps,
            'open': np.random.uniform(45000, 55000, 100),
            'high': np.random.uniform(46000, 56000, 100),
            'low': np.random.uniform(44000, 54000, 100),
            'close': np.random.uniform(45000, 55000, 100),
            'volume': np.random.uniform(100, 1000, 100)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(data, config)
        
        # Should handle duplicates (e.g., keep last)
        results = engine.run()
        assert isinstance(results['total_trades'], int)
    
    def test_nan_prices(self):
        """Test with NaN price values"""
        prices = np.random.uniform(45000, 55000, 100)
        prices[30:35] = np.nan  # NaN prices
        
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1H'),
            'open': prices,
            'high': prices + 1000,
            'low': prices - 1000,
            'close': prices,
            'volume': np.random.uniform(100, 1000, 100)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(data, config)
        
        # Should either interpolate or raise error
        with pytest.raises(ValueError, match="NaN values detected"):
            engine.run()
    
    def test_high_lower_than_low(self):
        """Test with invalid candles (high < low)"""
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1H'),
            'open': np.random.uniform(45000, 55000, 100),
            'high': np.random.uniform(44000, 54000, 100),  # High too low
            'low': np.random.uniform(46000, 56000, 100),   # Low too high
            'close': np.random.uniform(45000, 55000, 100),
            'volume': np.random.uniform(100, 1000, 100)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        engine = MTFBacktestEngine(data, config)
        
        with pytest.raises(ValueError, match="Invalid candle data.*high.*low"):
            engine.run()


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Test performance under various conditions"""
    
    def test_memory_usage_large_dataset(self):
        """Test memory usage doesn't exceed limits"""
        periods = 100000  # 100k candles
        
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=periods, freq='1min'),
            'open': np.random.uniform(45000, 55000, periods),
            'high': np.random.uniform(46000, 56000, periods),
            'low': np.random.uniform(44000, 54000, periods),
            'close': np.random.uniform(45000, 55000, periods),
            'volume': np.random.uniform(100, 1000, periods)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1min',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        import psutil
        import os
        process = psutil.Process(os.getpid())
        
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        
        engine = MTFBacktestEngine(data, config)
        results = engine.run()
        
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_increase = mem_after - mem_before
        
        print(f"Memory increase: {mem_increase:.2f} MB")
        
        # Memory increase should be reasonable (< 500MB)
        assert mem_increase < 500
    
    def test_execution_time_10k_candles(self):
        """Test execution time is within acceptable limits"""
        periods = 10000
        
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=periods, freq='1min'),
            'open': np.random.uniform(45000, 55000, periods),
            'high': np.random.uniform(46000, 56000, periods),
            'low': np.random.uniform(44000, 54000, periods),
            'close': np.random.uniform(45000, 55000, periods),
            'volume': np.random.uniform(100, 1000, periods)
        })
        
        config = {
            'symbol': 'BTCUSDT',
            'interval': '1min',
            'strategy_type': 'bollinger_mean_reversion',
            'params': {'bb_period': 20, 'bb_std': 2}
        }
        
        import time
        start_time = time.time()
        
        engine = MTFBacktestEngine(data, config)
        results = engine.run()
        
        execution_time = time.time() - start_time
        
        print(f"Execution time: {execution_time:.2f} seconds")
        
        # Should complete in under 10 seconds
        assert execution_time < 10


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
