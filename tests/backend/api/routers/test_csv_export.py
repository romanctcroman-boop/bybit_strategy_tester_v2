"""
Tests for CSV Export API - Quick Win #4
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from unittest.mock import Mock
import csv
import io

from backend.database import get_db
from backend.models import Backtest, Trade, Optimization, OptimizationResult


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock()


@pytest.fixture
def app_with_mock_db(mock_db):
    """Create FastAPI app with mocked database"""
    app = FastAPI()
    from backend.api.routers import csv_export
    
    # Override get_db dependency
    def get_mock_db():
        return mock_db
    
    app.dependency_overrides[get_db] = get_mock_db
    app.include_router(csv_export.router, prefix="/api/v1")
    
    return app


@pytest.fixture
def client(app_with_mock_db):
    """Create test client"""
    return TestClient(app_with_mock_db)


class TestBacktestCSVExport:
    """Test backtest CSV export endpoint."""
    
    def test_export_backtest_csv_not_found(self, client, mock_db):
        """Test 404 when backtest doesn't exist."""
        # Mock query to return None (backtest not found)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.get("/api/v1/export/backtests/99999/csv")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_export_backtest_csv_success(self, client, mock_db):
        """Test successful backtest export with trades."""
        # Create mock backtest
        mock_backtest = Mock(spec=Backtest)
        mock_backtest.id = 1
        mock_backtest.strategy_id = 1
        mock_backtest.symbol = "BTCUSDT"
        mock_backtest.timeframe = "1h"
        mock_backtest.start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_backtest.end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)
        mock_backtest.initial_capital = 10000.0
        mock_backtest.final_capital = 11500.0
        mock_backtest.total_return = 15.0
        mock_backtest.total_trades = 10
        mock_backtest.winning_trades = 7
        mock_backtest.losing_trades = 3
        mock_backtest.win_rate = 70.0
        mock_backtest.sharpe_ratio = 1.85
        mock_backtest.max_drawdown = -5.2
        
        # Create mock trade
        mock_trade = Mock(spec=Trade)
        mock_trade.entry_time = datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc)
        mock_trade.exit_time = datetime(2024, 1, 2, 14, 0, tzinfo=timezone.utc)
        mock_trade.side = "LONG"
        mock_trade.entry_price = 42000.0
        mock_trade.exit_price = 42500.0
        mock_trade.quantity = 0.1
        mock_trade.pnl = 50.0
        mock_trade.pnl_pct = 1.19
        mock_trade.cumulative_pnl = 50.0
        mock_trade.run_up = 75.0
        mock_trade.run_up_pct = 1.78
        mock_trade.drawdown = -10.0
        mock_trade.drawdown_pct = -0.24
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_backtest
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_trade]
        
        # Make request
        response = client.get("/api/v1/export/backtests/1/csv")
        
        # Assertions
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "backtest_1_BTCUSDT" in response.headers["content-disposition"]
        
        # Verify CSV content
        csv_content = response.text
        assert "# Backtest Export" in csv_content
        assert "BTCUSDT" in csv_content
        assert "42000.0000" in csv_content  # entry price
        assert "50.00" in csv_content  # pnl
    
    def test_export_backtest_csv_empty_trades(self, client, mock_db):
        """Test export with backtest but no trades."""
        # Mock backtest with no trades
        mock_backtest = Mock(spec=Backtest)
        mock_backtest.id = 2
        mock_backtest.strategy_id = 1
        mock_backtest.symbol = "ETHUSDT"
        mock_backtest.timeframe = "4h"
        mock_backtest.start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_backtest.end_date = datetime(2024, 1, 10, tzinfo=timezone.utc)
        mock_backtest.initial_capital = 5000.0
        mock_backtest.final_capital = None
        mock_backtest.total_return = None
        mock_backtest.total_trades = 0
        mock_backtest.winning_trades = None
        mock_backtest.losing_trades = None
        mock_backtest.win_rate = None
        mock_backtest.sharpe_ratio = None
        mock_backtest.max_drawdown = None
        
        # Mock queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_backtest
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        # Make request
        response = client.get("/api/v1/export/backtests/2/csv")
        
        # Assertions
        assert response.status_code == 200
        assert "# Backtest Export" in response.text
        assert "ETHUSDT" in response.text


class TestOptimizationCSVExport:
    """Test optimization CSV export endpoint."""
    
    def test_export_optimization_csv_not_found(self, client, mock_db):
        """Test 404 when optimization doesn't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.get("/api/v1/export/optimizations/99999/csv")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_export_optimization_csv_success(self, client, mock_db):
        """Test successful optimization export."""
        # Mock optimization
        mock_optimization = Mock(spec=Optimization)
        mock_optimization.id = 1
        mock_optimization.strategy_id = 1
        mock_optimization.optimization_type = "grid"
        
        # Mock optimization result
        mock_result = Mock(spec=OptimizationResult)
        mock_result.id = 1
        mock_result.parameters = {"fast_period": 10, "slow_period": 20}
        mock_result.metric_value = 1.234
        mock_result.backtest_id = 1
        
        # Mock queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_optimization
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_result]
        
        # Make request
        response = client.get("/api/v1/export/optimizations/1/csv")
        
        # Assertions
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "optimization_1" in response.headers["content-disposition"]
        
        # Verify CSV content
        csv_content = response.text
        assert "fast_period" in csv_content
        assert "slow_period" in csv_content
        assert "1.234" in csv_content
    
    def test_export_optimization_csv_empty_results(self, client, mock_db):
        """Test export with optimization but no results."""
        # Mock optimization with no results
        mock_optimization = Mock(spec=Optimization)
        mock_optimization.id = 2
        mock_optimization.strategy_id = 1
        mock_optimization.optimization_type = "grid"
        
        # Mock queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_optimization
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        # Make request
        response = client.get("/api/v1/export/optimizations/2/csv")
        
        # Assertions
        assert response.status_code == 200
        assert "# Optimization Export" in response.text


class TestCSVFormatting:
    """Test CSV formatting and Excel compatibility."""
    
    def test_csv_excel_compatibility(self, client, mock_db):
        """Test CSV is Excel-compatible (UTF-8 BOM)."""
        # Mock minimal backtest
        mock_backtest = Mock(spec=Backtest)
        mock_backtest.id = 1
        mock_backtest.symbol = "BTCUSDT"
        mock_backtest.timeframe = "1h"
        mock_backtest.start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_backtest.end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)
        mock_backtest.initial_capital = 1000.0
        mock_backtest.final_capital = None
        mock_backtest.total_return = None
        mock_backtest.total_trades = 0
        mock_backtest.winning_trades = None
        mock_backtest.losing_trades = None
        mock_backtest.win_rate = None
        mock_backtest.sharpe_ratio = None
        mock_backtest.max_drawdown = None
        
        # Mock queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_backtest
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        response = client.get("/api/v1/export/backtests/1/csv")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
    
    def test_csv_numeric_formatting(self, client, mock_db):
        """Test CSV numeric formatting (4 decimals for prices)."""
        # Mock backtest
        mock_backtest = Mock(spec=Backtest)
        mock_backtest.id = 1
        mock_backtest.symbol = "BTCUSDT"
        mock_backtest.timeframe = "1h"
        mock_backtest.start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_backtest.end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)
        mock_backtest.initial_capital = 1000.0
        mock_backtest.final_capital = 1100.0
        mock_backtest.total_return = 10.0
        mock_backtest.total_trades = 1
        mock_backtest.winning_trades = 1
        mock_backtest.losing_trades = 0
        mock_backtest.win_rate = 100.0
        mock_backtest.sharpe_ratio = 2.5
        mock_backtest.max_drawdown = -1.2
        
        # Mock trade with specific formatting test values
        mock_trade = Mock(spec=Trade)
        mock_trade.entry_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        mock_trade.exit_time = datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc)
        mock_trade.side = "LONG"
        mock_trade.entry_price = 2345.6789  # Test 4 decimal formatting
        mock_trade.exit_price = 2400.1234
        mock_trade.quantity = 1.123456
        mock_trade.pnl = 54.44
        mock_trade.pnl_pct = 2.32
        mock_trade.cumulative_pnl = 54.44
        mock_trade.run_up = 60.0
        mock_trade.run_up_pct = 2.56
        mock_trade.drawdown = -5.0
        mock_trade.drawdown_pct = -0.21
        
        # Mock queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_backtest
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_trade]
        
        response = client.get("/api/v1/export/backtests/1/csv")
        
        assert response.status_code == 200
        csv_content = response.text
        
        # Verify 4 decimal places for prices
        assert "2345.6789" in csv_content
        assert "2400.1234" in csv_content
        # Verify 6 decimal places for quantity
        assert "1.123456" in csv_content
