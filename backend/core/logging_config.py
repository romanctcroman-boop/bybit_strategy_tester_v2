"""
Logging Configuration
Centralized logging configuration for the backend

Supports both loguru (preferred) and standard logging for backward compatibility.
New code should use: from loguru import logger
Legacy code can use: from backend.core.logging_config import get_logger
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from loguru import Logger

# Type alias for loguru logger
LoguruLogger = Optional["Logger"]

try:
    from loguru import logger as loguru_logger

    LOGURU_AVAILABLE = True
except ImportError:
    LOGURU_AVAILABLE = False
    loguru_logger: LoguruLogger = None  # type: ignore[no-redef]

# Default log format
DEFAULT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
)
SIMPLE_FORMAT = "%(levelname)s: %(message)s"

# Loguru format (cleaner)
LOGURU_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    format_string: str | None = None,
    enable_console: bool = True,
) -> None:
    """
    Configure logging for the application

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file logging
        format_string: Custom format string (uses DEFAULT_FORMAT if None)
        enable_console: Whether to enable console logging
    """
    # Convert string level to logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        format_string or DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_log_level(level: str) -> None:
    """
    Change the log level for all handlers

    Args:
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    for handler in root_logger.handlers:
        handler.setLevel(numeric_level)

    # Also update loguru if available
    if LOGURU_AVAILABLE:
        loguru_logger.remove()
        loguru_logger.add(sys.stderr, level=level.upper(), format=LOGURU_FORMAT)


def setup_loguru(
    level: str = "INFO",
    log_file: Path | None = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """
    Configure loguru for the application (preferred over standard logging)

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file logging
        rotation: When to rotate the log file
        retention: How long to keep old log files
    """
    if not LOGURU_AVAILABLE:
        # Fall back to standard logging
        setup_logging(level=level, log_file=log_file)
        return

    # Remove default handler
    loguru_logger.remove()

    # Add console handler
    loguru_logger.add(
        sys.stderr,
        level=level.upper(),
        format=LOGURU_FORMAT,
        colorize=True,
    )

    # Add file handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        loguru_logger.add(
            log_file,
            level=level.upper(),
            format=LOGURU_FORMAT.replace("<green>", "")
            .replace("</green>", "")
            .replace("<level>", "")
            .replace("</level>", "")
            .replace("<cyan>", "")
            .replace("</cyan>", ""),
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
        )


# Intercept standard logging and redirect to loguru
class InterceptHandler(logging.Handler):
    """Handler to intercept standard logging calls and redirect to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        if not LOGURU_AVAILABLE or loguru_logger is None:
            return

        # Get corresponding Loguru level if it exists
        try:
            level: str | int = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame = sys._getframe(6)
        depth = 6
        while frame.f_back is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def enable_loguru_intercept() -> None:
    """
    Enable interception of standard logging calls to redirect to loguru.
    Call this to unify all logging output through loguru.
    """
    if not LOGURU_AVAILABLE:
        return

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


# Configure default logging on module import
setup_logging(
    level="INFO",
    enable_console=True,
)

# Setup loguru if available
if LOGURU_AVAILABLE:
    setup_loguru(level="INFO")


__all__ = [
    "DEFAULT_FORMAT",
    "LOGURU_AVAILABLE",
    "LOGURU_FORMAT",
    "SIMPLE_FORMAT",
    "enable_loguru_intercept",
    "get_logger",
    "set_log_level",
    "setup_logging",
    "setup_loguru",
]
