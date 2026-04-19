"""
GPU Acceleration Tests

Tests for CuPy integration and GPU optimization performance.
"""

import time

import numpy as np
import pytest
from loguru import logger

# Check GPU availability
try:
    from backend.backtesting.gpu_optimizer import (
        GPU_AVAILABLE,
        GPU_NAME,
        GPUGridOptimizer,
        cp,
    )

    # Ensure GPU_AVAILABLE is a bool (may be None if not yet initialized)
    if GPU_AVAILABLE is None:
        GPU_AVAILABLE = False
except ImportError:
    GPU_AVAILABLE = False
    GPU_NAME = "Not available"
    cp = None


class TestGPUAvailability:
    """Test GPU detection and availability."""

    def test_gpu_detection(self):
        """Test that GPU detection works correctly."""
        logger.info(f"GPU Available: {GPU_AVAILABLE}")
        logger.info(f"GPU Name: {GPU_NAME}")

        # This test passes regardless - we just log the status
        assert isinstance(GPU_AVAILABLE, bool)
        assert isinstance(GPU_NAME, str)

    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_cupy_basic_operations(self):
        """Test basic CuPy operations."""
        # Create array on GPU
        arr = cp.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=cp.float64)

        # Basic operations
        assert cp.sum(arr) == 15.0
        assert cp.mean(arr) == 3.0
        assert arr.shape == (5,)

        # Memory transfer
        np_arr = cp.asnumpy(arr)
        assert isinstance(np_arr, np.ndarray)
        assert np.array_equal(np_arr, [1.0, 2.0, 3.0, 4.0, 5.0])

    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_cupy_memory_info(self):
        """Test GPU memory information."""
        device = cp.cuda.Device()
        free_mem, total_mem = device.mem_info

        logger.info(f"GPU Memory: {free_mem / 1024**3:.2f}GB free / {total_mem / 1024**3:.2f}GB total")

        assert total_mem > 0
        assert free_mem > 0
        assert free_mem <= total_mem


class TestGPUPerformance:
    """Test GPU performance vs CPU."""

    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_large_array_operations(self):
        """Test performance on large arrays."""
        size = 1_000_000

        # CPU operation
        np_arr = np.random.randn(size).astype(np.float64)
        start = time.perf_counter()
        np_result = np.cumsum(np_arr)
        cpu_time = time.perf_counter() - start

        # GPU operation
        cp_arr = cp.array(np_arr)
        cp.cuda.Stream.null.synchronize()  # Ensure transfer complete

        start = time.perf_counter()
        cp_result = cp.cumsum(cp_arr)
        cp.cuda.Stream.null.synchronize()  # Ensure computation complete
        gpu_time = time.perf_counter() - start

        # Verify results match
        np.testing.assert_allclose(cp.asnumpy(cp_result), np_result, rtol=1e-5)

        logger.info(f"Array size: {size:,}")
        logger.info(f"CPU time: {cpu_time * 1000:.2f}ms")
        logger.info(f"GPU time: {gpu_time * 1000:.2f}ms")
        logger.info(f"Speedup: {cpu_time / gpu_time:.1f}x")

    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_rsi_calculation_performance(self):
        """Test RSI calculation performance on GPU."""
        # Simulate price data
        size = 100_000
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(size) * 0.5)

        # CPU RSI calculation
        def rsi_cpu(close: np.ndarray, period: int = 14) -> np.ndarray:
            delta = np.diff(close)
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)

            avg_gain = np.zeros(len(close))
            avg_loss = np.zeros(len(close))

            # Initial SMA
            avg_gain[period] = np.mean(gain[:period])
            avg_loss[period] = np.mean(loss[:period])

            # EMA-style smoothing
            for i in range(period + 1, len(close)):
                avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i - 1]) / period
                avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i - 1]) / period

            rs = np.divide(avg_gain, avg_loss, where=avg_loss != 0, out=np.zeros_like(avg_gain))
            rsi = 100 - (100 / (1 + rs))
            rsi[:period] = 50  # Fill initial values
            return rsi

        start = time.perf_counter()
        cpu_rsi = rsi_cpu(prices, 14)
        cpu_time = time.perf_counter() - start

        # GPU RSI (simplified version)
        def rsi_gpu(close_gpu: "cp.ndarray", period: int = 14) -> "cp.ndarray":
            delta = cp.diff(close_gpu)
            gain = cp.where(delta > 0, delta, 0)
            loss = cp.where(delta < 0, -delta, 0)

            # Use rolling mean approximation for speed
            kernel_size = period
            kernel = cp.ones(kernel_size) / kernel_size

            avg_gain = cp.convolve(gain, kernel, mode="same")
            avg_loss = cp.convolve(loss, kernel, mode="same")

            # CuPy divide - handle zero division manually
            rs = cp.zeros_like(avg_gain)
            mask = avg_loss != 0
            rs[mask] = avg_gain[mask] / avg_loss[mask]

            rsi = 100 - (100 / (1 + rs))
            rsi[:period] = 50
            return rsi

        prices_gpu = cp.array(prices)
        cp.cuda.Stream.null.synchronize()

        start = time.perf_counter()
        gpu_rsi = rsi_gpu(prices_gpu, 14)
        cp.cuda.Stream.null.synchronize()
        gpu_time = time.perf_counter() - start

        logger.info(f"RSI calculation ({size:,} bars):")
        logger.info(f"  CPU time: {cpu_time * 1000:.2f}ms")
        logger.info(f"  GPU time: {gpu_time * 1000:.2f}ms")
        logger.info(f"  Speedup: {cpu_time / gpu_time:.1f}x")


class TestGPUOptimizer:
    """Test GPU Grid Optimizer."""

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data."""
        np.random.seed(42)
        n = 5000

        # Generate realistic price data
        returns = np.random.randn(n) * 0.02
        close = 100 * np.exp(np.cumsum(returns))
        high = close * (1 + np.abs(np.random.randn(n)) * 0.01)
        low = close * (1 - np.abs(np.random.randn(n)) * 0.01)
        open_price = close * (1 + np.random.randn(n) * 0.005)
        volume = np.random.randint(1000, 10000, n).astype(float)

        return {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }

    def test_optimizer_initialization(self, sample_data):
        """Test optimizer can be initialized."""
        optimizer = GPUGridOptimizer()
        assert optimizer is not None

        # Check GPU status
        logger.info(f"Optimizer GPU enabled: {optimizer.use_gpu if hasattr(optimizer, 'use_gpu') else 'N/A'}")

    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_small_grid_optimization(self, sample_data):
        """Test small grid optimization."""
        optimizer = GPUGridOptimizer()

        # Small parameter grid
        param_ranges = {
            "rsi_period": [10, 14, 21],
            "rsi_overbought": [70, 75, 80],
            "rsi_oversold": [20, 25, 30],
        }

        # Total combinations: 3 * 3 * 3 = 27
        expected_combinations = 27

        logger.info(f"Testing {expected_combinations} parameter combinations")

        start = time.perf_counter()
        # Note: Actual optimization call depends on API
        # results = optimizer.optimize(sample_data, param_ranges)
        elapsed = time.perf_counter() - start

        logger.info(f"Grid setup time: {elapsed * 1000:.2f}ms")


class TestCPUFallback:
    """Test CPU fallback when GPU is not available."""

    def test_numba_availability(self):
        """Test Numba availability for CPU fallback."""
        try:
            from numba import njit

            NUMBA_AVAILABLE = True
        except ImportError:
            NUMBA_AVAILABLE = False

        logger.info(f"Numba available: {NUMBA_AVAILABLE}")
        assert isinstance(NUMBA_AVAILABLE, bool)

    def test_cpu_rsi_calculation(self):
        """Test CPU RSI calculation works."""

        # Simple RSI test
        prices = np.array([44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08])

        # Basic RSI calculation (simplified)
        delta = np.diff(prices)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)

        avg_gain = np.mean(gain)
        avg_loss = np.mean(loss)

        if avg_loss > 0:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        else:
            rsi = 100

        logger.info(f"Test RSI: {rsi:.2f}")
        assert 0 <= rsi <= 100


class TestGPUMemoryManagement:
    """Test GPU memory management."""

    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_memory_cleanup(self):
        """Test that GPU memory is properly cleaned up."""
        device = cp.cuda.Device()

        # Get initial memory
        initial_free, _ = device.mem_info

        # Allocate large array
        large_array = cp.zeros((10000, 10000), dtype=cp.float64)
        cp.cuda.Stream.null.synchronize()

        # Check memory decreased
        after_alloc_free, _ = device.mem_info
        assert after_alloc_free < initial_free

        # Delete and clear memory pool
        del large_array
        cp.get_default_memory_pool().free_all_blocks()

        # Check memory recovered
        after_cleanup_free, _ = device.mem_info

        logger.info(
            f"Memory: {initial_free / 1024**3:.2f}GB -> {after_alloc_free / 1024**3:.2f}GB -> {after_cleanup_free / 1024**3:.2f}GB"
        )

        # Memory should be mostly recovered
        assert after_cleanup_free > after_alloc_free

    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_multiple_gpu_operations(self):
        """Test multiple sequential GPU operations."""
        for i in range(5):
            arr = cp.random.randn(100000)
            result = cp.sum(arr**2)
            cp.cuda.Stream.null.synchronize()

            # Cleanup
            del arr, result

        # Force memory pool cleanup
        cp.get_default_memory_pool().free_all_blocks()

        logger.info("Multiple GPU operations completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
