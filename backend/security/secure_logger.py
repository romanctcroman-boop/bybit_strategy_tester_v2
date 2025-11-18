"""
Secure Logger - Enhanced logging with automatic sensitive data removal
Prevents accidental exposure of credentials, tokens, and PII
"""

import logging
import json
import re
from typing import Any, Dict, Optional, List, Set
from datetime import datetime
from pathlib import Path
import hashlib

from backend.security.audit_logger import audit_logger


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter that automatically removes sensitive data.
    
    Detects and redacts:
    - API keys and tokens
    - Passwords
    - Credit card numbers
    - Email addresses
    - IP addresses (optional)
    - JWT tokens
    - Database connection strings
    """
    
    # Patterns for sensitive data
    PATTERNS = {
        'api_key': r'(?i)(api[_-]?key|apikey|access[_-]?key|secret[_-]?key)["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})',
        'jwt': r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
        'password': r'(?i)(password|passwd|pwd)["\']?\s*[:=]\s*["\']?([^\s"\']{4,})',
        'credit_card': r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'ip_address': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        'bearer_token': r'(?i)bearer\s+([A-Za-z0-9_\-\.]{20,})',
        'connection_string': r'(?i)(mongodb|postgresql|mysql|redis)://[^\s"\']+',
    }
    
    # Keys that should be redacted in JSON/dict objects
    SENSITIVE_KEYS = {
        'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
        'access_key', 'secret_key', 'private_key', 'authorization', 'auth',
        'cookie', 'session', 'csrf', 'jwt', 'bearer'
    }
    
    def __init__(self, redact_ip: bool = False, hash_emails: bool = True):
        """
        Initialize filter.
        
        Args:
            redact_ip: Whether to redact IP addresses (useful for PII compliance)
            hash_emails: Hash email addresses instead of full redaction
        """
        super().__init__()
        self.redact_ip = redact_ip
        self.hash_emails = hash_emails
        
        # Compile patterns for performance
        self.compiled_patterns = {
            name: re.compile(pattern)
            for name, pattern in self.PATTERNS.items()
        }
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record to remove sensitive data"""
        # Sanitize message
        if isinstance(record.msg, str):
            record.msg = self._sanitize_string(record.msg)
        
        # Sanitize args
        if record.args:
            if isinstance(record.args, dict):
                record.args = self._sanitize_dict(record.args)
            elif isinstance(record.args, (tuple, list)):
                record.args = tuple(self._sanitize_value(arg) for arg in record.args)
        
        return True
    
    def _sanitize_string(self, text: str) -> str:
        """Remove sensitive data from string"""
        if not text:
            return text
        
        result = text
        
        # Replace API keys and tokens
        result = self.compiled_patterns['api_key'].sub(r'\1=***REDACTED***', result)
        result = self.compiled_patterns['jwt'].sub('***JWT_REDACTED***', result)
        result = self.compiled_patterns['password'].sub(r'\1=***REDACTED***', result)
        result = self.compiled_patterns['bearer_token'].sub('Bearer ***REDACTED***', result)
        result = self.compiled_patterns['connection_string'].sub(r'\1://***REDACTED***', result)
        
        # Replace credit cards
        result = self.compiled_patterns['credit_card'].sub('****-****-****-****', result)
        
        # Handle emails
        if self.hash_emails:
            result = self.compiled_patterns['email'].sub(
                lambda m: self._hash_email(m.group(0)),
                result
            )
        else:
            result = self.compiled_patterns['email'].sub('***EMAIL***', result)
        
        # Handle IPs
        if self.redact_ip:
            result = self.compiled_patterns['ip_address'].sub('***.***.***.***', result)
        
        return result
    
    def _sanitize_dict(self, data: Dict) -> Dict:
        """Remove sensitive data from dictionary"""
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        for key, value in data.items():
            # Check if key is sensitive
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in self.SENSITIVE_KEYS):
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = self._sanitize_value(value)
        
        return sanitized
    
    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize any value (recursive)"""
        if isinstance(value, str):
            return self._sanitize_string(value)
        elif isinstance(value, dict):
            return self._sanitize_dict(value)
        elif isinstance(value, (list, tuple)):
            return type(value)(self._sanitize_value(v) for v in value)
        else:
            return value
    
    def _hash_email(self, email: str) -> str:
        """Hash email for privacy while maintaining traceability"""
        hash_obj = hashlib.sha256(email.encode())
        return f"email_{hash_obj.hexdigest()[:16]}"


class StructuredLogger:
    """
    Structured JSON logger with automatic sensitive data removal.
    
    Features:
    - JSON formatted logs
    - Automatic sensitive data redaction
    - Context enrichment (user_id, request_id, etc.)
    - Multiple output handlers (file, console, remote)
    - Log aggregation support
    """
    
    def __init__(
        self,
        name: str,
        log_file: Optional[Path] = None,
        level: int = logging.INFO,
        redact_ip: bool = False,
        console_output: bool = True
    ):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name
            log_file: Path to log file
            level: Logging level
            redact_ip: Whether to redact IP addresses
            console_output: Whether to output to console
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Add sensitive data filter
        sensitive_filter = SensitiveDataFilter(redact_ip=redact_ip)
        self.logger.addFilter(sensitive_filter)
        
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # File handler - JSON format
        if log_file is None:
            log_file = log_dir / f"{name}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(file_handler)
        
        # Console handler - human readable (optional)
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)  # Only warnings+ to console
            console_handler.setFormatter(HumanReadableFormatter())
            self.logger.addHandler(console_handler)
        
        # Context data (enriches all log entries)
        self.context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Set context data that will be included in all logs"""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear all context data"""
        self.context.clear()
    
    def _enrich_record(self, extra: Optional[Dict] = None) -> Dict:
        """Enrich log record with context"""
        enriched = {
            **self.context,
            **(extra or {})
        }
        return enriched
    
    def debug(self, message: str, **extra):
        """Log debug message"""
        self.logger.debug(message, extra=self._enrich_record(extra))
    
    def info(self, message: str, **extra):
        """Log info message"""
        self.logger.info(message, extra=self._enrich_record(extra))
    
    def warning(self, message: str, **extra):
        """Log warning message"""
        self.logger.warning(message, extra=self._enrich_record(extra))
    
    def error(self, message: str, **extra):
        """Log error message"""
        self.logger.error(message, extra=self._enrich_record(extra))
    
    def critical(self, message: str, **extra):
        """Log critical message"""
        self.logger.critical(message, extra=self._enrich_record(extra))
    
    def security_event(
        self,
        event_type: str,
        severity: str,
        user_id: Optional[str] = None,
        **details
    ):
        """
        Log security event and also send to audit logger.
        
        Args:
            event_type: Type of security event
            severity: Severity level (low, medium, high, critical)
            user_id: User involved in event
            **details: Additional event details
        """
        message = f"Security event: {event_type}"
        
        extra = {
            'event_type': event_type,
            'severity': severity,
            'user_id': user_id,
            **details
        }
        
        # Log based on severity
        if severity in ['high', 'critical']:
            self.error(message, **extra)
        else:
            self.warning(message, **extra)
        
        # Also send to audit logger
        audit_logger.log_security_alert(
            alert_type=event_type,
            severity=severity,
            details=details
        )


class JSONFormatter(logging.Formatter):
    """JSON log formatter"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add location info
        log_data['location'] = {
            'file': record.pathname,
            'line': record.lineno,
            'function': record.funcName
        }
        
        return json.dumps(log_data, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """Human readable log formatter for console"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


# Pre-configured loggers for different components

def get_security_logger() -> StructuredLogger:
    """Get logger for security events"""
    return StructuredLogger(
        name='security',
        level=logging.INFO,
        redact_ip=False  # Keep IPs for security analysis
    )


def get_api_logger() -> StructuredLogger:
    """Get logger for API requests"""
    return StructuredLogger(
        name='api',
        level=logging.INFO,
        redact_ip=True  # Redact IPs for privacy
    )


def get_sandbox_logger() -> StructuredLogger:
    """Get logger for sandbox operations"""
    return StructuredLogger(
        name='sandbox',
        level=logging.INFO,
        redact_ip=False
    )


def get_backtest_logger() -> StructuredLogger:
    """Get logger for backtest operations"""
    return StructuredLogger(
        name='backtest',
        level=logging.INFO,
        redact_ip=True
    )


# Global instances
security_logger = get_security_logger()
api_logger = get_api_logger()
sandbox_logger = get_sandbox_logger()
backtest_logger = get_backtest_logger()
