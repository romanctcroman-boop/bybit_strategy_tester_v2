"""
integration_test_imports.py

Import adapter for integration tests using real components from the optimizations_output directory.

- Adds optimizations_output/ to sys.path for direct imports.
- Imports AsyncDataService, SR/RSI async functions, and BacktestEngine.
- Provides pytest fixture factories for test-friendly instantiation.
- Handles async context management for pytest-asyncio compatibility.
- Raises clear errors if imports fail.

Usage:
    from integration_test_imports import (
        create_test_data_service,
        create_test_backtest_engine,
        create_test_sr_rsi_functions,
    )

    # Use these factories in your pytest fixtures or test setup.
"""

import sys
from pathlib import Path

# --- Add optimizations_output/ to sys.path ---
try:
    # Path: tests/integration → bybit_strategy_tester_v2 → optimizations_output
    _optimizations_dir = Path(__file__).parent.parent.parent / "optimizations_output"
    if not _optimizations_dir.exists():
        raise FileNotFoundError(f"optimizations_output directory not found at: {_optimizations_dir}")
    sys.path.insert(0, str(_optimizations_dir.resolve()))
except Exception as e:
    raise ImportError(f"Failed to configure sys.path for optimizations_output: {e}")

# --- Import real components with error handling ---
try:
    from data_service_async_PRODUCTION_clean import AsyncDataService
except ImportError as e:
    raise ImportError(
        "Could not import AsyncDataService from data_service_async_PRODUCTION_clean.py. "
        "Check that the file exists and is error-free."
    ) from e

try:
    from sr_rsi_async_FIXED_v3 import (
        calculate_sr_levels_async,
        calculate_rsi_async,
        calculate_sr_rsi_parallel,
        test_sr_rsi_async,
    )
except ImportError as e:
    raise ImportError(
        "Could not import SR/RSI async functions from sr_rsi_async_FIXED_v3.py. "
        "Check that the file exists and is error-free."
    ) from e

try:
    # Use stable BacktestEngine from backend/core instead of optimizations_output
    import sys
    from pathlib import Path
    backend_core = Path(__file__).parent.parent.parent / "backend" / "core"
    if str(backend_core) not in sys.path:
        sys.path.insert(0, str(backend_core.resolve()))
    
    from backtest_engine import BacktestEngine
except ImportError as e:
    raise ImportError(
        "Could not import BacktestEngine from backend/core/backtest_engine.py. "
        "Check that the file exists and is error-free."
    ) from e

# --- Fixture Factories ---

def create_test_data_service(**kwargs):
    """
    Factory for AsyncDataService with test-friendly defaults.

    Args:
        max_concurrent (int): Maximum concurrent tasks (default: 10)
        pool_size (int): Pool size for async operations (default: 20)
        timeout (int): Timeout in seconds (default: 30)
        **kwargs: Additional keyword arguments for AsyncDataService

    Returns:
        AsyncDataService: Instance ready for use in tests.

    Usage:
        ds = create_test_data_service()
    """
    return AsyncDataService(
        max_concurrent=kwargs.get('max_concurrent', 10),
        pool_size=kwargs.get('pool_size', 20),
        timeout=kwargs.get('timeout', 30),
        **{k: v for k, v in kwargs.items() if k not in {'max_concurrent', 'pool_size', 'timeout'}}
    )

def create_test_backtest_engine(**kwargs):
    """
    Factory for BacktestEngine with test-friendly defaults.

    Args:
        **kwargs: Arguments for BacktestEngine constructor.

    Returns:
        BacktestEngine: Instance ready for use in tests.

    Usage:
        engine = create_test_backtest_engine(param1=..., param2=...)
    """
    return BacktestEngine(**kwargs)

def create_test_sr_rsi_functions():
    """
    Provides direct access to SR/RSI async calculation functions.

    Returns:
        dict: {
            'calculate_sr_levels_async': <function>,
            'calculate_rsi_async': <function>,
            'calculate_sr_rsi_parallel': <function>,
            'test_sr_rsi_async': <function>
        }

    Usage:
        funcs = create_test_sr_rsi_functions()
        await funcs['calculate_sr_levels_async'](...)
    """
    return {
        'calculate_sr_levels_async': calculate_sr_levels_async,
        'calculate_rsi_async': calculate_rsi_async,
        'calculate_sr_rsi_parallel': calculate_sr_rsi_parallel,
        'test_sr_rsi_async': test_sr_rsi_async,
    }

# --- Async Context Manager Helpers ---

import asyncio

class AsyncDataServiceTestContext:
    """
    Async context manager for AsyncDataService to ensure proper resource cleanup in tests.

    Usage:
        async with AsyncDataServiceTestContext() as ds:
            ...
    """
    def __init__(self, **kwargs):
        self.ds = create_test_data_service(**kwargs)

    async def __aenter__(self):
        return self.ds

    async def __aexit__(self, exc_type, exc, tb):
        # Ensure proper async cleanup if AsyncDataService has a close() coroutine
        close = getattr(self.ds, "close", None)
        if callable(close):
            if asyncio.iscoroutinefunction(close):
                await close()
            else:
                close()

# --- Pytest Fixtures (for direct use in test modules) ---

# Note: These are factories, not registered pytest fixtures.
# To use as pytest fixtures, import and use in your conftest.py or test modules, e.g.:
#
# @pytest.fixture
# async def data_service():
#     async with AsyncDataServiceTestContext() as ds:
#         yield ds

# --- End of integration_test_imports.py ---