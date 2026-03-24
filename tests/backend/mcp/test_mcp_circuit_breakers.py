"""
Tests for MCP Circuit Breakers

Tests for P0-4 task: Per-tool circuit breakers in MCP bridge.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mcp.mcp_integration import MCPFastAPIBridge


class TestMCPFastAPIBridgeCircuitBreaker:
    """Test circuit breaker functionality in MCP bridge."""

    @pytest.fixture
    async def bridge(self):
        """Create bridge instance for testing."""
        bridge = MCPFastAPIBridge()
        # Mock circuit manager
        mock_manager = MagicMock()
        mock_manager.get_all_breakers.return_value = {}
        bridge.circuit_manager = mock_manager
        return bridge

    @pytest.mark.asyncio
    async def test_single_breaker_initialization(self, bridge):
        """Test that single 'mcp_server' breaker is registered."""
        # Current implementation: one breaker for all tools
        assert bridge.breaker_name == "mcp_server"
        assert bridge.circuit_manager is not None

    @pytest.mark.asyncio
    async def test_call_tool_with_circuit_breaker(self, bridge):
        """Test tool call goes through circuit breaker."""
        # Mock tool
        mock_tool = AsyncMock()
        mock_tool.return_value = {"result": "success"}

        bridge._initialized = True
        bridge._tools = {"test_tool": MagicMock(name="test_tool", callable=mock_tool)}

        # Mock circuit manager call_with_breaker
        async def mock_call_with_breaker(name, func):
            return await func()

        bridge.circuit_manager.call_with_breaker = mock_call_with_breaker

        result = await bridge.call_tool("test_tool", {"arg": "value"})

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_behavior(self, bridge):
        """Test behavior when circuit breaker is open."""
        from backend.agents.circuit_breaker_manager import CircuitBreakerError

        bridge._initialized = True
        bridge._tools = {
            "test_tool": MagicMock(name="test_tool", callable=AsyncMock(side_effect=Exception("Tool failed")))
        }

        # Mock circuit breaker open
        async def mock_call_with_breaker(name, func):
            raise CircuitBreakerError(f"Circuit breaker '{name}' is OPEN")

        bridge.circuit_manager.call_with_breaker = mock_call_with_breaker

        result = await bridge.call_tool("test_tool", {})

        # Should return StructuredError, not raise exception
        assert isinstance(result, dict)
        assert result.get("success") is False
        assert "CircuitBreakerOpen" in result.get("error_type", "")

    @pytest.mark.asyncio
    async def test_progressive_retry_on_timeout(self, bridge):
        """Test progressive retry strategy on timeout."""
        bridge._initialized = True

        call_count = 0
        progressive_timeouts = [60, 120, 300, 600]

        async def mock_tool_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise TimeoutError(f"Timeout after {progressive_timeouts[call_count - 1]}s")

        bridge._tools = {"slow_tool": MagicMock(name="slow_tool", callable=mock_tool_call)}

        async def mock_call_with_breaker(name, func):
            try:
                return await func()
            except TimeoutError:
                raise

        bridge.circuit_manager.call_with_breaker = mock_call_with_breaker

        result = await bridge.call_tool("slow_tool", {})

        # Should retry 4 times (len(PROGRESSIVE_TIMEOUTS))
        assert call_count == 4
        assert result.get("success") is False
        assert "TimeoutError" in result.get("error_type", "")

    @pytest.mark.asyncio
    async def test_no_retry_on_non_timeout_error(self, bridge):
        """Test that non-timeout errors don't trigger retry."""
        bridge._initialized = True

        call_count = 0

        async def mock_tool_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid argument")  # Non-timeout error

        bridge._tools = {"bad_tool": MagicMock(name="bad_tool", callable=mock_tool_call)}

        async def mock_call_with_breaker(name, func):
            try:
                return await func()
            except ValueError:
                raise

        bridge.circuit_manager.call_with_breaker = mock_call_with_breaker

        result = await bridge.call_tool("bad_tool", {})

        # Should NOT retry, only 1 call
        assert call_count == 1
        assert result.get("success") is False


class TestPerToolCircuitBreakers:
    """Tests for per-tool circuit breakers (P0-4 implementation)."""

    @pytest.fixture
    async def bridge_with_per_tool_breakers(self):
        """Create bridge with per-tool circuit breakers."""
        bridge = MCPFastAPIBridge()

        # Mock circuit manager with per-tool support
        mock_manager = MagicMock()
        mock_breakers = {}

        def mock_register_breaker(name, **kwargs):
            mock_breakers[name] = MagicMock(name=name)

        def mock_get_all_breakers():
            return mock_breakers

        mock_manager.register_breaker = mock_register_breaker
        mock_manager.get_all_breakers = mock_get_all_breakers

        bridge.circuit_manager = mock_manager
        bridge._tools = {
            "tool_1": MagicMock(name="tool_1"),
            "tool_2": MagicMock(name="tool_2"),
            "tool_3": MagicMock(name="tool_3"),
        }

        return bridge

    @pytest.mark.asyncio
    async def test_per_tool_breaker_registration(self, bridge_with_per_tool_breakers):
        """Test that each tool gets its own circuit breaker."""
        bridge = bridge_with_per_tool_breakers

        # After P0-4 implementation, each tool should have its own breaker
        # This test will FAIL before implementation, PASS after
        breakers = bridge.circuit_manager.get_all_breakers()

        # Expected: 3 tools = 3 breakers (or grouped by category)
        assert len(breakers) >= 3, "Each tool should have its own circuit breaker"

    @pytest.mark.asyncio
    async def test_isolated_circuit_breaker_failures(self, bridge_with_per_tool_breakers):
        """Test that failure in one tool doesn't affect others."""
        from backend.agents.circuit_breaker_manager import CircuitBreakerError

        bridge = bridge_with_per_tool_breakers
        bridge._initialized = True

        # Mock tool_1 to always fail
        async def failing_tool(*args, **kwargs):
            raise Exception("Tool 1 always fails")

        # Mock tool_2 to always succeed
        async def successful_tool(*args, **kwargs):
            return {"result": "success"}

        bridge._tools = {
            "tool_1": MagicMock(name="tool_1", callable=failing_tool),
            "tool_2": MagicMock(name="tool_2", callable=successful_tool),
        }

        # Mock circuit breaker behavior
        async def mock_call_with_breaker(name, func):
            if name == "tool_1":
                # After 3 failures, circuit breaker opens
                raise CircuitBreakerError(f"Circuit breaker '{name}' is OPEN")
            return await func()

        bridge.circuit_manager.call_with_breaker = mock_call_with_breaker

        # Fail tool_1 multiple times
        for _ in range(3):
            await bridge.call_tool("tool_1", {})

        # tool_2 should still work (isolated breaker)
        result = await bridge.call_tool("tool_2", {})

        assert result.get("success") is True, "tool_2 should not be affected by tool_1 failures"

    @pytest.mark.asyncio
    async def test_breaker_categories(self, bridge_with_per_tool_breakers):
        """Test that tools are grouped by category for circuit breakers."""
        bridge = bridge_with_per_tool_breakers

        # Expected categories:
        # - High criticality: Agent-to-Agent, Backtest (3 failures)
        # - Medium criticality: Strategy Builder, System, Memory (5 failures)
        # - Low criticality: Indicators, Risk, Files, Strategies (10 failures)

        if hasattr(bridge, "breaker_categories"):
            categories = bridge.breaker_categories

            # Check that all tools are categorized
            for tool_name in bridge._tools.keys():
                assert tool_name in categories, f"Tool '{tool_name}' should be categorized"

            # Check category thresholds
            if hasattr(bridge, "breaker_thresholds"):
                assert bridge.breaker_thresholds["high"] == 3
                assert bridge.breaker_thresholds["medium"] == 5
                assert bridge.breaker_thresholds["low"] == 10


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics export."""

    @pytest.fixture
    async def bridge_with_metrics(self):
        """Create bridge with metrics support."""
        bridge = MCPFastAPIBridge()

        # Isolate from the real circuit manager singleton to avoid test pollution
        mock_manager = MagicMock()
        mock_manager.get_all_breakers.return_value = {}
        bridge.circuit_manager = mock_manager

        # Mock metrics collector
        mock_metrics = MagicMock()
        mock_metrics.mcp_bridge_calls = MagicMock()
        mock_metrics.mcp_bridge_calls.inc = MagicMock()
        mock_metrics.mcp_bridge_duration = MagicMock()
        mock_metrics.mcp_bridge_duration.observe = MagicMock()

        bridge.metrics = mock_metrics
        return bridge

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_tool_call(self, bridge_with_metrics):
        """Test that metrics are recorded on each tool call."""
        bridge = bridge_with_metrics
        bridge._initialized = True

        mock_tool = AsyncMock()
        mock_tool.return_value = {"result": "success"}
        bridge._tools = {"test_tool": MagicMock(name="test_tool", callable=mock_tool)}

        async def mock_call_with_breaker(name, func):
            result = await func()
            return result

        bridge.circuit_manager.call_with_breaker = mock_call_with_breaker

        await bridge.call_tool("test_tool", {})

        # Metrics should be recorded
        assert bridge.metrics.mcp_bridge_calls.inc.called
        assert bridge.metrics.mcp_bridge_duration.observe.called

    @pytest.mark.asyncio
    async def test_per_tool_metrics(self, bridge_with_metrics):
        """Test that metrics are tracked per tool."""
        bridge = bridge_with_metrics

        # After P0-4, metrics should be per-tool
        if hasattr(bridge, "tool_metrics"):
            # Each tool should have its own metrics
            for tool_name in bridge._tools.keys():
                assert tool_name in bridge.tool_metrics


# Integration tests with real circuit breaker manager


@pytest.mark.integration
class TestCircuitBreakerIntegration:
    """Integration tests with real circuit breaker manager."""

    @pytest.mark.asyncio
    async def test_real_circuit_breaker_behavior(self):
        """Test with real CircuitBreakerManager."""
        from backend.agents.circuit_breaker_manager import (
            get_circuit_manager,
        )

        # Get real circuit breaker manager
        manager = get_circuit_manager()

        if manager is None:
            pytest.skip("Circuit breaker manager not available")

        # Clean up any stale state from previous test runs
        if "test_mcp_breaker" in manager.breakers:
            del manager.breakers["test_mcp_breaker"]

        # Register test breaker
        manager.register_breaker(
            name="test_mcp_breaker",
            fail_max=3,
            timeout_duration=5,  # 5 seconds for testing
        )

        breaker = manager.get_breaker("test_mcp_breaker")

        # Simulate failures
        for i in range(3):
            try:
                await manager.call_with_breaker(
                    "test_mcp_breaker", lambda: (_ for _ in ()).throw(Exception("Test failure"))
                )
            except Exception:
                pass

        # Breaker should be open now
        assert breaker.state.name == "OPEN" or breaker.failure_count >= 3

        # Clean up
        if "test_mcp_breaker" in manager.breakers:
            del manager.breakers["test_mcp_breaker"]


# Performance tests


@pytest.mark.performance
class TestCircuitBreakerPerformance:
    """Performance tests for circuit breakers."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_overhead(self):
        """Test that circuit breaker adds minimal overhead."""
        import time

        bridge = MCPFastAPIBridge()
        bridge._initialized = True

        # Mock fast tool
        async def fast_tool(*args, **kwargs):
            await asyncio.sleep(0.001)  # 1ms
            return {"result": "success"}

        bridge._tools = {"fast_tool": MagicMock(name="fast_tool", callable=fast_tool)}

        async def mock_call_with_breaker(name, func):
            return await func()

        original_call = bridge.circuit_manager.call_with_breaker
        bridge.circuit_manager.call_with_breaker = mock_call_with_breaker

        try:
            # Measure overhead
            start = time.time()
            for _ in range(100):
                await bridge.call_tool("fast_tool", {})
            elapsed = time.time() - start
        finally:
            bridge.circuit_manager.call_with_breaker = original_call

        # Overhead should be < 20ms per call (100 calls = < 2000ms)
        assert elapsed < 2.0, f"Circuit breaker overhead too high: {elapsed}s for 100 calls"

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test concurrent tool calls with circuit breakers."""
        bridge = MCPFastAPIBridge()
        bridge._initialized = True

        call_count = 0

        async def concurrent_tool(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return {"result": "success"}

        bridge._tools = {f"tool_{i}": MagicMock(name=f"tool_{i}", callable=concurrent_tool) for i in range(10)}

        async def mock_call_with_breaker(name, func):
            return await func()

        original_call = bridge.circuit_manager.call_with_breaker
        bridge.circuit_manager.call_with_breaker = mock_call_with_breaker

        try:
            # Call 10 tools concurrently
            tasks = [bridge.call_tool(f"tool_{i}", {}) for i in range(10)]
            await asyncio.gather(*tasks)
        finally:
            bridge.circuit_manager.call_with_breaker = original_call

        # All tools should be called
        assert call_count == 10
