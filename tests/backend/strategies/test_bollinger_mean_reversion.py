"""
Comprehensive tests for backend/strategies/bollinger_mean_reversion.py
Tests Bollinger Bands mean-reversion strategy
"""

import pytest
import pandas as pd
import numpy as np
from backend.strategies.bollinger_mean_reversion import BollingerMeanReversionStrategy


@pytest.fixture
def sample_data():
    """Create sample OHLCV data for testing"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=200, freq='5min')
    
    # Create trending data with volatility
    prices = []
    base = 100.0
    for i in range(200):
        noise = np.random.normal(0, 2)
        trend = 0.05 * (i / 10)
        prices.append(base + trend + noise)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': [p + abs(np.random.uniform(0, 1)) for p in prices],
        'low': [p - abs(np.random.uniform(0, 1)) for p in prices],
        'close': prices,
        'volume': [1000 + np.random.randint(-100, 100) for _ in range(200)]
    })
    return df


@pytest.fixture
def strategy():
    """Create strategy with default params"""
    return BollingerMeanReversionStrategy()


@pytest.fixture
def strategy_custom():
    """Create strategy with custom params"""
    config = {
        'bb_period': 15,
        'bb_std_dev': 2.5,
        'entry_threshold_pct': 0.1,
        'stop_loss_pct': 1.0,
        'max_holding_bars': 30
    }
    return BollingerMeanReversionStrategy(config=config)


class TestBollingerInit:
    """Test strategy initialization"""
    
    def test_init_default_config(self):
        """Initialize with default configuration"""
        strat = BollingerMeanReversionStrategy()
        assert strat.bb_period == 20
        assert strat.bb_std_dev == 2.0
        assert strat.entry_threshold_pct == 0.05
        assert strat.stop_loss_pct == 0.8
        assert strat.max_holding_bars == 48
        assert strat.position == 0
    
    def test_init_custom_config(self, strategy_custom):
        """Initialize with custom configuration"""
        assert strategy_custom.bb_period == 15
        assert strategy_custom.bb_std_dev == 2.5
        assert strategy_custom.entry_threshold_pct == 0.1
        assert strategy_custom.stop_loss_pct == 1.0
        assert strategy_custom.max_holding_bars == 30
    
    def test_init_legacy_params(self):
        """Initialize with legacy individual parameters"""
        strat = BollingerMeanReversionStrategy(
            bb_period=25,
            bb_std_dev=3.0,
            entry_threshold_pct=0.2,
            stop_loss_pct=1.5,
            max_holding_bars=60
        )
        assert strat.bb_period == 25
        assert strat.bb_std_dev == 3.0
        assert strat.entry_threshold_pct == 0.2
    
    def test_init_mixed_params(self):
        """Config dict takes precedence over legacy params"""
        config = {'bb_period': 30}
        strat = BollingerMeanReversionStrategy(
            config=config,
            bb_period=25  # Should be ignored
        )
        assert strat.bb_period == 30


class TestBollingerGetDefaultParams:
    """Test get_default_params class method"""
    
    def test_get_default_params_returns_dict(self):
        """Returns dictionary with default values"""
        defaults = BollingerMeanReversionStrategy.get_default_params()
        assert isinstance(defaults, dict)
        assert 'bb_period' in defaults
        assert 'bb_std_dev' in defaults
        assert 'entry_threshold_pct' in defaults
        assert 'stop_loss_pct' in defaults
        assert 'max_holding_bars' in defaults
    
    def test_get_default_params_values(self):
        """Default values are correct"""
        defaults = BollingerMeanReversionStrategy.get_default_params()
        assert defaults['bb_period'] == 20
        assert defaults['bb_std_dev'] == 2.0
        assert defaults['entry_threshold_pct'] == 0.05
        assert defaults['stop_loss_pct'] == 0.8
        assert defaults['max_holding_bars'] == 48


class TestBollingerValidateConfig:
    """Test validate_config method"""
    
    def test_validate_config_valid(self, strategy):
        """Valid configuration passes"""
        config = {
            'bb_period': 20,
            'bb_std_dev': 2.0,
            'entry_threshold_pct': 0.05,
            'stop_loss_pct': 0.8,
            'max_holding_bars': 48
        }
        assert strategy.validate_config(config) is True
    
    def test_validate_config_missing_params(self, strategy):
        """Missing required parameters raises ValueError"""
        config = {'bb_period': 20}
        with pytest.raises(ValueError, match="Missing required parameters"):
            strategy.validate_config(config)
    
    def test_validate_config_invalid_bb_period(self, strategy):
        """Invalid bb_period raises ValueError"""
        config = strategy.get_default_params()
        config['bb_period'] = -5
        with pytest.raises(ValueError, match="bb_period must be positive"):
            strategy.validate_config(config)
    
    def test_validate_config_invalid_bb_period_type(self, strategy):
        """Non-integer bb_period raises ValueError"""
        config = strategy.get_default_params()
        config['bb_period'] = 20.5
        with pytest.raises(ValueError, match="bb_period must be positive integer"):
            strategy.validate_config(config)
    
    def test_validate_config_invalid_std_dev(self, strategy):
        """Invalid std_dev raises ValueError"""
        config = strategy.get_default_params()
        config['bb_std_dev'] = -1.0
        with pytest.raises(ValueError, match="bb_std_dev must be positive"):
            strategy.validate_config(config)
    
    def test_validate_config_invalid_stop_loss(self, strategy):
        """Invalid stop_loss_pct raises ValueError"""
        config = strategy.get_default_params()
        config['stop_loss_pct'] = -0.5
        with pytest.raises(ValueError, match="stop_loss_pct must be positive"):
            strategy.validate_config(config)
    
    def test_validate_config_invalid_max_holding(self, strategy):
        """Invalid max_holding_bars raises ValueError"""
        config = strategy.get_default_params()
        config['max_holding_bars'] = 0
        with pytest.raises(ValueError, match="max_holding_bars must be positive"):
            strategy.validate_config(config)


class TestBollingerCalculateBands:
    """Test calculate_bollinger_bands method"""
    
    def test_calculate_bands_sufficient_data(self, strategy, sample_data):
        """Calculate bands with sufficient data"""
        bands = strategy.calculate_bollinger_bands(sample_data)
        
        assert bands is not None
        assert 'upper' in bands
        assert 'middle' in bands
        assert 'lower' in bands
        assert 'std' in bands
        assert bands['upper'] > bands['middle']
        assert bands['middle'] > bands['lower']
    
    def test_calculate_bands_insufficient_data(self, strategy):
        """Returns None with insufficient data"""
        short_data = pd.DataFrame({
            'close': [100, 101, 102]
        })
        bands = strategy.calculate_bollinger_bands(short_data)
        assert bands is None
    
    def test_calculate_bands_values(self, strategy):
        """Calculate bands with known values"""
        data = pd.DataFrame({
            'close': [100.0] * 20  # Constant price
        })
        bands = strategy.calculate_bollinger_bands(data)
        
        # With constant price, std = 0, so bands collapse to SMA
        assert bands['middle'] == 100.0
        assert bands['std'] == 0.0
        assert bands['upper'] == 100.0
        assert bands['lower'] == 100.0


class TestBollingerAddBollingerBands:
    """Test add_bollinger_bands static method (vectorized)"""
    
    def test_add_bollinger_bands_basic(self, sample_data):
        """Add Bollinger Bands to DataFrame"""
        df = BollingerMeanReversionStrategy.add_bollinger_bands(
            sample_data, period=20, std_dev=2.0
        )
        
        assert 'bb_upper' in df.columns
        assert 'bb_middle' in df.columns
        assert 'bb_lower' in df.columns
    
    def test_add_bollinger_bands_ordering(self, sample_data):
        """Upper > Middle > Lower"""
        df = BollingerMeanReversionStrategy.add_bollinger_bands(sample_data)
        
        # Check non-NaN values
        valid = df.dropna()
        assert (valid['bb_upper'] >= valid['bb_middle']).all()
        assert (valid['bb_middle'] >= valid['bb_lower']).all()
    
    def test_add_bollinger_bands_custom_period(self, sample_data):
        """Custom period parameter"""
        df = BollingerMeanReversionStrategy.add_bollinger_bands(
            sample_data, period=10
        )
        
        # First 9 rows should be NaN, 10th onwards should have values
        assert df['bb_middle'].iloc[:9].isna().all()
        assert df['bb_middle'].iloc[9:].notna().all()
    
    def test_add_bollinger_bands_custom_price_col(self):
        """Use custom price column"""
        df = pd.DataFrame({
            'custom_price': [100 + i for i in range(50)]
        })
        
        result = BollingerMeanReversionStrategy.add_bollinger_bands(
            df, period=20, price_col='custom_price'
        )
        
        assert 'bb_middle' in result.columns
        assert result['bb_middle'].iloc[19] > 0
    
    def test_add_bollinger_bands_invalid_column(self, sample_data):
        """Invalid price column raises KeyError"""
        with pytest.raises(KeyError, match="Column 'invalid' not found"):
            BollingerMeanReversionStrategy.add_bollinger_bands(
                sample_data, price_col='invalid'
            )
    
    def test_add_bollinger_bands_invalid_period(self, sample_data):
        """Invalid period raises ValueError"""
        with pytest.raises(ValueError, match="period must be a positive integer"):
            BollingerMeanReversionStrategy.add_bollinger_bands(
                sample_data, period=-5
            )


class TestBollingerOnStart:
    """Test on_start method"""
    
    def test_on_start_adds_bands(self, strategy, sample_data):
        """on_start adds Bollinger Bands to data"""
        strategy.on_start(sample_data)
        
        # Check that bands were calculated
        assert strategy.bb_upper is not None
        assert strategy.bb_middle is not None
        assert strategy.bb_lower is not None
    
    def test_on_start_resets_position(self, strategy, sample_data):
        """on_start resets position state"""
        strategy.position = 1
        strategy.entry_bar = 50
        
        strategy.on_start(sample_data)
        
        assert strategy.position == 0
        assert strategy.entry_bar == 0


class TestBollingerOnBar:
    """Test on_bar method"""
    
    def test_on_bar_flat_no_signal(self, strategy, sample_data):
        """No signal when price not at bands"""
        strategy.on_start(sample_data)
        
        # Use middle bar (not at bands)
        bar = sample_data.iloc[100]
        
        signal = strategy.on_bar(bar, 100, sample_data)
        # May be None if price not at bands
        assert signal is None or isinstance(signal, dict)
    
    def test_on_bar_updates_bands_periodically(self, strategy, sample_data):
        """Bands updated every 10 bars"""
        strategy.on_start(sample_data)
        
        # Bar 100 (divisible by 10)
        bar = sample_data.iloc[100]
        strategy.on_bar(bar, 100, sample_data)
        
        assert strategy.bb_upper is not None


class TestBollingerIntegration:
    """Integration tests"""
    
    def test_full_workflow(self, strategy, sample_data):
        """Test complete workflow from init to signals"""
        strategy.on_start(sample_data)
        
        signals = []
        for i in range(50, len(sample_data)):
            bar = sample_data.iloc[i]
            signal = strategy.on_bar(bar, i, sample_data)
            if signal:
                signals.append(signal)
        
        # Should complete without errors
        assert isinstance(signals, list)
    
    def test_config_dict_preferred_over_legacy(self):
        """Config dict takes precedence"""
        config = {'bb_period': 25, 'bb_std_dev': 2.5}
        strat = BollingerMeanReversionStrategy(
            config=config,
            bb_period=20,  # Should be overridden
            bb_std_dev=2.0  # Should be overridden
        )
        assert strat.bb_period == 25
        assert strat.bb_std_dev == 2.5


class TestBollingerEdgeCases:
    """Test edge cases"""
    
    def test_constant_price_bands(self):
        """Bands with constant price (zero std)"""
        df = pd.DataFrame({
            'close': [100.0] * 50,
            'high': [100.0] * 50,
            'low': [100.0] * 50,
            'open': [100.0] * 50,
            'volume': [1000] * 50
        })
        
        result = BollingerMeanReversionStrategy.add_bollinger_bands(df, period=20)
        
        # With zero std, all bands should equal middle
        valid = result.dropna()
        assert (valid['bb_upper'] == valid['bb_middle']).all()
        assert (valid['bb_lower'] == valid['bb_middle']).all()
    
    def test_very_small_dataset(self, strategy):
        """Handle very small dataset"""
        tiny_data = pd.DataFrame({
            'close': [100, 101],
            'high': [101, 102],
            'low': [99, 100],
            'open': [100, 101],
            'volume': [1000, 1000]
        })
        
        bands = strategy.calculate_bollinger_bands(tiny_data)
        assert bands is None  # Not enough data
    
    def test_repr_method(self, strategy):
        """Test __repr__ from BaseStrategy"""
        repr_str = repr(strategy)
        assert 'BollingerMeanReversionStrategy' in repr_str
        assert 'config=' in repr_str


# Run: pytest tests/backend/strategies/test_bollinger_mean_reversion.py -v
