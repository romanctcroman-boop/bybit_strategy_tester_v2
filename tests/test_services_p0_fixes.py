"""
Tests for Services System P0 Fixes.

Tests for critical fixes identified in the services system audit:
- P0 #1: HTTP client resource leak in OrderExecutor
- P0 #2: API credentials encryption in memory
- P0 #3: Thread-safe cache in Bybit adapter
- P0 #4: Graceful shutdown for live trading
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOrderExecutorContextManager:
    """Test P0 #1-2: HTTP client leak and credential encryption."""

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Test that context manager properly closes HTTP client."""
        from backend.services.live_trading.order_executor import OrderExecutor

        executor = None
        async with OrderExecutor(
            api_key="test_key",
            api_secret="test_secret",
            testnet=True,
        ) as executor:
            # Client should be available
            assert not executor._closed
            client = await executor._get_client()
            assert client is not None

        # After exit, should be closed
        assert executor._closed

    @pytest.mark.asyncio
    async def test_close_clears_credentials(self):
        """Test that close() clears sensitive data from memory."""
        from backend.services.live_trading.order_executor import OrderExecutor

        executor = OrderExecutor(
            api_key="secret_api_key_12345",
            api_secret="secret_api_secret_67890",
            testnet=True,
        )

        # Verify we can decrypt before close
        assert executor.api_key == "secret_api_key_12345"
        assert executor.api_secret == "secret_api_secret_67890"

        await executor.close()

        # After close, encrypted data should be cleared
        assert executor._api_key_encrypted == b""
        assert executor._api_secret_encrypted == b""

    @pytest.mark.asyncio
    async def test_credentials_encrypted_in_memory(self):
        """Test that credentials are not stored in plaintext."""
        from backend.services.live_trading.order_executor import OrderExecutor

        test_key = "my_api_key_123"
        test_secret = "my_api_secret_456"

        executor = OrderExecutor(
            api_key=test_key,
            api_secret=test_secret,
            testnet=True,
        )

        # Encrypted bytes should not contain plaintext
        assert test_key.encode() != executor._api_key_encrypted
        assert test_secret.encode() != executor._api_secret_encrypted

        # But decryption should work
        assert executor.api_key == test_key
        assert executor.api_secret == test_secret

        await executor.close()

    @pytest.mark.asyncio
    async def test_double_close_is_safe(self):
        """Test that calling close() multiple times is safe."""
        from backend.services.live_trading.order_executor import OrderExecutor

        executor = OrderExecutor(
            api_key="test",
            api_secret="test",
            testnet=True,
        )

        # Close multiple times - should not raise
        await executor.close()
        await executor.close()
        await executor.close()

        assert executor._closed

    @pytest.mark.asyncio
    async def test_get_client_after_close_raises(self):
        """Test that _get_client() raises after close."""
        from backend.services.live_trading.order_executor import OrderExecutor

        executor = OrderExecutor(
            api_key="test",
            api_secret="test",
            testnet=True,
        )

        await executor.close()

        with pytest.raises(RuntimeError, match="closed"):
            await executor._get_client()

    @pytest.mark.asyncio
    async def test_lazy_client_initialization(self):
        """Test that HTTP client is lazily initialized."""
        from backend.services.live_trading.order_executor import OrderExecutor

        executor = OrderExecutor(
            api_key="test",
            api_secret="test",
            testnet=True,
        )

        # Client should be None initially
        assert executor._client is None

        # After getting client, it should be created
        client = await executor._get_client()
        assert executor._client is not None
        assert executor._client is client

        await executor.close()


class TestBybitAdapterThreadSafety:
    """Test P0 #3: Thread-safe cache in Bybit adapter."""

    def test_cache_lock_exists(self):
        """Test that cache lock is created."""
        from backend.services.adapters.bybit import BybitAdapter

        adapter = BybitAdapter()
        assert hasattr(adapter, "_cache_lock")
        assert isinstance(adapter._cache_lock, type(threading.RLock()))

    def test_concurrent_cache_access(self):
        """Test that concurrent cache access doesn't cause race conditions."""
        from backend.services.adapters.bybit import BybitAdapter

        adapter = BybitAdapter(timeout=5)
        errors = []

        def access_cache(thread_id: int):
            try:
                for _ in range(10):
                    # Read cache
                    with adapter._cache_lock:
                        _ = dict(adapter._instruments_cache)

                    # Write cache
                    with adapter._cache_lock:
                        adapter._instruments_cache[f"TEST{thread_id}USDT"] = {
                            "symbol": f"TEST{thread_id}USDT",
                            "status": "Trading",
                        }
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        # Run concurrent access
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(access_cache, i) for i in range(10)]
            for f in futures:
                f.result()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    @patch("backend.services.adapters.bybit.requests.get")
    def test_refresh_cache_double_check_locking(self, mock_get):
        """Test that refresh uses double-check locking pattern."""
        from backend.services.adapters.bybit import BybitAdapter

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "list": [
                    {"symbol": "BTCUSDT", "status": "Trading"},
                    {"symbol": "ETHUSDT", "status": "Trading"},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        adapter = BybitAdapter(timeout=5)

        # First refresh should call API
        adapter._refresh_instruments_cache(force=True)
        assert mock_get.call_count == 1
        assert "BTCUSDT" in adapter._instruments_cache

        # Second refresh within TTL should not call API
        adapter._refresh_instruments_cache(force=False)
        assert mock_get.call_count == 1  # Still 1


class TestGracefulShutdown:
    """Test P0 #4: Graceful shutdown for live trading."""

    @pytest.mark.asyncio
    async def test_shutdown_manager_basic(self):
        """Test basic shutdown manager functionality."""
        from backend.services.live_trading.graceful_shutdown import (
            GracefulShutdownManager,
            ShutdownState,
        )

        manager = GracefulShutdownManager(timeout=5.0)

        # Initial state
        assert manager.context.state == ShutdownState.RUNNING
        assert not manager.is_shutting_down
        assert not manager.shutdown_requested

        # Request shutdown
        manager.request_shutdown("Test shutdown")
        assert manager.shutdown_requested
        assert manager.context.reason == "Test shutdown"

        # Execute shutdown
        context = await manager.shutdown()
        assert context.state == ShutdownState.SHUTDOWN_COMPLETE
        assert len(context.errors) == 0

    @pytest.mark.asyncio
    async def test_shutdown_components_in_order(self):
        """Test that components are shutdown in priority order."""
        from backend.services.live_trading.graceful_shutdown import (
            GracefulShutdownManager,
        )

        shutdown_order = []

        async def strategy_stop():
            shutdown_order.append("strategy_runner")

        async def position_stop():
            shutdown_order.append("position_manager")

        async def executor_close():
            shutdown_order.append("order_executor")

        manager = GracefulShutdownManager(timeout=5.0)
        manager.register_component("order_executor", executor_close)  # Priority 3
        manager.register_component("strategy_runner", strategy_stop)  # Priority 1
        manager.register_component("position_manager", position_stop)  # Priority 2

        manager.request_shutdown("Test")
        await manager.shutdown()

        # Should be in priority order
        assert shutdown_order == ["strategy_runner", "position_manager", "order_executor"]

    @pytest.mark.asyncio
    async def test_context_manager_usage(self):
        """Test shutdown manager as async context manager."""
        from backend.services.live_trading.graceful_shutdown import (
            GracefulShutdownManager,
            ShutdownState,
        )

        async with GracefulShutdownManager(timeout=2.0) as manager:
            assert manager.context.state == ShutdownState.RUNNING

        # After exit, should be complete
        assert manager.context.state == ShutdownState.SHUTDOWN_COMPLETE

    @pytest.mark.asyncio
    async def test_shutdown_with_position_closing(self):
        """Test shutdown with position closing enabled."""
        from backend.services.live_trading.graceful_shutdown import (
            GracefulShutdownManager,
        )

        positions_closed = []

        async def close_positions():
            positions_closed.append("BTCUSDT")
            positions_closed.append("ETHUSDT")
            return {"BTCUSDT": True, "ETHUSDT": True}

        manager = GracefulShutdownManager(
            timeout=5.0,
            close_positions_on_shutdown=True,
        )
        manager.set_position_closer(close_positions)
        manager.request_shutdown("Test")

        context = await manager.shutdown()

        assert "BTCUSDT" in context.closed_positions
        assert "ETHUSDT" in context.closed_positions

    @pytest.mark.asyncio
    async def test_shutdown_callback_notification(self):
        """Test that callbacks are notified on shutdown."""
        from backend.services.live_trading.graceful_shutdown import (
            GracefulShutdownManager,
        )

        callback_called = []

        async def on_shutdown(context):
            callback_called.append(True)

        manager = GracefulShutdownManager(timeout=5.0)
        manager.on_shutdown(on_shutdown)
        manager.request_shutdown("Test")

        await manager.shutdown()

        assert len(callback_called) == 1

    @pytest.mark.asyncio
    async def test_setup_convenience_function(self):
        """Test setup_graceful_shutdown convenience function."""
        from backend.services.live_trading.graceful_shutdown import (
            ShutdownState,
            setup_graceful_shutdown,
        )

        shutdown_called = []

        async def stop1():
            shutdown_called.append("runner")

        async def stop2():
            shutdown_called.append("executor")

        manager = setup_graceful_shutdown(
            ("strategy_runner", stop1),
            ("order_executor", stop2),
            timeout=5.0,
        )

        # Uninstall handlers for test
        manager.uninstall_signal_handlers()

        manager.request_shutdown("Test")
        await manager.shutdown()

        assert manager.context.state == ShutdownState.SHUTDOWN_COMPLETE
        assert "runner" in shutdown_called
        assert "executor" in shutdown_called

    @pytest.mark.asyncio
    async def test_shutdown_handles_component_errors(self):
        """Test that shutdown continues even if component fails."""
        from backend.services.live_trading.graceful_shutdown import (
            GracefulShutdownManager,
        )

        async def failing_component():
            raise RuntimeError("Component failed!")

        async def working_component():
            pass

        manager = GracefulShutdownManager(timeout=5.0)
        manager.register_component("failing", failing_component)
        manager.register_component("working", working_component)
        manager.request_shutdown("Test")

        context = await manager.shutdown()

        # Should complete despite error
        assert len(context.errors) >= 1
        assert any("failed" in e.lower() for e in context.errors)


class TestXOREncryption:
    """Test credential encryption utility."""

    def test_xor_encrypt_decrypt(self):
        """Test XOR encryption roundtrip."""
        from backend.services.live_trading.order_executor import OrderExecutor

        key = b"0123456789abcdef"
        data = b"sensitive_data_here"

        encrypted = OrderExecutor._xor_encrypt(data, key)
        decrypted = OrderExecutor._xor_encrypt(encrypted, key)

        assert encrypted != data
        assert decrypted == data

    def test_xor_different_keys(self):
        """Test that different keys produce different results."""
        from backend.services.live_trading.order_executor import OrderExecutor

        data = b"test_data"
        key1 = b"key1key1key1key1"
        key2 = b"key2key2key2key2"

        encrypted1 = OrderExecutor._xor_encrypt(data, key1)
        encrypted2 = OrderExecutor._xor_encrypt(data, key2)

        assert encrypted1 != encrypted2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
