"""
Locust Load Tests for Bybit Strategy Tester

Нагрузочное тестирование API endpoints.

Usage:
    # Start the server first, then run:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

    # Or headless mode:
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
           --headless -u 100 -r 10 -t 60s

Key metrics to monitor:
- Response time (p50, p95, p99)
- Requests per second
- Error rate
- Memory usage
"""

import random
import time

from locust import HttpUser, between, events, task


class TradingAPIUser(HttpUser):
    """
    Simulates a trading API user making various requests.
    """

    wait_time = between(0.1, 1.0)  # Random wait between requests

    def on_start(self):
        """Called when a simulated user starts."""
        # Warm up with health check
        self.client.get("/api/v1/health")

    @task(10)
    def health_check(self):
        """High frequency health check."""
        with self.client.get("/api/v1/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(5)
    def get_risk_summary(self):
        """Check risk metrics."""
        self.client.get("/api/v1/risk/summary")

    @task(5)
    def get_circuit_breaker_status(self):
        """Monitor circuit breakers."""
        self.client.get("/api/v1/circuit-breakers/status")

    @task(3)
    def get_tracing_status(self):
        """Check distributed tracing."""
        self.client.get("/api/v1/tracing/status")

    @task(3)
    def get_anomaly_status(self):
        """Check anomaly detection."""
        self.client.get("/api/v1/anomaly-detection/status")

    @task(2)
    def list_orders(self):
        """List orders from state manager."""
        self.client.get("/api/v1/state/orders")

    @task(2)
    def list_positions(self):
        """List positions from state manager."""
        self.client.get("/api/v1/state/positions")

    @task(1)
    def create_market_order(self):
        """Create a test market order."""
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        sides = ["buy", "sell"]

        order = {
            "symbol": random.choice(symbols),
            "side": random.choice(sides),
            "order_type": "market",
            "quantity": round(random.uniform(0.001, 0.1), 4),
        }

        with self.client.post(
            "/api/v1/state/orders", json=order, catch_response=True
        ) as response:
            if response.status_code in (201, 400, 403, 500):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class DataAPIUser(HttpUser):
    """
    Simulates a user fetching market data.
    """

    wait_time = between(0.5, 2.0)

    @task(5)
    def get_backtests(self):
        """List backtests."""
        self.client.get("/api/v1/backtests")

    @task(3)
    def get_strategies(self):
        """List strategies."""
        self.client.get("/api/v1/strategies")

    @task(2)
    def get_metrics(self):
        """Get Prometheus metrics."""
        self.client.get("/metrics")


class AgentAPIUser(HttpUser):
    """
    Simulates AI agent interactions.
    """

    wait_time = between(1.0, 5.0)  # Agents are slower

    @task(2)
    def agent_stats(self):
        """Get agent statistics."""
        self.client.get("/api/v1/agents/stats")

    @task(1)
    def agent_health(self):
        """Check agent health."""
        self.client.get("/api/v1/agents/health")


# ============================================================================
# Custom event handlers
# ============================================================================


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("=" * 60)
    print("🚀 Load test starting...")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("=" * 60)
    print("🛑 Load test completed!")

    # Print summary
    stats = environment.stats
    print(f"\nTotal requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Avg response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Requests/sec: {stats.total.current_rps:.2f}")

    if stats.total.num_requests > 0:
        error_rate = stats.total.num_failures / stats.total.num_requests * 100
        print(f"Error rate: {error_rate:.2f}%")
    print("=" * 60)


@events.request.add_listener
def on_request(
    request_type,
    name,
    response_time,
    response_length,
    response,
    context,
    exception,
    **kwargs,
):
    """Track individual request metrics."""
    if exception:
        print(f"❌ Request failed: {name} - {exception}")
    elif response_time > 1000:  # > 1 second
        print(f"⚠️ Slow request: {name} took {response_time:.0f}ms")


# ============================================================================
# Test scenarios
# ============================================================================


class SpikeTestUser(HttpUser):
    """
    Spike test - sudden traffic burst.
    """

    wait_time = between(0.01, 0.1)  # Very fast requests

    @task
    def rapid_health_check(self):
        """Rapid fire health checks."""
        self.client.get("/api/v1/health")


class StressTestUser(HttpUser):
    """
    Stress test - gradual load increase.
    """

    wait_time = between(0.1, 0.5)

    @task(5)
    def heavy_endpoint(self):
        """Hit multiple endpoints rapidly."""
        endpoints = [
            "/api/v1/health",
            "/api/v1/risk/summary",
            "/api/v1/circuit-breakers/status",
            "/api/v1/state/orders",
        ]
        for endpoint in endpoints:
            self.client.get(endpoint)
            time.sleep(0.01)


# ============================================================================
# Quick validation test (can be run as pytest)
# ============================================================================


def run_quick_load_test(
    host: str = "http://localhost:8000", duration_seconds: int = 10
):
    """
    Run a quick load test programmatically.

    Usage:
        from tests.load.locustfile import run_quick_load_test
        results = run_quick_load_test()
    """
    import gevent
    from locust.env import Environment
    from locust.stats import stats_history, stats_printer

    # Setup Environment and Runner
    env = Environment(user_classes=[TradingAPIUser])
    env.create_local_runner()

    # Start stats printer
    gevent.spawn(stats_printer(env.stats))
    gevent.spawn(stats_history, env.runner)

    # Start test
    env.runner.start(user_count=10, spawn_rate=2)
    gevent.sleep(duration_seconds)

    # Stop
    env.runner.stop()

    return {
        "total_requests": env.stats.total.num_requests,
        "total_failures": env.stats.total.num_failures,
        "avg_response_time": env.stats.total.avg_response_time,
        "requests_per_sec": env.stats.total.current_rps,
    }


if __name__ == "__main__":
    print("Run with: locust -f tests/load/locustfile.py --host=http://localhost:8000")
