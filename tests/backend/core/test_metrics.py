"""
Comprehensive tests for backend/core/metrics.py

Coverage Target: 100%
Tests: Prometheus metrics tracking for Bybit adapter
"""

import pytest
from unittest.mock import patch, MagicMock
import time
from backend.core.metrics import (
    # Metrics objects
    bybit_api_requests_total,
    bybit_api_duration_seconds,
    bybit_cache_operations_total,
    bybit_cache_size_bytes,
    bybit_cache_items_total,
    bybit_candles_fetched_total,
    bybit_candles_stored_total,
    bybit_errors_total,
    bybit_rate_limit_hits_total,
    bybit_retry_attempts_total,
    bybit_historical_fetches_total,
    bybit_historical_fetch_duration_seconds,
    bybit_historical_api_requests_per_fetch,
    bybit_adapter_info,
    # Functions
    track_api_request,
    record_cache_hit,
    record_cache_miss,
    record_cache_set,
    record_api_fetch,
    record_db_store,
    record_rate_limit_hit,
    record_retry_attempt,
    record_historical_fetch,
    init_adapter_info,
)


# ==================== METRICS INITIALIZATION TESTS ====================


class TestMetricsInitialization:
    """Test that all metrics are properly initialized"""

    def test_api_requests_counter_exists(self):
        """Test API requests counter is initialized"""
        assert bybit_api_requests_total is not None
        assert hasattr(bybit_api_requests_total, 'labels')

    def test_api_duration_histogram_exists(self):
        """Test API duration histogram is initialized"""
        assert bybit_api_duration_seconds is not None
        assert hasattr(bybit_api_duration_seconds, 'labels')

    def test_cache_operations_counter_exists(self):
        """Test cache operations counter is initialized"""
        assert bybit_cache_operations_total is not None

    def test_cache_size_gauge_exists(self):
        """Test cache size gauge is initialized"""
        assert bybit_cache_size_bytes is not None

    def test_cache_items_gauge_exists(self):
        """Test cache items gauge is initialized"""
        assert bybit_cache_items_total is not None

    def test_candles_fetched_counter_exists(self):
        """Test candles fetched counter is initialized"""
        assert bybit_candles_fetched_total is not None

    def test_candles_stored_counter_exists(self):
        """Test candles stored counter is initialized"""
        assert bybit_candles_stored_total is not None

    def test_errors_counter_exists(self):
        """Test errors counter is initialized"""
        assert bybit_errors_total is not None

    def test_rate_limit_counter_exists(self):
        """Test rate limit counter is initialized"""
        assert bybit_rate_limit_hits_total is not None

    def test_retry_attempts_counter_exists(self):
        """Test retry attempts counter is initialized"""
        assert bybit_retry_attempts_total is not None

    def test_historical_fetches_counter_exists(self):
        """Test historical fetches counter is initialized"""
        assert bybit_historical_fetches_total is not None

    def test_historical_duration_histogram_exists(self):
        """Test historical duration histogram is initialized"""
        assert bybit_historical_fetch_duration_seconds is not None

    def test_historical_requests_histogram_exists(self):
        """Test historical requests histogram is initialized"""
        assert bybit_historical_api_requests_per_fetch is not None

    def test_adapter_info_exists(self):
        """Test adapter info metric is initialized"""
        assert bybit_adapter_info is not None


# ==================== TRACK_API_REQUEST DECORATOR TESTS ====================


class TestTrackApiRequestDecorator:
    """Test track_api_request decorator"""

    def test_decorator_tracks_successful_request(self):
        """Test decorator tracks successful API request"""
        @track_api_request('BTCUSDT', '15', 'kline')
        def dummy_api_call():
            return "success"
        
        with patch.object(bybit_api_requests_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            result = dummy_api_call()
            
            assert result == "success"
            mock_labels.assert_called_with(
                symbol='BTCUSDT',
                interval='15',
                endpoint='kline',
                status='success'
            )
            mock_counter.inc.assert_called_once()

    def test_decorator_tracks_failed_request(self):
        """Test decorator tracks failed API request"""
        @track_api_request('ETHUSDT', '60', 'kline')
        def failing_api_call():
            raise ValueError("API error")
        
        with patch.object(bybit_api_requests_total, 'labels') as mock_api_labels, \
             patch.object(bybit_errors_total, 'labels') as mock_error_labels:
            
            mock_api_counter = MagicMock()
            mock_error_counter = MagicMock()
            mock_api_labels.return_value = mock_api_counter
            mock_error_labels.return_value = mock_error_counter
            
            with pytest.raises(ValueError):
                failing_api_call()
            
            # Should track error status
            mock_api_labels.assert_called_with(
                symbol='ETHUSDT',
                interval='60',
                endpoint='kline',
                status='error'
            )
            
            # Should track error type
            mock_error_labels.assert_called_with(
                error_type='ValueError',
                symbol='ETHUSDT',
                interval='60'
            )

    def test_decorator_tracks_duration(self):
        """Test decorator tracks request duration"""
        @track_api_request('BTCUSDT', '15', 'kline')
        def slow_api_call():
            time.sleep(0.01)  # 10ms
            return "done"
        
        with patch.object(bybit_api_duration_seconds, 'labels') as mock_labels:
            mock_histogram = MagicMock()
            mock_labels.return_value = mock_histogram
            
            slow_api_call()
            
            mock_labels.assert_called_with(
                symbol='BTCUSDT',
                interval='15',
                endpoint='kline'
            )
            
            # Check that observe was called with a duration
            assert mock_histogram.observe.called
            observed_duration = mock_histogram.observe.call_args[0][0]
            assert observed_duration > 0

    def test_decorator_preserves_function_metadata(self):
        """Test decorator preserves original function metadata"""
        @track_api_request('BTCUSDT', '15', 'kline')
        def documented_function():
            """This is a documented function"""
            return 42
        
        assert documented_function.__doc__ == "This is a documented function"
        assert documented_function.__name__ == "documented_function"

    def test_decorator_with_arguments(self):
        """Test decorator works with functions that have arguments"""
        @track_api_request('BTCUSDT', '15', 'kline')
        def api_call_with_args(symbol, limit=100):
            return f"{symbol}-{limit}"
        
        with patch.object(bybit_api_requests_total, 'labels'):
            result = api_call_with_args('ETHUSDT', limit=200)
            assert result == "ETHUSDT-200"

    def test_decorator_with_custom_endpoint(self):
        """Test decorator with custom endpoint"""
        @track_api_request('BTCUSDT', '15', 'trades')
        def fetch_trades():
            return "trades"
        
        with patch.object(bybit_api_requests_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            fetch_trades()
            
            mock_labels.assert_called_with(
                symbol='BTCUSDT',
                interval='15',
                endpoint='trades',
                status='success'
            )


# ==================== CACHE METRICS TESTS ====================


class TestCacheMetrics:
    """Test cache-related metric functions"""

    def test_record_cache_hit(self):
        """Test recording cache hit"""
        with patch.object(bybit_cache_operations_total, 'labels') as mock_ops_labels, \
             patch.object(bybit_candles_fetched_total, 'labels') as mock_fetch_labels:
            
            mock_ops_counter = MagicMock()
            mock_fetch_counter = MagicMock()
            mock_ops_labels.return_value = mock_ops_counter
            mock_fetch_labels.return_value = mock_fetch_counter
            
            record_cache_hit('BTCUSDT', '15', 100)
            
            mock_ops_labels.assert_called_with(operation='get', result='hit')
            mock_ops_counter.inc.assert_called_once()
            
            mock_fetch_labels.assert_called_with(
                symbol='BTCUSDT',
                interval='15',
                source='cache'
            )
            mock_fetch_counter.inc.assert_called_once_with(100)

    def test_record_cache_miss(self):
        """Test recording cache miss"""
        with patch.object(bybit_cache_operations_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            record_cache_miss('ETHUSDT', '60')
            
            mock_labels.assert_called_with(operation='get', result='miss')
            mock_counter.inc.assert_called_once()

    def test_record_cache_set(self):
        """Test recording cache set operation"""
        with patch.object(bybit_cache_operations_total, 'labels') as mock_ops_labels, \
             patch.object(bybit_candles_stored_total, 'labels') as mock_store_labels:
            
            mock_ops_counter = MagicMock()
            mock_store_counter = MagicMock()
            mock_ops_labels.return_value = mock_ops_counter
            mock_store_labels.return_value = mock_store_counter
            
            record_cache_set('BTCUSDT', '15', 50)
            
            mock_ops_labels.assert_called_with(operation='set', result='success')
            mock_ops_counter.inc.assert_called_once()
            
            mock_store_labels.assert_called_with(
                symbol='BTCUSDT',
                interval='15',
                destination='cache'
            )
            mock_store_counter.inc.assert_called_once_with(50)


# ==================== DATA METRICS TESTS ====================


class TestDataMetrics:
    """Test data-related metric functions"""

    def test_record_api_fetch(self):
        """Test recording API fetch"""
        with patch.object(bybit_candles_fetched_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            record_api_fetch('BTCUSDT', '15', 200)
            
            mock_labels.assert_called_with(
                symbol='BTCUSDT',
                interval='15',
                source='api'
            )
            mock_counter.inc.assert_called_once_with(200)

    def test_record_db_store(self):
        """Test recording database storage"""
        with patch.object(bybit_candles_stored_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            record_db_store('ETHUSDT', '60', 150)
            
            mock_labels.assert_called_with(
                symbol='ETHUSDT',
                interval='60',
                destination='db'
            )
            mock_counter.inc.assert_called_once_with(150)


# ==================== ERROR METRICS TESTS ====================


class TestErrorMetrics:
    """Test error-related metric functions"""

    def test_record_rate_limit_hit(self):
        """Test recording rate limit hit"""
        with patch.object(bybit_rate_limit_hits_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            record_rate_limit_hit('BTCUSDT')
            
            mock_labels.assert_called_with(symbol='BTCUSDT')
            mock_counter.inc.assert_called_once()

    def test_record_retry_attempt(self):
        """Test recording retry attempt"""
        with patch.object(bybit_retry_attempts_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            record_retry_attempt('BTCUSDT', '15', 2)
            
            mock_labels.assert_called_with(
                symbol='BTCUSDT',
                interval='15',
                attempt='2'
            )
            mock_counter.inc.assert_called_once()


# ==================== HISTORICAL FETCH TESTS ====================


class TestHistoricalFetchMetrics:
    """Test historical fetch metric function"""

    def test_record_historical_fetch(self):
        """Test recording complete historical fetch"""
        with patch.object(bybit_historical_fetches_total, 'labels') as mock_fetch_labels, \
             patch.object(bybit_historical_fetch_duration_seconds, 'labels') as mock_duration_labels, \
             patch.object(bybit_historical_api_requests_per_fetch, 'labels') as mock_requests_labels, \
             patch.object(bybit_candles_fetched_total, 'labels') as mock_candles_labels:
            
            mock_fetch_counter = MagicMock()
            mock_duration_histogram = MagicMock()
            mock_requests_histogram = MagicMock()
            mock_candles_counter = MagicMock()
            
            mock_fetch_labels.return_value = mock_fetch_counter
            mock_duration_labels.return_value = mock_duration_histogram
            mock_requests_labels.return_value = mock_requests_histogram
            mock_candles_labels.return_value = mock_candles_counter
            
            record_historical_fetch(
                symbol='BTCUSDT',
                interval='15',
                duration=45.5,
                api_requests=10,
                candles_fetched=1000
            )
            
            # Check fetch counter
            mock_fetch_labels.assert_called_with(symbol='BTCUSDT', interval='15')
            mock_fetch_counter.inc.assert_called_once()
            
            # Check duration histogram
            mock_duration_labels.assert_called_with(symbol='BTCUSDT', interval='15')
            mock_duration_histogram.observe.assert_called_once_with(45.5)
            
            # Check API requests histogram
            mock_requests_labels.assert_called_with(symbol='BTCUSDT', interval='15')
            mock_requests_histogram.observe.assert_called_once_with(10)
            
            # Check candles fetched counter
            mock_candles_labels.assert_called_with(
                symbol='BTCUSDT',
                interval='15',
                source='api'
            )
            mock_candles_counter.inc.assert_called_once_with(1000)


# ==================== ADAPTER INFO TESTS ====================


class TestAdapterInfo:
    """Test adapter info initialization"""

    def test_init_adapter_info_default_version(self):
        """Test initializing adapter info with default version"""
        with patch.object(bybit_adapter_info, 'info') as mock_info:
            init_adapter_info()
            
            mock_info.assert_called_once_with({'version': '2.0'})

    def test_init_adapter_info_custom_version(self):
        """Test initializing adapter info with custom version"""
        with patch.object(bybit_adapter_info, 'info') as mock_info:
            init_adapter_info(version='3.0')
            
            mock_info.assert_called_once_with({'version': '3.0'})

    def test_init_adapter_info_with_config(self):
        """Test initializing adapter info with additional config"""
        with patch.object(bybit_adapter_info, 'info') as mock_info:
            init_adapter_info(
                version='2.1',
                cache_enabled=True,
                max_retries=3,
                rate_limit=100
            )
            
            expected_info = {
                'version': '2.1',
                'cache_enabled': 'True',
                'max_retries': '3',
                'rate_limit': '100'
            }
            mock_info.assert_called_once_with(expected_info)

    def test_init_adapter_info_converts_values_to_strings(self):
        """Test that config values are converted to strings"""
        with patch.object(bybit_adapter_info, 'info') as mock_info:
            init_adapter_info(
                int_value=42,
                float_value=3.14,
                bool_value=False,
                none_value=None
            )
            
            call_args = mock_info.call_args[0][0]
            assert call_args['int_value'] == '42'
            assert call_args['float_value'] == '3.14'
            assert call_args['bool_value'] == 'False'
            assert call_args['none_value'] == 'None'


# ==================== INTEGRATION TESTS ====================


class TestMetricsIntegration:
    """Integration tests for metrics tracking"""

    def test_complete_fetch_workflow(self):
        """Test complete workflow of fetching data with metrics"""
        with patch.object(bybit_cache_operations_total, 'labels') as mock_cache, \
             patch.object(bybit_candles_fetched_total, 'labels') as mock_fetched, \
             patch.object(bybit_candles_stored_total, 'labels') as mock_stored:
            
            mock_cache_counter = MagicMock()
            mock_fetched_counter = MagicMock()
            mock_stored_counter = MagicMock()
            
            mock_cache.return_value = mock_cache_counter
            mock_fetched.return_value = mock_fetched_counter
            mock_stored.return_value = mock_stored_counter
            
            # Simulate workflow: cache miss -> API fetch -> cache set -> DB store
            record_cache_miss('BTCUSDT', '15')
            record_api_fetch('BTCUSDT', '15', 100)
            record_cache_set('BTCUSDT', '15', 100)
            record_db_store('BTCUSDT', '15', 100)
            
            # Verify all metrics were called
            assert mock_cache.call_count >= 2  # miss + set
            assert mock_fetched.call_count >= 1  # api fetch only
            assert mock_stored.call_count >= 2  # cache + db

    def test_error_tracking_workflow(self):
        """Test error tracking in API call"""
        @track_api_request('BTCUSDT', '15', 'kline')
        def failing_call():
            raise ConnectionError("Network error")
        
        with patch.object(bybit_api_requests_total, 'labels') as mock_api, \
             patch.object(bybit_errors_total, 'labels') as mock_errors:
            
            mock_api_counter = MagicMock()
            mock_error_counter = MagicMock()
            mock_api.return_value = mock_api_counter
            mock_errors.return_value = mock_error_counter
            
            with pytest.raises(ConnectionError):
                failing_call()
            
            # Verify error was tracked
            assert mock_errors.called
            error_call_args = mock_errors.call_args[1]
            assert error_call_args['error_type'] == 'ConnectionError'

    def test_retry_workflow(self):
        """Test retry attempts tracking"""
        with patch.object(bybit_retry_attempts_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            # Simulate 3 retry attempts
            for attempt in range(1, 4):
                record_retry_attempt('BTCUSDT', '15', attempt)
            
            assert mock_labels.call_count == 3
            assert mock_counter.inc.call_count == 3

    def test_rate_limit_tracking(self):
        """Test rate limit hit tracking"""
        with patch.object(bybit_rate_limit_hits_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            # Simulate multiple rate limit hits
            for _ in range(5):
                record_rate_limit_hit('BTCUSDT')
            
            assert mock_counter.inc.call_count == 5


# ==================== EDGE CASES TESTS ====================


class TestMetricsEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_zero_candles_fetch(self):
        """Test recording fetch with zero candles"""
        with patch.object(bybit_candles_fetched_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            record_api_fetch('BTCUSDT', '15', 0)
            
            mock_counter.inc.assert_called_once_with(0)

    def test_large_candles_count(self):
        """Test recording very large number of candles"""
        with patch.object(bybit_candles_fetched_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            record_api_fetch('BTCUSDT', '15', 1000000)
            
            mock_counter.inc.assert_called_once_with(1000000)

    def test_special_characters_in_symbol(self):
        """Test metrics with special characters in symbol"""
        with patch.object(bybit_cache_operations_total, 'labels') as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter
            
            record_cache_miss('BTC/USDT', '15')
            
            # Should work without errors
            assert mock_labels.called

    def test_empty_config_dict(self):
        """Test init_adapter_info with empty config"""
        with patch.object(bybit_adapter_info, 'info') as mock_info:
            init_adapter_info(version='1.0')
            
            mock_info.assert_called_once_with({'version': '1.0'})

    def test_historical_fetch_zero_duration(self):
        """Test historical fetch with zero duration"""
        with patch.object(bybit_historical_fetch_duration_seconds, 'labels') as mock_labels:
            mock_histogram = MagicMock()
            mock_labels.return_value = mock_histogram
            
            record_historical_fetch('BTCUSDT', '15', 0.0, 5, 100)
            
            mock_histogram.observe.assert_called_once_with(0.0)
