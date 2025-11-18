"""
Tests for Secure Logging System
Tests sensitive data filtering, structured logging, and audit trail
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from backend.security.secure_logger import (
    SensitiveDataFilter,
    StructuredLogger,
    security_logger,
    api_logger
)
from backend.security.audit_logger import audit_logger


class TestSensitiveDataFilter:
    """Test sensitive data filtering"""
    
    def test_filter_api_key(self):
        """Test API key redaction"""
        filter_obj = SensitiveDataFilter()
        
        text = "API_KEY=sk_live_1234567890abcdefghijk"
        result = filter_obj._sanitize_string(text)
        
        assert "sk_live_1234567890abcdefghijk" not in result
        assert "***REDACTED***" in result
    
    def test_filter_jwt_token(self):
        """Test JWT token redaction"""
        filter_obj = SensitiveDataFilter()
        
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = filter_obj._sanitize_string(text)
        
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "***JWT_REDACTED***" in result
    
    def test_filter_password(self):
        """Test password redaction"""
        filter_obj = SensitiveDataFilter()
        
        text = "password=MySecretPass123"
        result = filter_obj._sanitize_string(text)
        
        assert "MySecretPass123" not in result
        assert "***REDACTED***" in result
    
    def test_filter_credit_card(self):
        """Test credit card redaction"""
        filter_obj = SensitiveDataFilter()
        
        text = "Card: 4532-1234-5678-9010"
        result = filter_obj._sanitize_string(text)
        
        assert "4532-1234-5678-9010" not in result
        assert "****-****-****-****" in result
    
    def test_filter_email_hash(self):
        """Test email hashing"""
        filter_obj = SensitiveDataFilter(hash_emails=True)
        
        text = "Email: user@example.com"
        result = filter_obj._sanitize_string(text)
        
        assert "user@example.com" not in result
        assert "email_" in result  # Hashed email
    
    def test_filter_email_redact(self):
        """Test email full redaction"""
        filter_obj = SensitiveDataFilter(hash_emails=False)
        
        text = "Email: user@example.com"
        result = filter_obj._sanitize_string(text)
        
        assert "user@example.com" not in result
        assert "***EMAIL***" in result
    
    def test_filter_ip_address(self):
        """Test IP address redaction"""
        filter_obj = SensitiveDataFilter(redact_ip=True)
        
        text = "IP: 192.168.1.100"
        result = filter_obj._sanitize_string(text)
        
        assert "192.168.1.100" not in result
        assert "***.***.***" in result
    
    def test_filter_connection_string(self):
        """Test connection string redaction"""
        filter_obj = SensitiveDataFilter()
        
        text = "mongodb://user:pass@localhost:27017/db"
        result = filter_obj._sanitize_string(text)
        
        assert "user:pass" not in result
        assert "***REDACTED***" in result
    
    def test_filter_dict(self):
        """Test dictionary filtering"""
        filter_obj = SensitiveDataFilter()
        
        data = {
            "username": "john",
            "password": "secret123",
            "api_key": "sk_live_abc123",
            "email": "john@example.com"
        }
        
        result = filter_obj._sanitize_dict(data)
        
        assert result["username"] == "john"
        assert result["password"] == "***REDACTED***"
        assert result["api_key"] == "***REDACTED***"
        assert "john@example.com" not in str(result)
    
    def test_filter_nested_dict(self):
        """Test nested dictionary filtering"""
        filter_obj = SensitiveDataFilter()
        
        data = {
            "user": {
                "name": "john",
                "credentials": {
                    "password": "secret123",
                    "token": "abc123xyz"
                }
            }
        }
        
        result = filter_obj._sanitize_dict(data)
        
        assert result["user"]["name"] == "john"
        assert result["user"]["credentials"]["password"] == "***REDACTED***"
        assert result["user"]["credentials"]["token"] == "***REDACTED***"
    
    def test_filter_list(self):
        """Test list filtering"""
        filter_obj = SensitiveDataFilter()
        
        data = ["username", "password=secret123", "api_key=abc123"]
        result = filter_obj._sanitize_value(data)
        
        assert result[0] == "username"
        assert "secret123" not in result[1]
        assert "abc123" not in result[2]
    
    def test_no_false_positives(self):
        """Test that normal text is not filtered"""
        filter_obj = SensitiveDataFilter()
        
        text = "This is a normal message with no sensitive data"
        result = filter_obj._sanitize_string(text)
        
        assert result == text


class TestStructuredLogger:
    """Test structured logging"""
    
    def test_logger_creation(self):
        """Test logger creation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger(
                name="test_logger",
                log_file=log_file,
                console_output=False
            )
            
            assert logger.logger.name == "test_logger"
            assert log_file.parent.exists()
    
    def test_info_logging(self):
        """Test info logging"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger(
                name="test_logger",
                log_file=log_file,
                console_output=False
            )
            
            logger.info("Test message", user_id="user123", action="test")
            
            # Read log file
            with open(log_file, 'r') as f:
                log_entry = json.loads(f.readline())
            
            assert log_entry["message"] == "Test message"
            assert log_entry["level"] == "INFO"
    
    def test_sensitive_data_auto_removal(self):
        """Test automatic sensitive data removal"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger(
                name="test_logger",
                log_file=log_file,
                console_output=False
            )
            
            logger.info(
                "User login",
                password="secret123",
                api_key="sk_live_abc123"
            )
            
            # Read log file
            with open(log_file, 'r') as f:
                content = f.read()
            
            assert "secret123" not in content
            assert "sk_live_abc123" not in content
            assert "***REDACTED***" in content
    
    def test_context_enrichment(self):
        """Test context enrichment"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger(
                name="test_logger",
                log_file=log_file,
                console_output=False
            )
            
            logger.set_context(request_id="req123", user_id="user456")
            logger.info("Test message")
            
            # Read log file
            with open(log_file, 'r') as f:
                log_entry = json.loads(f.readline())
            
            # Context should be in log entry (in extra field or similar)
            content = json.dumps(log_entry)
            assert "req123" in content or "user456" in content
    
    def test_security_event_logging(self):
        """Test security event logging"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger(
                name="test_logger",
                log_file=log_file,
                console_output=False
            )
            
            logger.security_event(
                event_type="failed_login",
                severity="medium",
                user_id="user123",
                ip_address="192.168.1.1"
            )
            
            # Read log file
            with open(log_file, 'r') as f:
                log_entry = json.loads(f.readline())
            
            assert "failed_login" in json.dumps(log_entry)
            assert log_entry["level"] == "WARNING"  # Medium severity


class TestAuditLoggerExtensions:
    """Test audit logger new methods"""
    
    def test_log_authentication_attempt(self):
        """Test authentication logging"""
        # Mock logger
        with patch.object(audit_logger.logger, 'info') as mock_info:
            audit_logger.log_authentication_attempt(
                user="user123",
                success=True,
                method="jwt",
                ip_address="192.168.1.1"
            )
            
            mock_info.assert_called_once()
            log_data = json.loads(mock_info.call_args[0][0])
            
            assert log_data["event"] == "authentication_attempt"
            assert log_data["user"] == "user123"
            assert log_data["success"] is True
    
    def test_log_authorization_check(self):
        """Test authorization logging"""
        with patch.object(audit_logger.logger, 'info') as mock_info:
            audit_logger.log_authorization_check(
                user="user123",
                resource="backtest",
                action="create",
                success=True
            )
            
            mock_info.assert_called_once()
            log_data = json.loads(mock_info.call_args[0][0])
            
            assert log_data["event"] == "authorization_check"
            assert log_data["details"]["resource"] == "backtest"
            assert log_data["details"]["action"] == "create"
    
    def test_log_rate_limit_hit(self):
        """Test rate limit logging"""
        with patch.object(audit_logger.logger, 'warning') as mock_warning:
            audit_logger.log_rate_limit_hit(
                user="user123",
                endpoint="/api/backtest",
                limit=60
            )
            
            mock_warning.assert_called_once()
            log_data = json.loads(mock_warning.call_args[0][0])
            
            assert log_data["event"] == "rate_limit_hit"
            assert log_data["success"] is False
    
    def test_log_token_refresh(self):
        """Test token refresh logging"""
        with patch.object(audit_logger.logger, 'info') as mock_info:
            audit_logger.log_token_refresh(
                user="user123",
                token_type="access"
            )
            
            mock_info.assert_called_once()
            log_data = json.loads(mock_info.call_args[0][0])
            
            assert log_data["event"] == "token_refresh"
            assert log_data["details"]["token_type"] == "access"
    
    def test_log_token_revocation(self):
        """Test token revocation logging"""
        with patch.object(audit_logger.logger, 'warning') as mock_warning:
            audit_logger.log_token_revocation(
                user="user123",
                token_type="refresh",
                reason="expired"
            )
            
            mock_warning.assert_called_once()
            log_data = json.loads(mock_warning.call_args[0][0])
            
            assert log_data["event"] == "token_revocation"
            assert log_data["details"]["reason"] == "expired"
    
    def test_log_suspicious_activity(self):
        """Test suspicious activity logging"""
        with patch.object(audit_logger.logger, 'error') as mock_error:
            audit_logger.log_suspicious_activity(
                activity_type="brute_force",
                severity="high",
                user="user123"
            )
            
            mock_error.assert_called_once()
            log_data = json.loads(mock_error.call_args[0][0])
            
            assert log_data["event"] == "suspicious_activity"
            assert log_data["details"]["severity"] == "high"
    
    def test_log_sandbox_execution(self):
        """Test sandbox execution logging"""
        with patch.object(audit_logger.logger, 'info') as mock_info:
            audit_logger.log_sandbox_execution(
                user="user123",
                sandbox_id="sandbox_abc123",
                success=True,
                duration_ms=1500.5
            )
            
            mock_info.assert_called_once()
            log_data = json.loads(mock_info.call_args[0][0])
            
            assert log_data["event"] == "sandbox_execution"
            assert log_data["details"]["duration_ms"] == 1500.5
    
    def test_sensitive_data_sanitization(self):
        """Test that audit logger sanitizes sensitive data"""
        with patch.object(audit_logger.logger, 'info') as mock_info:
            audit_logger.log_authentication_attempt(
                user="user123",
                success=True,
                method="jwt"
            )
            
            # Add details with sensitive data
            audit_logger.log_config_change(
                change_type="api_key_update",
                details={
                    "old_key": "sk_live_old123",
                    "new_key": "sk_live_new456"
                },
                user="admin"
            )
            
            # Check that sensitive data was redacted
            log_data = json.loads(mock_info.call_args_list[-1][0][0])
            log_str = json.dumps(log_data)
            
            assert "sk_live_old123" not in log_str
            assert "sk_live_new456" not in log_str
            assert "***REDACTED***" in log_str


class TestLoggerIntegration:
    """Test logger integration"""
    
    def test_multiple_loggers_coexist(self):
        """Test that multiple loggers work together"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger1 = StructuredLogger(
                name="logger1",
                log_file=Path(tmpdir) / "logger1.log",
                console_output=False
            )
            
            logger2 = StructuredLogger(
                name="logger2",
                log_file=Path(tmpdir) / "logger2.log",
                console_output=False
            )
            
            logger1.info("Message from logger1")
            logger2.info("Message from logger2")
            
            # Check both log files
            with open(Path(tmpdir) / "logger1.log", 'r') as f:
                log1 = json.loads(f.readline())
            
            with open(Path(tmpdir) / "logger2.log", 'r') as f:
                log2 = json.loads(f.readline())
            
            assert log1["message"] == "Message from logger1"
            assert log2["message"] == "Message from logger2"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
