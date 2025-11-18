"""
Tests for Charts API endpoints (ТЗ 3.7.2)
"""

import pytest
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    """FastAPI test client"""
    from backend.api.app import app
    return TestClient(app)


@pytest.fixture
def mock_data_service():
    """Mock DataService for testing"""
    with patch('backend.api.routers.backtests._get_data_service') as mock_get_ds:
        service = MagicMock()
        # Create context manager mock
        mock_context = MagicMock()
        mock_context.__enter__.return_value = service
        mock_context.__exit__.return_value = None
        mock_get_ds.return_value = lambda: mock_context
        yield service


@pytest.fixture
def sample_backtest_with_charts(mock_data_service):
    """Sample backtest with equity curve and trades data"""
    
    # Generate equity curve (100 points)
    start_time = datetime(2024, 1, 1)
    equity_data = []
    equity = 10000.0
    
    for i in range(100):
        time = start_time + timedelta(hours=i)
        equity += (i % 10 - 5) * 10  # Oscillating equity
        equity_data.append({
            'time': time.isoformat(),
            'equity': equity
        })
    
    # Generate trades
    trades = []
    for i in range(20):
        trade = {
            'entry_time': (start_time + timedelta(hours=i*5)).isoformat(),
            'entry_price': 40000 + i * 100,
            'exit_time': (start_time + timedelta(hours=i*5 + 2)).isoformat(),
            'exit_price': 40000 + i * 100 + (i % 3 - 1) * 200,
            'pnl': (i % 3 - 1) * 20,
            'pnl_pct': (i % 3 - 1) * 0.5,
            'side': 'long',
            'qty': 0.1
        }
        trades.append(trade)
    
    return {
        'id': 1,
        'symbol': 'BTCUSDT',
        'timeframe': '15m',
        'status': 'completed',
        'results': {
            'equity': equity_data,
            'trades': trades
        }
    }


class TestChartsAPI:
    """Test Charts API endpoints"""
    
    def test_equity_curve_endpoint_success(self, client, sample_backtest_with_charts, mock_data_service):
        """Test successful equity curve generation"""
        
        mock_data_service.get_backtest.return_value = type('Backtest', (), sample_backtest_with_charts)()
        
        response = client.get('/api/v1/backtests/1/charts/equity_curve')
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'plotly_json' in data
        assert data['plotly_json'] is not None
        
        # Verify it's valid JSON
        plotly_data = json.loads(data['plotly_json'])
        assert 'data' in plotly_data
        assert 'layout' in plotly_data
    
    def test_equity_curve_with_drawdown_parameter(self, client, sample_backtest_with_charts, mock_data_service):
        """Test equity curve with show_drawdown parameter"""
        
        mock_data_service.get_backtest.return_value = type('Backtest', (), sample_backtest_with_charts)()
        
        # With drawdown
        response = client.get('/api/v1/backtests/1/charts/equity_curve?show_drawdown=true')
        assert response.status_code == 200
        
        # Without drawdown
        response = client.get('/api/v1/backtests/1/charts/equity_curve?show_drawdown=false')
        assert response.status_code == 200
    
    def test_drawdown_overlay_endpoint_success(self, client, sample_backtest_with_charts, mock_data_service):
        """Test successful drawdown overlay generation"""
        
        mock_data_service.get_backtest.return_value = type('Backtest', (), sample_backtest_with_charts)()
        
        response = client.get('/api/v1/backtests/1/charts/drawdown_overlay')
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'plotly_json' in data
        plotly_data = json.loads(data['plotly_json'])
        assert 'data' in plotly_data
        assert len(plotly_data['data']) >= 2  # Equity + Drawdown traces
    
    def test_pnl_distribution_endpoint_success(self, client, sample_backtest_with_charts, mock_data_service):
        """Test successful PnL distribution generation"""
        
        mock_data_service.get_backtest.return_value = type('Backtest', (), sample_backtest_with_charts)()
        
        response = client.get('/api/v1/backtests/1/charts/pnl_distribution')
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'plotly_json' in data
        plotly_data = json.loads(data['plotly_json'])
        assert 'data' in plotly_data
        assert plotly_data['data'][0]['type'] == 'histogram'
    
    def test_pnl_distribution_with_bins_parameter(self, client, sample_backtest_with_charts, mock_data_service):
        """Test PnL distribution with custom bins"""
        
        mock_data_service.get_backtest.return_value = type('Backtest', (), sample_backtest_with_charts)()
        
        # Custom bins
        response = client.get('/api/v1/backtests/1/charts/pnl_distribution?bins=50')
        assert response.status_code == 200
        
        # Invalid bins (too small)
        response = client.get('/api/v1/backtests/1/charts/pnl_distribution?bins=5')
        assert response.status_code == 422
        
        # Invalid bins (too large)
        response = client.get('/api/v1/backtests/1/charts/pnl_distribution?bins=150')
        assert response.status_code == 422
    
    def test_charts_backtest_not_found(self, client, mock_data_service):
        """Test 404 when backtest not found"""
        
        mock_data_service.get_backtest.return_value = None
        
        response = client.get('/api/v1/backtests/999/charts/equity_curve')
        assert response.status_code == 404
        assert 'not found' in response.json()['detail'].lower()
    
    def test_charts_backtest_not_completed(self, client, mock_data_service):
        """Test 400 when backtest not completed"""
        
        backtest = {
            'id': 1,
            'status': 'running',
            'results': None
        }
        mock_data_service.get_backtest.return_value = type('Backtest', (), backtest)()
        
        response = client.get('/api/v1/backtests/1/charts/equity_curve')
        assert response.status_code == 400
        assert 'completed' in response.json()['detail'].lower()
    
    def test_charts_no_equity_data(self, client, mock_data_service):
        """Test 400 when no equity data available"""
        
        backtest = {
            'id': 1,
            'status': 'completed',
            'results': {
                'equity': [],  # Empty
                'trades': []
            }
        }
        mock_data_service.get_backtest.return_value = type('Backtest', (), backtest)()
        
        response = client.get('/api/v1/backtests/1/charts/equity_curve')
        assert response.status_code == 400
        assert 'no equity data' in response.json()['detail'].lower()
    
    def test_charts_no_trades_data(self, client, mock_data_service):
        """Test 400 when no trades data available"""
        
        backtest = {
            'id': 1,
            'status': 'completed',
            'results': {
                'equity': [{'time': datetime.now().isoformat(), 'equity': 10000}],
                'trades': []  # Empty
            }
        }
        mock_data_service.get_backtest.return_value = type('Backtest', (), backtest)()
        
        response = client.get('/api/v1/backtests/1/charts/pnl_distribution')
        assert response.status_code == 400
        assert 'no trades' in response.json()['detail'].lower()


class TestChartsIntegration:
    """Integration tests for Charts API"""
    
    def test_all_charts_for_same_backtest(self, client, sample_backtest_with_charts, mock_data_service):
        """Test generating all chart types for same backtest"""
        
        mock_data_service.get_backtest.return_value = type('Backtest', (), sample_backtest_with_charts)()
        
        # Get all charts
        equity_response = client.get('/api/v1/backtests/1/charts/equity_curve')
        drawdown_response = client.get('/api/v1/backtests/1/charts/drawdown_overlay')
        pnl_response = client.get('/api/v1/backtests/1/charts/pnl_distribution')
        
        # All should succeed
        assert equity_response.status_code == 200
        assert drawdown_response.status_code == 200
        assert pnl_response.status_code == 200
        
        # All should have plotly_json
        assert 'plotly_json' in equity_response.json()
        assert 'plotly_json' in drawdown_response.json()
        assert 'plotly_json' in pnl_response.json()
    
    def test_charts_json_serialization(self, client, sample_backtest_with_charts, mock_data_service):
        """Test that Plotly JSON is properly serialized"""
        
        mock_data_service.get_backtest.return_value = type('Backtest', (), sample_backtest_with_charts)()
        
        response = client.get('/api/v1/backtests/1/charts/equity_curve')
        
        assert response.status_code == 200
        data = response.json()
        
        # Parse Plotly JSON
        plotly_data = json.loads(data['plotly_json'])
        
        # Verify structure
        assert isinstance(plotly_data, dict)
        assert 'data' in plotly_data
        assert 'layout' in plotly_data
        assert isinstance(plotly_data['data'], list)
        assert len(plotly_data['data']) > 0
        
        # Verify trace has required fields
        trace = plotly_data['data'][0]
        assert 'x' in trace
        assert 'y' in trace
        assert 'type' in trace
