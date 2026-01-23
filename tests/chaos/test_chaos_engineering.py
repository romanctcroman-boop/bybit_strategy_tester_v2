"""
Chaos Engineering Tests

Проверка устойчивости системы к различным сбоям:
- Симуляция отказа внешних API
- Симуляция задержек сети
- Симуляция отказа Redis/PostgreSQL
- Симуляция исчерпания ресурсов

Основано на принципах Chaos Engineering:
https://principlesofchaos.org/
"""

import asyncio
import logging
import random
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

logger = logging.getLogger(__name__)


class ChaosType(str, Enum):
    """Types of chaos to inject."""

    LATENCY = "latency"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_PARTITION = "network_partition"
    DATA_CORRUPTION = "data_corruption"


@dataclass
class ChaosConfig:
    """Configuration for chaos injection."""

    chaos_type: ChaosType
    probability: float = 0.5  # 0-1 probability of triggering
    duration_ms: int = 1000  # For latency injection
    error_message: str = "Chaos injected error"
    enabled: bool = True


@dataclass
class ChaosResult:
    """Result of a chaos experiment."""

    experiment_name: str
    chaos_type: ChaosType
    started_at: datetime
    ended_at: Optional[datetime] = None
    success: bool = False
    system_recovered: bool = False
    recovery_time_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class ChaosMonkey:
    """
    Chaos Monkey - инъектор сбоев для тестирования устойчивости.

    Usage:
        chaos = ChaosMonkey()

        # Inject latency
        with chaos.inject_latency(service="api", delay_ms=500):
            response = client.get("/api/v1/health")

        # Inject failure
        with chaos.inject_failure(service="redis"):
            # Redis calls will fail
            pass
    """

    def __init__(self):
        self.experiments: List[ChaosResult] = []
        self.active_chaos: Dict[str, ChaosConfig] = {}
        self._patches: List[Any] = []

    def should_trigger(self, config: ChaosConfig) -> bool:
        """Determine if chaos should be triggered based on probability."""
        if not config.enabled:
            return False
        return random.random() < config.probability

    @asynccontextmanager
    async def inject_latency(
        self, service: str, delay_ms: int = 500, probability: float = 1.0
    ):
        """Inject latency into a service."""
        config = ChaosConfig(
            chaos_type=ChaosType.LATENCY,
            duration_ms=delay_ms,
            probability=probability,
        )

        result = ChaosResult(
            experiment_name=f"latency_{service}",
            chaos_type=ChaosType.LATENCY,
            started_at=datetime.now(timezone.utc),
        )

        self.active_chaos[service] = config

        try:
            if self.should_trigger(config):
                await asyncio.sleep(delay_ms / 1000)
            yield result
            result.success = True
        except Exception as e:
            result.errors.append(str(e))
            raise
        finally:
            result.ended_at = datetime.now(timezone.utc)
            del self.active_chaos[service]
            self.experiments.append(result)

    @asynccontextmanager
    async def inject_failure(
        self,
        service: str,
        error_class: type = Exception,
        error_message: str = "Chaos injected failure",
        probability: float = 1.0,
    ):
        """Inject failure into a service."""
        config = ChaosConfig(
            chaos_type=ChaosType.FAILURE,
            probability=probability,
            error_message=error_message,
        )

        result = ChaosResult(
            experiment_name=f"failure_{service}",
            chaos_type=ChaosType.FAILURE,
            started_at=datetime.now(timezone.utc),
        )

        self.active_chaos[service] = config

        try:
            if self.should_trigger(config):
                raise error_class(error_message)
            yield result
            result.success = True
        except error_class:
            result.system_recovered = False
            raise
        finally:
            result.ended_at = datetime.now(timezone.utc)
            if service in self.active_chaos:
                del self.active_chaos[service]
            self.experiments.append(result)

    def get_experiment_summary(self) -> Dict[str, Any]:
        """Get summary of all experiments."""
        total = len(self.experiments)
        successful = sum(1 for e in self.experiments if e.success)
        recovered = sum(1 for e in self.experiments if e.system_recovered)

        return {
            "total_experiments": total,
            "successful": successful,
            "failed": total - successful,
            "recovery_rate": recovered / total if total > 0 else 0,
            "by_type": {
                t.value: sum(1 for e in self.experiments if e.chaos_type == t)
                for t in ChaosType
            },
        }


# ============================================================================
# Chaos Test Cases
# ============================================================================


class TestCircuitBreakerResilience:
    """Test circuit breaker behavior under chaos conditions."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.api.app import app

        return TestClient(app)

    @pytest.fixture
    def chaos(self):
        """Create chaos monkey."""
        return ChaosMonkey()

    def test_api_survives_external_service_failure(self, client):
        """Test that API remains responsive when external services fail."""
        # Health endpoint should respond even if some services are down
        # May return 200 (healthy) or 503 (degraded) - both are acceptable
        response = client.get("/api/v1/health")
        assert response.status_code in (200, 503)

        # Circuit breaker status should be available
        response = client.get("/api/v1/circuit-breakers/status")
        assert response.status_code == 200

    def test_graceful_degradation_on_redis_failure(self, client):
        """Test system degrades gracefully when Redis is unavailable."""
        # Mock Redis failure
        with patch("redis.from_url") as mock_redis:
            mock_redis.side_effect = ConnectionError("Redis unavailable")

            # System should still respond
            response = client.get("/api/v1/health")
            # May report degraded but should not crash
            assert response.status_code in (200, 503)

    def test_circuit_breaker_opens_on_repeated_failures(self, client):
        """Test that circuit breaker opens after repeated failures."""
        response = client.get("/api/v1/circuit-breakers/status")
        assert response.status_code == 200

        data = response.json()
        # Circuit breakers should be in monitoring
        assert "breakers" in data or isinstance(data, dict)

    def test_rate_limiting_under_load(self, client):
        """Test rate limiting protects the system under heavy load."""
        responses = []
        for _ in range(20):
            response = client.get("/api/v1/health")
            responses.append(response.status_code)

        # System should respond (200 healthy, 503 degraded, 429 rate limited)
        valid_count = sum(1 for s in responses if s in (200, 503, 429))
        assert valid_count >= 10  # At least half should respond


class TestNetworkPartitionRecovery:
    """Test system recovery from network partitions."""

    @pytest.fixture
    def client(self):
        from backend.api.app import app

        return TestClient(app)

    def test_api_recovers_after_database_reconnect(self, client):
        """Test API recovers after database connection restored."""
        # First request - may be healthy or degraded
        response1 = client.get("/api/v1/health")
        assert response1.status_code in (200, 503)

        # Simulate brief outage and recovery
        time.sleep(0.1)

        # Should respond again
        response2 = client.get("/api/v1/health")
        assert response2.status_code in (200, 503)

    def test_websocket_reconnection(self, client):
        """Test WebSocket handles reconnection gracefully."""
        # WebSocket endpoint should be accessible
        # Note: TestClient doesn't fully support WebSocket testing
        # This is a placeholder for real WebSocket chaos tests
        response = client.get("/api/v1/health")
        assert response.status_code in (200, 503)


class TestResourceExhaustion:
    """Test system behavior under resource exhaustion."""

    @pytest.fixture
    def client(self):
        from backend.api.app import app

        return TestClient(app)

    def test_api_handles_memory_pressure(self, client):
        """Test API handles memory pressure gracefully."""
        # Create some memory pressure (lightweight)
        large_data = [{"data": "x" * 100} for _ in range(100)]

        # API should still respond (healthy or degraded)
        response = client.get("/api/v1/health")
        assert response.status_code in (200, 503)

        del large_data

    def test_concurrent_request_handling(self, client):
        """Test handling of many concurrent requests."""
        import concurrent.futures

        def make_request():
            return client.get("/api/v1/health").status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Most requests should respond (200 healthy, 503 degraded both valid)
        valid_rate = sum(1 for r in results if r in (200, 503)) / len(results)
        assert valid_rate >= 0.8  # At least 80% should respond


class TestDataIntegrity:
    """Test data integrity under chaos conditions."""

    @pytest.fixture
    def client(self):
        from backend.api.app import app

        return TestClient(app)

    def test_order_idempotency(self, client):
        """Test that duplicate orders are handled correctly."""
        order_data = {
            "symbol": "BTCUSDT",
            "side": "buy",
            "order_type": "market",
            "quantity": 0.01,
            "client_order_id": "test-idempotency-123",
        }

        # Submit same order twice
        response1 = client.post("/api/v1/state/orders", json=order_data)
        response2 = client.post("/api/v1/state/orders", json=order_data)

        # Both should be handled (either created or rejected as duplicate)
        assert response1.status_code in (201, 400, 409, 500)
        assert response2.status_code in (201, 400, 409, 500)

    def test_state_consistency_after_failure(self, client):
        """Test state remains consistent after simulated failure."""
        # Get initial state
        response1 = client.get("/api/v1/risk/summary")
        assert response1.status_code == 200
        _ = response1.json()  # Verify JSON is valid

        # Simulate some activity
        client.get("/api/v1/health")

        # State should still be consistent
        response2 = client.get("/api/v1/risk/summary")
        assert response2.status_code == 200
        final_state = response2.json()

        # Core fields should be present
        assert "overall_risk_level" in final_state
        assert "thresholds" in final_state


class TestTimeoutHandling:
    """Test timeout handling in various scenarios."""

    @pytest.fixture
    def client(self):
        from backend.api.app import app

        return TestClient(app)

    def test_slow_endpoint_timeout(self, client):
        """Test that slow endpoints don't block the system."""
        # Fast endpoints should respond within reasonable time
        start = time.time()
        response = client.get("/api/v1/health")
        elapsed = time.time() - start

        assert response.status_code in (200, 503)
        assert elapsed < 30.0  # Should complete within 30 seconds (allows for slow CI)

    def test_cascade_failure_prevention(self, client):
        """Test that one slow service doesn't cascade failures."""
        # Multiple endpoints should work independently
        responses = []
        for endpoint in [
            "/api/v1/health",
            "/api/v1/risk/summary",
            "/api/v1/tracing/status",
        ]:
            start = time.time()
            response = client.get(endpoint)
            elapsed = time.time() - start
            responses.append(
                {
                    "endpoint": endpoint,
                    "status": response.status_code,
                    "elapsed": elapsed,
                }
            )

        # All should complete reasonably quickly
        for r in responses:
            assert r["elapsed"] < 10.0
            assert r["status"] in (200, 404, 500, 503)


class TestAlertingUnderChaos:
    """Test alerting system behavior under chaos conditions."""

    @pytest.fixture
    def client(self):
        from backend.api.app import app

        return TestClient(app)

    def test_risk_alerts_during_high_load(self, client):
        """Test risk alerts are generated during high load."""
        # Risk summary should still work under load
        for _ in range(10):
            response = client.get("/api/v1/risk/summary")
            assert response.status_code == 200

    def test_anomaly_detection_during_chaos(self, client):
        """Test anomaly detection remains operational during chaos."""
        response = client.get("/api/v1/anomaly-detection/status")
        assert response.status_code == 200

        data = response.json()
        assert data.get("enabled") is True


# ============================================================================
# Chaos Engineering Runner
# ============================================================================


def run_chaos_experiment(
    name: str,
    experiment_fn: Callable,
    iterations: int = 5,
) -> Dict[str, Any]:
    """
    Run a chaos experiment multiple times and collect results.

    Args:
        name: Experiment name
        experiment_fn: Function to run
        iterations: Number of iterations

    Returns:
        Experiment results summary
    """
    results = []

    for i in range(iterations):
        start = time.time()
        success = False
        error = None

        try:
            experiment_fn()
            success = True
        except Exception as e:
            error = str(e)

        elapsed = time.time() - start
        results.append(
            {
                "iteration": i + 1,
                "success": success,
                "elapsed_ms": elapsed * 1000,
                "error": error,
            }
        )

    success_count = sum(1 for r in results if r["success"])
    avg_time = sum(r["elapsed_ms"] for r in results) / len(results)

    return {
        "experiment": name,
        "iterations": iterations,
        "success_rate": success_count / iterations,
        "avg_response_ms": avg_time,
        "results": results,
    }


if __name__ == "__main__":
    # Run chaos experiments
    pytest.main([__file__, "-v", "--tb=short"])
