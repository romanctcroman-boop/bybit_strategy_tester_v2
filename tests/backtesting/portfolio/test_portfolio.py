"""
📊 Tests for Multi-Symbol Portfolio Backtesting

Tests for portfolio engine, correlation analysis, risk parity.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.backtesting.portfolio import (
    PortfolioBacktestEngine,
    PortfolioConfig,
    CorrelationAnalysis,
    RiskParityAllocator,
)


def generate_mock_data(n_days=100):
    """Generate mock OHLCV data"""
    dates = pd.date_range('2025-01-01', periods=n_days, freq='D')
    
    data = pd.DataFrame({
        'open': np.random.randn(n_days).cumsum() + 100,
        'high': np.random.randn(n_days).cumsum() + 100,
        'low': np.random.randn(n_days).cumsum() + 100,
        'close': np.random.randn(n_days).cumsum() + 100,
        'volume': np.random.randint(1000, 10000, n_days),
    }, index=dates)
    
    return data


class TestPortfolioBacktestEngine:
    """Tests for PortfolioBacktestEngine"""
    
    def test_create_engine(self):
        """Test creating portfolio engine"""
        engine = PortfolioBacktestEngine()
        assert engine is not None
    
    def test_normalize_weights(self):
        """Test weight normalization"""
        engine = PortfolioBacktestEngine()
        
        # None = equal weights
        weights = engine._normalize_weights(None, ['BTC', 'ETH'])
        assert weights == {'BTC': 0.5, 'ETH': 0.5}
        
        # Custom weights
        weights = engine._normalize_weights({'BTC': 0.6, 'ETH': 0.4}, ['BTC', 'ETH'])
        assert weights == {'BTC': 0.6, 'ETH': 0.4}
        
        # Normalize to 1.0
        weights = engine._normalize_weights({'BTC': 60, 'ETH': 40}, ['BTC', 'ETH'])
        assert weights == {'BTC': 0.6, 'ETH': 0.4}
    
    def test_run_portfolio_backtest(self):
        """Test portfolio backtest"""
        engine = PortfolioBacktestEngine()
        
        # Mock data
        data_dict = {
            'BTCUSDT': generate_mock_data(),
            'ETHUSDT': generate_mock_data(),
        }
        
        config = PortfolioConfig(
            symbols=['BTCUSDT', 'ETHUSDT'],
            weights={'BTCUSDT': 0.6, 'ETHUSDT': 0.4},
        )
        
        from backend.backtesting.strategies import RSIStrategy
        
        result = engine.run(
            strategy_class=RSIStrategy,
            data_dict=data_dict,
            config=config,
            strategy_params={'period': 14},
        )
        
        assert result is not None
        assert len(result.symbol_results) == 2
        assert 'BTCUSDT' in result.symbol_results
        assert 'ETHUSDT' in result.symbol_results
        assert len(result.portfolio_equity) > 0
        assert 'sharpe_ratio' in result.metrics


class TestCorrelationAnalysis:
    """Tests for CorrelationAnalysis"""
    
    def test_create_analyzer(self):
        """Test creating correlation analyzer"""
        analyzer = CorrelationAnalysis(window=30)
        assert analyzer is not None
    
    def test_correlation_matrix(self):
        """Test correlation matrix calculation"""
        analyzer = CorrelationAnalysis()
        
        # Mock returns
        returns_dict = {
            'BTC': pd.Series([0.01, -0.02, 0.03, -0.01, 0.02]),
            'ETH': pd.Series([0.02, -0.01, 0.02, 0.01, 0.03]),
        }
        
        corr_matrix = analyzer.calculate_correlation_matrix(returns_dict)
        
        assert corr_matrix.shape == (2, 2)
        assert corr_matrix.loc['BTC', 'BTC'] == 1.0
        assert corr_matrix.loc['ETH', 'ETH'] == 1.0
    
    def test_rolling_correlation(self):
        """Test rolling correlation"""
        analyzer = CorrelationAnalysis(window=3)
        
        returns1 = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
        returns2 = pd.Series([0.02, 0.01, 0.03, 0.02, 0.04])
        
        rolling_corr = analyzer.calculate_rolling_correlation(returns1, returns2)
        
        assert len(rolling_corr) == 5
        assert rolling_corr.iloc[2:] is not None
    
    def test_diversification_ratio(self):
        """Test diversification ratio calculation"""
        analyzer = CorrelationAnalysis()
        
        returns_dict = {
            'BTC': pd.Series(np.random.randn(100) * 0.02),
            'ETH': pd.Series(np.random.randn(100) * 0.03),
        }
        
        weights = {'BTC': 0.5, 'ETH': 0.5}
        
        div_ratio = analyzer.calculate_diversification_ratio(returns_dict, weights)
        
        assert div_ratio >= 1.0  # Should be >= 1 for diversified portfolio


class TestRiskParityAllocator:
    """Tests for RiskParityAllocator"""
    
    def test_create_allocator(self):
        """Test creating risk parity allocator"""
        allocator = RiskParityAllocator()
        assert allocator is not None
    
    def test_risk_parity_allocation(self):
        """Test risk parity allocation"""
        allocator = RiskParityAllocator()
        
        # Mock returns
        np.random.seed(42)
        returns = pd.DataFrame({
            'BTC': np.random.randn(100) * 0.02,
            'ETH': np.random.randn(100) * 0.03,
            'SOL': np.random.randn(100) * 0.04,
        })
        
        result = allocator.allocate(returns, method='risk_parity')
        
        assert result.weights is not None
        assert len(result.weights) == 3
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        assert result.diversification_ratio >= 1.0
    
    def test_sharpe_allocation(self):
        """Test Sharpe ratio maximization"""
        allocator = RiskParityAllocator()
        
        np.random.seed(42)
        returns = pd.DataFrame({
            'BTC': np.random.randn(100) * 0.02 + 0.001,
            'ETH': np.random.randn(100) * 0.03 + 0.002,
        })
        
        result = allocator.allocate(returns, method='sharpe')
        
        assert result.weights is not None
        assert len(result.weights) == 2
    
    def test_min_volatility_allocation(self):
        """Test minimum volatility allocation"""
        allocator = RiskParityAllocator()
        
        np.random.seed(42)
        returns = pd.DataFrame({
            'BTC': np.random.randn(100) * 0.02,
            'ETH': np.random.randn(100) * 0.03,
        })
        
        result = allocator.allocate(returns, method='min_volatility')
        
        assert result.weights is not None
        assert result.total_risk > 0
    
    def test_efficient_frontier(self):
        """Test efficient frontier calculation"""
        allocator = RiskParityAllocator()
        
        np.random.seed(42)
        returns = pd.DataFrame({
            'BTC': np.random.randn(100) * 0.02,
            'ETH': np.random.randn(100) * 0.03,
        })
        
        volatilities, portfolio_returns, weights_list = allocator.efficient_frontier(
            returns, n_points=10
        )
        
        assert len(volatilities) == 10
        assert len(portfolio_returns) == 10
        assert len(weights_list) == 10


class TestPortfolioConfig:
    """Tests for PortfolioConfig"""
    
    def test_create_config(self):
        """Test creating portfolio config"""
        config = PortfolioConfig(
            symbols=['BTCUSDT', 'ETHUSDT'],
            weights={'BTCUSDT': 0.6, 'ETHUSDT': 0.4},
            rebalance_frequency='monthly',
        )
        
        assert config.symbols == ['BTCUSDT', 'ETHUSDT']
        assert config.weights == {'BTCUSDT': 0.6, 'ETHUSDT': 0.4}
        assert config.rebalance_frequency == 'monthly'
