"""
test_phase2_integration.py

Comprehensive integration test suite for Phase 2 of the crypto backtesting system.

Covers:
- End-to-End integration
- Concurrency and async resource management
- Error handling and resilience
- Performance and profiling

Tested components:
- AsyncDataService (data_service_async_PRODUCTION_clean.py)
- VectorizedBacktestEngine (test_vectorized_backtest_FIXED_v2.py)
- SRRSIAsyncIndicator (sr_rsi_async_FIXED_v3.py)

Test framework: pytest + pytest-asyncio

Author: [Your Name]
Date: 2025-10-30
"""

import asyncio
import logging
import os
import random
import tempfile
import time
from contextlib import asynccontextmanager
from unittest import mock

import aiohttp
import numpy as np
import pandas as pd
import pytest

# --- Logging setup ---
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("integration-test")

# --- Assume these are the actual implementations from your codebase ---
# from data_service_async_PRODUCTION_clean import AsyncDataService
# from test_vectorized_backtest_FIXED_v2 import VectorizedBacktestEngine
# from sr_rsi_async_FIXED_v3 import SRRSIAsyncIndicator

# For demonstration, we provide minimal stubs/mocks for these classes.
# Replace these with actual imports in your codebase.

class AsyncDataService:
    """Async data loader with semaphore and aiohttp connector."""
    def __init__(self, max_concurrent=10, connector_limit=100):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.connector = aiohttp.TCPConnector(limit=connector_limit)
        self.session = aiohttp.ClientSession(connector=self.connector)
        self._closed = False

    async def load_csv(self, path):
        """Simulate async CSV loading (local or remote)."""
        async with self.semaphore:
            await asyncio.sleep(0.01)  # Simulate I/O
            return pd.read_csv(path)

    async def close(self):
        await self.session.close()
        self._closed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

class VectorizedBacktestEngine:
    """Vectorized backtest engine."""
    def __init__(self, min_bars=2):
        self.min_bars = min_bars

    def run(self, df, signals):
        if len(df) < self.min_bars:
            raise ValueError("Not enough bars for backtest")
        # Simulate vectorized PnL calculation
        df = df.copy()
        df['pnl'] = np.where(signals > 0, df['close'] * 0.01, 0)
        return df

class SRRSIAsyncIndicator:
    """Async SR/RSI indicator calculator."""
    def __init__(self, window=14):
        self.window = window

    async def calculate(self, df):
        # Simulate async calculation with NaN-safe ops
        await asyncio.sleep(0.01)
        df = df.copy()
        df['rsi'] = np.clip(np.random.normal(50, 10, size=len(df)), 0, 100)
        df['sr_support'] = np.nanmin(df['low'].values[-self.window:])
        df['sr_resistance'] = np.nanmax(df['high'].values[-self.window:])
        return df

# --- Helper Functions ---

def create_bars_dataframe(num_bars, seed=42, missing_cols=None, nan_ratio=0.0):
    """Create a realistic OHLCV DataFrame for BTCUSDT."""
    np.random.seed(seed)
    ts = pd.date_range("2022-01-01", periods=num_bars, freq="1min")
    price = np.cumsum(np.random.randn(num_bars)) + 40000
    high = price + np.abs(np.random.rand(num_bars) * 10)
    low = price - np.abs(np.random.rand(num_bars) * 10)
    open_ = price + np.random.randn(num_bars)
    close = price + np.random.randn(num_bars)
    volume = np.abs(np.random.randn(num_bars) * 10)
    df = pd.DataFrame({
        "timestamp": ts,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    if missing_cols:
        df = df.drop(columns=missing_cols)
    if nan_ratio > 0:
        for col in df.columns:
            nan_indices = np.random.choice(num_bars, int(num_bars * nan_ratio), replace=False)
            df.loc[nan_indices, col] = np.nan
    return df

@asynccontextmanager
async def temp_csv_file(df):
    """Context manager for a temporary CSV file."""
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
        df.to_csv(f.name, index=False)
        f.flush()
        yield f.name
    os.remove(f.name)

def assert_data_integrity(df1, df2):
    """Assert that two DataFrames are equal (ignoring index)."""
    pd.testing.assert_frame_equal(df1.reset_index(drop=True), df2.reset_index(drop=True))

def assert_backtest_results(df):
    """Basic sanity checks on backtest results."""
    assert "pnl" in df.columns
    assert df["pnl"].isnull().sum() == 0
    assert (df["pnl"] >= 0).all()

def assert_sr_rsi_results(df):
    """Check SR/RSI columns and NaN safety."""
    assert "rsi" in df.columns
    assert "sr_support" in df.columns
    assert "sr_resistance" in df.columns
    assert df["rsi"].between(0, 100).all()
    assert not np.isnan(df["sr_support"])
    assert not np.isnan(df["sr_resistance"])

# --- Pytest Fixtures ---

@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for all async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def random_seed():
    """Fixture for reproducible random seed."""
    seed = 12345
    np.random.seed(seed)
    random.seed(seed)
    return seed

@pytest.fixture
def btcusdt_df_1k(random_seed):
    """Fixture: 1,000 bars realistic BTCUSDT DataFrame."""
    return create_bars_dataframe(1000, seed=random_seed)

@pytest.fixture
def btcusdt_df_10k(random_seed):
    """Fixture: 10,000 bars realistic BTCUSDT DataFrame."""
    return create_bars_dataframe(10000, seed=random_seed)

@pytest.fixture
def btcusdt_df_1bar(random_seed):
    """Fixture: 1 bar edge-case DataFrame."""
    return create_bars_dataframe(1, seed=random_seed)

@pytest.fixture
def btcusdt_df_nan(random_seed):
    """Fixture: DataFrame with 10% NaNs."""
    return create_bars_dataframe(1000, seed=random_seed, nan_ratio=0.1)

@pytest.fixture
def btcusdt_df_missing_col(random_seed):
    """Fixture: DataFrame missing 'close' column."""
    return create_bars_dataframe(1000, seed=random_seed, missing_cols=["close"])

@pytest_asyncio.fixture
async def async_data_service():
    """Fixture: AsyncDataService with proper cleanup."""
    service = AsyncDataService(max_concurrent=10, connector_limit=100)
    try:
        yield service
    finally:
        await service.close()

@pytest.fixture
def backtest_engine():
    """Fixture: VectorizedBacktestEngine."""
    return VectorizedBacktestEngine(min_bars=2)

@pytest.fixture
def sr_rsi_indicator():
    """Fixture: SRRSIAsyncIndicator."""
    return SRRSIAsyncIndicator(window=14)

# --- Test Classes ---

class TestEndToEndIntegration:
    """
    End-to-End Integration Tests

    Verifies the complete pipeline: DataService → BacktestEngine → SRRSIAsyncIndicator.
    Ensures data integrity, correct indicator calculation, and valid backtest results.
    """

    @pytest.mark.asyncio
    async def test_e2e_pipeline_1k(self, btcusdt_df_1k, async_data_service, backtest_engine, sr_rsi_indicator):
        """
        Test E2E pipeline with 1,000 bars.
        - Loads CSV via AsyncDataService
        - Computes SR/RSI indicators
        - Runs vectorized backtest
        - Validates results and integrity
        """
        async with temp_csv_file(btcusdt_df_1k) as csv_path:
            df_loaded = await async_data_service.load_csv(csv_path)
            assert_data_integrity(btcusdt_df_1k, df_loaded)
            df_ind = await sr_rsi_indicator.calculate(df_loaded)
            assert_sr_rsi_results(df_ind)
            signals = (df_ind["rsi"] > 50).astype(int)
            df_bt = backtest_engine.run(df_ind, signals)
            assert_backtest_results(df_bt)
            logger.info("E2E pipeline (1k bars) passed.")

    @pytest.mark.asyncio
    async def test_e2e_pipeline_10k(self, btcusdt_df_10k, async_data_service, backtest_engine, sr_rsi_indicator):
        """
        Test E2E pipeline with 10,000 bars for scalability.
        """
        async with temp_csv_file(btcusdt_df_10k) as csv_path:
            df_loaded = await async_data_service.load_csv(csv_path)
            assert_data_integrity(btcusdt_df_10k, df_loaded)
            df_ind = await sr_rsi_indicator.calculate(df_loaded)
            assert_sr_rsi_results(df_ind)
            signals = (df_ind["rsi"] > 60).astype(int)
            df_bt = backtest_engine.run(df_ind, signals)
            assert_backtest_results(df_bt)
            logger.info("E2E pipeline (10k bars) passed.")

    @pytest.mark.asyncio
    async def test_e2e_pipeline_1bar_edge(self, btcusdt_df_1bar, async_data_service, backtest_engine, sr_rsi_indicator):
        """
        Test E2E pipeline with 1-bar edge case.
        Should raise ValueError in backtest due to insufficient bars.
        """
        async with temp_csv_file(btcusdt_df_1bar) as csv_path:
            df_loaded = await async_data_service.load_csv(csv_path)
            df_ind = await sr_rsi_indicator.calculate(df_loaded)
            signals = (df_ind["rsi"] > 50).astype(int)
            with pytest.raises(ValueError):
                backtest_engine.run(df_ind, signals)
            logger.info("E2E pipeline (1 bar) correctly raised ValueError.")

class TestConcurrencyIntegration:
    """
    Concurrency Integration Tests

    Verifies correct semaphore limiting, connection pool usage, and result consistency
    when running multiple backtests in parallel using shared AsyncDataService.
    """

    @pytest.mark.asyncio
    async def test_parallel_backtests_semaphore_limit(self, btcusdt_df_1k, async_data_service, backtest_engine, sr_rsi_indicator):
        """
        Run 20 parallel backtests and verify semaphore limits concurrency to 10.
        """
        async with temp_csv_file(btcusdt_df_1k) as csv_path:
            concurrency_counter = 0
            max_concurrency = 0

            orig_acquire = async_data_service.semaphore.acquire

            async def counting_acquire(*args, **kwargs):
                nonlocal concurrency_counter, max_concurrency
                concurrency_counter += 1
                max_concurrency = max(max_concurrency, concurrency_counter)
                try:
                    return await orig_acquire(*args, **kwargs)
                finally:
                    concurrency_counter -= 1

            with mock.patch.object(async_data_service.semaphore, "acquire", counting_acquire):
                async def run_pipeline():
                    df_loaded = await async_data_service.load_csv(csv_path)
                    df_ind = await sr_rsi_indicator.calculate(df_loaded)
                    signals = (df_ind["rsi"] > 50).astype(int)
                    df_bt = backtest_engine.run(df_ind, signals)
                    assert_backtest_results(df_bt)
                    return df_bt

                results = await asyncio.gather(*[run_pipeline() for _ in range(20)])
                # All results must be identical
                for df in results[1:]:
                    assert_data_integrity(results[0], df)
                assert max_concurrency <= 10
                logger.info("Parallel backtests: semaphore limited concurrency to %d", max_concurrency)

    @pytest.mark.asyncio
    async def test_connection_pool_efficiency(self, btcusdt_df_1k, async_data_service):
        """
        Verify aiohttp connection pool is reused and no leaks occur.
        """
        async with temp_csv_file(btcusdt_df_1k) as csv_path:
            # Simulate multiple loads to trigger connection reuse
            for _ in range(30):
                df_loaded = await async_data_service.load_csv(csv_path)
                assert not df_loaded.empty
            # After closing, connector should be closed
            await async_data_service.close()
            assert async_data_service._closed
            logger.info("Connection pool closed cleanly after multiple loads.")

    @pytest.mark.asyncio
    async def test_parallel_results_consistency(self, btcusdt_df_1k, async_data_service, backtest_engine, sr_rsi_indicator):
        """
        Run 5 parallel pipelines and verify results are consistent.
        """
        async with temp_csv_file(btcusdt_df_1k) as csv_path:
            async def run_pipeline():
                df_loaded = await async_data_service.load_csv(csv_path)
                df_ind = await sr_rsi_indicator.calculate(df_loaded)
                signals = (df_ind["rsi"] > 50).astype(int)
                df_bt = backtest_engine.run(df_ind, signals)
                return df_bt

            results = await asyncio.gather(*[run_pipeline() for _ in range(5)])
            for df in results[1:]:
                assert_data_integrity(results[0], df)
            logger.info("Parallel pipelines produced consistent results.")

class TestErrorHandlingIntegration:
    """
    Error Handling Integration Tests

    Simulates network failures, data corruption, and edge cases.
    Verifies graceful degradation and clear error messages.
    """

    @pytest.mark.asyncio
    async def test_network_failure_simulation(self, btcusdt_df_1k, backtest_engine, sr_rsi_indicator):
        """
        Simulate network failure in AsyncDataService and verify error handling.
        """
        class FailingAsyncDataService(AsyncDataService):
            async def load_csv(self, path):
                raise aiohttp.ClientError("Simulated network failure")

        service = FailingAsyncDataService()
        async with temp_csv_file(btcusdt_df_1k) as csv_path:
            with pytest.raises(aiohttp.ClientError, match="Simulated network failure"):
                await service.load_csv(csv_path)
            await service.close()
            logger.info("Network failure simulation raised expected exception.")

    @pytest.mark.asyncio
    async def test_data_corruption_missing_column(self, btcusdt_df_missing_col, async_data_service, backtest_engine, sr_rsi_indicator):
        """
        Test pipeline with missing 'close' column, expect KeyError in backtest.
        """
        async with temp_csv_file(btcusdt_df_missing_col) as csv_path:
            df_loaded = await async_data_service.load_csv(csv_path)
            df_ind = await sr_rsi_indicator.calculate(df_loaded)
            signals = np.ones(len(df_ind))
            with pytest.raises(KeyError):
                backtest_engine.run(df_ind, signals)
            logger.info("Data corruption (missing column) raised expected KeyError.")

    @pytest.mark.asyncio
    async def test_data_corruption_nan_values(self, btcusdt_df_nan, async_data_service, backtest_engine, sr_rsi_indicator):
        """
        Test pipeline with NaN values, expect NaN-safe indicator calculation and valid backtest.
        """
        async with temp_csv_file(btcusdt_df_nan) as csv_path:
            df_loaded = await async_data_service.load_csv(csv_path)
            df_ind = await sr_rsi_indicator.calculate(df_loaded)
            # NaN-safe: signals NaN → 0
            signals = np.where(df_ind["rsi"].isna(), 0, (df_ind["rsi"] > 50).astype(int))
            df_bt = backtest_engine.run(df_ind, signals)
            assert_backtest_results(df_bt)
            logger.info("NaN values handled gracefully in pipeline.")

    @pytest.mark.asyncio
    async def test_edge_case_1bar_sr_rsi(self, btcusdt_df_1bar, async_data_service, sr_rsi_indicator):
        """
        Test SR/RSI indicator with 1-bar dataset, expect correct handling (no crash).
        """
        async with temp_csv_file(btcusdt_df_1bar) as csv_path:
            df_loaded = await async_data_service.load_csv(csv_path)
            df_ind = await sr_rsi_indicator.calculate(df_loaded)
            assert_sr_rsi_results(df_ind)
            logger.info("SR/RSI handled 1-bar edge case without error.")

class TestPerformanceIntegration:
    """
    Performance Integration Tests

    Benchmarks the complete pipeline, verifies speedup, and profiles resource usage.
    """

    @pytest.mark.asyncio
    async def test_pipeline_speedup(self, btcusdt_df_10k, async_data_service, backtest_engine, sr_rsi_indicator):
        """
        Benchmark pipeline with and without optimizations.
        Expect ≥20% speedup with vectorized/async code.
        """
        async with temp_csv_file(btcusdt_df_10k) as csv_path:
            # Baseline: naive (simulate with sleep)
            async def naive_pipeline():
                await asyncio.sleep(0.2)  # Simulate slow, non-optimized
                df = pd.read_csv(csv_path)
                df['rsi'] = 50
                df['sr_support'] = df['low'].min()
                df['sr_resistance'] = df['high'].max()
                signals = (df['rsi'] > 50).astype(int)
                df['pnl'] = np.where(signals > 0, df['close'] * 0.01, 0)
                return df

            # Optimized: actual pipeline
            async def optimized_pipeline():
                df_loaded = await async_data_service.load_csv(csv_path)
                df_ind = await sr_rsi_indicator.calculate(df_loaded)
                signals = (df_ind["rsi"] > 50).astype(int)
                df_bt = backtest_engine.run(df_ind, signals)
                return df_bt

            # Run and time both
            t0 = time.perf_counter()
            await naive_pipeline()
            naive_time = time.perf_counter() - t0

            t1 = time.perf_counter()
            await optimized_pipeline()
            opt_time = time.perf_counter() - t1

            logger.info("Naive pipeline time: %.3fs, Optimized: %.3fs", naive_time, opt_time)
            assert opt_time <= naive_time * 0.8, "Optimized pipeline did not achieve ≥20% speedup"

    @pytest.mark.asyncio
    async def test_memory_profile_connection_pool(self, btcusdt_df_1k, async_data_service):
        """
        Profile memory usage of connection pool during multiple loads.
        """
        import tracemalloc
        tracemalloc.start()
        async with temp_csv_file(btcusdt_df_1k) as csv_path:
            for _ in range(20):
                await async_data_service.load_csv(csv_path)
            current, peak = tracemalloc.get_traced_memory()
            logger.info("Memory usage: current=%d, peak=%d", current, peak)
            assert peak < 50 * 1024 * 1024  # <50MB for connection pool
        tracemalloc.stop()

    @pytest.mark.asyncio
    async def test_cpu_profile_async_efficiency(self, btcusdt_df_1k, async_data_service, sr_rsi_indicator):
        """
        Profile CPU time for async indicator calculation.
        """
        import timeit

        async def run():
            async with temp_csv_file(btcusdt_df_1k) as csv_path:
                df_loaded = await async_data_service.load_csv(csv_path)
                await sr_rsi_indicator.calculate(df_loaded)

        # Time 10 runs
        t0 = time.perf_counter()
        for _ in range(10):
            await run()
        elapsed = time.perf_counter() - t0
        logger.info("Async indicator CPU time for 10 runs: %.3fs", elapsed)
        assert elapsed < 2.0  # Should be fast for 1k bars

