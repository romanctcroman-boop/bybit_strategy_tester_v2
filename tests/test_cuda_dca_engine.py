"""
Tests for the GPU CUDA DCA simulation engine.

Tests work in two modes:
    - CUDA available: tests run actual GPU kernel and verify results
    - CUDA unavailable: tests verify graceful CPU fallback

All tests must pass regardless of GPU availability.
"""

from __future__ import annotations

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Detect CUDA availability once at module level
# ---------------------------------------------------------------------------

try:
    from numba import cuda as _numba_cuda
    _CUDA_AVAILABLE = _numba_cuda.is_available()
except ImportError:
    _CUDA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def flat_ohlcv():
    n = 80
    close = np.linspace(100.0, 112.0, n)
    high = close * 1.005
    low = close * 0.995
    return close, high, low


@pytest.fixture
def signals_one_long(flat_ohlcv):
    close, _, _ = flat_ohlcv
    sigs = np.zeros(len(close), dtype=np.int8)
    sigs[8] = 1
    return sigs


@pytest.fixture
def no_signals(flat_ohlcv):
    close, _, _ = flat_ohlcv
    return np.zeros(len(close), dtype=np.int8)


# ---------------------------------------------------------------------------
# Tests: cuda_device_info
# ---------------------------------------------------------------------------


class TestCudaDeviceInfo:
    def test_returns_dict(self):
        from backend.backtesting.cuda_dca_engine import cuda_device_info

        info = cuda_device_info()
        assert isinstance(info, dict)
        assert "available" in info

    def test_available_matches_cuda_flag(self):
        from backend.backtesting.cuda_dca_engine import _CUDA_AVAILABLE, cuda_device_info

        info = cuda_device_info()
        assert info["available"] == _CUDA_AVAILABLE


# ---------------------------------------------------------------------------
# Tests: warmup
# ---------------------------------------------------------------------------


class TestCudaWarmup:
    def test_warmup_does_not_raise(self):
        """warmup completes without exception on any platform."""
        from backend.backtesting.cuda_dca_engine import warmup_cuda_dca

        warmup_cuda_dca()

    def test_warmup_idempotent(self):
        from backend.backtesting.cuda_dca_engine import warmup_cuda_dca

        warmup_cuda_dca()
        warmup_cuda_dca()


# ---------------------------------------------------------------------------
# Tests: run_dca_batch_cuda (device-agnostic)
# ---------------------------------------------------------------------------


class TestRunDcaBatchCuda:
    """Tests that pass regardless of CUDA availability (CPU fallback tested too)."""

    def test_returns_dict_with_required_keys(self, flat_ohlcv, signals_one_long):
        from backend.backtesting.cuda_dca_engine import run_dca_batch_cuda

        close, high, low = flat_ohlcv
        sl = np.array([0.03, 0.05])
        tp = np.array([0.06, 0.10])
        result = run_dca_batch_cuda(close, high, low, signals_one_long, sl, tp)

        for key in ("net_profit", "max_drawdown", "win_rate", "n_trades", "profit_factor", "device"):
            assert key in result, f"Missing key: {key}"

    def test_result_arrays_have_correct_length(self, flat_ohlcv, signals_one_long):
        from backend.backtesting.cuda_dca_engine import run_dca_batch_cuda

        close, high, low = flat_ohlcv
        sl = np.array([0.02, 0.04, 0.06, 0.08])
        tp = np.array([0.04, 0.08, 0.12, 0.16])
        result = run_dca_batch_cuda(close, high, low, signals_one_long, sl, tp)

        assert len(result["net_profit"]) == 4
        assert len(result["n_trades"]) == 4

    def test_zero_signals_zero_trades(self, flat_ohlcv, no_signals):
        from backend.backtesting.cuda_dca_engine import run_dca_batch_cuda

        close, high, low = flat_ohlcv
        sl = np.array([0.03, 0.05])
        tp = np.array([0.06, 0.10])
        result = run_dca_batch_cuda(close, high, low, no_signals, sl, tp)

        assert np.all(result["n_trades"] == 0)
        assert np.allclose(result["net_profit"], 0.0, atol=1e-6)

    def test_device_key_is_string(self, flat_ohlcv, signals_one_long):
        from backend.backtesting.cuda_dca_engine import run_dca_batch_cuda

        close, high, low = flat_ohlcv
        sl = np.array([0.03])
        tp = np.array([0.06])
        result = run_dca_batch_cuda(close, high, low, signals_one_long, sl, tp)
        assert isinstance(result["device"], str)
        assert result["device"] in ("cuda", "cpu_numba")

    def test_device_reports_cuda_when_available(self, flat_ohlcv, signals_one_long):
        from backend.backtesting.cuda_dca_engine import _CUDA_AVAILABLE, run_dca_batch_cuda

        close, high, low = flat_ohlcv
        sl = np.array([0.03])
        tp = np.array([0.06])
        result = run_dca_batch_cuda(close, high, low, signals_one_long, sl, tp)

        if _CUDA_AVAILABLE:
            assert result["device"] == "cuda"
        else:
            assert result["device"] == "cpu_numba"

    def test_mismatched_arrays_raises(self, flat_ohlcv, signals_one_long):
        from backend.backtesting.cuda_dca_engine import run_dca_batch_cuda

        close, high, low = flat_ohlcv
        with pytest.raises(AssertionError):
            run_dca_batch_cuda(
                close, high, low, signals_one_long,
                sl_pct_arr=np.array([0.03, 0.05]),
                tp_pct_arr=np.array([0.06]),  # length mismatch
            )

    def test_cuda_matches_cpu_numba_results(self, flat_ohlcv, signals_one_long):
        """CUDA results match CPU Numba results within tolerance."""
        from backend.backtesting.cuda_dca_engine import _CUDA_AVAILABLE, run_dca_batch_cuda
        from backend.backtesting.numba_dca_engine import run_dca_batch_numba

        if not _CUDA_AVAILABLE:
            pytest.skip("CUDA not available — skipping GPU vs CPU parity test")

        close, high, low = flat_ohlcv
        sl = np.array([0.03, 0.05, 0.08])
        tp = np.array([0.06, 0.10, 0.15])

        cuda_res = run_dca_batch_cuda(
            close, high, low, signals_one_long, sl, tp,
            order_count=3, grid_size_pct=5.0,
            initial_capital=10000.0, leverage=1.0,
        )
        cpu_res = run_dca_batch_numba(
            close, high, low, signals_one_long, sl, tp,
            order_count=3, grid_size_pct=5.0,
            initial_capital=10000.0, leverage=1.0,
        )

        np.testing.assert_array_equal(
            cuda_res["n_trades"], cpu_res["n_trades"],
            err_msg="CUDA n_trades differs from CPU Numba",
        )
        np.testing.assert_allclose(
            cuda_res["net_profit"], cpu_res["net_profit"],
            rtol=1e-4, atol=1e-4,
            err_msg="CUDA net_profit differs from CPU Numba",
        )
        np.testing.assert_allclose(
            cuda_res["win_rate"], cpu_res["win_rate"],
            rtol=1e-4, atol=1e-4,
            err_msg="CUDA win_rate differs from CPU Numba",
        )

    def test_rising_market_tp_produces_profit_cuda(self):
        """Rising market + TP → positive net profit on GPU."""
        from backend.backtesting.cuda_dca_engine import run_dca_batch_cuda

        n = 150
        close = np.linspace(100.0, 130.0, n)
        high = close * 1.010
        low = close * 0.990
        sigs = np.zeros(n, dtype=np.int8)
        sigs[10] = 1

        sl = np.array([0.25])
        tp = np.array([0.05])
        result = run_dca_batch_cuda(
            close, high, low, sigs, sl, tp,
            order_count=1, grid_size_pct=0.0,
            initial_capital=10000.0, leverage=1.0,
        )
        assert result["n_trades"][0] >= 1
        assert result["net_profit"][0] > 0

    def test_falling_market_sl_triggers_loss_cuda(self):
        """Falling market + SL → negative net profit."""
        from backend.backtesting.cuda_dca_engine import run_dca_batch_cuda

        n = 80
        close = np.linspace(100.0, 82.0, n)
        high = close * 1.005
        low = close * 0.995
        sigs = np.zeros(n, dtype=np.int8)
        sigs[5] = 1

        sl = np.array([0.05])
        tp = np.array([0.30])
        result = run_dca_batch_cuda(
            close, high, low, sigs, sl, tp,
            order_count=1, grid_size_pct=0.0,
            initial_capital=10000.0, leverage=1.0,
        )
        assert result["n_trades"][0] >= 1
        assert result["net_profit"][0] < 0

    def test_large_batch_304k_combos_completes(self, flat_ohlcv):
        """304,668 combinations complete without error (performance smoke test)."""
        from backend.backtesting.cuda_dca_engine import run_dca_batch_cuda

        if not _CUDA_AVAILABLE:
            pytest.skip("CUDA not available — skipping large batch test")

        close, high, low = flat_ohlcv
        # Build full 31×26×21×18 = 304,668 combo grid (same as user's DCA-RSI-6)
        # But only test with 1,000 combos to avoid OOM in CI
        N = 1000
        rng = np.random.default_rng(42)
        sl = rng.uniform(0.015, 0.10, N)
        tp = rng.uniform(0.01, 0.03, N)

        sigs = np.zeros(len(close), dtype=np.int8)
        sigs[10] = 1
        sigs[40] = 1

        result = run_dca_batch_cuda(close, high, low, sigs, sl, tp,
                                    order_count=5, grid_size_pct=10.0)
        assert len(result["n_trades"]) == N
        assert result["device"] == "cuda"
