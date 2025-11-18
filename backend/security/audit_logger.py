"""
Audit Logger - Tracks all operations with API keys and security events
Provides security monitoring and compliance logging
"""
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import re


class AuditLogger:
    """
    Security audit logger for API key operations and security events.
    
    Logs all:
    - Key access attempts
    - Key modifications
    - Decryption failures
    - Configuration changes
    - Authentication events
    - Authorization events
    - Security incidents
    """
    
    # Sensitive patterns to sanitize
    SENSITIVE_PATTERNS = [
        (r'(?i)(password|passwd|pwd)["\']?\s*[:=]\s*["\']?([^\s"\']{4,})', r'\1=***REDACTED***'),
        (r'(?i)(api[_-]?key|apikey|token)["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})', r'\1=***REDACTED***'),
        (r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', '***JWT_REDACTED***'),
    ]
    
    def __init__(self):
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup audit logger with file and console handlers"""
        logger = logging.getLogger('api_keys_audit')
        logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if logger.handlers:
            return logger
        
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # File handler - JSON format for parsing
        log_file = log_dir / "api_keys_audit.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Console handler - human readable
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)  # Only warnings/errors to console
        
        # Formatters
        file_formatter = logging.Formatter('%(message)s')
        console_formatter = logging.Formatter(
            '%(asctime)s - AUDIT - %(levelname)s - %(message)s'
        )
        
        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize sensitive data from value"""
        if isinstance(value, str):
            result = value
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                result = re.sub(pattern, replacement, result)
            return result
        elif isinstance(value, dict):
            return {k: self._sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            return type(value)(self._sanitize_value(v) for v in value)
        else:
            return value
    
    def _create_log_entry(
        self,
        event: str,
        key_name: Optional[str] = None,
        user: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create structured log entry with automatic sanitization"""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event,
            "success": success,
        }
        
        if key_name:
            entry["key_name"] = key_name
        
        if user:
            entry["user"] = user
        
        if ip_address:
            entry["ip_address"] = ip_address
        
        if correlation_id:
            entry["correlation_id"] = correlation_id
        
        if details:
            # Sanitize details before logging
            entry["details"] = self._sanitize_value(details)
        
        return entry
    
    def log_key_access(
        self,
        key_name: str,
        success: bool = True,
        user: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """
        Log API key access attempt.
        
        Args:
            key_name: Name of the key accessed
            success: Whether access was successful
            user: User who accessed the key
            ip_address: IP address of request
        """
        entry = self._create_log_entry(
            event="key_access",
            key_name=key_name,
            user=user,
            success=success,
            ip_address=ip_address
        )
        
        if success:
            self.logger.info(json.dumps(entry))
        else:
            self.logger.warning(json.dumps(entry))
    
    def log_key_creation(
        self,
        key_name: str,
        user: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log creation of new API key"""
        entry = self._create_log_entry(
            event="key_created",
            key_name=key_name,
            user=user,
            ip_address=ip_address
        )
        self.logger.info(json.dumps(entry))
    
    def log_key_update(
        self,
        key_name: str,
        user: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log update of existing API key"""
        entry = self._create_log_entry(
            event="key_updated",
            key_name=key_name,
            user=user,
            ip_address=ip_address
        )
        self.logger.info(json.dumps(entry))
    
    def log_key_rotation(
        self,
        key_name: str,
        user: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log key rotation event"""
        entry = self._create_log_entry(
            event="key_rotated",
            key_name=key_name,
            user=user,
            ip_address=ip_address
        )
        self.logger.info(json.dumps(entry))
    
    def log_key_deletion(
        self,
        key_name: str,
        user: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log key deletion"""
        entry = self._create_log_entry(
            event="key_deleted",
            key_name=key_name,
            user=user,
            ip_address=ip_address
        )
        self.logger.warning(json.dumps(entry))
    
    def log_decryption_failure(
        self,
        key_name: str,
        error: str,
        user: Optional[str] = None
    ):
        """Log failed decryption attempt"""
        entry = self._create_log_entry(
            event="decryption_failed",
            key_name=key_name,
            user=user,
            success=False,
            details={"error": error}
        )
        self.logger.error(json.dumps(entry))
    
    def log_master_key_access(
        self,
        success: bool = True,
        environment: Optional[str] = None
    ):
        """Log master key access"""
        entry = self._create_log_entry(
            event="master_key_access",
            success=success,
            details={"environment": environment} if environment else None
        )
        
        if success:
            self.logger.info(json.dumps(entry))
        else:
            self.logger.error(json.dumps(entry))
    
    def log_config_change(
        self,
        change_type: str,
        details: Dict[str, Any],
        user: Optional[str] = None
    ):
        """Log configuration change"""
        entry = self._create_log_entry(
            event="config_changed",
            user=user,
            details={
                "change_type": change_type,
                **details
            }
        )
        self.logger.info(json.dumps(entry))
    
    def log_security_alert(
        self,
        alert_type: str,
        severity: str,
        details: Dict[str, Any]
    ):
        """Log security alert"""
        entry = self._create_log_entry(
            event="security_alert",
            success=False,
            details={
                "alert_type": alert_type,
                "severity": severity,
                **details
            }
        )
        
        if severity in ["high", "critical"]:
            self.logger.error(json.dumps(entry))
        else:
            self.logger.warning(json.dumps(entry))
    
    # === NEW METHODS FOR EXTENDED LOGGING ===
    
    def log_authentication_attempt(
        self,
        user: str,
        success: bool,
        method: str = "jwt",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Log authentication attempt.
        
        Args:
            user: Username or user ID
            success: Whether authentication succeeded
            method: Authentication method (jwt, api_key, oauth, etc.)
            ip_address: Client IP address
            user_agent: Client user agent
            correlation_id: Request correlation ID
        """
        entry = self._create_log_entry(
            event="authentication_attempt",
            user=user,
            success=success,
            ip_address=ip_address,
            correlation_id=correlation_id,
            details={
                "method": method,
                "user_agent": user_agent
            }
        )
        
        if success:
            self.logger.info(json.dumps(entry))
        else:
            self.logger.warning(json.dumps(entry))
    
    def log_authorization_check(
        self,
        user: str,
        resource: str,
        action: str,
        success: bool,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Log authorization check.
        
        Args:
            user: Username or user ID
            resource: Resource being accessed
            action: Action being performed
            success: Whether authorization succeeded
            ip_address: Client IP address
            correlation_id: Request correlation ID
        """
        entry = self._create_log_entry(
            event="authorization_check",
            user=user,
            success=success,
            ip_address=ip_address,
            correlation_id=correlation_id,
            details={
                "resource": resource,
                "action": action
            }
        )
        
        if success:
            self.logger.info(json.dumps(entry))
        else:
            self.logger.warning(json.dumps(entry))
    
    def log_rate_limit_hit(
        self,
        user: Optional[str] = None,
        ip_address: Optional[str] = None,
        endpoint: Optional[str] = None,
        limit: Optional[int] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Log rate limit hit.
        
        Args:
            user: Username or user ID
            ip_address: Client IP address
            endpoint: API endpoint
            limit: Rate limit threshold
            correlation_id: Request correlation ID
        """
        entry = self._create_log_entry(
            event="rate_limit_hit",
            user=user,
            success=False,
            ip_address=ip_address,
            correlation_id=correlation_id,
            details={
                "endpoint": endpoint,
                "limit": limit
            }
        )
        
        self.logger.warning(json.dumps(entry))
    
    def log_token_refresh(
        self,
        user: str,
        token_type: str = "access",
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Log token refresh event.
        
        Args:
            user: Username or user ID
            token_type: Type of token (access, refresh, api)
            ip_address: Client IP address
            correlation_id: Request correlation ID
        """
        entry = self._create_log_entry(
            event="token_refresh",
            user=user,
            success=True,
            ip_address=ip_address,
            correlation_id=correlation_id,
            details={
                "token_type": token_type
            }
        )
        
        self.logger.info(json.dumps(entry))
    
    def log_token_revocation(
        self,
        user: str,
        token_type: str,
        reason: str,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Log token revocation.
        
        Args:
            user: Username or user ID
            token_type: Type of token (access, refresh, api)
            reason: Reason for revocation
            ip_address: Client IP address
            correlation_id: Request correlation ID
        """
        entry = self._create_log_entry(
            event="token_revocation",
            user=user,
            success=True,
            ip_address=ip_address,
            correlation_id=correlation_id,
            details={
                "token_type": token_type,
                "reason": reason
            }
        )
        
        self.logger.warning(json.dumps(entry))
    
    def log_suspicious_activity(
        self,
        activity_type: str,
        severity: str,
        user: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Log suspicious activity.
        
        Args:
            activity_type: Type of suspicious activity
            severity: Severity level (low, medium, high, critical)
            user: Username or user ID
            ip_address: Client IP address
            details: Additional details
            correlation_id: Request correlation ID
        """
        entry = self._create_log_entry(
            event="suspicious_activity",
            user=user,
            success=False,
            ip_address=ip_address,
            correlation_id=correlation_id,
            details={
                "activity_type": activity_type,
                "severity": severity,
                **(details or {})
            }
        )
        
        if severity in ["high", "critical"]:
            self.logger.error(json.dumps(entry))
        else:
            self.logger.warning(json.dumps(entry))
    
    def log_sandbox_execution(
        self,
        user: str,
        sandbox_id: str,
        success: bool,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Log sandbox code execution.
        
        Args:
            user: Username or user ID
            sandbox_id: Sandbox container ID
            success: Whether execution succeeded
            duration_ms: Execution duration in milliseconds
            error: Error message if failed
            correlation_id: Request correlation ID
        """
        entry = self._create_log_entry(
            event="sandbox_execution",
            user=user,
            success=success,
            correlation_id=correlation_id,
            details={
                "sandbox_id": sandbox_id,
                "duration_ms": duration_ms,
                "error": error
            }
        )
        
        if success:
            self.logger.info(json.dumps(entry))
        else:
            self.logger.warning(json.dumps(entry))


# Singleton instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get singleton AuditLogger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# Convenient alias
audit_logger = get_audit_logger()
