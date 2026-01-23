"""
DeepSeek API Client
Simplified client for health checks
"""

import logging
import os
import time

import httpx

from backend.reliability.http_retry import httpx_retry
from reliability.retry_policy import is_http_error_retryable

try:
    from backend.agents.circuit_breaker_manager import (
        get_circuit_manager,
        CircuitBreakerError,
    )
except Exception:  # pragma: no cover - optional in lightweight scripts
    get_circuit_manager = None  # type: ignore
    CircuitBreakerError = Exception  # type: ignore


logger = logging.getLogger(__name__)


class DeepSeekClient:
    """DeepSeek API client for health checks"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.timeout = 10.0
        self.failure_count = 0
        self.last_failure_time = 0.0

        self.breaker_name = "deepseek_api"
        self.circuit_manager = None
        if get_circuit_manager is not None:
            try:
                self.circuit_manager = get_circuit_manager()
                if self.breaker_name not in self.circuit_manager.get_all_breakers():
                    self.circuit_manager.register_breaker(
                        name=self.breaker_name,
                        fail_max=5,
                        timeout_duration=60,
                        expected_exception=Exception,
                    )
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning(
                    "DeepSeekClient could not initialize circuit breaker manager: %s",
                    exc,
                )
                self.circuit_manager = None

    async def test_connection(self) -> bool:
        """Test connection to DeepSeek API"""
        if not self.api_key:
            return False

        async def _models_request():
            async def _call():
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        f"{self.base_url}/models",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    if is_http_error_retryable(response.status_code):
                        response.raise_for_status()
                    return response

            return await httpx_retry("deepseek.chat_completion", _call)

        try:
            if self.circuit_manager:
                response = await self.circuit_manager.call_with_breaker(
                    self.breaker_name,
                    _models_request,
                )
            else:
                response = await _models_request()

            is_healthy = response.status_code == 200
            if is_healthy:
                self.failure_count = 0
            else:
                self.failure_count += 1
                self.last_failure_time = time.time()
            return is_healthy

        except CircuitBreakerError:
            logger.warning("DeepSeek circuit breaker open; skipping health probe")
        except httpx.TimeoutException as exc:
            logger.warning("DeepSeek health probe timeout: %s", exc)
        except Exception as exc:
            logger.error("DeepSeek health probe failed: %s", exc)

        self.failure_count += 1
        self.last_failure_time = time.time()
        return False

    async def check_health(self) -> dict:
        """Check API health status"""
        is_healthy = await self.test_connection()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "DeepSeek API",
            "available": is_healthy,
            "failure_count": self.failure_count,
            "circuit_breaker_state": self._breaker_state(),
        }

    def _breaker_state(self) -> str:
        if not self.circuit_manager:
            return "unmanaged"
        state = self.circuit_manager.get_breaker_state(self.breaker_name)
        return state.value if state else "unknown"
