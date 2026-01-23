"""
MCP Circuit Breaker and Concurrency Control

Extracted from app.py for better modularity.
Provides fault tolerance for MCP tool execution.
"""

import asyncio
import os
import time
from typing import Dict


class CircuitBreaker:
    """
    Circuit breaker pattern for MCP tools.

    Opens after threshold failures and stays open for timeout_seconds.
    """

    def __init__(self, threshold: int = 5, timeout_seconds: int = 60):
        self.threshold = threshold
        self.timeout_seconds = timeout_seconds
        self.failures = 0
        self.open_until = 0.0

    def is_open(self) -> bool:
        return self.failures >= self.threshold and time.time() < self.open_until

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.time() + self.timeout_seconds

    def reset(self):
        self.failures = 0
        self.open_until = 0.0


# Configurable via env vars
CB_THRESHOLD = int(os.getenv("MCP_CB_FAILURE_THRESHOLD", "5"))
CB_TIMEOUT = int(os.getenv("MCP_CB_TIMEOUT_SECONDS", "60"))
MAX_CONCURRENCY = int(os.getenv("MCP_MAX_CONCURRENT", "10"))

# Per-tool circuit breakers
circuit_breakers: Dict[str, CircuitBreaker] = {}

# Semaphore for concurrency control
mcp_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


def get_circuit_breaker(tool_name: str) -> CircuitBreaker:
    """Get or create circuit breaker for a tool."""
    if tool_name not in circuit_breakers:
        circuit_breakers[tool_name] = CircuitBreaker(CB_THRESHOLD, CB_TIMEOUT)
    return circuit_breakers[tool_name]


__all__ = [
    "CircuitBreaker",
    "circuit_breakers",
    "mcp_semaphore",
    "get_circuit_breaker",
    "CB_THRESHOLD",
    "CB_TIMEOUT",
    "MAX_CONCURRENCY",
]
