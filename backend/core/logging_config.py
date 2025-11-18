"""
Structured logging configuration for production.

Features:
- JSON formatted logs for easy parsing
- Contextual information (symbol, interval, etc.)
- Different log levels for different environments
- Rotation and archival support
"""

import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        """
        log_data: Dict[str, Any] = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        if hasattr(record, 'symbol'):
            log_data['symbol'] = record.symbol
        if hasattr(record, 'interval'):
            log_data['interval'] = record.interval
        if hasattr(record, 'candles_count'):
            log_data['candles_count'] = record.candles_count
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'api_requests'):
            log_data['api_requests'] = record.api_requests
        if hasattr(record, 'error_type'):
            log_data['error_type'] = record.error_type
        if hasattr(record, 'status_code'):
            log_data['status_code'] = record.status_code
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
    json_format: bool = False
) -> None:
    """
    Setup application logging.
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        json_format: Use JSON formatting (True for production)
    """
    # Convert string to log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    if json_format:
        # JSON formatter for production
        console_handler.setFormatter(JSONFormatter())
    else:
        # Human-readable formatter for development
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
    
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Rotating file handler
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        
        if json_format:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
        
        root_logger.addHandler(file_handler)
    
    # Log startup message
    logging.info(
        "Logging configured",
        extra={
            'log_level': log_level,
            'json_format': json_format,
            'log_file': log_file
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance with proper configuration.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
