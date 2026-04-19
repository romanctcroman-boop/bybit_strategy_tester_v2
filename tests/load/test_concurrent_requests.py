"""
Concurrent Load Tests — 100+ parallel requests via httpx AsyncClient.

PURPOSE:
    Verifies that the FastAPI application handles concurrent requests correctly:
    - No race conditions in shared state
    - No deadlocks under load
    - Response times stay within acceptable bounds
    - Error rate stays below threshold

APPROACH:
    Uses httpx.AsyncClient with ASGI transport — no running server required.
    Tests the actual FastAPI app in-process with real SQLite and mocked LLMs.

USAGE:
    pytest tests/load/test_concurrent_requests.py -v
    pytest tests/load/test_concurrent_requests.py -v -k "test_100"
"""

from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any

import httpx
import pytest

from backend.api.app import app as _fastapi_app

# ---------------------------------------------------------------------------
# App fixture (module-scoped to avoid recreating the app 100 times)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app():
    return _fastapi_app


@pytest.fixture(scope="module")
def async_client(app):
    """httpx AsyncClient backed by ASGI transport — no server needed."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        timeout=30.0,
    )


@pytest.fixture(scope="module")
def slow_client(app):
    """AsyncClient with extended timeout for CPU-heavy POST endpoints (backtests).

    In-process ASGI tests run everything in one thread.  20+ concurrent
    backtests serialise behind each other, so total wall-time can exceed the
    default 30 s per-request timeout.  This client allows up to 120 s so
    load tests can verify absence of crashes without false timeouts.
    """
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        timeout=120.0,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv_payload(n: int = 100) -> dict[str, Any]:
    """Minimal strategy-builder run payload."""
    return {
        "strategy_graph": {
            "name": "LoadTest RSI",
            "interval": "15",
            "blocks": [
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "params": {"period": 14, "oversold": 30, "overbought": 70},
                    "isMain": False,
                },
                {
                    "id": "strategy_node",
                    "type": "strategy",
                    "params": {},
                    "isMain": True,
                },
            ],
            "connections": [
                {
                    "from": "rsi_1",
                    "fromPort": "long",
                    "to": "strategy_node",
                    "toPort": "entry_long",
                }
            ],
        },
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "start_date": "2025-01-01",
        "end_date": "2025-03-01",
        "initial_capital": 10000,
        "commission_value": 0.0007,
        "direction": "long",
    }


async def _fire_n(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    n: int,
    **kwargs,
) -> tuple[list[int], list[float]]:
    """Fire n concurrent requests, return (status_codes, response_times_s)."""

    async def one() -> tuple[int, float]:
        t0 = time.perf_counter()
        resp = await client.request(method, url, **kwargs)
        return resp.status_code, time.perf_counter() - t0

    results = await asyncio.gather(*[one() for _ in range(n)], return_exceptions=True)
    codes, times = [], []
    for r in results:
        if isinstance(r, Exception):
            codes.append(0)
            times.append(30.0)
        else:
            codes.append(r[0])
            times.append(r[1])
    return codes, times


# ---------------------------------------------------------------------------
# Test class: Health endpoint concurrency
# ---------------------------------------------------------------------------


class TestConcurrentHealthEndpoint:
    """Health endpoint must be rock-solid under load."""

    @pytest.mark.asyncio
    async def test_10_concurrent_health_checks(self, async_client):
        codes, times = await _fire_n(async_client, "GET", "/healthz", 10)
        ok = sum(1 for c in codes if c == 200)
        assert ok == 10, f"Only {ok}/10 health checks returned 200"

    @pytest.mark.asyncio
    async def test_50_concurrent_health_checks(self, async_client):
        codes, times = await _fire_n(async_client, "GET", "/healthz", 50)
        ok = sum(1 for c in codes if c == 200)
        error_rate = 1.0 - ok / 50
        assert error_rate <= 0.05, f"Error rate {error_rate:.0%} > 5% for 50 concurrent"

    @pytest.mark.asyncio
    async def test_100_concurrent_health_checks(self, async_client):
        codes, times = await _fire_n(async_client, "GET", "/healthz", 100)
        ok = sum(1 for c in codes if c in (200, 503))  # 503 acceptable under startup
        error_rate = 1.0 - ok / 100
        assert error_rate <= 0.10, f"Error rate {error_rate:.0%} > 10% for 100 concurrent"

    @pytest.mark.asyncio
    async def test_health_p95_latency_under_500ms(self, async_client):
        _, times = await _fire_n(async_client, "GET", "/healthz", 50)
        sorted_t = sorted(times)
        p95 = sorted_t[int(len(sorted_t) * 0.95)]
        assert p95 < 0.5, f"Health endpoint p95={p95 * 1000:.0f}ms > 500ms"

    @pytest.mark.asyncio
    async def test_health_max_latency_reasonable(self, async_client):
        _, times = await _fire_n(async_client, "GET", "/healthz", 20)
        assert max(times) < 5.0, f"Max health latency {max(times):.2f}s > 5s"


# ---------------------------------------------------------------------------
# Test class: Strategies list endpoint
# ---------------------------------------------------------------------------


class TestConcurrentStrategiesEndpoint:
    """GET /api/strategies — read-only, should be highly concurrent."""

    @pytest.mark.asyncio
    async def test_20_concurrent_strategy_list(self, async_client):
        codes, _ = await _fire_n(async_client, "GET", "/api/strategies/", 20)
        ok = sum(1 for c in codes if c in (200, 404))
        assert ok == 20

    @pytest.mark.asyncio
    async def test_50_concurrent_strategy_list(self, async_client):
        codes, times = await _fire_n(async_client, "GET", "/api/strategies/", 50)
        ok = sum(1 for c in codes if c in (200, 404))
        error_rate = 1.0 - ok / 50
        assert error_rate <= 0.05, f"Strategy list error_rate={error_rate:.0%}"

    @pytest.mark.asyncio
    async def test_100_concurrent_strategy_list_no_crash(self, async_client):
        """100 parallel reads must not crash the server."""
        codes, _ = await _fire_n(async_client, "GET", "/api/strategies/", 100)
        # Accept any HTTP response — just no connection errors (code 0)
        crashes = sum(1 for c in codes if c == 0)
        assert crashes == 0, f"{crashes} connection errors under 100 concurrent reads"

    @pytest.mark.asyncio
    async def test_strategy_list_p99_under_2s(self, async_client):
        _, times = await _fire_n(async_client, "GET", "/api/strategies/", 30)
        sorted_t = sorted(times)
        p99 = sorted_t[int(len(sorted_t) * 0.99)]
        assert p99 < 2.0, f"Strategy list p99={p99:.2f}s > 2s"


# ---------------------------------------------------------------------------
# Test class: OpenAPI schema endpoint
# ---------------------------------------------------------------------------


class TestConcurrentOpenAPI:
    """OpenAPI schema is cached — should handle many concurrent requests."""

    @pytest.mark.asyncio
    async def test_100_concurrent_openapi_schema(self, async_client):
        codes, times = await _fire_n(async_client, "GET", "/openapi.json", 100)
        ok = sum(1 for c in codes if c == 200)
        error_rate = 1.0 - ok / 100
        assert error_rate <= 0.05, f"OpenAPI error_rate={error_rate:.0%} > 5%"

    @pytest.mark.asyncio
    async def test_openapi_p95_latency(self, async_client):
        # App has 860 routes — first schema generation is CPU-intensive (~760ms).
        # Under 50 concurrent requests the p95 is ~2-3s on this machine.
        # Threshold is 5s — guards against catastrophic regression, not absolute speed.
        _, times = await _fire_n(async_client, "GET", "/openapi.json", 50)
        sorted_t = sorted(times)
        p95 = sorted_t[int(len(sorted_t) * 0.95)]
        assert p95 < 5.0, f"OpenAPI p95={p95 * 1000:.0f}ms > 5000ms"


# ---------------------------------------------------------------------------
# Test class: Mixed endpoint load (realistic traffic pattern)
# ---------------------------------------------------------------------------


class TestMixedConcurrentLoad:
    """Mixed load across multiple endpoints — simulates real usage pattern."""

    @pytest.mark.asyncio
    async def test_mixed_100_requests_no_crashes(self, async_client):
        """Fire 100 mixed requests: 50% health, 30% strategies, 20% openapi."""
        endpoints = [("GET", "/healthz")] * 50 + [("GET", "/api/strategies/")] * 30 + [("GET", "/openapi.json")] * 20

        async def one(method, url):
            t0 = time.perf_counter()
            try:
                resp = await async_client.request(method, url)
                return resp.status_code, time.perf_counter() - t0
            except Exception:
                return 0, 30.0

        results = await asyncio.gather(*[one(m, u) for m, u in endpoints])
        codes = [r[0] for r in results]
        crashes = sum(1 for c in codes if c == 0)
        assert crashes == 0, f"{crashes} connection errors in mixed load"

    @pytest.mark.asyncio
    async def test_mixed_load_error_rate_below_5_pct(self, async_client):
        endpoints = [("GET", "/healthz")] * 40 + [("GET", "/api/strategies/")] * 40 + [("GET", "/openapi.json")] * 20

        async def one(method, url):
            try:
                resp = await async_client.request(method, url)
                return resp.status_code
            except Exception:
                return 0

        codes = await asyncio.gather(*[one(m, u) for m, u in endpoints])
        error_rate = sum(1 for c in codes if c not in (200, 404)) / len(codes)
        assert error_rate <= 0.05, f"Mixed load error_rate={error_rate:.0%} > 5%"

    @pytest.mark.asyncio
    async def test_sequential_batches_consistent_latency(self, async_client):
        """Response time should not degrade significantly across 3 batches of 30."""
        batch_p50s = []
        for _ in range(3):
            _, times = await _fire_n(async_client, "GET", "/healthz", 30)
            batch_p50s.append(statistics.median(times))
            await asyncio.sleep(0.1)

        # Last batch should not be >3× slower than first batch
        assert batch_p50s[2] < batch_p50s[0] * 3 + 0.1, (
            f"Latency degrading: {[f'{t * 1000:.0f}ms' for t in batch_p50s]}"
        )


# ---------------------------------------------------------------------------
# Test class: Throughput benchmarks
# ---------------------------------------------------------------------------


class TestThroughputBenchmarks:
    """Measure actual throughput numbers for the health endpoint."""

    @pytest.mark.asyncio
    async def test_health_throughput_above_50_rps(self, async_client):
        """Health endpoint should sustain at least 50 requests per second."""
        n = 100
        t0 = time.perf_counter()
        await asyncio.gather(*[async_client.get("/healthz") for _ in range(n)])
        elapsed = time.perf_counter() - t0
        rps = n / elapsed
        assert rps >= 50, f"Throughput {rps:.0f} rps < 50 rps minimum"

    @pytest.mark.asyncio
    async def test_strategies_throughput_above_10_rps(self, async_client):
        """Strategies list (DB query) should sustain at least 10 rps."""
        n = 30
        t0 = time.perf_counter()
        await asyncio.gather(*[async_client.get("/api/strategies/") for _ in range(n)])
        elapsed = time.perf_counter() - t0
        rps = n / elapsed
        assert rps >= 10, f"Strategy list throughput {rps:.0f} rps < 10 rps minimum"


# ---------------------------------------------------------------------------
# Test class: Concurrent POST /api/v1/backtests/
# ---------------------------------------------------------------------------


def _make_backtest_payload() -> dict[str, Any]:
    """Minimal BacktestCreateRequest payload for the main backtest endpoint."""
    return {
        "symbol": "BTCUSDT",
        "interval": "15",
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2025-02-01T00:00:00Z",
        "strategy_type": "sma_crossover",
        "strategy_params": {"fast_period": 10, "slow_period": 30},
        "initial_capital": 10000,
        "position_size": 0.5,
        "direction": "long",
        "commission_value": 0.0007,
    }


class TestConcurrentBacktestsPOST:
    """POST /api/v1/backtests/ under concurrent load.

    Backtests involve DB writes + backtest engine execution.  We accept any
    HTTP status (200, 4xx, 5xx) as "handled" — we only reject connection-level
    failures (code 0, which mean server panicked or dropped the socket).
    """

    @pytest.mark.asyncio
    async def test_5_concurrent_backtest_posts_no_crash(self, slow_client):
        """5 simultaneous POST requests must not crash the server."""
        codes, _ = await _fire_n(slow_client, "POST", "/api/v1/backtests/", 5, json=_make_backtest_payload())
        crashes = sum(1 for c in codes if c == 0)
        assert crashes == 0, f"{crashes}/5 connection errors in concurrent backtest POSTs"

    @pytest.mark.asyncio
    async def test_20_concurrent_backtest_posts_no_crash(self, slow_client):
        """20 simultaneous POSTs — server must survive, all requests handled."""
        codes, _ = await _fire_n(slow_client, "POST", "/api/v1/backtests/", 20, json=_make_backtest_payload())
        crashes = sum(1 for c in codes if c == 0)
        assert crashes == 0, f"{crashes}/20 connection errors under concurrent backtest load"

    @pytest.mark.asyncio
    async def test_50_concurrent_backtest_posts_all_handled(self, slow_client):
        """50 simultaneous POSTs — every request must receive an HTTP response."""
        codes, _ = await _fire_n(slow_client, "POST", "/api/v1/backtests/", 50, json=_make_backtest_payload())
        crashes = sum(1 for c in codes if c == 0)
        handled = sum(1 for c in codes if c != 0)
        assert crashes == 0, f"{crashes}/50 connection errors in 50 concurrent POSTs"
        assert handled == 50, f"Only {handled}/50 requests received an HTTP response"

    @pytest.mark.asyncio
    async def test_backtest_post_no_deadlock(self, slow_client):
        """Concurrent POSTs must not deadlock — httpx 120 s timeout is the guard.

        In-process ASGI testing serialises backtest work, so per-request
        latency scales with concurrency.  We only assert that every request
        eventually returns (no code 0 / hung connection).
        """
        codes, _ = await _fire_n(slow_client, "POST", "/api/v1/backtests/", 20, json=_make_backtest_payload())
        crashes = sum(1 for c in codes if c == 0)
        assert crashes == 0, f"{crashes}/20 requests hung or dropped (possible deadlock)"


# ---------------------------------------------------------------------------
# Test class: 200+ simultaneous connections (pool exhaustion check)
# ---------------------------------------------------------------------------


class TestConnectionPoolBehavior:
    """Stress-test the connection pool with 200+ simultaneous requests."""

    @pytest.mark.asyncio
    async def test_200_concurrent_health_no_pool_exhaustion(self, async_client):
        """200 simultaneous GETs to a trivial endpoint must not exhaust the pool."""
        codes, times = await _fire_n(async_client, "GET", "/healthz", 200)
        crashes = sum(1 for c in codes if c == 0)
        # Soft timeout: ≥10% timing out strongly suggests pool exhaustion
        hard_timeouts = sum(1 for t in times if t >= 29.9)
        assert crashes == 0, f"{crashes}/200 connection errors at 200 concurrency"
        assert hard_timeouts < 20, f"{hard_timeouts}/200 requests timed out — possible connection pool exhaustion"

    @pytest.mark.asyncio
    async def test_200_concurrent_mixed_endpoints(self, async_client):
        """200 concurrent requests spread across three endpoints."""
        tasks = [("GET", "/healthz")] * 100 + [("GET", "/api/strategies/")] * 60 + [("GET", "/openapi.json")] * 40

        async def one(method: str, url: str) -> int:
            try:
                resp = await async_client.request(method, url)
                return resp.status_code
            except Exception:
                return 0

        codes = await asyncio.gather(*[one(m, u) for m, u in tasks])
        crashes = sum(1 for c in codes if c == 0)
        assert crashes == 0, f"{crashes}/200 connection errors in mixed 200-connection test"

    @pytest.mark.asyncio
    async def test_connection_pool_recovers_after_burst(self, async_client):
        """After a 200-connection burst, normal requests still work."""
        # Burst
        await _fire_n(async_client, "GET", "/healthz", 200)
        await asyncio.sleep(0.1)
        # Normal request after burst
        codes, times = await _fire_n(async_client, "GET", "/healthz", 10)
        ok = sum(1 for c in codes if c == 200)
        assert ok == 10, f"Pool did not recover: only {ok}/10 success after 200-conn burst"
        assert max(times) < 2.0, f"Post-burst max latency {max(times):.2f}s > 2s"


# ---------------------------------------------------------------------------
# Test class: Sustained load (multiple waves)
# ---------------------------------------------------------------------------


class TestSustainedLoad:
    """Multiple sequential waves — verify latency does not degrade over time."""

    @pytest.mark.asyncio
    async def test_5_waves_of_50_no_latency_drift(self, async_client):
        """5 waves × 50 requests = 250 total. Last wave must not be 5× slower."""
        wave_medians: list[float] = []
        for _ in range(5):
            _, times = await _fire_n(async_client, "GET", "/healthz", 50)
            wave_medians.append(statistics.median(times))
            await asyncio.sleep(0.05)

        baseline = wave_medians[0]
        worst = max(wave_medians)
        assert worst < baseline * 5 + 0.5, (
            f"Sustained-load degradation detected: {[f'{t * 1000:.0f}ms' for t in wave_medians]}"
        )

    @pytest.mark.asyncio
    async def test_sustained_load_zero_crashes_over_5_waves(self, async_client):
        """250 total requests across 5 waves — zero connection errors allowed."""
        all_codes: list[int] = []
        for _ in range(5):
            codes, _ = await _fire_n(async_client, "GET", "/healthz", 50)
            all_codes.extend(codes)
            await asyncio.sleep(0.02)
        crashes = sum(1 for c in all_codes if c == 0)
        assert crashes == 0, f"{crashes}/250 connection errors across 5 sustained waves"

    @pytest.mark.asyncio
    async def test_mixed_get_post_sustained_waves(self, slow_client):
        """3 waves mixing GET health checks with POST backtest requests."""
        all_crashes = 0
        for _ in range(3):
            # 30 GETs + 5 POSTs per wave = 105 requests total
            get_codes, _ = await _fire_n(slow_client, "GET", "/healthz", 30)
            post_codes, _ = await _fire_n(slow_client, "POST", "/api/v1/backtests/", 5, json=_make_backtest_payload())
            all_crashes += sum(1 for c in get_codes + post_codes if c == 0)
            await asyncio.sleep(0.05)

        assert all_crashes == 0, f"{all_crashes} connection errors in mixed GET/POST sustained waves"


# ---------------------------------------------------------------------------
# Test class: Race conditions (concurrent reads + writes)
# ---------------------------------------------------------------------------


class TestRaceConditions:
    """Detect race conditions by firing concurrent reads and writes simultaneously."""

    @pytest.mark.asyncio
    async def test_concurrent_read_write_no_crash(self, slow_client):
        """Simultaneous GETs and POSTs must not cause 500-level panics."""
        get_tasks = [("GET", "/healthz")] * 40 + [("GET", "/api/strategies/")] * 20
        post_tasks = [("POST", "/api/v1/backtests/")] * 10

        async def do_get(url: str) -> int:
            try:
                resp = await slow_client.get(url)
                return resp.status_code
            except Exception:
                return 0

        async def do_post() -> int:
            try:
                resp = await slow_client.post("/api/v1/backtests/", json=_make_backtest_payload())
                return resp.status_code
            except Exception:
                return 0

        all_coros = [do_get(u) for _, u in get_tasks] + [do_post() for _ in post_tasks]
        codes = await asyncio.gather(*all_coros)
        crashes = sum(1 for c in codes if c == 0)
        assert crashes == 0, f"{crashes} connection errors in concurrent read+write test"

    @pytest.mark.asyncio
    async def test_strategy_list_stable_during_backtest_writes(self, slow_client):
        """Strategy list reads must not fail while backtest POSTs are in-flight."""

        async def read_strategies() -> int:
            try:
                resp = await slow_client.get("/api/strategies/")
                return resp.status_code
            except Exception:
                return 0

        async def write_backtest() -> int:
            try:
                resp = await slow_client.post("/api/v1/backtests/", json=_make_backtest_payload())
                return resp.status_code
            except Exception:
                return 0

        coros = [read_strategies() for _ in range(30)] + [write_backtest() for _ in range(10)]
        codes = await asyncio.gather(*coros)
        read_codes = codes[:30]
        crashes_in_reads = sum(1 for c in read_codes if c == 0)
        assert crashes_in_reads == 0, f"{crashes_in_reads} crashes in strategy-list reads during concurrent POSTs"
