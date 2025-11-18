"""
Tests for backend.core.logging_config module.

Tests cover:
- JSONFormatter log formatting with various fields
- setup_logging with different configurations
- get_logger function
"""

import logging
import json
import sys
from io import StringIO
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from backend.core.logging_config import (
    JSONFormatter,
    setup_logging,
    get_logger
)


class TestJSONFormatter:
    """Tests for JSONFormatter class."""
    
    def test_basic_log_formatting(self):
        """Test basic log record formatting to JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['level'] == 'INFO'
        assert log_data['logger'] == 'test.logger'
        assert log_data['module'] == 'test_module'
        assert log_data['function'] == 'test_function'
        assert log_data['line'] == 42
        assert log_data['message'] == 'Test message'
        assert 'timestamp' in log_data
        assert log_data['timestamp'].endswith('Z')
    
    def test_log_with_exception(self):
        """Test log formatting with exception info."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['message'] == 'Error occurred'
        assert 'exception' in log_data
        assert 'ValueError: Test error' in log_data['exception']
    
    def test_log_with_trading_context(self):
        """Test log formatting with trading-specific fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="trading.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=20,
            msg="Data fetched",
            args=(),
            exc_info=None
        )
        record.module = "data_service"
        record.funcName = "fetch_candles"
        record.symbol = "BTCUSDT"
        record.interval = "1h"
        record.candles_count = 100
        record.duration_ms = 250
        record.api_requests = 2
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['symbol'] == 'BTCUSDT'
        assert log_data['interval'] == '1h'
        assert log_data['candles_count'] == 100
        assert log_data['duration_ms'] == 250
        assert log_data['api_requests'] == 2
    
    def test_log_with_error_context(self):
        """Test log formatting with error-specific fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="api.logger",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=30,
            msg="API error",
            args=(),
            exc_info=None
        )
        record.module = "bybit_api"
        record.funcName = "request"
        record.error_type = "RateLimitError"
        record.status_code = 429
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['error_type'] == 'RateLimitError'
        assert log_data['status_code'] == 429
    
    def test_log_without_extra_fields(self):
        """Test log formatting without optional fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="simple.logger",
            level=logging.DEBUG,
            pathname="/test/path.py",
            lineno=5,
            msg="Debug message",
            args=(),
            exc_info=None
        )
        record.module = "test"
        record.funcName = "test_func"
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        # Should only have basic fields
        assert 'symbol' not in log_data
        assert 'interval' not in log_data
        assert 'error_type' not in log_data
        assert log_data['message'] == 'Debug message'


class TestSetupLogging:
    """Tests for setup_logging function."""
    
    def test_setup_with_defaults(self):
        """Test logging setup with default parameters."""
        setup_logging()
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) >= 1
        
        # Check console handler exists
        console_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(console_handlers) > 0
    
    def test_setup_with_debug_level(self):
        """Test logging setup with DEBUG level."""
        setup_logging(log_level="DEBUG")
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
    
    def test_setup_with_warning_level(self):
        """Test logging setup with WARNING level."""
        setup_logging(log_level="WARNING")
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING
    
    def test_setup_with_json_format(self):
        """Test logging setup with JSON formatting."""
        setup_logging(json_format=True)
        
        root_logger = logging.getLogger()
        console_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
        
        assert len(console_handlers) > 0
        handler = console_handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)
    
    def test_setup_with_human_readable_format(self):
        """Test logging setup with human-readable formatting."""
        setup_logging(json_format=False)
        
        root_logger = logging.getLogger()
        console_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
        
        assert len(console_handlers) > 0
        handler = console_handlers[0]
        assert not isinstance(handler.formatter, JSONFormatter)
    
    def test_setup_with_file_logging(self, tmp_path):
        """Test logging setup with file output."""
        log_file = tmp_path / "test.log"
        setup_logging(log_file=str(log_file))
        
        root_logger = logging.getLogger()
        
        # Check file handler exists
        from logging.handlers import RotatingFileHandler
        file_handlers = [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) > 0
        
        # Test writing to file
        logger = logging.getLogger("test")
        logger.info("Test message")
        
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content
    
    def test_setup_with_file_json_format(self, tmp_path):
        """Test logging setup with JSON format to file."""
        log_file = tmp_path / "test_json.log"
        setup_logging(log_file=str(log_file), json_format=True)
        
        logger = logging.getLogger("test")
        logger.info("JSON test message")
        
        assert log_file.exists()
        content = log_file.read_text()
        
        # Should contain JSON formatted log
        lines = [line for line in content.split('\n') if line.strip()]
        assert len(lines) > 0
        
        # Parse first log entry (should be valid JSON)
        log_data = json.loads(lines[0])
        assert 'timestamp' in log_data
        assert 'level' in log_data
    
    def test_setup_creates_log_directory(self, tmp_path):
        """Test that setup_logging creates log directory if it doesn't exist."""
        log_file = tmp_path / "logs" / "nested" / "test.log"
        setup_logging(log_file=str(log_file))
        
        assert log_file.parent.exists()
        assert log_file.parent.is_dir()
    
    def test_setup_removes_existing_handlers(self):
        """Test that setup_logging removes existing handlers."""
        root_logger = logging.getLogger()
        
        # Add dummy handler
        dummy_handler = logging.StreamHandler()
        root_logger.addHandler(dummy_handler)
        initial_handler_count = len(root_logger.handlers)
        
        # Setup logging should replace handlers
        setup_logging()
        
        # Handler count should change (old removed, new added)
        assert dummy_handler not in root_logger.handlers
    
    def test_setup_with_invalid_log_level(self):
        """Test setup_logging with invalid log level (should default to INFO)."""
        setup_logging(log_level="INVALID")
        
        root_logger = logging.getLogger()
        # Should default to INFO
        assert root_logger.level == logging.INFO
    
    def test_file_rotation_config(self, tmp_path):
        """Test that file handler has correct rotation settings."""
        log_file = tmp_path / "rotating.log"
        setup_logging(log_file=str(log_file))
        
        root_logger = logging.getLogger()
        from logging.handlers import RotatingFileHandler
        file_handlers = [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]
        
        assert len(file_handlers) > 0
        handler = file_handlers[0]
        
        # Check rotation settings
        assert handler.maxBytes == 10 * 1024 * 1024  # 10 MB
        assert handler.backupCount == 5


class TestGetLogger:
    """Tests for get_logger function."""
    
    def test_get_logger_basic(self):
        """Test getting a logger instance."""
        logger = get_logger("test.module")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"
    
    def test_get_logger_different_names(self):
        """Test getting loggers with different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        
        assert logger1.name == "module1"
        assert logger2.name == "module2"
        assert logger1 is not logger2
    
    def test_get_logger_same_name_returns_same_instance(self):
        """Test that getting logger with same name returns same instance."""
        logger1 = get_logger("same.module")
        logger2 = get_logger("same.module")
        
        assert logger1 is logger2
    
    def test_get_logger_inherits_root_config(self):
        """Test that created logger inherits root configuration."""
        setup_logging(log_level="DEBUG")
        logger = get_logger("test.inherit")
        
        # Should inherit DEBUG level from root (either directly or via parent chain)
        root_logger = logging.getLogger()
        assert logger.level == 0 or logger.level == root_logger.level
        
        # Logger should be in the root logger hierarchy
        current = logger
        while current.parent:
            current = current.parent
        assert current is root_logger or current.name == 'root'


class TestIntegration:
    """Integration tests for logging system."""
    
    def test_full_logging_workflow(self, tmp_path):
        """Test complete logging workflow from setup to output."""
        log_file = tmp_path / "integration.log"
        
        # Setup logging
        setup_logging(log_level="INFO", log_file=str(log_file), json_format=True)
        
        # Get logger and log messages
        logger = get_logger("integration.test")
        logger.info("Integration test message")
        logger.warning("Warning message")
        
        # Verify file exists and contains logs
        assert log_file.exists()
        content = log_file.read_text()
        
        lines = [line for line in content.split('\n') if line.strip()]
        assert len(lines) >= 2
        
        # Parse and verify JSON logs
        for line in lines[:2]:
            log_data = json.loads(line)
            assert 'timestamp' in log_data
            assert log_data['level'] in ['INFO', 'WARNING']
    
    def test_logging_with_extra_context(self, tmp_path):
        """Test logging with trading context fields."""
        log_file = tmp_path / "context.log"
        setup_logging(log_file=str(log_file), json_format=True)
        
        logger = get_logger("context.test")
        logger.info(
            "Trade executed",
            extra={
                'symbol': 'ETHUSDT',
                'interval': '5m',
                'candles_count': 50
            }
        )
        
        content = log_file.read_text()
        lines = [line for line in content.split('\n') if line.strip()]
        
        # Find our log entry
        trade_log = None
        for line in lines:
            data = json.loads(line)
            if 'Trade executed' in data.get('message', ''):
                trade_log = data
                break
        
        assert trade_log is not None
        assert trade_log['symbol'] == 'ETHUSDT'
        assert trade_log['interval'] == '5m'
        assert trade_log['candles_count'] == 50
