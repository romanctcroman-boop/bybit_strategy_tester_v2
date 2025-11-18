"""
Reliability Module - 110% Uptime Guarantee System

Implements production-ready resilience patterns based on:
- DeepSeek Agent recommendations
- Perplexity Agent best practices
- Netflix Hystrix patterns
- AWS Well-Architected Framework

Modules:
- circuit_breaker: Prevent cascading failures ✅
- retry_policy: Automatic recovery with exponential backoff ✅
- key_rotation: Intelligent API key management ✅
- service_monitor: Health monitoring and alerting ✅
- mcp_manager: Auto-recovery for MCP server (Coming soon)
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitBreakerConfig,
    CircuitBreakerStats,
    CircuitState,
    CircuitBreakerError,
)

from .retry_policy import (
    RetryPolicy,
    RetryConfig,
    RetryableException,
    NonRetryableException,
    is_http_error_retryable,
)

from .key_rotation import (
    KeyRotation,
    KeyConfig,
    KeyStatus,
    KeyHealth,
)

from .service_monitor import (
    ServiceMonitor,
    ServiceConfig,
    HealthStatus,
    ServiceHealth,
    HealthCheckResult,
)

__all__ = [
    # Circuit Breaker
    'CircuitBreaker',
    'CircuitBreakerRegistry',
    'CircuitBreakerConfig',
    'CircuitBreakerStats',
    'CircuitState',
    'CircuitBreakerError',
    # Retry Policy
    'RetryPolicy',
    'RetryConfig',
    'RetryableException',
    'NonRetryableException',
    'is_http_error_retryable',
    # Key Rotation
    'KeyRotation',
    'KeyConfig',
    'KeyStatus',
    'KeyHealth',
    # Service Monitor
    'ServiceMonitor',
    'ServiceConfig',
    'HealthStatus',
    'ServiceHealth',
    'HealthCheckResult',
]

__version__ = '1.3.0'  # Added Service Monitor
