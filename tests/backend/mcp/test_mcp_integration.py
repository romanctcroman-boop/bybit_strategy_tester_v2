"""
Integration tests for MCP Circuit Breakers (P0-4 implementation)

These tests use the real MCP bridge and circuit breaker manager.
"""

import pytest

from backend.mcp.mcp_integration import get_mcp_bridge


@pytest.mark.integration
class TestMCPBridgePerToolBreakersIntegration:
    """Integration tests for per-tool circuit breakers."""

    @pytest.fixture
    async def real_bridge(self):
        """Create real bridge instance (no mocks)."""
        bridge = get_mcp_bridge()
        # Don't initialize - we'll test initialization separately
        return bridge

    @pytest.mark.asyncio
    async def test_bridge_initialization_registers_breakers(self, real_bridge):
        """Test that initialization registers per-tool breakers."""
        # Initialize bridge
        await real_bridge.initialize()

        # Check that breakers are registered
        assert len(real_bridge.circuit_breakers) > 0, "Per-tool breakers should be registered after initialization"

        # Check that categories are assigned
        assert len(real_bridge.breaker_categories) > 0, "Tool categories should be assigned after initialization"

        # Check that metrics are initialized
        assert len(real_bridge.tool_metrics) > 0, "Tool metrics should be initialized after initialization"

        print(f"✅ Registered {len(real_bridge.circuit_breakers)} per-tool breakers")

    @pytest.mark.asyncio
    async def test_breaker_categories_assigned(self, real_bridge):
        """Test that all tools have categories assigned."""
        await real_bridge.initialize()

        # Every tool should have a category
        for tool_name in real_bridge._tools.keys():
            assert tool_name in real_bridge.breaker_categories, f"Tool '{tool_name}' should have a category"

            category = real_bridge.breaker_categories[tool_name]
            assert category in ["high", "medium", "low"], f"Category for '{tool_name}' should be high/medium/low"

        print(f"✅ All {len(real_bridge.breaker_categories)} tools categorized")

    @pytest.mark.asyncio
    async def test_high_criticality_tools(self, real_bridge):
        """Test that high criticality tools are correctly categorized."""
        await real_bridge.initialize()

        # Expected high criticality tools
        high_tools = [
            "mcp_agent_to_agent_send_to_deepseek",
            "mcp_agent_to_agent_send_to_perplexity",
            "mcp_agent_to_agent_get_consensus",
        ]

        for tool_name in high_tools:
            if tool_name in real_bridge._tools:
                category = real_bridge.breaker_categories.get(tool_name)
                assert category == "high", f"Tool '{tool_name}' should be high criticality"

        print("✅ High criticality tools correctly categorized")

    @pytest.mark.asyncio
    async def test_breaker_thresholds(self, real_bridge):
        """Test that breaker thresholds match categories."""
        await real_bridge.initialize()

        # Check thresholds
        assert real_bridge.BREAKER_THRESHOLDS["high"] == 3
        assert real_bridge.BREAKER_THRESHOLDS["medium"] == 5
        assert real_bridge.BREAKER_THRESHOLDS["low"] == 10

        print("✅ Breaker thresholds correctly configured")

    @pytest.mark.asyncio
    async def test_metrics_initialized(self, real_bridge):
        """Test that metrics are initialized for all tools."""
        await real_bridge.initialize()

        # Every tool should have metrics
        for tool_name in real_bridge._tools.keys():
            assert tool_name in real_bridge.tool_metrics, f"Tool '{tool_name}' should have metrics"

            metrics = real_bridge.tool_metrics[tool_name]

            # Check required fields
            required_fields = [
                "calls",
                "successes",
                "failures",
                "timeouts",
                "circuit_breaks",
                "last_call",
                "last_error",
                "avg_latency_ms",
            ]
            for field in required_fields:
                assert field in metrics, f"Metrics for '{tool_name}' should have '{field}' field"

        print(f"✅ Metrics initialized for {len(real_bridge.tool_metrics)} tools")

    @pytest.mark.asyncio
    async def test_get_tool_metrics_api(self, real_bridge):
        """Test get_tool_metrics() API."""
        await real_bridge.initialize()

        # Get metrics for specific tool
        if real_bridge._tools:
            first_tool = list(real_bridge._tools.keys())[0]
            metrics = real_bridge.get_tool_metrics(first_tool)

            assert isinstance(metrics, dict)
            assert "calls" in metrics

            # Get all metrics
            all_metrics = real_bridge.get_tool_metrics()
            assert isinstance(all_metrics, dict)
            assert len(all_metrics) == len(real_bridge.tool_metrics)

        print("✅ get_tool_metrics() API works correctly")

    @pytest.mark.asyncio
    async def test_get_breaker_status_api(self, real_bridge):
        """Test get_breaker_status() API."""
        await real_bridge.initialize()

        # Get status for specific tool
        if real_bridge._tools:
            first_tool = list(real_bridge._tools.keys())[0]
            status = real_bridge.get_breaker_status(first_tool)

            assert isinstance(status, dict)
            assert "tool" in status
            assert "breaker_name" in status
            assert "category" in status
            assert "state" in status
            assert "threshold" in status

            # Check values
            assert status["tool"] == first_tool
            assert status["category"] in ["high", "medium", "low"]
            assert status["threshold"] in [3, 5, 10]

            # Get all statuses
            all_statuses = real_bridge.get_breaker_status()
            assert isinstance(all_statuses, dict)

        print("✅ get_breaker_status() API works correctly")

    @pytest.mark.asyncio
    async def test_isolated_breaker_behavior(self, real_bridge):
        """Test that breakers are isolated per tool."""
        await real_bridge.initialize()

        if len(real_bridge._tools) < 2:
            pytest.skip("Need at least 2 tools for isolation test")

        # Get two different tools
        tools = list(real_bridge._tools.keys())[:2]
        tool1, tool2 = tools

        # Get breaker names
        breaker1 = real_bridge.circuit_breakers.get(tool1)
        breaker2 = real_bridge.circuit_breakers.get(tool2)

        # Breakers should be different
        assert breaker1 != breaker2, f"Tools '{tool1}' and '{tool2}' should have different breakers"

        print(f"✅ Breakers are isolated: {breaker1} != {breaker2}")

    @pytest.mark.asyncio
    async def test_category_based_thresholds(self, real_bridge):
        """Test that different categories have different thresholds."""
        await real_bridge.initialize()

        # Group tools by category
        by_category = {"high": [], "medium": [], "low": []}

        for tool_name, category in real_bridge.breaker_categories.items():
            by_category[category].append(tool_name)

        # Check that we have tools in different categories
        categories_with_tools = [cat for cat, tools in by_category.items() if tools]

        assert len(categories_with_tools) >= 2, "Should have tools in at least 2 categories"

        print(f"✅ Tools distributed across categories: {categories_with_tools}")


@pytest.mark.asyncio
class TestMCPBridgeMetricsRecording:
    """Test metrics recording in real bridge."""

    @pytest.fixture
    async def initialized_bridge(self):
        """Create and initialize real bridge."""
        bridge = get_mcp_bridge()
        await bridge.initialize()
        return bridge

    async def test_metrics_recorded_on_call(self, initialized_bridge):
        """Test that metrics are recorded when calling tool."""
        if not initialized_bridge._tools:
            pytest.skip("No tools available")

        # Get first tool
        tool_name = list(initialized_bridge._tools.keys())[0]

        # Get initial metrics
        initial_metrics = initialized_bridge.get_tool_metrics(tool_name)
        initial_calls = initial_metrics.get("calls", 0)

        # Try to call tool (may fail, but metrics should be recorded)
        try:
            await initialized_bridge.call_tool(tool_name, {})
        except Exception:
            pass  # Expected - tool may require specific arguments

        # Check that calls counter incremented
        current_metrics = initialized_bridge.get_tool_metrics(tool_name)
        current_calls = current_metrics.get("calls", 0)

        assert current_calls > initial_calls, "Calls counter should increment on tool call"

        print(f"✅ Metrics recorded: calls={current_calls}")

    async def test_latency_tracking(self, initialized_bridge):
        """Test that latency is tracked for successful calls."""
        # This test requires a tool that can be successfully called
        # For now, just check that the field exists and is numeric

        for tool_name, metrics in initialized_bridge.tool_metrics.items():
            assert "avg_latency_ms" in metrics
            assert isinstance(metrics["avg_latency_ms"], (int, float))

        print(f"✅ Latency tracking initialized for {len(initialized_bridge.tool_metrics)} tools")


# Performance benchmarks


@pytest.mark.benchmark
class TestCircuitBreakerPerformance:
    """Performance benchmarks for circuit breakers."""

    @pytest.fixture
    async def initialized_bridge(self):
        """Create and initialize real bridge."""
        bridge = get_mcp_bridge()
        await bridge.initialize()
        return bridge

    @pytest.mark.asyncio
    async def test_breaker_overhead(self, initialized_bridge):
        """Benchmark circuit breaker overhead."""
        import time

        if not initialized_bridge._tools:
            pytest.skip("No tools available")

        tool_name = list(initialized_bridge._tools.keys())[0]

        # Warmup
        try:
            await initialized_bridge.call_tool(tool_name, {})
        except Exception:
            pass

        # Benchmark
        iterations = 100
        start = time.perf_counter()

        for _ in range(iterations):
            try:
                await initialized_bridge.call_tool(tool_name, {})
            except Exception:
                pass

        elapsed = time.perf_counter() - start
        avg_per_call = (elapsed / iterations) * 1000  # ms

        # Overhead should be < 10ms per call
        assert avg_per_call < 10, f"Circuit breaker overhead too high: {avg_per_call:.2f}ms per call"

        print(f"✅ Breaker overhead: {avg_per_call:.2f}ms per call (target: <10ms)")
