"""
Comprehensive tests for backend/strategies/base.py

Testing BaseStrategy abstract base class:
- Initialization and config storage
- Abstract method enforcement
- validate_config called during __init__
- get_default_params class method
- __repr__ method
- ValueError propagation from validate_config
"""
import pytest
import pandas as pd
from backend.strategies.base import BaseStrategy


# ==================== CONCRETE TEST STRATEGY ====================


class TestConcreteStrategy(BaseStrategy):
    """Concrete strategy for testing"""
    
    def on_start(self, data: pd.DataFrame) -> None:
        """Implement abstract method"""
        self.data_length = len(data)
    
    def on_bar(self, bar: pd.Series, bar_index: int, data: pd.DataFrame):
        """Implement abstract method"""
        if bar['close'] > 50000:
            return {
                'action': 'LONG',
                'reason': 'Price above 50000',
                'entry_price': bar['close']
            }
        return None
    
    def validate_config(self, config):
        """Implement abstract method"""
        if 'required_param' not in config:
            raise ValueError("Missing required_param")
        if config['required_param'] <= 0:
            raise ValueError("required_param must be positive")
        return True
    
    @classmethod
    def get_default_params(cls):
        """Override default params"""
        return {
            'required_param': 10,
            'optional_param': 'default_value'
        }


class IncompleteStrategy(BaseStrategy):
    """Strategy missing abstract methods for testing"""
    pass


class NoValidationStrategy(BaseStrategy):
    """Strategy with minimal validation"""
    
    def on_start(self, data: pd.DataFrame) -> None:
        pass
    
    def on_bar(self, bar: pd.Series, bar_index: int, data: pd.DataFrame):
        return None
    
    def validate_config(self, config):
        """Always valid"""
        return True


# ==================== INITIALIZATION TESTS ====================


class TestBaseStrategyInit:
    """Test BaseStrategy initialization"""
    
    def test_init_stores_config(self):
        """Test that config is stored in self.config"""
        config = {'required_param': 5, 'extra': 'value'}
        strategy = TestConcreteStrategy(config)
        
        assert strategy.config == config
        assert strategy.config['required_param'] == 5
        assert strategy.config['extra'] == 'value'
    
    def test_init_calls_validate_config(self):
        """Test that __init__ calls validate_config"""
        # Valid config should pass
        config = {'required_param': 10}
        strategy = TestConcreteStrategy(config)
        assert strategy.config == config
        
        # Invalid config should raise ValueError
        with pytest.raises(ValueError, match="Missing required_param"):
            TestConcreteStrategy({})
    
    def test_init_with_empty_config(self):
        """Test initialization with empty config (should fail validation)"""
        with pytest.raises(ValueError, match="Missing required_param"):
            TestConcreteStrategy({})
    
    def test_init_with_invalid_param_value(self):
        """Test initialization with invalid parameter value"""
        config = {'required_param': -5}
        with pytest.raises(ValueError, match="must be positive"):
            TestConcreteStrategy(config)
    
    def test_init_with_minimal_valid_config(self):
        """Test initialization with minimal valid config"""
        config = {'required_param': 1}
        strategy = TestConcreteStrategy(config)
        assert strategy.config['required_param'] == 1


# ==================== ABSTRACT METHOD TESTS ====================


class TestAbstractMethods:
    """Test abstract method enforcement"""
    
    def test_cannot_instantiate_base_strategy(self):
        """Test that BaseStrategy cannot be instantiated directly"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseStrategy({'param': 'value'})
    
    def test_incomplete_strategy_raises_error(self):
        """Test that missing abstract methods prevents instantiation"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteStrategy({'param': 'value'})
    
    def test_complete_strategy_can_instantiate(self):
        """Test that implementing all abstract methods allows instantiation"""
        strategy = TestConcreteStrategy({'required_param': 5})
        assert isinstance(strategy, BaseStrategy)
        assert isinstance(strategy, TestConcreteStrategy)
    
    def test_on_start_is_abstract(self):
        """Test that on_start must be implemented"""
        # IncompleteStrategy doesn't implement any methods
        assert not hasattr(IncompleteStrategy, 'on_start') or \
               IncompleteStrategy.on_start.__isabstractmethod__
    
    def test_on_bar_is_abstract(self):
        """Test that on_bar must be implemented"""
        assert not hasattr(IncompleteStrategy, 'on_bar') or \
               IncompleteStrategy.on_bar.__isabstractmethod__
    
    def test_validate_config_is_abstract(self):
        """Test that validate_config must be implemented"""
        assert not hasattr(IncompleteStrategy, 'validate_config') or \
               IncompleteStrategy.validate_config.__isabstractmethod__


# ==================== METHOD BEHAVIOR TESTS ====================


class TestOnStartMethod:
    """Test on_start method behavior"""
    
    def test_on_start_receives_dataframe(self):
        """Test that on_start receives DataFrame and can process it"""
        strategy = TestConcreteStrategy({'required_param': 5})
        
        data = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [99, 100, 101],
            'close': [102, 103, 104],
            'volume': [1000, 1100, 1200]
        })
        
        strategy.on_start(data)
        
        # Check that strategy processed the data
        assert hasattr(strategy, 'data_length')
        assert strategy.data_length == 3
    
    def test_on_start_with_empty_dataframe(self):
        """Test on_start with empty DataFrame"""
        strategy = TestConcreteStrategy({'required_param': 5})
        data = pd.DataFrame()
        
        strategy.on_start(data)
        assert strategy.data_length == 0
    
    def test_on_start_called_before_on_bar(self):
        """Test typical workflow: on_start then on_bar"""
        strategy = TestConcreteStrategy({'required_param': 5})
        
        data = pd.DataFrame({
            'close': [50001, 50002],
            'open': [50000, 50001],
            'high': [50100, 50100],
            'low': [49900, 49900],
            'volume': [1000, 1000]
        })
        
        strategy.on_start(data)
        
        # Now call on_bar
        bar = data.iloc[0]
        signal = strategy.on_bar(bar, 0, data)
        
        assert signal is not None
        assert signal['action'] == 'LONG'


class TestOnBarMethod:
    """Test on_bar method behavior"""
    
    def test_on_bar_generates_long_signal(self):
        """Test on_bar generates LONG signal when price > 50000"""
        strategy = TestConcreteStrategy({'required_param': 5})
        
        bar = pd.Series({
            'open': 50000,
            'high': 51000,
            'low': 49000,
            'close': 50500,
            'volume': 1000
        })
        
        data = pd.DataFrame([bar])
        signal = strategy.on_bar(bar, 0, data)
        
        assert signal is not None
        assert signal['action'] == 'LONG'
        assert signal['reason'] == 'Price above 50000'
        assert signal['entry_price'] == 50500
    
    def test_on_bar_no_signal_below_threshold(self):
        """Test on_bar returns None when price <= 50000"""
        strategy = TestConcreteStrategy({'required_param': 5})
        
        bar = pd.Series({
            'open': 49000,
            'high': 49500,
            'low': 48500,
            'close': 49000,
            'volume': 1000
        })
        
        data = pd.DataFrame([bar])
        signal = strategy.on_bar(bar, 0, data)
        
        assert signal is None
    
    def test_on_bar_receives_bar_index(self):
        """Test on_bar receives correct bar_index"""
        strategy = NoValidationStrategy({})
        
        bars = [
            {'close': 100, 'open': 99, 'high': 101, 'low': 98, 'volume': 1000},
            {'close': 101, 'open': 100, 'high': 102, 'low': 99, 'volume': 1100}
        ]
        
        for i, bar_dict in enumerate(bars):
            bar = pd.Series(bar_dict)
            data = pd.DataFrame(bars[:i+1])
            # Just verify it can be called with bar_index
            strategy.on_bar(bar, i, data)
    
    def test_on_bar_receives_historical_data(self):
        """Test on_bar receives historical data up to current bar"""
        strategy = NoValidationStrategy({})
        
        full_data = pd.DataFrame({
            'close': [100, 101, 102, 103],
            'open': [99, 100, 101, 102],
            'high': [101, 102, 103, 104],
            'low': [98, 99, 100, 101],
            'volume': [1000, 1100, 1200, 1300]
        })
        
        # Simulate calling on_bar at bar_index=2
        bar = full_data.iloc[2]
        historical_data = full_data.iloc[:3]  # Up to and including bar_index=2
        
        strategy.on_bar(bar, 2, historical_data)
        # Just verify no errors


class TestValidateConfig:
    """Test validate_config method"""
    
    def test_validate_config_returns_true_on_valid(self):
        """Test validate_config returns True for valid config"""
        strategy = TestConcreteStrategy({'required_param': 10})
        result = strategy.validate_config({'required_param': 5})
        assert result is True
    
    def test_validate_config_raises_on_missing_param(self):
        """Test validate_config raises ValueError on missing param"""
        strategy = NoValidationStrategy({})
        
        # TestConcreteStrategy requires 'required_param'
        with pytest.raises(ValueError, match="Missing required_param"):
            TestConcreteStrategy.validate_config(None, {})
    
    def test_validate_config_raises_on_invalid_value(self):
        """Test validate_config raises ValueError on invalid value"""
        with pytest.raises(ValueError, match="must be positive"):
            TestConcreteStrategy.validate_config(None, {'required_param': 0})
    
    def test_validate_config_always_true_strategy(self):
        """Test strategy with no validation requirements"""
        strategy = NoValidationStrategy({'any': 'config'})
        result = strategy.validate_config({'any': 'config'})
        assert result is True
        
        # Should accept empty config too
        result = strategy.validate_config({})
        assert result is True


# ==================== CLASS METHOD TESTS ====================


class TestGetDefaultParams:
    """Test get_default_params class method"""
    
    def test_get_default_params_base_class(self):
        """Test BaseStrategy.get_default_params returns empty dict"""
        defaults = BaseStrategy.get_default_params()
        assert defaults == {}
        assert isinstance(defaults, dict)
    
    def test_get_default_params_concrete_strategy(self):
        """Test concrete strategy can override get_default_params"""
        defaults = TestConcreteStrategy.get_default_params()
        
        assert 'required_param' in defaults
        assert defaults['required_param'] == 10
        assert 'optional_param' in defaults
        assert defaults['optional_param'] == 'default_value'
    
    def test_get_default_params_no_validation_strategy(self):
        """Test strategy without override uses base implementation"""
        defaults = NoValidationStrategy.get_default_params()
        assert defaults == {}
    
    def test_get_default_params_is_class_method(self):
        """Test get_default_params can be called on class directly"""
        # Should work without instantiation
        defaults = TestConcreteStrategy.get_default_params()
        assert isinstance(defaults, dict)
        
        # Should also work on instance
        strategy = TestConcreteStrategy({'required_param': 5})
        instance_defaults = strategy.get_default_params()
        assert instance_defaults == defaults


# ==================== REPR TEST ====================


class TestReprMethod:
    """Test __repr__ method"""
    
    def test_repr_includes_class_name(self):
        """Test __repr__ includes class name"""
        strategy = TestConcreteStrategy({'required_param': 5})
        repr_str = repr(strategy)
        
        assert 'TestConcreteStrategy' in repr_str
    
    def test_repr_includes_config(self):
        """Test __repr__ includes config"""
        config = {'required_param': 5, 'extra': 'value'}
        strategy = TestConcreteStrategy(config)
        repr_str = repr(strategy)
        
        assert 'config=' in repr_str
        assert str(config) in repr_str or "'required_param': 5" in repr_str
    
    def test_repr_with_empty_config(self):
        """Test __repr__ with minimal config"""
        strategy = TestConcreteStrategy({'required_param': 1})
        repr_str = repr(strategy)
        
        assert 'TestConcreteStrategy' in repr_str
        assert 'config=' in repr_str
    
    def test_repr_is_string(self):
        """Test __repr__ returns string"""
        strategy = TestConcreteStrategy({'required_param': 5})
        repr_str = repr(strategy)
        
        assert isinstance(repr_str, str)


# ==================== INTEGRATION TESTS ====================


class TestStrategyIntegration:
    """Test complete strategy workflow"""
    
    def test_full_backtest_workflow(self):
        """Test complete backtest workflow: init -> on_start -> on_bar loop"""
        config = {'required_param': 5}
        strategy = TestConcreteStrategy(config)
        
        # Create sample data
        data = pd.DataFrame({
            'open': [49000, 50000, 51000],
            'high': [49500, 50500, 51500],
            'low': [48500, 49500, 50500],
            'close': [49200, 50200, 51200],
            'volume': [1000, 1100, 1200]
        })
        
        # Step 1: on_start
        strategy.on_start(data)
        assert strategy.data_length == 3
        
        # Step 2: on_bar loop
        signals = []
        for i in range(len(data)):
            bar = data.iloc[i]
            historical = data.iloc[:i+1]
            signal = strategy.on_bar(bar, i, historical)
            if signal:
                signals.append(signal)
        
        # Should have 2 signals (bars 1 and 2 have close > 50000)
        assert len(signals) == 2
        assert all(s['action'] == 'LONG' for s in signals)
    
    def test_strategy_with_default_params(self):
        """Test using get_default_params for initialization"""
        defaults = TestConcreteStrategy.get_default_params()
        strategy = TestConcreteStrategy(defaults)
        
        assert strategy.config['required_param'] == 10
        assert strategy.config['optional_param'] == 'default_value'
    
    def test_multiple_strategy_instances(self):
        """Test multiple strategy instances are independent"""
        strategy1 = TestConcreteStrategy({'required_param': 5})
        strategy2 = TestConcreteStrategy({'required_param': 10})
        
        assert strategy1.config['required_param'] == 5
        assert strategy2.config['required_param'] == 10
        
        # Modify one shouldn't affect other
        strategy1.config['new_param'] = 'test'
        assert 'new_param' not in strategy2.config


# ==================== EDGE CASES ====================


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_config_with_none_values(self):
        """Test config with None values"""
        config = {'required_param': 5, 'optional': None}
        strategy = TestConcreteStrategy(config)
        
        assert strategy.config['optional'] is None
    
    def test_config_with_nested_dict(self):
        """Test config with nested dictionary"""
        config = {
            'required_param': 5,
            'nested': {'key': 'value', 'number': 42}
        }
        strategy = TestConcreteStrategy(config)
        
        assert strategy.config['nested']['key'] == 'value'
        assert strategy.config['nested']['number'] == 42
    
    def test_very_large_config(self):
        """Test strategy with large config dictionary"""
        config = {'required_param': 5}
        for i in range(100):
            config[f'param_{i}'] = i
        
        strategy = TestConcreteStrategy(config)
        assert len(strategy.config) == 101  # 100 + required_param
    
    def test_on_bar_with_single_row_dataframe(self):
        """Test on_bar with minimal historical data (single row)"""
        strategy = TestConcreteStrategy({'required_param': 5})
        
        data = pd.DataFrame({
            'close': [50001],
            'open': [50000],
            'high': [50100],
            'low': [49900],
            'volume': [1000]
        })
        
        bar = data.iloc[0]
        signal = strategy.on_bar(bar, 0, data)
        
        assert signal is not None
        assert signal['action'] == 'LONG'
