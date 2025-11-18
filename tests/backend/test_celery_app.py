"""
Test suite for backend.celery_app

Tests Celery app configuration and helper functions.
"""

import os
from unittest.mock import patch

import pytest

from backend.celery_app import (
    _get_bool,
    _get_int,
    celery_app,
)


class TestGetBoolHelper:
    """Test _get_bool() helper function."""

    def test_get_bool_with_none_returns_default(self):
        """_get_bool() returns default when env var is None."""
        with patch.dict(os.environ, {}, clear=False):
            assert _get_bool("NONEXISTENT_VAR", True) is True
            assert _get_bool("NONEXISTENT_VAR", False) is False

    def test_get_bool_with_1_returns_true(self):
        """_get_bool() returns True for '1'."""
        with patch.dict(os.environ, {"TEST_VAR": "1"}, clear=False):
            assert _get_bool("TEST_VAR", False) is True

    def test_get_bool_with_0_returns_false(self):
        """_get_bool() returns False for '0'."""
        with patch.dict(os.environ, {"TEST_VAR": "0"}, clear=False):
            assert _get_bool("TEST_VAR", True) is False

    def test_get_bool_with_true_returns_true(self):
        """_get_bool() returns True for 'true'."""
        with patch.dict(os.environ, {"TEST_VAR": "true"}, clear=False):
            assert _get_bool("TEST_VAR", False) is True

    def test_get_bool_with_false_returns_false(self):
        """_get_bool() returns False for 'false' (not in accepted values)."""
        with patch.dict(os.environ, {"TEST_VAR": "false"}, clear=False):
            # "false" is not in ("1", "true", "yes", "on")
            assert _get_bool("TEST_VAR", True) is False

    def test_get_bool_with_yes_returns_true(self):
        """_get_bool() returns True for 'yes'."""
        with patch.dict(os.environ, {"TEST_VAR": "yes"}, clear=False):
            assert _get_bool("TEST_VAR", False) is True

    def test_get_bool_with_on_returns_true(self):
        """_get_bool() returns True for 'on'."""
        with patch.dict(os.environ, {"TEST_VAR": "on"}, clear=False):
            assert _get_bool("TEST_VAR", False) is True

    def test_get_bool_case_insensitive(self):
        """_get_bool() is case-insensitive."""
        test_cases = ["TRUE", "True", "YES", "Yes", "ON", "On"]
        for value in test_cases:
            with patch.dict(os.environ, {"TEST_VAR": value}, clear=False):
                assert _get_bool("TEST_VAR", False) is True

    def test_get_bool_with_whitespace(self):
        """_get_bool() strips whitespace."""
        with patch.dict(os.environ, {"TEST_VAR": "  1  "}, clear=False):
            assert _get_bool("TEST_VAR", False) is True
        with patch.dict(os.environ, {"TEST_VAR": "  true  "}, clear=False):
            assert _get_bool("TEST_VAR", False) is True

    def test_get_bool_with_invalid_value_returns_false(self):
        """_get_bool() returns False for invalid values."""
        invalid_values = ["invalid", "2", "no", "off", ""]
        for value in invalid_values:
            with patch.dict(os.environ, {"TEST_VAR": value}, clear=False):
                assert _get_bool("TEST_VAR", True) is False

    def test_get_bool_empty_string(self):
        """_get_bool() treats empty string as falsy."""
        with patch.dict(os.environ, {"TEST_VAR": ""}, clear=False):
            assert _get_bool("TEST_VAR", True) is False


class TestGetIntHelper:
    """Test _get_int() helper function."""

    def test_get_int_with_none_returns_default(self):
        """_get_int() returns default when env var is None."""
        with patch.dict(os.environ, {}, clear=False):
            assert _get_int("NONEXISTENT_VAR", 42) == 42
            assert _get_int("NONEXISTENT_VAR", 0) == 0

    def test_get_int_with_valid_integer(self):
        """_get_int() parses valid integer strings."""
        with patch.dict(os.environ, {"TEST_VAR": "123"}, clear=False):
            assert _get_int("TEST_VAR", 0) == 123

    def test_get_int_with_negative_integer(self):
        """_get_int() handles negative integers."""
        with patch.dict(os.environ, {"TEST_VAR": "-456"}, clear=False):
            assert _get_int("TEST_VAR", 0) == -456

    def test_get_int_with_zero(self):
        """_get_int() handles zero."""
        with patch.dict(os.environ, {"TEST_VAR": "0"}, clear=False):
            assert _get_int("TEST_VAR", 99) == 0

    def test_get_int_with_large_number(self):
        """_get_int() handles large integers."""
        with patch.dict(os.environ, {"TEST_VAR": "1000000"}, clear=False):
            assert _get_int("TEST_VAR", 0) == 1000000

    def test_get_int_with_invalid_value_returns_default(self):
        """_get_int() returns default for invalid values."""
        invalid_values = ["abc", "12.34", "1e5", "", "true"]
        for value in invalid_values:
            with patch.dict(os.environ, {"TEST_VAR": value}, clear=False):
                assert _get_int("TEST_VAR", 99) == 99

    def test_get_int_with_whitespace(self):
        """_get_int() handles whitespace in integer strings."""
        with patch.dict(os.environ, {"TEST_VAR": "  42  "}, clear=False):
            # int() strips whitespace automatically
            assert _get_int("TEST_VAR", 0) == 42

    def test_get_int_with_float_string_returns_default(self):
        """_get_int() returns default for float strings."""
        with patch.dict(os.environ, {"TEST_VAR": "3.14"}, clear=False):
            assert _get_int("TEST_VAR", 10) == 10


class TestCeleryAppConfiguration:
    """Test Celery app configuration."""

    def test_celery_app_exists(self):
        """celery_app is initialized."""
        assert celery_app is not None
        assert celery_app.main == "bybit_strategy_tester_v2"

    def test_celery_app_name(self):
        """Celery app has correct name."""
        assert celery_app.main == "bybit_strategy_tester_v2"

    @patch.dict(os.environ, {"CELERY_BROKER_URL": "redis://localhost:6379/0"}, clear=False)
    def test_broker_url_from_env(self):
        """Broker URL can be configured via environment."""
        # Need to reimport to pick up env changes
        import importlib
        import backend.celery_app
        importlib.reload(backend.celery_app)
        from backend.celery_app import celery_app as reloaded_app
        
        # Broker should be set from environment
        assert "redis://" in str(reloaded_app.broker_connection().as_uri())

    def test_celery_app_has_config(self):
        """Celery app has configuration."""
        assert hasattr(celery_app, "conf")
        assert celery_app.conf is not None

    def test_task_default_queue_configuration(self):
        """task_default_queue is configured."""
        # Should have default value
        assert celery_app.conf.task_default_queue == "default"

    def test_task_acks_late_configuration(self):
        """task_acks_late is configured."""
        # Should be True by default
        assert celery_app.conf.task_acks_late is True

    def test_worker_prefetch_multiplier_configuration(self):
        """worker_prefetch_multiplier is configured."""
        # Should have default value
        assert celery_app.conf.worker_prefetch_multiplier == 4

    def test_task_default_retry_delay_configuration(self):
        """task_default_retry_delay is configured."""
        # Should have default value
        assert celery_app.conf.task_default_retry_delay == 5

    def test_task_max_retries_configuration(self):
        """task_max_retries is configured."""
        # Should have default value
        assert celery_app.conf.task_max_retries == 3

    def test_task_annotations_has_rate_limit(self):
        """task_annotations includes rate limit."""
        assert "task_annotations" in celery_app.conf
        assert "*" in celery_app.conf.task_annotations
        assert "rate_limit" in celery_app.conf.task_annotations["*"]
        assert celery_app.conf.task_annotations["*"]["rate_limit"] == "100/s"

    def test_task_always_eager_default_false(self):
        """task_always_eager defaults to False."""
        # Default should be False (tasks run asynchronously)
        assert celery_app.conf.task_always_eager is False


class TestCeleryAppIntegration:
    """Test Celery app integration scenarios."""

    @patch.dict(os.environ, {
        "CELERY_EAGER": "1",
        "CELERY_TASK_DEFAULT_QUEUE": "test_queue",
        "CELERY_ACKS_LATE": "0",
        "CELERY_PREFETCH_MULTIPLIER": "8",
        "CELERY_TASK_DEFAULT_RETRY_DELAY": "10",
        "CELERY_TASK_MAX_RETRIES": "5",
    }, clear=False)
    def test_all_env_vars_applied(self):
        """All environment variables are applied to config."""
        # Reload module to pick up environment changes
        import importlib
        import backend.celery_app
        importlib.reload(backend.celery_app)
        from backend.celery_app import celery_app as reloaded_app
        
        assert reloaded_app.conf.task_always_eager is True
        assert reloaded_app.conf.task_default_queue == "test_queue"
        assert reloaded_app.conf.task_acks_late is False
        assert reloaded_app.conf.worker_prefetch_multiplier == 8
        assert reloaded_app.conf.task_default_retry_delay == 10
        assert reloaded_app.conf.task_max_retries == 5

    def test_celery_app_can_register_tasks(self):
        """Celery app can register tasks."""
        @celery_app.task
        def dummy_task():
            return "test"
        
        assert "test_celery_app.dummy_task" in celery_app.tasks

    def test_celery_app_has_backend(self):
        """Celery app has result backend configured."""
        assert celery_app.backend is not None


class TestCeleryAppEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch.dict(os.environ, {"CELERY_PREFETCH_MULTIPLIER": "0"}, clear=False)
    def test_zero_prefetch_multiplier(self):
        """Prefetch multiplier can be set to 0."""
        import importlib
        import backend.celery_app
        importlib.reload(backend.celery_app)
        from backend.celery_app import celery_app as reloaded_app
        
        assert reloaded_app.conf.worker_prefetch_multiplier == 0

    @patch.dict(os.environ, {"CELERY_TASK_MAX_RETRIES": "0"}, clear=False)
    def test_zero_max_retries(self):
        """Max retries can be set to 0 (no retries)."""
        import importlib
        import backend.celery_app
        importlib.reload(backend.celery_app)
        from backend.celery_app import celery_app as reloaded_app
        
        assert reloaded_app.conf.task_max_retries == 0

    @patch.dict(os.environ, {"CELERY_TASK_DEFAULT_RETRY_DELAY": "1"}, clear=False)
    def test_minimal_retry_delay(self):
        """Retry delay can be set to 1 second."""
        import importlib
        import backend.celery_app
        importlib.reload(backend.celery_app)
        from backend.celery_app import celery_app as reloaded_app
        
        assert reloaded_app.conf.task_default_retry_delay == 1

    @patch.dict(os.environ, {"CELERY_TASK_DEFAULT_QUEUE": ""}, clear=False)
    def test_empty_queue_name(self):
        """Empty queue name is accepted."""
        import importlib
        import backend.celery_app
        importlib.reload(backend.celery_app)
        from backend.celery_app import celery_app as reloaded_app
        
        assert reloaded_app.conf.task_default_queue == ""

    @patch.dict(os.environ, {
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://",
    }, clear=False)
    def test_memory_backend_for_testing(self):
        """Memory backend can be used for testing."""
        import importlib
        import backend.celery_app
        importlib.reload(backend.celery_app)
        from backend.celery_app import celery_app as reloaded_app
        
        # Memory broker should be configured
        assert "memory" in str(reloaded_app.broker_connection().as_uri())

    def test_celery_app_has_all_attribute(self):
        """Module exports __all__ with celery_app."""
        from backend import celery_app as module
        assert hasattr(module, "__all__")
        assert "celery_app" in module.__all__

    @patch.dict(os.environ, {"CELERY_PREFETCH_MULTIPLIER": "999999"}, clear=False)
    def test_very_large_prefetch_multiplier(self):
        """Very large prefetch multiplier is accepted."""
        import importlib
        import backend.celery_app
        importlib.reload(backend.celery_app)
        from backend.celery_app import celery_app as reloaded_app
        
        assert reloaded_app.conf.worker_prefetch_multiplier == 999999

    @patch.dict(os.environ, {"CELERY_TASK_MAX_RETRIES": "-1"}, clear=False)
    def test_negative_max_retries(self):
        """Negative max retries is parsed as integer."""
        import importlib
        import backend.celery_app
        importlib.reload(backend.celery_app)
        from backend.celery_app import celery_app as reloaded_app
        
        assert reloaded_app.conf.task_max_retries == -1
