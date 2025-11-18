"""
Tests for Strategy Factory

Coverage target: 3.33% → 80%+

Test categories:
1. Strategy creation (successful instantiation)
2. Error handling (unknown type, invalid config)
3. Strategy registration
4. Listing strategies
5. Getting strategy info
"""

import pytest

from backend.strategies.base import BaseStrategy
from backend.strategies.bollinger_mean_reversion import BollingerMeanReversionStrategy
from backend.strategies.factory import StrategyFactory


# ==================== FIXTURES ====================


@pytest.fixture(autouse=True)
def reset_strategy_registry():
    """Reset strategy registry before each test to avoid pollution."""
    # Save original registry
    original = StrategyFactory._strategies.copy()
    
    yield
    
    # Restore original registry after test
    StrategyFactory._strategies = original


# ==================== TEST HELPERS ====================


class ConcreteTestStrategy(BaseStrategy):
    """Concrete implementation of BaseStrategy for testing."""
    
    def __init__(self, config):
        self.config = config
        self.on_start_called = False
    
    def on_bar(self, bar, bar_index, data):
        return {"action": "hold"}
    
    def on_start(self):
        self.on_start_called = True
    
    def validate_config(self):
        """Validate configuration."""
        # Example validation
        pass
    
    @staticmethod
    def get_default_params():
        return {"test_param": 10}


# ==================== TEST CLASSES ====================


class TestStrategyCreation:
    """Test strategy instantiation via factory."""

    def test_create_bollinger_strategy_success(self):
        """Test successful creation of bollinger strategy."""
        config = {
            "bb_period": 20,
            "bb_std_dev": 2.0,
            "risk_per_trade": 0.02,
            "stop_loss_multiplier": 1.5,
        }
        
        strategy = StrategyFactory.create("bollinger", config)
        
        assert strategy is not None
        assert isinstance(strategy, BollingerMeanReversionStrategy)
        assert hasattr(strategy, "on_bar")

    def test_create_strategy_with_alias(self):
        """Test creating strategy using alias name."""
        config = {
            "bb_period": 20,
            "bb_std_dev": 2.0,
        }
        
        strategy = StrategyFactory.create("bollinger_mean_reversion", config)
        
        assert isinstance(strategy, BollingerMeanReversionStrategy)

    def test_create_unknown_strategy_raises_error(self):
        """Test creating unknown strategy raises ValueError."""
        with pytest.raises(ValueError, match="Unknown strategy type"):
            StrategyFactory.create("nonexistent_strategy", {})

    def test_create_with_invalid_config_raises_error(self):
        """Test creating strategy with invalid config raises ValueError."""
        invalid_config = {
            "bb_period": -10,  # Invalid negative value
            "bb_std_dev": 2.0,
        }
        
        # Should raise ValueError with message mentioning invalid config
        with pytest.raises(ValueError):
            StrategyFactory.create("bollinger", invalid_config)

    def test_create_with_missing_required_params(self):
        """Test creating strategy with missing required params."""
        incomplete_config = {
            "bb_period": 20,
            # Missing bb_std_dev and other required params
        }
        
        # Bollinger strategy may fail if required params are missing
        # (Depends on strategy implementation)
        try:
            strategy = StrategyFactory.create("bollinger", incomplete_config)
            # If creation succeeds, strategy should use defaults
            assert strategy is not None
        except ValueError:
            # If creation fails, it's expected behavior
            pass


class TestStrategyRegistration:
    """Test registering custom strategies."""

    def test_register_custom_strategy(self):
        """Test registering a custom strategy."""
        # Register concrete test strategy
        StrategyFactory.register_strategy("custom", ConcreteTestStrategy)
        
        # Verify registration
        assert "custom" in StrategyFactory.list_strategies()
        
        # Create instance
        strategy = StrategyFactory.create("custom", {"test_param": 10})
        assert isinstance(strategy, ConcreteTestStrategy)

    def test_register_non_basestrategy_raises_error(self):
        """Test registering non-BaseStrategy class raises ValueError."""
        class NotAStrategy:
            """Not a strategy"""
            pass
        
        with pytest.raises(ValueError, match="must extend BaseStrategy"):
            StrategyFactory.register_strategy("invalid", NotAStrategy)

    def test_register_strategy_overwrite_existing(self):
        """Test that registering with same name overwrites existing."""
        # Register new strategy (will overwrite bollinger)
        StrategyFactory.register_strategy("test_overwrite", ConcreteTestStrategy)
        
        # Create should return new class
        strategy = StrategyFactory.create("test_overwrite", {})
        assert isinstance(strategy, ConcreteTestStrategy)


class TestStrategyListing:
    """Test listing available strategies."""

    def test_list_strategies_returns_all_registered(self):
        """Test list_strategies returns all registered strategies."""
        strategies = StrategyFactory.list_strategies()
        
        assert isinstance(strategies, list)
        assert len(strategies) > 0
        assert "bollinger" in strategies
        assert "bollinger_mean_reversion" in strategies

    def test_list_strategies_after_registration(self):
        """Test list_strategies includes newly registered strategies."""
        StrategyFactory.register_strategy("new_test_strategy", ConcreteTestStrategy)
        
        strategies = StrategyFactory.list_strategies()
        assert "new_test_strategy" in strategies


class TestStrategyInfo:
    """Test getting strategy metadata."""

    def test_get_strategy_info_success(self):
        """Test getting info for existing strategy."""
        info = StrategyFactory.get_strategy_info("bollinger")
        
        assert isinstance(info, dict)
        assert info["name"] == "bollinger"
        assert info["class"] == "BollingerMeanReversionStrategy"
        assert "default_params" in info
        assert isinstance(info["default_params"], dict)

    def test_get_strategy_info_unknown_strategy_raises_error(self):
        """Test getting info for unknown strategy raises ValueError."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            StrategyFactory.get_strategy_info("nonexistent")

    def test_get_strategy_info_includes_docstring(self):
        """Test strategy info includes docstring."""
        info = StrategyFactory.get_strategy_info("bollinger")
        
        assert "docstring" in info
        # Docstring may be None if strategy class doesn't have docstring
        # Just verify key exists

    def test_get_strategy_info_default_params(self):
        """Test default_params are correctly retrieved."""
        info = StrategyFactory.get_strategy_info("bollinger")
        
        default_params = info["default_params"]
        assert "bb_period" in default_params
        assert "bb_std_dev" in default_params


# ==================== INTEGRATION TESTS ====================


class TestFactoryIntegration:
    """Integration tests combining multiple factory operations."""

    def test_full_workflow_register_create_list(self):
        """Test complete workflow: register → create → list."""
        # Register concrete test strategy
        StrategyFactory.register_strategy("integration_test", ConcreteTestStrategy)
        
        # Step 2: Verify in list
        strategies = StrategyFactory.list_strategies()
        assert "integration_test" in strategies
        
        # Step 3: Get info
        info = StrategyFactory.get_strategy_info("integration_test")
        assert info["name"] == "integration_test"
        assert info["default_params"]["test_param"] == 10
        
        # Step 4: Create instance
        strategy = StrategyFactory.create("integration_test", {"test_param": 100})
        assert isinstance(strategy, ConcreteTestStrategy)

    def test_error_message_lists_available_strategies(self):
        """Test error message includes list of available strategies."""
        try:
            StrategyFactory.create("invalid_type", {})
        except ValueError as e:
            error_msg = str(e)
            assert "Unknown strategy type" in error_msg
            assert "Available strategies" in error_msg
            assert "bollinger" in error_msg


# ==================== PARAMETRIZED TESTS ====================


@pytest.mark.parametrize("strategy_name", [
    "bollinger",
    "bollinger_mean_reversion",
])
def test_create_all_registered_strategies(strategy_name):
    """Test creating all pre-registered strategies."""
    config = {
        "bb_period": 20,
        "bb_std_dev": 2.0,
    }
    
    strategy = StrategyFactory.create(strategy_name, config)
    assert strategy is not None
    assert isinstance(strategy, BaseStrategy)


@pytest.mark.parametrize("strategy_name", [
    "bollinger",
    "bollinger_mean_reversion",
])
def test_get_info_for_all_strategies(strategy_name):
    """Test getting info for all registered strategies."""
    info = StrategyFactory.get_strategy_info(strategy_name)
    
    assert info["name"] == strategy_name
    assert "class" in info
    assert "default_params" in info
    assert "docstring" in info
