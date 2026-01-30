"""
Graceful Shutdown Manager for Live Trading.

Handles orderly shutdown of live trading components when receiving
system signals (SIGINT, SIGTERM) or application shutdown events.

Features:
- Signal handling for graceful termination
- Ordered shutdown sequence
- Position closing before shutdown
- Trade state persistence
- Timeout handling for stuck operations
"""

import asyncio
import atexit
import logging
import signal
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ShutdownState(Enum):
    """Shutdown state enum."""

    RUNNING = "running"
    SHUTDOWN_REQUESTED = "shutdown_requested"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN_COMPLETE = "shutdown_complete"


@dataclass
class ShutdownContext:
    """Context for shutdown operations."""

    state: ShutdownState = ShutdownState.RUNNING
    reason: str = ""
    requested_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    errors: list[str] = field(default_factory=list)
    closed_positions: list[str] = field(default_factory=list)


class GracefulShutdownManager:
    """
    Manages graceful shutdown for live trading components.

    Usage:
        shutdown_manager = GracefulShutdownManager()

        # Register components
        shutdown_manager.register_component("position_manager", position_manager.stop)
        shutdown_manager.register_component("strategy_runner", runner.stop)
        shutdown_manager.register_component("order_executor", executor.close)

        # Install signal handlers
        shutdown_manager.install_signal_handlers()

        # Or use as context manager
        async with shutdown_manager:
            # Your trading code
            await run_trading()
    """

    # Default shutdown timeout in seconds
    DEFAULT_TIMEOUT = 30.0

    # Component shutdown order priority (lower = shutdown first)
    PRIORITY_ORDER = {
        "strategy_runner": 1,  # Stop generating signals first
        "position_manager": 2,  # Then stop position tracking
        "order_executor": 3,  # Then close order connections
        "websocket_client": 4,  # Then close WebSocket
        "default": 10,  # Unknown components shutdown last
    }

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        close_positions_on_shutdown: bool = False,
    ):
        """
        Initialize shutdown manager.

        Args:
            timeout: Maximum time to wait for shutdown in seconds
            close_positions_on_shutdown: If True, close all positions before shutdown
        """
        self.timeout = timeout
        self.close_positions_on_shutdown = close_positions_on_shutdown

        self._context = ShutdownContext()
        self._components: dict[str, Callable] = {}
        self._position_closer: Optional[Callable] = None
        self._callbacks: list[Callable] = []
        self._shutdown_event = asyncio.Event()
        self._original_handlers: dict[signal.Signals, Optional[signal.Handlers]] = {}

        logger.info(
            f"GracefulShutdownManager initialized (timeout={timeout}s, close_positions={close_positions_on_shutdown})"
        )

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._context.state in (
            ShutdownState.SHUTDOWN_REQUESTED,
            ShutdownState.SHUTTING_DOWN,
        )

    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._context.state != ShutdownState.RUNNING

    @property
    def context(self) -> ShutdownContext:
        """Get current shutdown context."""
        return self._context

    def register_component(
        self,
        name: str,
        shutdown_func: Callable,
    ) -> None:
        """
        Register a component for orderly shutdown.

        Args:
            name: Component name (used for priority ordering)
            shutdown_func: Async or sync function to call on shutdown
        """
        self._components[name] = shutdown_func
        logger.debug(f"Registered component for shutdown: {name}")

    def unregister_component(self, name: str) -> None:
        """Unregister a component."""
        if name in self._components:
            del self._components[name]
            logger.debug(f"Unregistered component: {name}")

    def set_position_closer(self, closer: Callable) -> None:
        """
        Set function to close all positions.

        Args:
            closer: Async function that closes all positions
        """
        self._position_closer = closer

    def on_shutdown(self, callback: Callable) -> None:
        """
        Register callback to be called on shutdown.

        Args:
            callback: Async or sync function to call
        """
        self._callbacks.append(callback)

    def install_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown."""
        # Handle SIGINT (Ctrl+C) and SIGTERM (kill)
        signals_to_handle = [signal.SIGINT, signal.SIGTERM]

        # On Windows, SIGBREAK is also useful
        if sys.platform == "win32":
            signals_to_handle.append(signal.SIGBREAK)

        for sig in signals_to_handle:
            try:
                # Store original handler
                self._original_handlers[sig] = signal.getsignal(sig)

                # Install our handler
                signal.signal(sig, self._signal_handler)
                logger.debug(f"Installed handler for {sig.name}")
            except (ValueError, OSError) as e:
                logger.warning(f"Could not install handler for {sig}: {e}")

        # Register atexit handler for cleanup
        atexit.register(self._atexit_handler)

    def uninstall_signal_handlers(self) -> None:
        """Restore original signal handlers."""
        for sig, original in self._original_handlers.items():
            try:
                if original is not None:
                    signal.signal(sig, original)
                else:
                    signal.signal(sig, signal.SIG_DFL)
                logger.debug(f"Restored handler for {sig.name}")
            except (ValueError, OSError) as e:
                logger.warning(f"Could not restore handler for {sig}: {e}")

        self._original_handlers.clear()

    def _signal_handler(self, signum: int, frame) -> None:
        """Signal handler callback."""
        sig_name = signal.Signals(signum).name
        logger.warning(f"Received signal {sig_name}, initiating graceful shutdown...")

        # Request shutdown
        self.request_shutdown(f"Signal {sig_name}")

        # Schedule async shutdown in event loop if running
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.shutdown())
        except RuntimeError:
            # No running loop, will be handled by atexit
            pass

    def _atexit_handler(self) -> None:
        """Atexit handler for final cleanup."""
        if self._context.state == ShutdownState.RUNNING:
            logger.info("Atexit handler triggered, performing cleanup...")
            # Can't run async code in atexit, but we can log
            self._context.state = ShutdownState.SHUTDOWN_COMPLETE

    def request_shutdown(self, reason: str = "Requested") -> None:
        """
        Request shutdown initiation.

        Args:
            reason: Reason for shutdown
        """
        if self._context.state == ShutdownState.RUNNING:
            self._context.state = ShutdownState.SHUTDOWN_REQUESTED
            self._context.reason = reason
            self._context.requested_at = datetime.now(timezone.utc)
            self._shutdown_event.set()
            logger.info(f"Shutdown requested: {reason}")

    async def wait_for_shutdown(self) -> None:
        """Wait until shutdown is requested."""
        await self._shutdown_event.wait()

    async def shutdown(self) -> ShutdownContext:
        """
        Execute graceful shutdown sequence.

        Returns:
            ShutdownContext with shutdown results
        """
        if self._context.state == ShutdownState.SHUTDOWN_COMPLETE:
            return self._context

        if self._context.state == ShutdownState.SHUTTING_DOWN:
            logger.warning("Shutdown already in progress")
            return self._context

        self._context.state = ShutdownState.SHUTTING_DOWN
        logger.info(f"Starting graceful shutdown (reason: {self._context.reason})")

        try:
            # Phase 1: Close positions if configured
            if self.close_positions_on_shutdown and self._position_closer:
                await self._close_positions()

            # Phase 2: Notify callbacks
            await self._notify_callbacks()

            # Phase 3: Shutdown components in order
            await self._shutdown_components()

        except asyncio.TimeoutError:
            error = f"Shutdown timed out after {self.timeout}s"
            logger.error(error)
            self._context.errors.append(error)
        except Exception as e:
            error = f"Shutdown error: {e}"
            logger.exception(error)
            self._context.errors.append(error)
        finally:
            self._context.state = ShutdownState.SHUTDOWN_COMPLETE
            self._context.completed_at = datetime.now(timezone.utc)

            # Uninstall signal handlers
            self.uninstall_signal_handlers()

            if self._context.errors:
                logger.warning(f"Shutdown completed with {len(self._context.errors)} errors")
            else:
                logger.info("Graceful shutdown completed successfully")

        return self._context

    async def _close_positions(self) -> None:
        """Close all positions before shutdown."""
        logger.info("Closing all positions before shutdown...")

        try:
            async with asyncio.timeout(self.timeout / 3):
                if asyncio.iscoroutinefunction(self._position_closer):
                    result = await self._position_closer()
                else:
                    result = self._position_closer()

                if isinstance(result, dict):
                    for symbol, success in result.items():
                        if success:
                            self._context.closed_positions.append(symbol)
                        else:
                            self._context.errors.append(f"Failed to close position: {symbol}")

                logger.info(f"Closed {len(self._context.closed_positions)} positions")
        except asyncio.TimeoutError:
            logger.warning("Position closing timed out")
            self._context.errors.append("Position closing timed out")
        except Exception as e:
            logger.error(f"Error closing positions: {e}")
            self._context.errors.append(f"Position close error: {e}")

    async def _notify_callbacks(self) -> None:
        """Notify registered callbacks."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self._context)
                else:
                    callback(self._context)
            except Exception as e:
                logger.error(f"Callback error: {e}")
                self._context.errors.append(f"Callback error: {e}")

    async def _shutdown_components(self) -> None:
        """Shutdown all registered components in order."""
        # Sort components by priority
        sorted_components = sorted(
            self._components.items(), key=lambda x: self.PRIORITY_ORDER.get(x[0], self.PRIORITY_ORDER["default"])
        )

        remaining_timeout = self.timeout * 2 / 3  # 2/3 of timeout for components
        time_per_component = remaining_timeout / max(len(sorted_components), 1)

        for name, shutdown_func in sorted_components:
            logger.info(f"Shutting down component: {name}")

            try:
                async with asyncio.timeout(time_per_component):
                    if asyncio.iscoroutinefunction(shutdown_func):
                        await shutdown_func()
                    else:
                        shutdown_func()
                logger.debug(f"Component {name} shutdown complete")
            except asyncio.TimeoutError:
                error = f"Component {name} shutdown timed out"
                logger.warning(error)
                self._context.errors.append(error)
            except Exception as e:
                error = f"Component {name} shutdown error: {e}"
                logger.error(error)
                self._context.errors.append(error)

    # Context manager support
    async def __aenter__(self) -> "GracefulShutdownManager":
        """Async context manager entry."""
        self.install_signal_handlers()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.shutdown()


# Convenience function for quick setup
def setup_graceful_shutdown(
    *components: tuple[str, Callable],
    position_closer: Optional[Callable] = None,
    close_positions: bool = False,
    timeout: float = 30.0,
) -> GracefulShutdownManager:
    """
    Quick setup for graceful shutdown.

    Usage:
        shutdown_manager = setup_graceful_shutdown(
            ("runner", runner.stop),
            ("executor", executor.close),
            position_closer=position_manager.close_all_positions,
            close_positions=True
        )

    Args:
        *components: Tuples of (name, shutdown_func)
        position_closer: Function to close positions
        close_positions: Whether to close positions on shutdown
        timeout: Shutdown timeout

    Returns:
        Configured GracefulShutdownManager
    """
    manager = GracefulShutdownManager(
        timeout=timeout,
        close_positions_on_shutdown=close_positions,
    )

    for name, func in components:
        manager.register_component(name, func)

    if position_closer:
        manager.set_position_closer(position_closer)

    manager.install_signal_handlers()

    return manager


@contextmanager
def shutdown_guard(manager: GracefulShutdownManager):
    """
    Synchronous context manager for shutdown protection.

    Usage:
        with shutdown_guard(manager):
            # Protected code that shouldn't be interrupted
            execute_critical_operation()
    """
    if manager.is_shutting_down:
        raise RuntimeError("Shutdown in progress, cannot execute protected code")

    yield

    if manager.is_shutting_down:
        logger.warning("Shutdown was requested during protected operation")
