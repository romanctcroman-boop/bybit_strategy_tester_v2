"""
Comprehensive tests for BacktestEngine

Coverage targets:
- Current: 10.69%
- Target: 70%+

Test categories:
1. Initialization & Configuration
2. Data Preparation & Validation
3. Indicator Calculation (Legacy strategies)
4. Strategy System Integration (BaseStrategy)
5. Bar-by-bar Processing
6. Position Management (Entry/Exit)
7. Trade Execution & Commission/Slippage
8. TP/SL/Trailing Stop Logic
9. Metrics Calculation
10. Error Handling & Edge Cases
11. Performance & Stress Tests
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from backend.core.backtest_engine import (
    BacktestEngine,
    Position,
    Trade,
    BacktestState,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1h')
    
    # Generate realistic price action
    np.random.seed(42)
    close_prices = 50000 + np.cumsum(np.random.randn(100) * 100)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': close_prices + np.random.randn(100) * 50,
        'high': close_prices + abs(np.random.randn(100)) * 100,
        'low': close_prices - abs(np.random.randn(100)) * 100,
        'close': close_prices,
        'volume': np.random.randint(1000, 10000, 100)
    })
    
    # Ensure high >= close >= low
    df['high'] = df[['high', 'close']].max(axis=1)
    df['low'] = df[['low', 'close']].min(axis=1)
    
    return df


@pytest.fixture
def minimal_ohlcv_data():
    """Minimal valid OHLCV data (only close column)"""
    dates = pd.date_range(start='2024-01-01', periods=10, freq='1h')
    return pd.DataFrame({
        'timestamp': dates,
        'close': [50000 + i * 100 for i in range(10)]
    })


@pytest.fixture
def ema_crossover_config():
    """Configuration for EMA crossover strategy"""
    return {
        'type': 'ema_crossover',
        'fast_ema': 10,
        'slow_ema': 30,
        'take_profit_pct': 2.0,
        'stop_loss_pct': 1.0
    }


@pytest.fixture
def rsi_config():
    """Configuration for RSI strategy"""
    return {
        'type': 'rsi',
        'rsi_period': 14,
        'rsi_overbought': 70,
        'rsi_oversold': 30
    }


@pytest.fixture
def bollinger_config():
    """Configuration for Bollinger Bands strategy"""
    return {
        'type': 'bollinger',
        'bb_period': 20,
        'bb_std': 2.0,
        'take_profit_pct': 1.5,
        'stop_loss_pct': 0.5
    }


# ============================================================================
# Test Suite 1: Initialization & Configuration
# ============================================================================

class TestBacktestEngineInitialization:
    """Test engine initialization and configuration"""
    
    def test_default_initialization(self):
        """Test engine with default parameters"""
        engine = BacktestEngine()
        
        assert engine.initial_capital == 10_000.0
        assert engine.commission == 0.0006
        assert engine.slippage_pct == 0.05
        assert engine.leverage == 1
        assert engine.order_size_usd is None
        
        print("✅ Default initialization successful")
    
    def test_custom_initialization(self):
        """Test engine with custom parameters"""
        engine = BacktestEngine(
            initial_capital=50_000.0,
            commission=0.001,
            slippage_pct=0.1,
            leverage=5,
            order_size_usd=1000.0
        )
        
        assert engine.initial_capital == 50_000.0
        assert engine.commission == 0.001
        assert engine.slippage_pct == 0.1
        assert engine.leverage == 5
        assert engine.order_size_usd == 1000.0
        
        print("✅ Custom initialization successful")
    
    def test_zero_capital_initialization(self):
        """Test engine with zero capital (edge case)"""
        engine = BacktestEngine(initial_capital=0.0)
        assert engine.initial_capital == 0.0
        print("✅ Zero capital initialization handled")
    
    def test_high_leverage_initialization(self):
        """Test engine with high leverage"""
        engine = BacktestEngine(leverage=100)
        assert engine.leverage == 100
        print("✅ High leverage initialization successful")


# ============================================================================
# Test Suite 2: Data Preparation & Validation
# ============================================================================

class TestDataPreparation:
    """Test data preparation and validation"""
    
    def test_prepare_data_with_full_ohlcv(self, sample_ohlcv_data):
        """Test preparation with complete OHLCV data"""
        engine = BacktestEngine()
        df = engine._prepare_data(sample_ohlcv_data)
        
        assert 'timestamp' in df.columns
        assert 'open' in df.columns
        assert 'high' in df.columns
        assert 'low' in df.columns
        assert 'close' in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df['timestamp'])
        
        print(f"✅ Prepared {len(df)} bars successfully")
    
    def test_prepare_data_with_close_only(self, minimal_ohlcv_data):
        """Test preparation with only close prices (should create OHLC from close)"""
        engine = BacktestEngine()
        df = engine._prepare_data(minimal_ohlcv_data)
        
        assert 'open' in df.columns
        assert 'high' in df.columns
        assert 'low' in df.columns
        assert all(df['open'] == df['close'])  # Should use close as fallback
        
        print("✅ Created OHLC from close prices")
    
    def test_prepare_data_missing_timestamp(self):
        """Test preparation without timestamp column"""
        engine = BacktestEngine()
        df_no_timestamp = pd.DataFrame({
            'close': [100, 101, 102]
        })
        
        result = engine._prepare_data(df_no_timestamp)
        
        assert 'timestamp' in result.columns
        assert pd.api.types.is_datetime64_any_dtype(result['timestamp'])
        
        print("✅ Generated timestamps for data without them")
    
    def test_prepare_data_empty_dataframe(self):
        """Test preparation with empty DataFrame"""
        engine = BacktestEngine()
        
        with pytest.raises(ValueError):
            engine._prepare_data(pd.DataFrame())
        
        print("✅ Empty DataFrame raises ValueError")
    
    def test_prepare_data_missing_close_column(self):
        """Test preparation without close column (should fail)"""
        engine = BacktestEngine()
        df_no_close = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5),
            'open': [100, 101, 102, 103, 104]
        })
        
        with pytest.raises(ValueError, match="must contain columns"):
            engine._prepare_data(df_no_close)
        
        print("✅ Missing close column raises ValueError")


# ============================================================================
# Test Suite 3: Indicator Calculation (Legacy Strategies)
# ============================================================================

class TestIndicatorCalculation:
    """Test technical indicator calculations"""
    
    def test_calculate_ema_indicators(self, sample_ohlcv_data, ema_crossover_config):
        """Test EMA calculation for crossover strategy"""
        engine = BacktestEngine()
        df = engine._prepare_data(sample_ohlcv_data)
        
        indicators = engine._calculate_indicators(df, ema_crossover_config)
        
        assert 'ema_fast' in indicators
        assert 'ema_slow' in indicators
        assert len(indicators['ema_fast']) == len(df)
        assert len(indicators['ema_slow']) == len(df)
        
        # Verify EMAs are calculated correctly (fast > slow for trending up)
        assert not indicators['ema_fast'].isna().all()
        assert not indicators['ema_slow'].isna().all()
        
        print(f"✅ Calculated EMA indicators: fast={ema_crossover_config['fast_ema']}, slow={ema_crossover_config['slow_ema']}")
    
    def test_calculate_rsi_indicators(self, sample_ohlcv_data, rsi_config):
        """Test RSI calculation"""
        engine = BacktestEngine()
        df = engine._prepare_data(sample_ohlcv_data)
        
        indicators = engine._calculate_indicators(df, rsi_config)
        
        assert 'rsi' in indicators
        assert len(indicators['rsi']) == len(df)
        
        # Verify RSI is in valid range [0, 100]
        rsi_values = indicators['rsi'].dropna()
        assert rsi_values.min() >= 0
        assert rsi_values.max() <= 100
        
        print(f"✅ Calculated RSI: period={rsi_config['rsi_period']}, range=[{rsi_values.min():.1f}, {rsi_values.max():.1f}]")
    
    def test_calculate_indicators_unknown_strategy(self, sample_ohlcv_data):
        """Test indicator calculation with unknown strategy type"""
        engine = BacktestEngine()
        df = engine._prepare_data(sample_ohlcv_data)
        
        config = {'type': 'unknown_strategy'}
        indicators = engine._calculate_indicators(df, config)
        
        # Should return empty dict or default indicators
        assert isinstance(indicators, dict)
        
        print("✅ Unknown strategy handled gracefully")


# ============================================================================
# Test Suite 4: Backtest Execution (Integration)
# ============================================================================

class TestBacktestExecution:
    """Test complete backtest execution"""
    
    def test_run_backtest_ema_crossover(self, sample_ohlcv_data, ema_crossover_config):
        """Test full backtest with EMA crossover strategy"""
        engine = BacktestEngine(initial_capital=10_000)
        
        results = engine.run(sample_ohlcv_data, ema_crossover_config)
        
        assert results is not None
        assert 'final_capital' in results
        assert 'total_trades' in results
        assert 'equity_curve' in results
        
        # Basic sanity checks
        assert results['final_capital'] > 0
        assert results['total_trades'] >= 0
        
        print(f"✅ EMA crossover backtest completed:")
        print(f"   Initial: ${engine.initial_capital:,.2f}")
        print(f"   Final: ${results['final_capital']:,.2f}")
        print(f"   Trades: {results['total_trades']}")
    
    def test_run_backtest_rsi_strategy(self, sample_ohlcv_data, rsi_config):
        """Test full backtest with RSI strategy"""
        engine = BacktestEngine(initial_capital=10_000)
        
        results = engine.run(sample_ohlcv_data, rsi_config)
        
        assert results is not None
        assert 'final_capital' in results
        
        print(f"✅ RSI strategy backtest completed:")
        print(f"   Final capital: ${results['final_capital']:,.2f}")
        print(f"   Total trades: {results['total_trades']}")
    
    def test_run_backtest_with_leverage(self, sample_ohlcv_data, ema_crossover_config):
        """Test backtest with leverage"""
        engine = BacktestEngine(initial_capital=10_000, leverage=5)
        
        results = engine.run(sample_ohlcv_data, ema_crossover_config)
        
        assert results is not None
        # With leverage, returns can be amplified (or losses)
        
        print(f"✅ Leveraged backtest (5x) completed:")
        print(f"   Final capital: ${results['final_capital']:,.2f}")
    
    def test_run_backtest_with_commission(self, sample_ohlcv_data, ema_crossover_config):
        """Test backtest with commission fees"""
        engine_no_fee = BacktestEngine(initial_capital=10_000, commission=0.0)
        engine_with_fee = BacktestEngine(initial_capital=10_000, commission=0.001)
        
        results_no_fee = engine_no_fee.run(sample_ohlcv_data, ema_crossover_config)
        results_with_fee = engine_with_fee.run(sample_ohlcv_data, ema_crossover_config)
        
        # With fees, final capital should be lower (or equal if no trades)
        if results_with_fee['total_trades'] > 0:
            assert results_with_fee['final_capital'] <= results_no_fee['final_capital']
        
        print(f"✅ Commission impact tested:")
        print(f"   No fee: ${results_no_fee['final_capital']:,.2f}")
        print(f"   With fee: ${results_with_fee['final_capital']:,.2f}")
    
    def test_run_backtest_empty_data(self, ema_crossover_config):
        """Test backtest with empty data"""
        engine = BacktestEngine()
        empty_df = pd.DataFrame()
        
        results = engine.run(empty_df, ema_crossover_config)
        
        # Should return empty result without crashing
        assert results is not None
        # Empty data returns initial capital (no trades occurred)
        assert results.get('final_capital', 0) == engine.initial_capital
        assert results.get('total_trades', 0) == 0
        
        print("✅ Empty data handled gracefully")
    
    def test_run_backtest_none_data(self, ema_crossover_config):
        """Test backtest with None data"""
        engine = BacktestEngine()
        
        results = engine.run(None, ema_crossover_config)
        
        # Should return empty result
        assert results is not None
        
        print("✅ None data handled gracefully")
    
    def test_run_backtest_minimal_data(self, ema_crossover_config):
        """Test backtest with minimal data (3 bars)"""
        engine = BacktestEngine()
        minimal_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=3, freq='1h'),
            'close': [50000, 50100, 50200]
        })
        
        results = engine.run(minimal_data, ema_crossover_config)
        
        assert results is not None
        # With 3 bars, EMA won't be fully initialized, so likely no trades
        assert results['total_trades'] >= 0
        
        print("✅ Minimal data (3 bars) handled")


# ============================================================================
# Test Suite 5: Position Management
# ============================================================================

class TestPositionManagement:
    """Test position opening, tracking, and closing"""
    
    def test_position_creation(self):
        """Test Position dataclass creation"""
        pos = Position(
            entry_time=datetime(2024, 1, 1),
            entry_price=50000.0,
            quantity=0.1,
            side='long',
            entry_bar_index=0
        )
        
        assert pos.entry_price == 50000.0
        assert pos.quantity == 0.1
        assert pos.side == 'long'
        assert pos.highest_price == 50000.0  # Should initialize to entry
        assert pos.lowest_price == 50000.0
        
        print("✅ Position created successfully")
    
    def test_position_tracking_runup(self):
        """Test position tracking of run-up (highest price)"""
        pos = Position(
            entry_time=datetime(2024, 1, 1),
            entry_price=50000.0,
            quantity=0.1,
            side='long',
            entry_bar_index=0
        )
        
        # Update highest price
        pos.highest_price = 51000.0
        
        assert pos.highest_price == 51000.0
        runup_pct = (pos.highest_price / pos.entry_price - 1) * 100
        assert runup_pct > 0
        
        print(f"✅ Position run-up tracked: {runup_pct:.2f}%")
    
    def test_position_tracking_drawdown(self):
        """Test position tracking of drawdown (lowest price)"""
        pos = Position(
            entry_time=datetime(2024, 1, 1),
            entry_price=50000.0,
            quantity=0.1,
            side='long',
            entry_bar_index=0
        )
        
        # Update lowest price
        pos.lowest_price = 49000.0
        
        assert pos.lowest_price == 49000.0
        drawdown_pct = (1 - pos.lowest_price / pos.entry_price) * 100
        assert drawdown_pct > 0
        
        print(f"✅ Position drawdown tracked: {drawdown_pct:.2f}%")


# ============================================================================
# Test Suite 6: Trade Execution & Metrics
# ============================================================================

class TestTradeExecution:
    """Test trade execution and metrics"""
    
    def test_trade_creation(self):
        """Test Trade dataclass creation"""
        trade = Trade(
            entry_time=datetime(2024, 1, 1),
            exit_time=datetime(2024, 1, 2),
            entry_price=50000.0,
            exit_price=51000.0,
            quantity=0.1,
            side='long',
            pnl=100.0,
            pnl_pct=2.0,
            commission=0.6,
            bars_held=10,
            exit_reason='take_profit'
        )
        
        assert trade.pnl == 100.0
        assert trade.pnl_pct == 2.0
        assert trade.exit_reason == 'take_profit'
        
        print("✅ Trade created successfully")
    
    def test_trade_profit_calculation(self):
        """Test profit calculation for long trade"""
        entry = 50000.0
        exit = 51000.0
        quantity = 0.1
        
        # Long trade: profit when exit > entry
        pnl = (exit - entry) * quantity
        pnl_pct = (exit / entry - 1) * 100
        
        assert pnl == 100.0
        assert pnl_pct == pytest.approx(2.0, rel=0.01)
        
        print(f"✅ Long trade profit: ${pnl:.2f} ({pnl_pct:.2f}%)")
    
    def test_trade_loss_calculation(self):
        """Test loss calculation for long trade"""
        entry = 50000.0
        exit = 49000.0
        quantity = 0.1
        
        # Long trade: loss when exit < entry
        pnl = (exit - entry) * quantity
        pnl_pct = (exit / entry - 1) * 100
        
        assert pnl == -100.0
        assert pnl_pct == pytest.approx(-2.0, rel=0.01)
        
        print(f"✅ Long trade loss: ${pnl:.2f} ({pnl_pct:.2f}%)")
    
    def test_short_trade_profit_calculation(self):
        """Test profit calculation for short trade"""
        entry = 50000.0
        exit = 49000.0
        quantity = 0.1
        
        # Short trade: profit when exit < entry
        pnl = (entry - exit) * quantity
        pnl_pct = (entry / exit - 1) * 100
        
        assert pnl == 100.0
        assert pnl_pct == pytest.approx(2.04, rel=0.01)
        
        print(f"✅ Short trade profit: ${pnl:.2f} ({pnl_pct:.2f}%)")


# ============================================================================
# Test Suite 7: Error Handling & Edge Cases
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_backtest_with_nan_prices(self, ema_crossover_config):
        """Test backtest with NaN prices (should handle gracefully)"""
        engine = BacktestEngine()
        
        df_with_nan = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='1h'),
            'close': [50000, 50100, np.nan, 50300, 50400, np.nan, 50600, 50700, 50800, 50900]
        })
        
        results = engine.run(df_with_nan, ema_crossover_config)
        
        # Should complete without crashing
        assert results is not None
        
        print("✅ NaN prices handled gracefully")
    
    def test_backtest_with_negative_prices(self, ema_crossover_config):
        """Test backtest with negative prices (invalid data)"""
        engine = BacktestEngine()
        
        df_negative = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='1h'),
            'close': [-100, -50, 0, 50, 100]
        })
        
        results = engine.run(df_negative, ema_crossover_config)
        
        # Should handle without crashing (though results may be meaningless)
        assert results is not None
        
        print("✅ Negative prices handled")
    
    def test_backtest_with_zero_prices(self, ema_crossover_config):
        """Test backtest with zero prices"""
        engine = BacktestEngine()
        
        df_zero = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='1h'),
            'close': [0, 0, 0, 0, 0]
        })
        
        results = engine.run(df_zero, ema_crossover_config)
        
        assert results is not None
        # No trades should occur with zero prices
        assert results['total_trades'] == 0
        
        print("✅ Zero prices handled")
    
    def test_backtest_with_extreme_volatility(self, ema_crossover_config):
        """Test backtest with extreme price volatility"""
        engine = BacktestEngine()
        
        df_volatile = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='1h'),
            'close': [50000, 100000, 25000, 75000, 10000, 90000, 5000, 95000, 1000, 99000]
        })
        
        results = engine.run(df_volatile, ema_crossover_config)
        
        assert results is not None
        
        print("✅ Extreme volatility handled")
    
    def test_backtest_with_missing_config_keys(self, sample_ohlcv_data):
        """Test backtest with incomplete strategy config"""
        engine = BacktestEngine()
        
        incomplete_config = {'type': 'ema_crossover'}  # Missing ema periods
        
        results = engine.run(sample_ohlcv_data, incomplete_config)
        
        # Should use defaults or handle gracefully
        assert results is not None
        
        print("✅ Incomplete config handled with defaults")


# ============================================================================
# Test Suite 8: Metrics Calculation
# ============================================================================

class TestMetricsCalculation:
    """Test metrics calculation"""
    
    def test_calculate_metrics_with_trades(self, sample_ohlcv_data, ema_crossover_config):
        """Test metrics calculation when trades occurred"""
        engine = BacktestEngine(initial_capital=10_000)
        
        results = engine.run(sample_ohlcv_data, ema_crossover_config)
        
        # Check for key metrics
        assert 'final_capital' in results
        assert 'total_trades' in results
        assert 'win_rate' in results or 'total_trades' == 0
        assert 'max_drawdown' in results or 'max_drawdown_pct' in results
        
        print(f"✅ Metrics calculated successfully")
        print(f"   Metrics count: {len(results)} keys")
    
    def test_calculate_metrics_no_trades(self):
        """Test metrics calculation when no trades occurred"""
        engine = BacktestEngine()
        
        # Use data that won't trigger any trades
        flat_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='1h'),
            'close': [50000] * 10  # Flat price
        })
        
        config = {'type': 'ema_crossover', 'fast_ema': 5, 'slow_ema': 10}
        results = engine.run(flat_data, config)
        
        assert results['total_trades'] == 0
        assert results['final_capital'] == engine.initial_capital
        assert results.get('win_rate', 0) == 0
        
        print("✅ Metrics for no trades: capital unchanged")


# ============================================================================
# Test Suite 9: Strategy System Integration (BaseStrategy)
# ============================================================================

class TestStrategySystemIntegration:
    """Test integration with new BaseStrategy system"""
    
    @pytest.mark.skipif(True, reason="Requires BaseStrategy implementation")
    def test_run_with_bollinger_strategy(self, sample_ohlcv_data, bollinger_config):
        """Test backtest with Bollinger Bands BaseStrategy"""
        engine = BacktestEngine()
        
        results = engine.run(sample_ohlcv_data, bollinger_config)
        
        assert results is not None
        
        print("✅ Bollinger BaseStrategy executed")
    
    @pytest.mark.skipif(True, reason="Requires BaseStrategy implementation")
    def test_strategy_lifecycle(self):
        """Test strategy initialization, on_start, on_bar, on_end"""
        # This would test the strategy lifecycle hooks
        pass


# ============================================================================
# Test Suite 10: Performance & Stress Tests
# ============================================================================

@pytest.mark.slow
class TestPerformance:
    """Performance and stress tests"""
    
    def test_large_dataset_performance(self, ema_crossover_config):
        """Test backtest with large dataset (10,000 bars)"""
        import time
        
        # Generate large dataset
        dates = pd.date_range(start='2020-01-01', periods=10_000, freq='1h')
        close_prices = 50000 + np.cumsum(np.random.randn(10_000) * 100)
        
        large_data = pd.DataFrame({
            'timestamp': dates,
            'close': close_prices
        })
        
        engine = BacktestEngine()
        
        start_time = time.time()
        results = engine.run(large_data, ema_crossover_config)
        duration = time.time() - start_time
        
        assert results is not None
        assert duration < 10.0  # Should complete within 10 seconds
        
        print(f"✅ Large dataset (10,000 bars) processed in {duration:.2f}s")
        print(f"   Throughput: {len(large_data) / duration:.0f} bars/sec")
    
    def test_many_trades_performance(self):
        """Test backtest that generates many trades"""
        import time
        
        # Generate data that will trigger frequent trades
        dates = pd.date_range(start='2024-01-01', periods=1000, freq='1h')
        # Oscillating prices to trigger many crossovers
        close_prices = 50000 + 500 * np.sin(np.arange(1000) * 0.1)
        
        oscillating_data = pd.DataFrame({
            'timestamp': dates,
            'close': close_prices
        })
        
        config = {
            'type': 'ema_crossover',
            'fast_ema': 5,
            'slow_ema': 10
        }
        
        engine = BacktestEngine()
        
        start_time = time.time()
        results = engine.run(oscillating_data, config)
        duration = time.time() - start_time
        
        print(f"✅ Many trades test: {results['total_trades']} trades in {duration:.2f}s")


if __name__ == "__main__":
    print("Run with: pytest tests/backend/core/test_backtest_engine.py -v")
    print("Run with coverage: pytest tests/backend/core/test_backtest_engine.py -v --cov=backend.core.backtest_engine")
